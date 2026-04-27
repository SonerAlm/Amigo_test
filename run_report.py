#!/usr/bin/env python3
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TMP = ROOT / ".tmp"
LOCK = TMP / "run.lock"
LOG = TMP / "run.log"

TOOLS = ROOT / "tools"

STEPS = [
    ("check_uptime.py",      False),
    ("check_performance.py", False),
    ("check_broken_links.py",False),
    ("generate_report.py",   True),
    ("send_email.py",        True),
]


def setup_logging() -> logging.Logger:
    TMP.mkdir(exist_ok=True)
    logger = logging.getLogger("run_report")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s]  %(message)s", "%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(LOG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def acquire_lock(logger: logging.Logger) -> bool:
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().strip())
            # Check if that PID is still alive
            os.kill(pid, 0)
            logger.warning(f"Another run is in progress (PID {pid}). Exiting.")
            return False
        except (ProcessLookupError, ValueError):
            logger.info("Stale lock file found — removing.")
            LOCK.unlink(missing_ok=True)
    LOCK.write_text(str(os.getpid()))
    return True


def release_lock():
    LOCK.unlink(missing_ok=True)


def run_tool(script: str, critical: bool, logger: logging.Logger) -> bool:
    script_path = TOOLS / script
    python = sys.executable

    logger.info(f"Running {script}...")
    start = time.time()

    result = subprocess.run(
        [python, str(script_path)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    elapsed = round(time.time() - start, 1)

    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            logger.info(f"  {script}: {line}")
    if result.stderr.strip():
        for line in result.stderr.strip().splitlines():
            logger.warning(f"  {script} stderr: {line}")

    if result.returncode == 0:
        logger.info(f"  {script}: OK ({elapsed}s)")
        return True

    msg = f"{script}: FAILED (exit {result.returncode}, {elapsed}s)"
    if critical:
        logger.critical(msg)
        raise SystemExit(1)
    else:
        logger.warning(msg)
        return False


def main():
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Starting performance report run")

    if not acquire_lock(logger):
        sys.exit(1)

    start_total = time.time()
    try:
        for script, critical in STEPS:
            run_tool(script, critical, logger)

        elapsed = round(time.time() - start_total)
        logger.info(f"Run complete. Duration: {elapsed}s")
        sys.exit(0)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
