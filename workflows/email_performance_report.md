# Email Performance Report

## Objective
Audit a website across four performance dimensions every weekday morning and deliver a color-coded HTML report with prioritized improvement recommendations to a specified inbox.

---

## Required Inputs (.env)

| Variable | Required | Description |
|---|---|---|
| `WEBSITE_URL` | Yes | Full URL including scheme — e.g. `https://example.com` |
| `PAGESPEED_API_KEY` | No | Google Cloud API key. Without it: 25 req/day per IP. With it: 25,000/day. Get one at https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com |
| `GMAIL_USER` | Yes | Gmail address used as sender and SMTP auth username |
| `GMAIL_APP_PASSWORD` | Yes | 16-character Google App Password. **Not** your account password. Requires 2FA enabled. Generate at https://myaccount.google.com/apppasswords |
| `REPORT_EMAIL` | Yes | Recipient address for the report |

---

## Tools Used (execution order)

1. `tools/check_uptime.py` — HTTP GET to site, measures response time and status
2. `tools/check_performance.py` — PageSpeed Insights API (mobile + desktop)
3. `tools/check_broken_links.py` — Crawls homepage, HEAD/GET-checks all links (max 60)
4. `tools/generate_report.py` — Aggregates all data, builds HTML email
5. `tools/send_email.py` — Sends via Gmail SMTP

Orchestrated by `run_report.py` (root level).

---

## Steps

1. Ensure all `.env` variables are set (see above)
2. Install dependencies: `pip3 install -r requirements.txt`
3. Test the full pipeline manually: `python3 run_report.py`
4. Confirm email arrives at `REPORT_EMAIL`
5. Register the schedule: `chmod +x setup_cron.sh && ./setup_cron.sh`
6. Verify registration: `launchctl list | grep amigo`

---

## Expected Output

- `.tmp/uptime_data.json` — uptime status, response time, status code
- `.tmp/performance_data.json` — Core Web Vitals + Lighthouse scores for mobile and desktop
- `.tmp/broken_links_data.json` — all checked links with status codes
- `.tmp/email_body.html` — complete HTML email (open in browser to preview)
- `.tmp/run.log` — timestamped execution log
- Email sent to `REPORT_EMAIL` with subject: `{site} — Performance Report {date} — {status}`

---

## Metrics & Thresholds

### Core Web Vitals

| Metric | Good | Needs Work | Poor |
|---|---|---|---|
| LCP (Largest Contentful Paint) | < 2.5s | 2.5s – 4s | > 4s |
| FCP (First Contentful Paint) | < 1.8s | 1.8s – 3s | > 3s |
| TBT (Total Blocking Time) | < 200ms | 200ms – 600ms | > 600ms |
| Speed Index | < 3.4s | 3.4s – 5.8s | > 5.8s |
| CLS (Cumulative Layout Shift) | < 0.1 | 0.1 – 0.25 | > 0.25 |

### Lighthouse Scores (0–100)

| Rating | Range |
|---|---|
| Good | ≥ 90 |
| Needs Work | 50 – 89 |
| Poor | < 50 |

Colors: green (#1e8e3e) / amber (#f9ab00) / red (#d93025)

---

## How to Run Manually

```bash
# Full run (all tools → email)
python3 run_report.py

# Individual tools (for debugging)
python3 tools/check_uptime.py
python3 tools/check_performance.py
python3 tools/check_broken_links.py
python3 tools/generate_report.py
python3 tools/send_email.py

# Preview the HTML email
open .tmp/email_body.html
```

---

## Schedule Management

```bash
# Register Mon-Fri 8am schedule
chmod +x setup_cron.sh && ./setup_cron.sh

# Trigger a manual run via launchd
launchctl start com.amigo.performancereport

# Check if loaded
launchctl list | grep amigo

# View launchd logs
tail -f .tmp/launchd_stderr.log

# Remove the schedule
launchctl unload ~/Library/LaunchAgents/com.amigo.performancereport.plist
```

---

## Troubleshooting

### Email not arriving
- Check `.tmp/run.log` for errors
- Verify `GMAIL_APP_PASSWORD` is a 16-char App Password (not account password)
- Ensure 2FA is enabled on the Gmail account
- Check Gmail's Sent folder to confirm it was sent

### PageSpeed returning no data
- Without an API key, the limit is ~25 requests/day per IP — wait until next day or add a key
- Try running `python3 tools/check_performance.py` manually; check stderr for the specific error
- Verify `WEBSITE_URL` is a publicly accessible URL (not localhost, not behind auth)

### Broken links tool is slow
- Each link has a 10s timeout; 60 links × 10s worst case = 10 minutes
- Reduce the cap by editing `MAX_LINKS = 60` in `tools/check_broken_links.py`
- External links that time out will show as broken — this is expected for rate-limited resources

### launchd not triggering
- The Mac must be awake and logged in at 8am
- launchd will NOT catch up on missed runs if the machine was asleep
- Check `launchctl list | grep amigo` — if it shows an error code, check `.tmp/launchd_stderr.log`
- Make sure Python is on the PATH used by launchd — the plist sets `PATH` to include `/opt/homebrew/bin`

### "python3 not found" in launchd
- Edit the plist at `~/Library/LaunchAgents/com.amigo.performancereport.plist`
- Replace the `<string>python3</string>` in `ProgramArguments` with the absolute path from `which python3`
- Reload: `launchctl unload ~/Library/LaunchAgents/com.amigo.performancereport.plist && launchctl load -w ~/Library/LaunchAgents/com.amigo.performancereport.plist`

---

## Notes

- PageSpeed Insights measures a simulated load, not a live user session. Results vary slightly run-to-run.
- The broken links checker only crawls the homepage (depth 1). It does not follow internal links to subpages.
- Same-domain links are checked with GET; external links with HEAD (retries with GET on 405).
- JavaScript-rendered links (SPAs injecting `<a>` tags after load) are not detected — only server-rendered HTML is parsed.
- The launchd job uses `RunAtLoad: false` — it will NOT run immediately when registered, only at the scheduled time.
