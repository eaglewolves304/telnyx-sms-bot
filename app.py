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

# ======================
# MEMORY (simple session map)
# ======================
conversations = {}

# ======================
# TELEGRAM SENDER
# ======================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text
        })
    except Exception as e:
        print("TELEGRAM ERROR:", str(e))

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

        # store mapping per sender (basic inbox linking)
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

        if not message.startswith("/reply"):
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

        from_number = conversations[customer]["your_number"]
        recipient = conversations[customer]["customer"]

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

        requests.post(url, json=payload, headers=headers)

        send_telegram(f"""✅ Sent SMS

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
# VOICE EVENTS (SIP SAFE MODE)
# ======================
@app.route("/voice", methods=["POST"])
def voice():
    data = request.json
    print("VOICE INCOMING:", data)

    try:
        event = data.get("data", {}).get("event_type", "")
        payload = data.get("data", {}).get("payload", {})

        from_number = payload.get("from")
        to_number = payload.get("to")
        call_control_id = payload.get("call_control_id")

        # CALL START
        if event == "call.initiated":
            send_telegram(f"""📞 Incoming Call

From: {from_number}
To: {to_number}
""")

        # CALL ANSWERED
        elif event == "call.answered":
            send_telegram("📞 Call answered")

        # CALL ENDED → START VOICEMAIL RECORDING
        elif event == "call.hangup":
            send_telegram("📞 Call ended")

            if call_control_id:
                url = f"https://api.telnyx.com/v2/calls/{call_control_id}/actions/record_start"

                headers = {
                    "Authorization": f"Bearer {TELNYX_API_KEY}",
                    "Content-Type": "application/json"
                }

                requests.post(url, headers=headers, json={
                    "format": "mp3",
                    "channels": "single"
                })

                send_telegram(f"""🎙️ Voicemail Recording Started

From: {from_number}
To: {to_number}
""")

        return {"ok": True}

    except Exception as e:
        print("VOICE ERROR:", str(e))
        return {"error": str(e)}

# ======================
# RECORDING DELIVERY
# ======================
@app.route("/recording", methods=["POST"])
def recording():
    data = request.json
    print("RECORDING EVENT:", data)

    try:
        payload = data["data"]["payload"]

        recording_url = payload.get("recording_urls", {}).get("mp3")
        from_number = payload.get("from")
        to_number = payload.get("to")

        if recording_url:
            send_telegram(f"""🎙️ NEW VOICEMAIL

From: {from_number}
To: {to_number}

Audio:
{recording_url}
""")

        return {"ok": True}

    except Exception as e:
        print("RECORDING ERROR:", str(e))
        return {"error": str(e)}

# ======================
# CALL LOG (DEBUG)
# ======================
@app.route("/call-log", methods=["POST"])
def call_log():
    data = request.json
    print("CALL LOG:", data)

    try:
        payload = data["data"]["payload"]

        from_number = payload.get("from")
        to_number = payload.get("to")
        status = payload.get("call_state", "unknown")

        send_telegram(f"""📞 Call Event

From: {from_number}
To: {to_number}
Status: {status}
""")

        return {"ok": True}

    except Exception as e:
        print("CALL LOG ERROR:", str(e))
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
