from flask import Flask, request
import requests
import os
import time
from datetime import datetime

app = Flask(__name__)

# ======================
# CONFIG
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")

if not BOT_TOKEN or not CHAT_ID:
    raise Exception("Missing Telegram environment variables")

# ======================
# MEMORY
# ======================
sessions = {}
active_calls = {}

SESSION_WINDOW = 30 * 60  # 30 minutes

# ======================
# HELPERS
# ======================
def now_ts():
    return int(time.time())

def now_readable():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text
        })
    except:
        pass

def session_key(a, b):
    return f"{a}→{b}"

def get_session(key):
    s = sessions.get(key)
    if s and (now_ts() - s["last_update"] > SESSION_WINDOW):
        sessions.pop(key, None)
        return None
    return s

def update_session(from_number, to_number, msg, msg_type):
    key = session_key(from_number, to_number)
    s = get_session(key)

    if not s:
        s = {
            "from": from_number,
            "to": to_number,
            "last": msg,
            "type": msg_type,
            "created": now_readable(),
            "last_update": now_ts(),
            "count": 1
        }
        sessions[key] = s
    else:
        s["last"] = msg
        s["type"] = msg_type
        s["last_update"] = now_ts()
        s["count"] += 1

    return key, s

def inbox():
    if not sessions:
        return "📱 INBOX EMPTY"

    text = "📱 WHATSAPP STYLE INBOX\n\n"
    for k, s in sessions.items():
        text += (
            f"{k}\n"
            f"💬 {s['last']}\n"
            f"📌 {s['type']}\n"
            f"🕒 {s['created']}\n"
            f"🔁 {s['count']} msgs\n\n"
        )
    return text

# ======================
# SMS → TELEGRAM
# ======================
@app.route("/sms", methods=["POST"])
def sms():
    try:
        data = request.json
        payload = data["data"]["payload"]

        msg = payload.get("text", "")
        sender = payload["from"]["phone_number"]
        to_number = payload["to"][0]["phone_number"]

        update_session(sender, to_number, msg, "SMS")

        send_telegram(
            f"📩 SMS\n\nFrom: {sender}\nTo: {to_number}\n\n{msg}\n\n{inbox()}"
        )

        return {"ok": True}

    except:
        return {"error": "sms failed"}

# ======================
# TELEGRAM → SMS
# ======================
@app.route("/telegram", methods=["POST"])
def telegram():
    try:
        data = request.json
        msg = data.get("message", {}).get("text", "")

        if not msg.startswith("/reply"):
            send_telegram(inbox())
            return {"ok": True}

        parts = msg.split(" ", 2)

        if len(parts) < 3:
            send_telegram("⚠️ Use /reply number message")
            return {"error": "bad format"}

        number = parts[1]
        text = parts[2]

        url = "https://api.telnyx.com/v2/messages"
        headers = {
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        }

        requests.post(url, json={
            "from": number,
            "to": number,
            "text": text
        }, headers=headers)

        update_session(number, number, text, "OUTGOING")

        send_telegram(f"✅ SENT\n\nTo: {number}\n\n{text}\n\n{inbox()}")

        return {"ok": True}

    except:
        return {"error": "telegram failed"}

# ======================
# VOICE / CALL EVENTS
# ======================
@app.route("/voice", methods=["POST"])
def voice():
    try:
        data = request.json
        event = data.get("data", {}).get("event_type", "")
        payload = data.get("data", {}).get("payload", {})

        call_id = payload.get("call_control_id")
        from_number = payload.get("from")
        to_number = payload.get("to")

        # CALL START (RINGING)
        if event == "call.initiated":
            active_calls[call_id] = {
                "from": from_number,
                "to": to_number,
                "answered": False,
                "time": now_readable()
            }

            send_telegram(
                f"📞 RINGING\nFrom: {from_number}\nTo: {to_number}\nTime: {now_readable()}"
            )

        # CALL ANSWERED
        elif event == "call.answered":
            if call_id in active_calls:
                active_calls[call_id]["answered"] = True

            send_telegram(
                f"📞 ANSWERED\nFrom: {from_number}\nTo: {to_number}"
            )

        # CALL ENDED
        elif event == "call.hangup":
            call = active_calls.get(call_id, {
                "from": from_number,
                "to": to_number,
                "answered": False,
                "time": now_readable()
            })

            if not call["answered"]:
                send_telegram(
                    f"📞 MISSED CALL\nFrom: {call['from']}\nTo: {call['to']}\nTime: {call['time']}"
                )
            else:
                send_telegram(
                    f"📞 CALL ENDED\nFrom: {call['from']}\nTo: {call['to']}"
                )

            active_calls.pop(call_id, None)

        return {"ok": True}

    except:
        return {"error": "voice failed"}

# ======================
# FAX OUTGOING
# ======================
def send_fax(to_number, pdf_url):
    try:
        url = "https://api.telnyx.com/v2/faxes"
        headers = {
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        }

        r = requests.post(url, json={
            "to": to_number,
            "media_url": pdf_url
        }, headers=headers)

        send_telegram(f"📠 FAX SENT\nTo: {to_number}\nFile: {pdf_url}")

        return r.json()

    except Exception as e:
        send_telegram(f"❌ FAX ERROR\n{str(e)}")
        return {"error": str(e)}

# ======================
# FAX INBOUND ALERTS
# ======================
@app.route("/fax", methods=["POST"])
def fax():
    try:
        data = request.json
        payload = data.get("data", {}).get("payload", {})

        from_number = payload.get("from")
        to_number = payload.get("to")
        status = payload.get("status", "unknown")
        media_url = payload.get("media_url")

        send_telegram(
            f"📠 FAX RECEIVED\nFrom: {from_number}\nTo: {to_number}\nStatus: {status}\n\nFile:\n{media_url}"
        )

        return {"ok": True}

    except:
        return {"error": "fax failed"}

# ======================
# HEALTH CHECK
# ======================
@app.route("/")
def home():
    return "OK"

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
