import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"
MAX_LINKS = 60
LINK_TIMEOUT = 10
SKIP_SCHEMES = {"mailto", "tel", "javascript"}
# 403 from these domains is bot-blocking, not a real broken link
BOT_BLOCKED_DOMAINS = {"trustpilot.com", "uk.trustpilot.com", "www.trustpilot.com"}


def load_config(args):
    url = args.url or os.getenv("WEBSITE_URL")
    if not url:
        print("ERROR: WEBSITE_URL not set in .env and --url not provided", file=sys.stderr)
        sys.exit(1)
    return {"url": url}


def fetch_homepage_links(url: str, timeout: int = 15):
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return [], str(e)

    soup = BeautifulSoup(resp.text, "html.parser")
    seen = set()
    links = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("#"):
            continue
        parsed = urlparse(href)
        # Skip non-HTTP schemes (mailto, tel, javascript, and common typos like "javscript")
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            continue
        if parsed.scheme in SKIP_SCHEMES:
            continue
        absolute = urljoin(resp.url, href)
        # Strip fragment
        absolute = absolute.split("#")[0]
        if absolute not in seen:
            seen.add(absolute)
            links.append(absolute)

    return links, None


def is_same_domain(link_url: str, base_url: str) -> bool:
    return urlparse(link_url).netloc == urlparse(base_url).netloc


def check_link(url: str, same_domain: bool, timeout: int = LINK_TIMEOUT) -> dict:
    result = {"url": url, "method": None, "status_code": None, "ok": False, "error": None}
    method = "GET" if same_domain else "HEAD"
    result["method"] = method

    try:
        resp = requests.request(method, url, timeout=timeout, allow_redirects=True)
        # Retry HEAD with GET if server rejects HEAD
        if method == "HEAD" and resp.status_code == 405:
            result["method"] = "GET"
            resp = requests.get(url, timeout=timeout, allow_redirects=True)
        result["status_code"] = resp.status_code
        domain = urlparse(url).netloc
        # Treat 403 from known bot-blocking domains as OK
        if resp.status_code == 403 and domain in BOT_BLOCKED_DOMAINS:
            result["ok"] = True
        else:
            result["ok"] = 200 <= resp.status_code < 400
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "connection error"
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None)
    args = parser.parse_args()

    config = load_config(args)
    base_url = config["url"]
    TMP.mkdir(exist_ok=True)

    print(f"Fetching links from {base_url}...")
    all_links, fetch_error = fetch_homepage_links(base_url)

    output = {
        "base_url": base_url,
        "total_links_found": len(all_links),
        "links_checked": 0,
        "broken_count": 0,
        "links": [],
        "fetch_error": fetch_error,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if fetch_error:
        print(f"ERROR: Could not fetch homepage — {fetch_error}", file=sys.stderr)
        out = TMP / "broken_links_data.json"
        out.write_text(json.dumps(output, indent=2))
        sys.exit(1)

    links_to_check = all_links[:MAX_LINKS]
    print(f"Found {len(all_links)} links, checking {len(links_to_check)}...")

    results = []
    for i, link in enumerate(links_to_check, 1):
        same = is_same_domain(link, base_url)
        result = check_link(link, same)
        results.append(result)
        status = result["status_code"] or result["error"]
        marker = "OK" if result["ok"] else "BROKEN"
        print(f"  [{i}/{len(links_to_check)}] {marker} {status} — {link[:80]}")

    broken = [r for r in results if not r["ok"]]
    output["links_checked"] = len(results)
    output["broken_count"] = len(broken)
    output["links"] = results

    out = TMP / "broken_links_data.json"
    out.write_text(json.dumps(output, indent=2))
    print(f"Broken: {len(broken)}/{len(results)} | Written: {out}")
    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
