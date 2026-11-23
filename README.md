# TikTok Profile Scraper – Python

A fast, asynchronous TikTok profile scraper built with Python and `curl_cffi`. Extracts publicly available TikTok profile information, statistics, and contact details directly from profile pages.

The scraper uses multiple workers to process profiles concurrently, automatically handles blocked requests, restarts sessions, and saves results incrementally to CSV.

## 🚀 Key Features

- **Asynchronous Scraping:** Uses `asyncio` and multiple workers to process profiles concurrently.
- **Automatic Session Restart:** Creates a fresh session when a request is blocked or encounters an error.
- **Automatic Retry System:** Failed or blocked profiles are automatically added back to the queue for another attempt.
- **CSV Export:** Saves scraped data every 100 successful or processed profiles.
- **Resume Support:** Skips profiles already saved in the output CSV when restarting the script.
- **Failed Links Management:** Stores profiles that exceed the maximum retry limit in `failed_links.txt`.
- **Contact Extraction:** Detects email addresses, phone numbers, and website links from profile bios.
- **Profile Statistics:** Collects followers, following, likes, and video counts.
- **Customizable Workers:** Choose how many concurrent workers you want to run.
- **Configurable Timeout:** Set request timeout and retry limits according to your connection.

## 📊 Data Fields

The scraper extracts the following information:

| Field | Description |
|---|---|
| Source Link | TikTok profile URL |
| Username | TikTok username |
| Nickname | Profile display name |
| Follower | Total followers |
| Following | Total following |
| Likes | Total profile likes |
| Videos | Number of videos |
| Verified | Verification status |
| Private | Private account status |
| Bio Text | Profile biography |
| Bio Link | Link available in profile bio |
| Website | Extracted website URLs |
| Email | Extracted email addresses |
| Phone | Extracted phone numbers |
| Status | Scraping result status |

## 🛠️ Requirements

- Python 3.9+
- curl_cffi

## 📥 Installation

Clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/tiktok-profile-scraper.git
```

Navigate to the project directory:

```bash
cd tiktok-profile-scraper
```

Install the required dependency:

```bash
pip install curl_cffi
```

## 📂 Input File

Create a file named `links.txt` in the project directory.

Add TikTok profile URLs, one URL per line:

```text
https://www.tiktok.com/@username1
https://www.tiktok.com/@username2
https://www.tiktok.com/@username3
```

## ▶️ How to Run

Start scraping with the default settings:

```bash
python tiktok_scraper_instant.py
```

Run with 15 concurrent workers:

```bash
python tiktok_scraper_instant.py --workers 15
```

## ⚙️ Available Arguments

| Argument | Default | Description |
|---|---:|---|
| `--input` | links.txt | Input file containing profile URLs |
| `--output` | tiktok_results.csv | CSV output file |
| `--failed` | failed_links.txt | File for permanently failed links |
| `--workers` | 10 | Number of concurrent workers |
| `--delay` | 0.0 | Delay between requests per worker |
| `--timeout` | 15 | Request timeout in seconds |
| `--max-attempts` | 20 | Maximum attempts per profile |
| `--bail-after` | 0 | Stop after consecutive blocks without success |
| `--net-wait` | 1.0 | Pause after network errors |

### Examples

Run with 20 workers and a 30-second timeout:

```bash
python tiktok_scraper_instant.py --workers 20 --timeout 30
```

Use a maximum of 10 attempts per profile:

```bash
python tiktok_scraper_instant.py --max-attempts 10
```

Stop after 5 consecutive blocked requests:

```bash
python tiktok_scraper_instant.py --bail-after 5
```

## 🔄 How the Retry System Works

The scraper uses an automatic retry mechanism:

1. A worker requests a TikTok profile.
2. If the profile is successfully retrieved, the data is added to the CSV buffer.
3. If a profile returns a 404 or an unavailable status, it is recorded with its status.
4. If a request is blocked or the expected profile data is missing, the worker closes its current session.
5. A fresh session is created, and the profile is added back to the queue.
6. Network errors also trigger a fresh session and automatic retry.
7. After reaching the maximum retry limit, the profile is saved in `failed_links.txt`.

**Important:** The script does not intentionally pause all workers when one worker encounters a blocked request. Each worker manages its own session and retry process.

## 💾 Output Files

After execution, the project generates:

- `tiktok_results.csv` – Scraped profile information.
- `failed_links.txt` – Profiles that exceeded the retry limit.

The script also supports restarting from previous results. Profiles already recorded in the CSV are skipped on the next run.

Note: Links in `failed_links.txt` are not automatically merged into `links.txt`; add them to the input file before the next run if you want to retry them.

## ⚠️ Important Notes

- Results depend on TikTok page availability and the accessibility of profile information.
- Private account information is not accessed.
- Contact details are extracted only when publicly available in profile information.
- High concurrency may trigger rate limits, temporary blocks, or connection failures.
- Session restarts do not guarantee that blocked requests will succeed.
- Use responsibly and comply with TikTok's Terms of Service and applicable privacy laws.

## 👨‍💻 Author

**Mian Saif**

Python Developer | Web Scraping | Data Extraction | Automation | Lead Generation

**GitHub:** [Your GitHub Profile](https://github.com/miansaif727)

**Freelancer:** [Mian Saif](https://www.freelancer.com/u/miansaif727)

---

⭐ If you find this project useful, consider giving the repository a star!
