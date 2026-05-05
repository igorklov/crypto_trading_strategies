#!/usr/bin/env python3
"""
Send article #15 (Trend Lines) to Telegram channel @crypto_logic_pro.
"""
import os
import sys
import time
import requests

BOT_TOKEN = "8386011570:AAEstUNTuRrVJHX24XmsugUknTk3NXcEitE"
CHAT_ID = "-1003661909698"  # Channel @crypto_logic_pro
ARTICLE_FILE = "/root/.openclaw/workspace/article15/telegram.md"

def send_message(text, parse_mode=None, disable_web_page_preview=True):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok"):
            print(f"✓ Message sent (message_id: {data['result']['message_id']})")
            return True
        else:
            print(f"✗ Telegram API error: {data}")
            return False
    except Exception as e:
        print(f"✗ Failed to send message: {e}")
        return False

def main():
    if not os.path.exists(ARTICLE_FILE):
        print(f"Article file not found: {ARTICLE_FILE}")
        sys.exit(1)
    
    with open(ARTICLE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    parts = content.split('\n➖➖➖\n')
    total = len(parts)
    print(f"Found {total} message parts in article.")
    
    for i, part in enumerate(parts, 1):
        part = part.strip()
        if not part:
            continue
        print(f"\n[{i}/{total}] Sending message ({len(part)} chars)...")
        success = send_message(part)
        if not success:
            print(f"Failed to send part {i}. Aborting.")
            sys.exit(1)
        if i < total:
            time.sleep(1.5)
    
    print(f"\n✅ All {total} messages sent to Telegram channel @crypto_logic_pro.")

if __name__ == "__main__":
    main()
