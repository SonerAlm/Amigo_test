import os
import re
import smtplib
import ssl
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
TMP = ROOT / ".tmp"


def load_config():
    missing = []
    gmail_user = os.getenv("GMAIL_USER")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    report_email = os.getenv("REPORT_EMAIL")

    if not gmail_user:
        missing.append("GMAIL_USER")
    if not app_password:
        missing.append("GMAIL_APP_PASSWORD")
    if not report_email:
        missing.append("REPORT_EMAIL")

    if missing:
        print(f"ERROR: Missing required .env variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    recipients = [r.strip() for r in report_email.split(",") if r.strip()]
    return {"sender": gmail_user, "password": app_password, "recipients": recipients}


def extract_subject(html: str, fallback: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return fallback


def build_message(sender: str, recipients: list, subject: str, html_body: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    plain = ("This report requires an HTML-capable email client to view properly.\n"
             "Please open this email in Gmail, Apple Mail, or Outlook.")
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


def send_via_gmail(msg: MIMEMultipart, sender: str, password: str, recipients: list) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
        smtp.login(sender, password)
        smtp.sendmail(sender, recipients, msg.as_string())


def main():
    email_path = TMP / "email_body.html"
    if not email_path.exists():
        print("ERROR: .tmp/email_body.html not found — run generate_report.py first", file=sys.stderr)
        sys.exit(1)

    html_body = email_path.read_text()
    config = load_config()

    subject = extract_subject(html_body, fallback="Website Performance Report")
    msg = build_message(config["sender"], config["recipients"], subject, html_body)

    print(f"Sending to {', '.join(config['recipients'])}...")
    try:
        send_via_gmail(msg, config["sender"], config["password"], config["recipients"])
        print(f"Sent: {subject}")
        sys.exit(0)
    except smtplib.SMTPAuthenticationError:
        print(
            "ERROR: Gmail authentication failed.\n"
            "  - Make sure GMAIL_APP_PASSWORD is a Google App Password (not your account password).\n"
            "  - App Passwords require 2-Step Verification enabled on your Google account.\n"
            "  - Generate one at: https://myaccount.google.com/apppasswords",
            file=sys.stderr,
        )
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"ERROR: SMTP error — {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
