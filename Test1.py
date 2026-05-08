from flask import Flask, request
from dotenv import load_dotenv
from google import genai
import requests
import os
import time

load_dotenv()

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "abc123")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-1.5-flash")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = (
    "Bạn là chatbot Messenger tiếng Việt. "
    "Trả lời ngắn gọn, rõ ràng, đúng trọng tâm. "
    "Tối đa 5 câu. Nếu thiếu dữ liệu thì hỏi lại 1 câu ngắn."
)


@app.route("/")
def home():
    return "Messenger chatbot is running", 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    print("VERIFY WEBHOOK:", {
        "mode": mode,
        "token": token,
        "challenge": challenge
    })

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def messenger_webhook():
    data = request.get_json() or {}

    print("========== WEBHOOK POST ==========")
    print(data)

    if data.get("object") != "page":
        return "IGNORED", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")

            if "message" not in event:
                continue

            message_obj = event.get("message", {})

            if message_obj.get("is_echo"):
                print("Bỏ qua tin nhắn echo của bot")
                continue

            user_message = message_obj.get("text", "").strip()

            if not sender_id or not user_message:
                continue

            print("SENDER_ID:", sender_id)
            print("USER MESSAGE:", user_message)

            try:
                send_typing_on(sender_id)

                ai_reply = ask_gemini(user_message)

                print("AI REPLY:", ai_reply)

                send_messenger_message(sender_id, ai_reply)

            except Exception as e:
                print("LỖI XỬ LÝ:", e)
                send_messenger_message(
                    sender_id,
                    "Xin lỗi, bot đang gặp lỗi tạm thời. Anh thử lại sau nhé."
                )

    return "EVENT_RECEIVED", 200


def ask_gemini(message):
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Người dùng nhắn: {message}\n"
        "Bot trả lời:"
    )

    last_error = None

    for model_name in (GEMINI_MODEL, GEMINI_FALLBACK_MODEL):
        for delay in (0, 1.2, 2.5):
            try:
                if delay:
                    time.sleep(delay)

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                text = (response.text or "").strip()

                if text:
                    return text

            except Exception as e:
                last_error = e
                print(f"Lỗi Gemini model {model_name}:", e)

                if "503" not in str(e) and "UNAVAILABLE" not in str(e).upper():
                    break

    raise RuntimeError(f"Gemini lỗi: {last_error}")


def send_typing_on(recipient_id):
    if not PAGE_ACCESS_TOKEN:
        print("Thiếu PAGE_ACCESS_TOKEN")
        return

    url = f"https://graph.facebook.com/v22.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": "typing_on"
    }

    response = requests.post(url, json=payload)
    print("Typing status:", response.status_code)
    print("Typing response:", response.text)


def send_messenger_message(recipient_id, text):
    if not PAGE_ACCESS_TOKEN:
        print("Thiếu PAGE_ACCESS_TOKEN")
        return

    url = f"https://graph.facebook.com/v22.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }

    response = requests.post(url, json=payload)

    print("Messenger send status:", response.status_code)
    print("Messenger send response:", response.text)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)