FROM python:3.11-slim

# ضبط المتغيرات لضمان طباعة السجلات فوراً
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

WORKDIR /app

# تثبيت أدوات النظام الأساسية ومحرك Tesseract والخطوط
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    fonts-dejavu-core \
    bash \
    procps \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملفات المشروع
COPY . /app

# تثبيت متطلبات بايثون
RUN pip install --no-cache-dir -r requirements.txt

# جعل سكربتات التشغيل قابلة للتنفيذ
RUN chmod +x watchdog_bot.sh run_bot_linux_mac.sh

# المنفذ الخاص بالويب ولوحة المشرف
EXPOSE 10000

# تشغيل البوت عبر المشرف الحارس (Watchdog) لضمان العمل 24/7
CMD ["bash", "watchdog_bot.sh"]
