from flask import Flask, request
import requests

app = Flask(__name__)

# 🔐 PUT YOUR NEW BOT TOKEN HERE (from BotFather)
BOT_TOKEN = "8186394956:AAEVkJD9tWssRu_5PzX8vPH4ajfXvpBskVQ"

# 📩 Your Telegram chat ID
CHAT_ID = "8581143855"


@app.route("/sms", methods=["POST"])
def sms():
    data = request.json

    # Telnyx SMS payload parsing
    message = data["data"]["payload"].get("text", "")
    sender = data["data"]["payload"]["from"]["phone_number"]

    text = f"📩 SMS from {sender}:\n{message}"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    })

    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
