import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"


def load_config(args):
    url = args.url or os.getenv("WEBSITE_URL")
    if not url:
        print("ERROR: WEBSITE_URL not set in .env and --url not provided", file=sys.stderr)
        sys.exit(1)
    return {"url": url, "timeout": args.timeout}


def check_uptime(url: str, timeout: int = 15) -> dict:
    result = {
        "url": url,
        "final_url": None,
        "status_code": None,
        "response_time_ms": None,
        "is_up": False,
        "error": None,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        result["status_code"] = resp.status_code
        result["final_url"] = resp.url
        result["response_time_ms"] = round(resp.elapsed.total_seconds() * 1000, 1)
        result["is_up"] = 200 <= resp.status_code < 400
    except requests.exceptions.SSLError as e:
        result["error"] = f"SSL error: {e}"
    except requests.exceptions.Timeout:
        result["error"] = f"Request timed out after {timeout}s"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection error: {e}"
    except requests.exceptions.RequestException as e:
        result["error"] = f"Request failed: {e}"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None)
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()

    config = load_config(args)
    TMP.mkdir(exist_ok=True)

    result = check_uptime(config["url"], config["timeout"])
    out = TMP / "uptime_data.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"Uptime check: {'UP' if result['is_up'] else 'DOWN'} | "
          f"{result['status_code']} | {result['response_time_ms']}ms")
    print(f"Written: {out}")

    sys.exit(0 if result["is_up"] else 1)


if __name__ == "__main__":
    main()
