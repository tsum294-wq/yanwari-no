@echo off
chcp 65001 > nul
echo.

if not exist .env (
    echo [!] .env ファイルがありません。
    echo     .env.example をコピーして .env を作成し、
    echo     ANTHROPIC_API_KEY を入力してください。
    echo.
    echo     例: copy .env.example .env
    echo         メモ帳 .env
    echo.
    pause
    exit /b 1
)

echo [OK] 起動中... http://localhost:5001 をブラウザで開いてください
echo      終了するには Ctrl+C を押してください
echo.
set PYTHONIOENCODING=utf-8
"C:\Users\sunny\AppData\Local\Programs\Python\Python311\python.exe" app.py
pause
