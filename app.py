from flask import Flask, request
import requests
import os
import time
from datetime import datetime

app = Flask(__name__)

# ======================
# CONFIG
# ======================
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
# ======================
# MEMORY
# ======================
sessions = {}
active_calls = {}   # ✅ FIXED (WAS MISSING)

SESSION_WINDOW = 30 * 60

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
    except Exception as e:
        print("TELEGRAM ERROR:", str(e))

def make_session_key(from_number, to_number):
    return f"{from_number}→{to_number}"

def get_session(key):
    session = sessions.get(key)

    if session and (now_ts() - session["last_update"] > SESSION_WINDOW):
        sessions.pop(key, None)
        return None

    return session

def update_session(from_number, to_number, msg, msg_type):
    key = make_session_key(from_number, to_number)

    session = get_session(key)

    if not session:
        session = {
            "from": from_number,
            "to": to_number,
            "last_message": msg,
            "type": msg_type,
            "created": now_readable(),
            "last_update": now_ts(),
            "count": 1
        }
        sessions[key] = session
    else:
        session["last_message"] = msg
        session["type"] = msg_type
        session["last_update"] = now_ts()
        session["count"] += 1

    return key, session

def render_inbox():
    if not sessions:
        return "📱 INBOX EMPTY"

    text = "📱 *WHATSAPP STYLE INBOX*\n\n"

    for key, s in sessions.items():
        text += f"""📞 {key}
💬 {s['last_message']}
📌 {s['type']}
🕒 {s['created']} → {now_readable()}
🔁 msgs: {s['count']}

"""

    return text

# ======================
# SMS → TELEGRAM
# ======================
@app.route("/sms", methods=["POST"])
def sms():
    data = request.json
    print("SMS INCOMING:", data)

    try:
        payload = data["data"]["payload"]

        message = payload.get("text", "")
        sender = payload["from"]["phone_number"]
        to_number = payload["to"][0]["phone_number"]

        update_session(sender, to_number, message, "SMS")

        send_telegram(f"""📩 SMS

From: {sender}
To: {to_number}

{message}

---
{render_inbox()}
""")

        return {"ok": True}

    except Exception as e:
        print("SMS ERROR:", str(e))
        return {"error": str(e)}

# ======================
# TELEGRAM → SMS
# ======================
@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.json
    print("TELEGRAM INCOMING:", data)

    try:
        message = data.get("message", {}).get("text", "")

        if not message.startswith("/reply"):
            send_telegram(render_inbox())
            return {"ok": True}

        parts = message.split(" ", 2)

        if len(parts) < 3:
            send_telegram("⚠️ Format: /reply number message")
            return {"error": "bad format"}

        number = parts[1]
        text_message = parts[2]

        url = "https://api.telnyx.com/v2/messages"
        headers = {
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": number,
            "to": number,
            "text": text_message
        }

        requests.post(url, json=payload, headers=headers)

        update_session(number, number, text_message, "OUTGOING")

        send_telegram(f"""✅ SENT

To: {number}
Message: {text_message}

---
{render_inbox()}
""")

        return {"ok": True}

    except Exception as e:
        print("TELEGRAM ERROR:", str(e))
        return {"error": str(e)}

# ======================
# VOICE EVENTS (CALLS)
# ======================
@app.route("/voice", methods=["POST"])
def voice():
    data = request.json
    print("VOICE INCOMING:", data)

    try:
        event = data.get("data", {}).get("event_type", "")
        payload = data.get("data", {}).get("payload", {})

        call_id = payload.get("call_control_id")
        from_number = payload.get("from")
        to_number = payload.get("to")

        # -------------------------
        # CALL STARTED
        # -------------------------
        if event == "call.initiated":
            active_calls[call_id] = {
                "from": from_number,
                "to": to_number,
                "answered": False,
                "time": now_readable()
            }

        # -------------------------
        # CALL ANSWERED
        # -------------------------
        elif event == "call.answered":
            if call_id in active_calls:
                active_calls[call_id]["answered"] = True

            send_telegram(f"""📞 CALL ANSWERED

From: {from_number}
To: {to_number}
""")

        # -------------------------
        # CALL ENDED
        # -------------------------
        elif event == "call.hangup":

            call = active_calls.get(call_id, {
                "from": from_number,
                "to": to_number,
                "answered": False,
                "time": now_readable()
            })

            if not call["answered"]:
                send_telegram(f"""📞 MISSED CALL

From: {call['from']}
To: {call['to']}
Time: {call['time']}
""")
            else:
                send_telegram(f"""📞 CALL ENDED

From: {call['from']}
To: {call['to']}
""")

            active_calls.pop(call_id, None)

        return {"ok": True}

    except Exception as e:
        print("VOICE ERROR:", str(e))
        return {"error": str(e)}

# ======================
# CALL LOG
# ======================
@app.route("/call-log", methods=["POST"])
def call_log():
    data = request.json
    print("CALL LOG:", data)
    return {"ok": True}

# ======================
# HEALTH
# ======================
@app.route("/")
def home():
    return "OK"
# ======================
# TEMP DELETE
# ======================
@app.route("/test")
def test():
    send_telegram("✅ Telegram test successful")
    return "sent"

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

# ======================
# FAX
# ======================
def send_fax(to_number, pdf_url):
    url = "https://api.telnyx.com/v2/faxes"

    headers = {
        "Authorization": f"Bearer {TELNYX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": to_number,
        "from": TELNYX_FAX_NUMBER,
        "media_url": pdf_url
    }

    return requests.post(url, json=payload, headers=headers).json()
