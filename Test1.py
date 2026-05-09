from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from openai import OpenAI
import requests
import os

load_dotenv()

app = Flask(__name__)

FOCUSED_SYSTEM_PROMPT = """
Bạn là chuyên gia tư vấn Yến sào Nha Trang, Khánh Hòa.

Phong cách trả lời:
- Mở đầu thân thiện, đậm chất tư vấn bán hàng.
- Trả lời bằng tiếng Việt, ngắn gọn, dễ hiểu.
- Tư vấn như nhân viên bán hàng chuyên nghiệp.
- Ưu tiên giới thiệu lợi ích, đối tượng phù hợp, cách dùng và gợi ý sản phẩm.
- Không nói quá công dụng chữa bệnh.
- Không khẳng định yến sào thay thế thuốc điều trị.
- Nếu khách hỏi giá, phân loại hoặc nhu cầu biếu tặng thì tư vấn theo từng nhóm.
- Nếu thiếu thông tin, hỏi lại ngắn gọn.
- Có thể dùng emoji nhẹ nhàng như 🪺✨🎁

Câu mở đầu gợi ý khi khách bắt đầu chat:
"Chào anh/chị ạ 🪺✨ Em chuyên tư vấn Yến sào Nha Trang – Khánh Hòa chính gốc, phù hợp để bồi bổ sức khỏe, làm quà biếu sang trọng hoặc dùng hằng ngày cho gia đình. Anh/chị đang muốn mua yến cho mình, cho người thân hay làm quà tặng ạ?"

Quy tắc tư vấn:
- Người lớn tuổi: gợi ý yến tinh chế, yến chưng sẵn ít đường.
- Trẻ em: tư vấn lượng dùng vừa phải, ưu tiên yến chưng dễ dùng.
- Phụ nữ sau sinh: tư vấn nhẹ nhàng, nên hỏi tình trạng sức khỏe.
- Người bận rộn: gợi ý yến chưng sẵn tiện lợi.
- Quà biếu: gợi ý hộp quà sang trọng, yến tinh chế hoặc yến chưng cao cấp.
- Khách chưa biết chọn loại nào: hỏi nhu cầu, độ tuổi người dùng và ngân sách.

Giới hạn:
- Tối đa 5 câu.
- Không trả lời lan man.
- Không bịa chính sách giá nếu chưa có dữ liệu.
"""

# =========================
# ENV
# =========================

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")

# =========================
# OPENROUTER CLIENT
# =========================

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Yen Sao Nha Trang Chatbot",
    },
)

# =========================
# AI CHAT
# =========================

def ask_openrouter(message):

    if not OPENROUTER_API_KEY:
        raise ValueError("Thiếu OPENROUTER_API_KEY")

    if not OPENROUTER_MODEL:
        raise ValueError("Thiếu OPENROUTER_MODEL")

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {
                "role": "system",
                "content": FOCUSED_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": message,
            },
        ],
        temperature=0.4,
        max_tokens=350,
    )

    answer = response.choices[0].message.content.strip()

    answer = answer.replace("**", "")
    answer = answer.replace("__", "")
    answer = answer.replace("```", "")
    answer = answer.replace("##", "")

    return answer

# =========================
# WEB UI
# =========================

@app.route("/")
def index():
    return render_template("index.html")

# =========================
# API
# =========================

@app.route("/api", methods=["POST"])
def api():

    try:
        data = request.get_json() or {}
        message = str(data.get("message", "")).strip()

        if not message:
            return jsonify({"error": "Thiếu message"}), 400

        answer = ask_openrouter(message)

        return jsonify({"content": answer})

    except Exception as e:
        print("Lỗi /api:", e)
        return jsonify({"error": str(e)}), 500

# =========================
# WEBHOOK VERIFY
# =========================

@app.route("/webhook", methods=["GET"])
def verify_webhook():

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook xác minh thành công")
        return challenge, 200

    return "Verification failed", 403

# =========================
# MESSENGER WEBHOOK
# =========================

@app.route("/webhook", methods=["POST"])
def messenger_webhook():

    data = request.get_json() or {}

    print("ĐÃ NHẬN WEBHOOK:")
    print(data)

    try:
        if data.get("object") == "page":

            for entry in data.get("entry", []):

                for event in entry.get("messaging", []):

                    sender_id = event.get("sender", {}).get("id")

                    if "message" in event:

                        user_message = event["message"].get("text", "").strip()

                        if sender_id and user_message:

                            ai_reply = ask_openrouter(user_message)

                            send_messenger_message(
                                sender_id,
                                ai_reply
                            )

        return "EVENT_RECEIVED", 200

    except Exception as e:
        print("Lỗi webhook:", e)
        return "ERROR", 500

# =========================
# SEND MESSAGE
# =========================

def send_messenger_message(recipient_id, text):

    if not PAGE_ACCESS_TOKEN:
        print("Thiếu PAGE_ACCESS_TOKEN")
        return

    url = (
        "https://graph.facebook.com/"
        f"v22.0/me/messages"
        f"?access_token={PAGE_ACCESS_TOKEN}"
    )

    payload = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": text
        },
    }

    response = requests.post(url, json=payload)

    print("Messenger status:", response.status_code)
    print("Messenger response:", response.text)

# =========================
# RUN
# =========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 3000))

    app.run(
        host="0.0.0.0",
        port=port
    )