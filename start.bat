@echo off
chcp 65001 > nul
echo Starting yanwari-no app...
echo Open http://localhost:5001 in your browser
set PYTHONIOENCODING=utf-8
"C:\Users\sunny\AppData\Local\Programs\Python\Python311\python.exe" app.py
pause
