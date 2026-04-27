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

PAGESPEED_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

AUDIT_IDS = {
    "lcp_ms": "largest-contentful-paint",
    "fcp_ms": "first-contentful-paint",
    "tbt_ms": "total-blocking-time",
    "speed_index_ms": "speed-index",
    "cls": "cumulative-layout-shift",
}

CATEGORY_IDS = ["performance", "seo", "accessibility", "best-practices"]


def load_config(args):
    url = args.url or os.getenv("WEBSITE_URL")
    if not url:
        print("ERROR: WEBSITE_URL not set in .env and --url not provided", file=sys.stderr)
        sys.exit(1)
    return {"url": url, "api_key": os.getenv("PAGESPEED_API_KEY")}


def extract_metric(lh: dict, audit_id: str):
    try:
        return lh["audits"][audit_id]["numericValue"]
    except (KeyError, TypeError):
        return None


def fetch_pagespeed(url: str, strategy: str, api_key, timeout: int = 45) -> dict:
    result = {"strategy": strategy, "scores": {}, "vitals": {}, "error": None}
    params = {"url": url, "strategy": strategy}
    if api_key:
        params["key"] = api_key

    try:
        resp = requests.get(PAGESPEED_URL, params=params, timeout=timeout)
        if resp.status_code == 429:
            result["error"] = "API quota exceeded (HTTP 429)"
            return result
        if resp.status_code == 400:
            result["error"] = f"Bad request (HTTP 400) — check WEBSITE_URL"
            return result
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        result["error"] = f"Request timed out after {timeout}s"
        return result
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)
        return result

    lh = data.get("lighthouseResult", {})

    for key, audit_id in AUDIT_IDS.items():
        val = extract_metric(lh, audit_id)
        if val is not None:
            # API returns seconds for time-based metrics; convert to ms
            if key != "cls":
                val = round(val, 1)
            else:
                val = round(val, 4)
        result["vitals"][key] = val

    cats = lh.get("categories", {})
    for cat_id in CATEGORY_IDS:
        score = cats.get(cat_id, {}).get("score")
        key = cat_id.replace("-", "_")
        result["scores"][key] = round(score * 100) if score is not None else None

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None)
    args = parser.parse_args()

    config = load_config(args)
    TMP.mkdir(exist_ok=True)

    output = {"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    exit_code = 0

    for strategy in ("mobile", "desktop"):
        print(f"Fetching PageSpeed ({strategy})...")
        result = fetch_pagespeed(config["url"], strategy, config["api_key"])
        output[strategy] = result
        if result["error"]:
            print(f"  WARNING: {result['error']}", file=sys.stderr)
            exit_code = 1
        else:
            perf = result["scores"].get("performance", "?")
            lcp = result["vitals"].get("lcp_ms", "?")
            print(f"  Performance: {perf}/100 | LCP: {lcp}ms")

    out = TMP / "performance_data.json"
    out.write_text(json.dumps(output, indent=2))
    print(f"Written: {out}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
