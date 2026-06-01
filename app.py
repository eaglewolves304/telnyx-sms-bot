from flask import Flask, request
import requests
import os

app = Flask(__name__)

# ======================
# CONFIG
# ======================
BOT_TOKEN = "8186394956:AAF626X_G_qmsjpE7u8Ucsrlt2XqQN73nFI"
CHAT_ID = "8581143855"

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")

conversations = {}

# ======================
# TELEGRAM
# ======================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

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

        conversations[sender] = {
            "customer": sender,
            "your_number": to_number
        }

        send_telegram(f"""📩 SMS

To: {to_number}
From: {sender}

{message}

Reply:
/reply {sender} your message
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

        if not message or not message.startswith("/reply"):
            return {"ok": True}

        parts = message.split(" ", 2)

        if len(parts) < 3:
            send_telegram("⚠️ Format: /reply +number message")
            return {"error": "bad format"}

        customer = parts[1]
        text_message = parts[2]

        if customer not in conversations:
            send_telegram("❌ Conversation not found (server restarted)")
            return {"error": "not found"}

        recipient = conversations[customer]["customer"]
        from_number = conversations[customer]["your_number"]

        url = "https://api.telnyx.com/v2/messages"
        headers = {
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": from_number,
            "to": recipient,
            "text": text_message
        }

        r = requests.post(url, json=payload, headers=headers)

        send_telegram(f"""✅ Sent

From: {from_number}
To: {recipient}

{text_message}
""")

        return {"ok": True}

    except Exception as e:
        print("TELEGRAM ERROR:", str(e))
        send_telegram(f"❌ Error: {str(e)}")
        return {"error": str(e)}

# ======================
# VOICE API
# ======================
@app.route("/voice", methods=["POST"])
def voice():
    data = request.json
    print("VOICE INCOMING:", data)

    try:
        event = data.get("data", {}).get("event_type")

        payload = data.get("data", {}).get("payload", {})

        if event == "call.initiated":
            from_number = payload.get("from")
            to_number = payload.get("to")

            send_telegram(f"📞 Incoming Call\n\nFrom: {from_number}\nTo: {to_number}")

        elif event == "call.answered":
            send_telegram("📞 Call answered")

        elif event == "call.hangup":
            send_telegram("📞 Call ended")

        return {"ok": True}

    except Exception as e:
        print("VOICE ERROR:", str(e))
        send_telegram(f"❌ Voice error: {str(e)}")
        return {"error": str(e)}

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
