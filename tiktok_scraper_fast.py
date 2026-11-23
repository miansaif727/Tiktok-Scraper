"""
TikTok profile scraper - INSTANT RESTART version (no cooldown, no throttling)

On any block / timeout:
  * the worker throws away its session (fresh connection + cookies)
  * the link goes back into the queue
  * the worker immediately carries on - no sleeping, no pausing other workers

Saves to CSV every 100 profiles. Links that never succeed go to
failed_links.txt and are retried automatically on the next run.

Setup:   pip install curl_cffi
Run:     python tiktok_scraper_instant.py
         python tiktok_scraper_instant.py --workers 15
"""

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time

from curl_cffi.requests import AsyncSession

EXPORT_EVERY = 100
FIELDS = [
    "Source Link", "Username", "Nickname", "Follower", "Following", "Likes",
    "Videos", "Verified", "Private", "Bio Text", "Bio Link", "Website",
    "Email", "Phone", "Status",
]

JSON_RE = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', re.S
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s,;|]+|"
    r"\b[A-Za-z0-9\-]+\.(?:com|net|org|io|co|me|shop|store|app|tv|link|bio|ly|gg|xyz|pk|in|uk|us|ae)\b(?:/[^\s,;|]*)?",
    re.I,
)
PHONE_RE = re.compile(r"(?<![\w@])\+?\d[\d\s().\-]{7,}\d(?![\w@])")


def load_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def load_done(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {row.get("Source Link", "") for row in csv.DictReader(f)}


def extract_contacts(bio, bio_link):
    emails = list(dict.fromkeys(EMAIL_RE.findall(bio)))
    stripped = EMAIL_RE.sub(" ", bio)
    sites = [u.rstrip(".,)") for u in URL_RE.findall(stripped)]
    if bio_link:
        sites.insert(0, bio_link)
    sites = list(dict.fromkeys(sites))
    phones = []
    for m in PHONE_RE.findall(stripped):
        if 8 <= len(re.sub(r"\D", "", m)) <= 15:
            phones.append(m.strip())
    phones = list(dict.fromkeys(phones))
    return " | ".join(emails), " | ".join(phones), " | ".join(sites)


async def fetch(session, url, timeout):
    """Returns (kind, payload): kind in ok | gone | blocked."""
    r = await session.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)

    if r.status_code == 404:
        return "gone", "not_found (404)"
    if r.status_code != 200:
        return "blocked", f"http {r.status_code}"

    m = JSON_RE.search(r.text)
    if not m:
        return "blocked", "no_json (captcha/blocked page)"
    try:
        data = json.loads(m.group(1))
    except Exception:
        return "blocked", "bad_json"

    ud = (data.get("__DEFAULT_SCOPE__") or {}).get("webapp.user-detail")
    if not ud:
        return "blocked", "no_user_detail"

    info = ud.get("userInfo")
    if info and info.get("user"):
        u, st = info["user"], info.get("stats") or {}
        bio = (u.get("signature") or "").replace("\n", " ").strip()
        bio_link = (u.get("bioLink") or {}).get("link") or ""
        email, phone, website = extract_contacts(bio, bio_link)
        row = {
            "Source Link": url,
            "Username": u.get("uniqueId", ""),
            "Nickname": u.get("nickname", ""),
            "Follower": st.get("followerCount", ""),
            "Following": st.get("followingCount", ""),
            "Likes": st.get("heartCount", st.get("heart", "")),
            "Videos": st.get("videoCount", ""),
            "Verified": u.get("verified", ""),
            "Private": u.get("privateAccount", ""),
            "Bio Text": bio,
            "Bio Link": bio_link,
            "Website": website,
            "Email": email,
            "Phone": phone,
            "Status": "ok",
        }
        return "ok", row

    code = ud.get("statusCode")
    if code not in (None, 0):
        return "gone", f"unavailable ({code})"
    return "blocked", "empty_user"


