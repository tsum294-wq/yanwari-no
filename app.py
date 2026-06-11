import traceback
import json
import threading
import urllib.request
from collections import defaultdict
from datetime import date
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

_COUNTER_KEY = "yanwari_total"

def _redis(path):
    url   = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
    if not url or not token:
        return None
    try:
        req = urllib.request.Request(
            f"{url}/{path}",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.loads(r.read()).get("result")
    except Exception:
        return None

# ── 簡易レート制限（インメモリ・日次リセット）────────────────────────
# 悪用やバズによる高額請求を防ぐヒューズ。gunicorn単一ワーカー前提。
RATE_LIMIT_PER_IP_PER_DAY = 30    # 1IPあたり1日の生成回数
RATE_LIMIT_GLOBAL_PER_DAY = 500   # サイト全体の1日の生成回数

_rate_lock = threading.Lock()
_rate_day = date.today()
_rate_by_ip = defaultdict(int)
_rate_global = 0

def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    return fwd.split(",")[0].strip() if fwd else (request.remote_addr or "unknown")

def _check_rate_limit():
    """上限超過なら (jsonレスポンスdict, ステータス) を返す。OKなら None。"""
    global _rate_day, _rate_by_ip, _rate_global
    with _rate_lock:
        today = date.today()
        if today != _rate_day:
            _rate_day = today
            _rate_by_ip = defaultdict(int)
            _rate_global = 0
        if _rate_global >= RATE_LIMIT_GLOBAL_PER_DAY:
            return {"success": False, "error": "本日の生成上限に達しました。また明日お試しください。",
                    "error_type": "rate_limit"}, 429
        ip = _client_ip()
        if _rate_by_ip[ip] >= RATE_LIMIT_PER_IP_PER_DAY:
            return {"success": False, "error": "1日の利用上限に達しました。また明日お試しください。",
                    "error_type": "rate_limit"}, 429
        _rate_by_ip[ip] += 1
        _rate_global += 1
    return None


SITUATION_MAP = {
    "nomikai":     "飲み会・食事会への誘い",
    "goukon":      "合コン・デートへの誘い",
    "shift":       "バイトのシフト交代のお願い",
    "nijikai":     "2次会・3次会への誘い",
    "event":       "イベント・勉強会への誘い",
    "date":        "個人的なお出かけの誘い",
    "kokuhaku":    "告白・好意への返答",
    "work":        "仕事・副業の依頼断り",
    "kanyu":       "勧誘・セールスの断り",
    "okane":       "お金の貸し借りの断り",
    "line":        "LINEグループへの招待断り",
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


@app.route("/count")
def count():
    val = _redis(f"get/{_COUNTER_KEY}")
    return jsonify({"count": int(val) if val else 0})


@app.route("/health")
def health():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return jsonify({"ok": True, "key_set": True})
    return jsonify({"ok": False, "key_set": False,
                    "message": "ANTHROPIC_API_KEY が設定されていません"}), 200


@app.route("/generate-followup", methods=["POST"])
def generate_followup():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"success": False, "error": "ANTHROPIC_API_KEY が設定されていません", "error_type": "no_key"}), 400

    limited = _check_rate_limit()
    if limited:
        return jsonify(limited[0]), limited[1]

    data = request.json or {}
    situation    = SITUATION_MAP.get(data.get("situation", ""), data.get("situation", ""))
    relationship = RELATIONSHIP_MAP.get(data.get("relationship", ""), data.get("relationship", ""))
    original     = data.get("original_message", "").strip()

    prompt = f"""以下の状況で断り文を送った後、相手との関係を良好に保つための「フォローメッセージ」を2パターン生成してください。

【断った状況】{situation}
【相手との関係】{relationship}
【送った断り文】{original if original else "（省略）"}

フォローメッセージの要件:
- 断ってから2〜3日後に送るイメージ
- 断ったことを引きずらず、自然に関係を続けるための一言
- LINEでそのまま送れる文体
- AIっぽくない、人間らしい表現

以下の形式で出力してください:

【さりげないフォロー】
[文章]

【次の機会を作るフォロー】
[文章]"""

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return jsonify({"success": True, "result": message.content[0].text})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/generate", methods=["POST"])
def generate():
    # API キー確認
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({
            "success": False,
            "error": "ANTHROPIC_API_KEY が設定されていません。.env ファイルを確認してください。",
            "error_type": "no_key",
        }), 400

    limited = _check_rate_limit()
    if limited:
        return jsonify(limited[0]), limited[1]

    data = request.json or {}
    situation     = SITUATION_MAP.get(data.get("situation", ""), data.get("situation", ""))
    relationship  = RELATIONSHIP_MAP.get(data.get("relationship", ""), data.get("relationship", ""))
    details       = data.get("details", "").strip()
    detail_section = f"\n【補足情報】{details}" if details else ""

    prompt = PROMPT_TEMPLATE.format(
        situation=situation,
        relationship=relationship,
        detail_section=detail_section,
    )

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        _redis(f"incr/{_COUNTER_KEY}")
        return jsonify({"success": True, "result": message.content[0].text})
    except anthropic.AuthenticationError:
        return jsonify({
            "success": False,
            "error": "APIキーが無効です。https://console.anthropic.com で確認してください。",
            "error_type": "auth_error",
        }), 401
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("DEBUG", "false").lower() == "true"

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("=" * 50)
        print("⚠  ANTHROPIC_API_KEY が設定されていません")
        print("   .env ファイルに以下を追加してください:")
        print("   ANTHROPIC_API_KEY=sk-ant-xxxxx")
        print("=" * 50)

    app.run(host="0.0.0.0", port=port, debug=debug)
