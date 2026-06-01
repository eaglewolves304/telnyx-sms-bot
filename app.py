from flask import Flask, request
import requests
import os

app = Flask(__name__)

# ======================
# CONFIG
# ======================
BOT_TOKEN = "8186394956:AAEVkJD9tWssRu_5PzX8vPH4ajfXvpBskVQ"
CHAT_ID = "8581143855"

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
TELNYX_NUMBER = "+YOUR_TELNYX_NUMBER"

# simple memory (temporary inbox)
last_sender = {}

# ======================
# TELEGRAM SENDER
# ======================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    })

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

# which Telnyx number received the SMS
to_number = payload["to"][0]["phone_number"]

# store last sender (simple version)
last_sender["number"] = sender

text = f"""📩 SMS

To: {to_number}
From: {sender}

{message}

Reply:
/reply {sender} your message
"""

        send_telegram(text)

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

        if not message:
            return {"ok": True}

        # only handle /reply commands
        if not message.startswith("/reply"):
            return {"ok": True}

        parts = message.split(" ", 2)

        if len(parts) < 3:
            send_telegram("⚠️ Format: /reply +44number your message")
            return {"error": "bad format"}

        recipient = parts[1]
        text_message = parts[2]

        url = "https://api.telnyx.com/v2/messages"

        headers = {
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": TELNYX_NUMBER,
            "to": recipient,
            "text": text_message
        }

        r = requests.post(url, json=payload, headers=headers)

        print("TELNYX RESPONSE:", r.status_code, r.text)

        send_telegram(f"✅ Sent to {recipient}:\n{text_message}")

        return {"ok": True}

    except Exception as e:
        print("TELEGRAM ERROR:", str(e))
        send_telegram(f"❌ Error: {str(e)}")
        return {"error": str(e)}

# ======================
# RUN SERVER
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