async def main(args):
    links = list(dict.fromkeys(load_lines(args.input)))
    done = load_done(args.output)
    todo = [u for u in links if u not in done]
    print(f"Total: {len(links)} | done: {len(done)} | to scrape: {len(todo)}")
    if not todo:
        return 0

    write_header = not os.path.exists(args.output) or os.path.getsize(args.output) == 0
    queue = asyncio.Queue()
    for u in todo:
        queue.put_nowait((u, 1))

    buffer, failed = [], []
    lock = asyncio.Lock()
    st = {"remaining": len(todo), "ok": 0, "blocked": 0, "streak": 0, "neterr": 0,
          "abort": False, "t0": time.time()}

    def flush():
        nonlocal write_header
        if not buffer:
            return
        with open(args.output, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if write_header:
                w.writeheader()
                write_header = False
            w.writerows(buffer)
        print(f"  -> exported {len(buffer)} rows to {args.output}")
        buffer.clear()

    async def finish(row=None, fail_url=None):
        async with lock:
            if row:
                buffer.append(row)
                if len(buffer) >= EXPORT_EVERY:
                    flush()
            if fail_url:
                failed.append(fail_url)
            st["remaining"] -= 1

    async def worker():
        session = AsyncSession()
        try:
            while st["remaining"] > 0 and not st["abort"]:
                try:
                    url, attempt = await asyncio.wait_for(queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    continue

                if args.delay > 0:
                    await asyncio.sleep(args.delay)

                try:
                    kind, payload = await fetch(session, url, args.timeout)
                except Exception as e:
                    # connection dropped / timed out: a network problem, not a TikTok block
                    kind, payload = "neterr", type(e).__name__

                if kind == "neterr":
                    # don't burn the link's attempts; fresh session, put it back, brief pause
                    st["neterr"] += 1
                    try:
                        await session.close()
                    except Exception:
                        pass
                    session = AsyncSession()
                    queue.put_nowait((url, attempt))
                    print(f"  .. network error ({payload}), retrying | neterr={st['neterr']}")
                    if args.net_wait > 0:
                        await asyncio.sleep(args.net_wait)
                    continue

                if kind in ("ok", "gone"):
                    st["streak"] = 0
                    if kind == "ok":
                        st["ok"] += 1
                        await finish(row=payload)
                    else:
                        row = {k: "" for k in FIELDS}
                        row["Source Link"], row["Status"] = url, payload
                        await finish(row=row)
                else:
                    # blocked: restart this worker's session instantly, requeue, carry on
                    st["blocked"] += 1
                    st["streak"] += 1
                    try:
                        await session.close()
                    except Exception:
                        pass
                    session = AsyncSession()
                    if attempt < args.max_attempts:
                        queue.put_nowait((url, attempt + 1))
                    else:
                        await finish(fail_url=url)
                    if args.bail_after and st["streak"] >= args.bail_after:
                        st["abort"] = True
                        print(f"  !! {st['streak']} blocks in a row with no success - "
                              "TikTok is not reachable from this connection. Saving and stopping.")

                done_n = len(todo) - st["remaining"]
                rate = done_n / max(time.time() - st["t0"], 1) * 60
                shown = url.split("/")[-1] if kind == "ok" else payload
                print(f"[{done_n}/{len(todo)}] {kind:7} {str(shown):32.32}"
                      f" | ok={st['ok']} blocked={st['blocked']} {rate:.0f}/min")
        finally:
            try:
                await session.close()
            except Exception:
                pass

    try:
        await asyncio.gather(*[worker() for _ in range(args.workers)])
    finally:
        flush()
        if failed:
            with open(args.failed, "a", encoding="utf-8") as f:
                f.write("\n".join(failed) + "\n")
            print(f"{len(failed)} links never succeeded -> {args.failed} (just re-run to retry them)")
    print("Done." if not st["abort"] else "Stopped.")
    return 3 if st["abort"] else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="links.txt")
    ap.add_argument("--output", default="tiktok_results.csv")
    ap.add_argument("--failed", default="failed_links.txt")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--delay", type=float, default=0.0,
                    help="seconds between requests per worker (0 = none)")
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--max-attempts", type=int, default=20,
                    help="tries per link before it goes to failed_links.txt")
    ap.add_argument("--bail-after", type=int, default=0,
                    help="stop after this many blocks in a row with zero successes (0 = never, default)")
    ap.add_argument("--net-wait", type=float, default=1.0,
                    help="short pause (seconds) after a connection error so a dropped "
                         "internet connection doesn't spin the CPU")
    sys.exit(asyncio.run(main(ap.parse_args())))