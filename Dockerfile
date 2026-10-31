FROM python:3.11-slim

# ضبط المتغيرات لضمان طباعة السجلات فوراً
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

WORKDIR /app

# نسخ ملفات المشروع
COPY . /app

# تثبيت المتطلبات إذا وُجدت
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# المنفذ الخاص بالويب ولوحة المشرف
EXPOSE 10000

# تشغيل البوت والسيرفر
CMD ["python3", "telegram_bot.py"]
