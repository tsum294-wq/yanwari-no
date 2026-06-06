from flask import Flask, request, jsonify, render_template
import anthropic
import os

# .env ファイルがあれば読み込む（ローカル開発用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

SITUATION_MAP = {
    "nomikai":     "飲み会・食事会への誘い",
    "goukon":      "合コン・デートへの誘い",
    "shift":       "バイトのシフト交代のお願い",
    "nijikai":     "2次会・3次会への誘い",
    "event":       "イベント・勉強会への誘い",
    "date":        "個人的なお出かけの誘い",
    "other":       "その他の誘いやお願い",
}

RELATIONSHIP_MAP = {
    "friend":       "友達・同期",
    "senpai":       "先輩・上司",
    "kouhai":       "後輩・部下",
    "acquaintance": "あまり親しくない知人",
    "other":        "その他",
}

PROMPT_TEMPLATE = """\
日本語で、以下の状況に対する断り文を3パターン作成してください。

【断りたい状況】{situation}
【相手との関係】{relationship}{detail_section}

各パターンの要件:
- 相手を傷つけず、関係を壊さない断り方
- LINEやSNSでそのままコピペして送れる自然な文体
- AIっぽくない、人間らしい表現（「〜させていただく」系は避ける）
- 曖昧すぎず、でも直接すぎない日本語的な断り方
- 理由は一言程度（詳しく説明しすぎない）
- 温かみのある締め

以下の形式で厳密に出力してください（余計な前置きや説明は不要）:

【さらりと断る系】
（シンプルで軽い断り方）
[文章]

【気持ち重視系】
（申し訳なさと感謝を伝えつつ断る）
[文章]

【次につなげる系】
（今回は断りつつ関係を維持する）
[文章]\
"""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json or {}
    situation   = SITUATION_MAP.get(data.get("situation", ""), data.get("situation", ""))
    relationship = RELATIONSHIP_MAP.get(data.get("relationship", ""), data.get("relationship", ""))
    details     = data.get("details", "").strip()
    detail_section = f"\n【補足情報】{details}" if details else ""

    prompt = PROMPT_TEMPLATE.format(
        situation=situation,
        relationship=relationship,
        detail_section=detail_section,
    )

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return jsonify({"success": True, "result": message.content[0].text})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
