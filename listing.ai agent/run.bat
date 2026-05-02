@echo off
echo Installing dependencies...
pip install -q groq python-dotenv streamlit requests Pillow reportlab filelock

echo.
echo Starting humsad/listing.ai...
echo ─────────────────────────────────────────
streamlit run app.py

echo.
pause