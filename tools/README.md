# Tools

Python scripts for deterministic execution. Each script does one thing reliably.

## Conventions
- Accept inputs via CLI args or environment variables
- Print results to stdout or write to `.tmp/`
- Exit with code 0 on success, non-zero on failure
- Secrets come from `.env` only — never hardcoded

## Adding a New Tool
1. Check if an existing script can be extended first
2. Name it `verb_noun.py` — e.g. `scrape_page.py`, `send_slack_message.py`
3. Keep it focused: one responsibility per script
4. Add it to the relevant workflow in `workflows/`
