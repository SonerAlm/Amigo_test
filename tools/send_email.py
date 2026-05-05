import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def send_report():
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    report_emails = [e.strip() for e in os.getenv("REPORT_EMAIL", "").split(",") if e.strip()]

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report_path = os.path.join(repo_root, ".tmp", "email_body.html")

    with open(report_path, "r") as f:
        html_content = f.read()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Amigo eSIM Daily Performance Report"
    msg["From"] = gmail_user
    msg["To"] = ", ".join(report_emails)
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, report_emails, msg.as_string())
        print(f"Email sent successfully to {report_emails}")

if __name__ == "__main__":
    send_report()
