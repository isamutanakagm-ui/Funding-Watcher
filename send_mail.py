#!/usr/bin/env python3
"""GitHub Actions から呼ばれるメール送信スクリプト。
watcher.py の出力 output/email_preview.txt を SMTP で本人に送信する。
新規0件のときは送らない。
環境変数 (GitHub Secrets 経由):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_TO
"""
import os
import smtplib
import datetime as dt
from email.mime.text import MIMEText
from pathlib import Path

BODY = Path("output/email_preview.txt")
if not BODY.exists():
    print("email_preview.txt が無いのでスキップ")
    raise SystemExit(0)

body = BODY.read_text(encoding="utf-8")

# 新規0/更新0のときは送らない
if "新規 0 / 更新 0" in body:
    print("新規・更新なし → 送信スキップ")
    raise SystemExit(0)

# 件名行を抽出
first_line = body.splitlines()[0]
subject = first_line.replace("件名: ", "").strip() or f"[公募Watch] {dt.date.today()}"

msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = subject
msg["From"] = os.environ["SMTP_USER"]
msg["To"] = os.environ["MAIL_TO"]

host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
port = int(os.environ.get("SMTP_PORT", "587"))

with smtplib.SMTP(host, port) as s:
    s.starttls()
    s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
    s.send_message(msg)

print(f"送信完了 → {os.environ['MAIL_TO']}")
