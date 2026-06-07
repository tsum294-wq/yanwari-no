# やんわりNO – デプロイ手順

## ローカルでテスト

1. `start.bat` をダブルクリック
2. ブラウザで http://localhost:5001 を開く
   ※ ANTHROPIC_API_KEY が Windows 環境変数に設定されていること

## Render.com に本番デプロイ

1. GitHub に新規リポジトリを作成（例: `yanwari-no`）
2. 以下をコマンドプロンプトで実行:
   git remote add origin https://github.com/ユーザー名/yanwari-no.git
   git push -u origin master

3. https://render.com にアクセス → New > Web Service
4. GitHub リポジトリを選択
5. 設定:
   - Build Command: pip install -r requirements.txt
   - Start Command: gunicorn app:app
6. Environment Variables に追加:
   ANTHROPIC_API_KEY = (あなたの API キー)
7. Deploy → 数分でデプロイ完了

## デプロイ後にやること

- templates/index.html の shareToX() 内の URL を実際の Render URL に更新
  （デフォルト: yanwari-no.onrender.com）

## X（Twitter）投稿テンプレート

---
断るの苦手な人に届け

「飲み会断りたい」「合コン無理」「バイトシフト交代頼まれた」

状況を選ぶだけで自然な断り文をAIが即生成してくれるやつ作った

使ってみて → https://yanwari-no.onrender.com

#やんわりNO #Claude
---
