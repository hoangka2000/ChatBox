from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from google import genai
import os

load_dotenv()

app = Flask(__name__)

FOCUSED_SYSTEM_PROMPT = (
    "Bạn là trợ lý tiếng Việt. Trả lời đúng trọng tâm câu hỏi, ngắn gọn, rõ ràng.\n"
    "- Ưu tiên câu trả lời trực tiếp trước.\n"
    "- Chỉ giải thích thêm khi thật sự cần.\n"
    "- Tối đa 5 câu, tránh lan man.\n"
    "- Nếu thiếu dữ liệu, nêu rõ và hỏi lại 1 câu ngắn."
)

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

GEMINI_MODEL = "gemini-2.5-flash"


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

        prompt = (
            f"{FOCUSED_SYSTEM_PROMPT}\n\n"
            f"Câu hỏi người dùng: {message}\n"
            "Trả lời trọng tâm:"
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        answer = response.text.strip()

        return jsonify({"content": answer})

    except Exception as e:
        print("Lỗi Gemini:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)