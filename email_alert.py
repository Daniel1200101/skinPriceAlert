# email_alert.py
import time, ssl, smtplib
from email.message import EmailMessage
from collections import defaultdict

# ====== CONFIGURE THESE ======
EMAIL_ENABLED = True
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465          # 465=SSL, or use 587 with STARTTLS (then set SMTP_USE_SSL=False)
SMTP_USE_SSL = True

SENDER_EMAIL = "daniel21.berens@gmail.com"
SENDER_APP_PASSWORD = "nkoq mlsh wjmd xvkw"  # Gmail App Password (16 chars, no spaces)
RECIPIENTS = ["daniel21.berens@gmail.com"]

DEFAULT_SUBJECT = "CS2 Price Alert"

# Cooldown per *key* (seconds). Example keys: "batch", item URL, item name, etc.
EMAIL_COOLDOWN_SEC = 60
# =============================

_last_sent_ts = defaultdict(float)  # key -> last send timestamp


def _send_mail(subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENTS) if RECIPIENTS else SENDER_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)

    if SMTP_USE_SSL:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=20) as s:
            s.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
            s.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            s.send_message(msg)


def send_email_alert(body: str, key: str = "global", subject: str | None = None):
    """
    Send an email if the per-key cooldown has passed.
    - key: groups cooldowns independently (e.g., 'batch', item URL, etc.)
    - subject: optional; falls back to DEFAULT_SUBJECT
    """
    if not EMAIL_ENABLED:
        return

    now = time.time()
    if now - _last_sent_ts[key] < EMAIL_COOLDOWN_SEC:
        # still in cooldown for this key
        return

    try:
        _send_mail(subject or DEFAULT_SUBJECT, body)
        _last_sent_ts[key] = now
        print(f"📧 Email sent (key='{key}').")
    except Exception as e:
        print("✉️ Email error:", e)
