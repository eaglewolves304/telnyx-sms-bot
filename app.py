from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = "8186394956:AAEVkJD9tWssRu_5PzX8vPH4ajfXvpBskVQ"
CHAT_ID = "8581143855"

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
TELNYX_NUMBER = "+YOUR_REAL_TELNYX_NUMBER"

# simple test storage (NOT production-safe)
last_sender = {}

@app.route("/sms", methods=["POST"])
def sms():
    data = request.json

    message = data["data"]["payload"].get("text", "")
    sender = data["data"]["payload"]["from"]["phone_number"]

    last_sender["number"] = sender

    text = f"📩 SMS from {sender}:\n{message}"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    })

    return {"ok": True}


@app.route("/telegram", methods=["POST"])
def telegram():
    try:
        data = request.json
        message = data["message"]["text"]

        recipient = last_sender.get("number")

        if not recipient:
            return {"error": "No sender stored"}

        url = "https://api.telnyx.com/v2/messages"

        headers = {
            "Authorization": f"Bearer {TELNYX_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": TELNYX_NUMBER,
            "to": recipient,
            "text": message
        }

        requests.post(url, json=payload, headers=headers)

        return {"ok": True}

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
