from flask import Flask, request
import requests
import os
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN = "8186394956:AAEVkJD9tWssRu_5PzX8vPH4ajfXvpBskVQ"
CHAT_ID = "8581143855"

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
TELNYX_NUMBER = "+YOUR_TELNYX_NUMBER"

# inbox storage (temporary in-memory)
inbox = {}  # {phone: {"messages": []}}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    })


@app.route("/sms", methods=["POST"])
def sms():
    data = request.json

    message = data["data"]["payload"].get("text", "")
    sender = data["data"]["payload"]["from"]["phone_number"]
    time = datetime.now().strftime("%H:%M:%S")

    # create inbox entry if not exists
    if sender not in inbox:
        inbox[sender] = {"messages": []}

    # store message
    inbox[sender]["messages"].append({
        "from": sender,
        "text": message,
        "time": time
    })

    # format message for Telegram
    text = f"📩 SMS from {sender} at {time}\n\n{message}\n\nReply with:\n/reply {sender} your message"

    send_telegram(text)

    return {"ok": True}


@app.route("/telegram", methods=["POST"])
def telegram():
    data = request.json

    try:
        message = data["message"]["text"]

        # expected format: /reply +447... hello there
        if not message.startswith("/reply"):
            return {"ok": True}

        parts = message.split(" ", 2)

        if len(parts) < 3:
            return {"error": "Invalid format"}

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

        requests.post(url, json=payload, headers=headers)

        send_telegram(f"✅ Sent to {recipient}:\n{text_message}")

        return {"ok": True}

    except Exception as e:
        send_telegram(f"❌ Error: {str(e)}")
        return {"error": str(e)}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
