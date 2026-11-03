@echo off
chcp 65001 >nul
title Telegram Universal Search Bot - Ready (Auto Connected)
echo ========================================================
echo   بوت تيليجرام جاهز ومربوط بالتوكن الخاص بك تلقائيا
echo   فقط ضع هذا الملف بجانب ملف الـ JSON واضغط مرتين
echo ========================================================
echo.
python telegram_bot.py
pause
