from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai
import requests
import os
import time

load_dotenv()

app = Flask(__name__)

FOCUSED_SYSTEM_PROMPT = (
    "Bạn là trợ lý tiếng Việt. Trả lời đúng trọng tâm câu hỏi, ngắn gọn, rõ ràng.\n"
    "- Ưu tiên câu trả lời trực tiếp trước.\n"
    "- Chỉ giải thích thêm khi thật sự cần.\n"
    "- Tối đa 5 câu, tránh lan man.\n"
    "- Nếu thiếu dữ liệu, nêu rõ và hỏi lại 1 câu ngắn."
)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.0-flash")


def ask_gemini(message):
    prompt = (
        f"{FOCUSED_SYSTEM_PROMPT}\n\n"
        f"Câu hỏi người dùng: {message}\n"
        "Trả lời trọng tâm:"
    )
    last_error = None

    # Thử model chính trước, nếu lỗi do quá tải thì fallback model phụ.
    for model_name in (GEMINI_MODEL, GEMINI_FALLBACK_MODEL):
        for delay in (0, 1.2, 2.5):
            try:
                if delay:
                    time.sleep(delay)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = (response.text or "").strip()
                if text:
                    return text
            except Exception as e:
                last_error = e
                if "503" not in str(e) and "UNAVAILABLE" not in str(e).upper():
                    break

    raise RuntimeError(f"Gemini đang quá tải hoặc lỗi tạm thời: {last_error}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api", methods=["POST"])
def api():
    try:
        data = request.get_json() or {}
        message = str(data.get("message", "")).strip()

        if not message:
            return jsonify({"error": "Thiếu nội dung message"}), 400

        answer = ask_gemini(message)

        return jsonify({"content": answer})

    except Exception as e:
        print("Lỗi /api:", e)
        message = str(e)
        if "503" in message or "UNAVAILABLE" in message.upper():
            return jsonify({
                "error": "Model đang quá tải tạm thời. Vui lòng thử lại sau vài giây."
            }), 503
        return jsonify({"error": message}), 500


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook Messenger đã xác minh thành công")
        return challenge, 200

    return "Verification failed", 403


@app.route("/webhook", methods=["POST"])
def messenger_webhook():
    data = request.get_json() or {}
    print("ĐÃ NHẬN WEBHOOK MESSENGER:")
    print(data)

    try:
        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    sender_id = event.get("sender", {}).get("id")

                    if "message" in event:
                        user_message = event["message"].get("text", "").strip()

                        if sender_id and user_message:
                            ai_reply = ask_gemini(user_message)
                            send_messenger_message(sender_id, ai_reply)

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print("Lỗi Messenger webhook:", e)
        return "ERROR", 500


def send_messenger_message(recipient_id, text):
    if not PAGE_ACCESS_TOKEN:
        print("Thiếu PAGE_ACCESS_TOKEN")
        return

    url = f"https://graph.facebook.com/v22.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    payload = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": text
        }
    }

    response = requests.post(url, json=payload)

    print("Messenger send status:", response.status_code)
    print("Messenger send response:", response.text)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)