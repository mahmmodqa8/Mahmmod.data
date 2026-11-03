#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
بوت وسيرفر تيليجرام الشامل للاستعلامات وقواعد البيانات الضخمة (1.3GB+)
Universal Data Search Engine & Cloud Telegram Server (24/7)
=============================================================================
الميزات المدمجة:
1. محرك معالجة متدفق فائق السرعة لملفات +1.3GB بصفر استهلاك للرام (Zero-RAM Stream).
2. زر إيقاف البحث الفوري (Stop Search) داخل تيليجرام وعبر الأمر /stop.
3. لوحة تحكم وإدارة كاملة للمشرف (Admin Control Panel) داخل تيليجرام وعلى الويب.
4. نظام البث الجماعي (/broadcast) والمراسلة الخاصة لمستخدم محدد (/msg).
5. البحث المتعدد دفعة واحدة (/bulk) واستخراج تقارير مجمعة.
6. التصحيح التلقائي للأخطاء الإملائية (Fuzzy Matching).
7. كاشف الشركة المشغلة ونوع الخط (Carrier Lookup: جوال، أوريدو، بيزك، سلكوم، زين...).
8. تصدير جهة اتصال للهاتف مباشرة (vCard .vcf) بنقرة واحدة.
9. فاحص وتدقيق أرقام الهويات الرسمية (ID Luhn Checksum).
10. المقارنة التقاطعية بين هدفين (/compare target1 vs target2).
11. كاشف الارتباطات العائلية والأقارب (/family).
12. كاشف وفك الهاشات المشفرة ومحلل النمط النفسي لكلمات المرور.
13. التوزيع الجغرافي ونسب المدن والمحافظات (/geo).
14. تصدير النتائج لجدول إكسل (Excel .csv / UTF-8 BOM).
15. تنبيهات لحظية فورية للمشرف عند دخول مستخدمين جدد أو أهداف مراقبة.
16. التقرير اليومي التلقائي (/digest) والنسخ الاحتياطي السحابي الكامل (/backup).
17. تخصيص رسائل البوت مباشرة من تيليجرام (/setwelcome).
=============================================================================
"""

import os
import re
import sys
import json
import time
import math
import shutil
import difflib
import zipfile
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from datetime import datetime
from collections import defaultdict

# ==========================================
# ⚙️ الإعدادات الأساسية
# ==========================================
BOT_TOKEN = (os.environ.get("TG_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or "8964192076:AAHTY7fq2CSDWxgmBexPkRA4oAAbdzv1Xoo").strip()
PORT = int(os.environ.get("PORT", "10000"))
DATA_FILE = os.environ.get("TG_DATA_FILE", "data.json")

# ملفات الحفظ والتخزين الدائم
USERS_FILE = "bot_users.json"
LOGS_FILE = "search_logs.json"
ADMIN_FILE = "admin_config.json"
WATCHLIST_FILE = "watchlist.json"
CUSTOM_CONFIG_FILE = "custom_config.json"
BOOKMARKS_FILE = "user_bookmarks.json"

DB_LOCK = threading.Lock()
ACTIVE_SEARCH_ABORTS = {}  # chat_id -> threading.Event()
START_TIME = time.time()

# ==========================================
# 👮‍♂️ إدارة صلاحيات المشرف والإعدادات المخصصة
# ==========================================
def load_admin_id() -> int:
    env_id = os.environ.get("ADMIN_ID", "1745730457").strip()
    if env_id.isdigit() and int(env_id) > 0:
        return int(env_id)
    if os.path.exists(ADMIN_FILE):
        try:
            with open(ADMIN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("admin_id", 0)
        except Exception:
            pass
    return 0

def save_admin_id(admin_id: int):
    try:
        with open(ADMIN_FILE, "w", encoding="utf-8") as f:
            json.dump({"admin_id": admin_id, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

CURRENT_ADMIN_ID = load_admin_id()

def load_custom_config() -> dict:
    if os.path.exists(CUSTOM_CONFIG_FILE):
        try:
            with open(CUSTOM_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_custom_config(cfg: dict):
    with DB_LOCK:
        try:
            with open(CUSTOM_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

# ==========================================
# 👥 إدارة المستخدمين وسجلات الاستعلام
# ==========================================
def load_all_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_all_users(users_dict: dict):
    with DB_LOCK:
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users_dict, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def register_user(from_user: dict, text_action: str = "") -> dict:
    global CURRENT_ADMIN_ID
    if not from_user or "id" not in from_user:
        return {}
    user_id = str(from_user["id"])
    users = load_all_users()
    now = time.time()

    is_new = user_id not in users
    if is_new:
        users[user_id] = {
            "id": int(user_id),
            "first_name": from_user.get("first_name", ""),
            "last_name": from_user.get("last_name", ""),
            "username": from_user.get("username", ""),
            "first_seen": now,
            "last_active": now,
            "query_count": 0,
            "last_query": "",
            "is_blocked": False
        }
        # تعيين أول مستخدم كأدمن تلقائياً لو لم يكن محدد
        if CURRENT_ADMIN_ID == 0:
            CURRENT_ADMIN_ID = int(user_id)
            save_admin_id(CURRENT_ADMIN_ID)
            print(f"👑 تم تعيين أول مستخدم كأدمن رئيسي للبوت: {user_id} (@{from_user.get('username', '')})")
        elif CURRENT_ADMIN_ID > 0 and int(user_id) != CURRENT_ADMIN_ID:
            # تنبيه فوري للمشرف بدخول مستخدم جديد
            u_tag = f"@{from_user.get('username')}" if from_user.get("username") else from_user.get("first_name", user_id)
            tg_send_message(CURRENT_ADMIN_ID, f"🔔 *مستخدم جديد دخل البوت لأول مرة:*\n• الاسم: {from_user.get('first_name', '')} {from_user.get('last_name', '')}\n• المعرف: {u_tag}\n• Chat ID: `{user_id}`")

    u = users[user_id]
    u["last_active"] = now
    if from_user.get("first_name"): u["first_name"] = from_user["first_name"]
    if from_user.get("last_name"): u["last_name"] = from_user["last_name"]
    if from_user.get("username"): u["username"] = from_user["username"]

    if text_action and not text_action.startswith("/") and not text_action.startswith("ℹ️") and not text_action.startswith("📊"):
        u["query_count"] = u.get("query_count", 0) + 1
        u["last_query"] = text_action[:70]

    save_all_users(users)
    return u

def block_user(user_id: int) -> bool:
    users = load_all_users()
    s_id = str(user_id)
    if s_id in users:
        users[s_id]["is_blocked"] = True
        save_all_users(users)
        return True
    return False

def unblock_user(user_id: int) -> bool:
    users = load_all_users()
    s_id = str(user_id)
    if s_id in users:
        users[s_id]["is_blocked"] = False
        save_all_users(users)
        return True
    return False

def append_search_log(user_id: int, user_name: str, query: str, mode: str, matches_count: int, elapsed_ms: float):
    entry = {
        "timestamp": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user_id,
        "user_name": user_name,
        "query": query[:100],
        "mode": mode,
        "matches": matches_count,
        "elapsed_ms": round(elapsed_ms, 1)
    }
    with DB_LOCK:
        try:
            logs = []
            if os.path.exists(LOGS_FILE):
                with open(LOGS_FILE, "r", encoding="utf-8") as f:
                    logs = json.load(f)
            logs.insert(0, entry)
            logs = logs[:250]
            with open(LOGS_FILE, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def get_recent_logs(limit: int = 25) -> list:
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
                return logs[:limit]
        except Exception:
            return []
    return []

def load_watchlist() -> list:
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_watchlist(items: list):
    with DB_LOCK:
        try:
            with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def safe_first(val, default="-") -> str:
    if isinstance(val, (list, tuple, set)) and len(val) > 0:
        return str(list(val)[0]).strip() or default
    if isinstance(val, str) and val.strip():
        return val.strip()
    return default

# ==========================================
# 🔤 معالجة وتوحيد النصوص العربية والأسماء الثنائية
# ==========================================
BILINGUAL_NAMES = {
    "نور": ["noor", "nour"],
    "محمود": ["mahmoud", "mahmud", "mhmoud", "mahmod", "mahmmod", "mahmod", "mhamad"],
    "احمد": ["ahmed", "ahmad", "ahmd"],
    "محمد": ["mohammed", "mohamed", "mohammad", "muhammad", "mohd"],
    "علي": ["ali", "aly"],
    "عمر": ["omar", "umar"],
    "خالد": ["khaled", "khalid"],
    "يوسف": ["yousef", "youssef", "yusef", "joseph"],
    "ابراهيم": ["ibrahim", "ebrahim", "ibraheem"],
    "ساره": ["sara", "sarah"],
    "طارق": ["tariq", "tareq", "tarik"],
    "فادي": ["fadi", "fady"],
    "رامي": ["rami", "ramy"],
    "سامي": ["sami", "samy"],
    "حسن": ["hassan", "hasan"],
    "حسين": ["hussein", "hussain"],
    "عبدالله": ["abdullah", "abdallah", "abedallah"],
    "عبدالرحمن": ["abdulrahman", "abdelrahman"]
}

def normalize_arabic(text: str) -> str:
    if not text:
        return ""
    t = str(text).lower()
    t = re.sub(r"[أإآٱ]", "ا", t)
    t = re.sub(r"ة", "ه", t)
    t = re.sub(r"[ىيئ]", "ي", t)
    t = re.sub(r"ؤ", "و", t)
    t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", t)
    t = re.sub(r"عبد\s+", "عبد", t)
    t = re.sub(r"[-_.\s]+", " ", t).strip()
    return t

def get_bilingual_variants(query_norm: str) -> list:
    import itertools
    q_clean = query_norm.strip()
    q_norm = normalize_arabic(q_clean)
    variants = {q_clean.lower(), q_norm}

    # توليد كافة احتمالات الهمزات والألف والتاء المربوطة
    for word in [q_clean, q_norm]:
        chars = []
        for c in word:
            if c in "اأإآ": chars.append(["ا", "أ", "إ", "آ"])
            elif c in "ةه": chars.append(["ة", "ه"])
            elif c in "ىي": chars.append(["ى", "ي"])
            else: chars.append([c])
        total = 1
        for opt in chars: total *= len(opt)
        if total <= 16:
            for p in itertools.product(*chars):
                variants.add("".join(p))
        else:
            variants.add(word.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا"))
            variants.add(word.replace("ا", "أ"))

    # مطابقة القاموس المزدوج (عربي وإنجليزي)
    for ar_name, en_list in BILINGUAL_NAMES.items():
        if q_norm == ar_name or q_norm in en_list or q_clean.lower() in en_list:
            variants.add(ar_name)
            for en in en_list: variants.add(en)
            for c in ["ا", "أ", "إ", "آ"]:
                variants.add(ar_name.replace("ا", c))

    return list(variants)

# ==========================================
# 📶 كاشف الشركة المشغلة ونوع الخط (Carrier Lookup)
# ==========================================
CARRIER_RULES = [
    (r"^(?:\+?970|\+?972|00970|00972)?0?59", "🇵🇸 جوال (Jawwal)", "محمول 📱"),
    (r"^(?:\+?970|\+?972|00970|00972)?0?56", "🇵🇸 أوريدو (Ooredoo Palestine)", "محمول 📱"),
    (r"^(?:\+?970|\+?972|00970|00972)?0?2", "🇵🇸 القدس/رام الله/الخليل/بيت لحم", "أرضي ثابت ☎️"),
    (r"^(?:\+?970|\+?972|00970|00972)?0?9", "🇵🇸 نابلس/طولكرم/قلقيلية/سلفيت", "أرضي ثابت ☎️"),
    (r"^(?:\+?970|\+?972|00970|00972)?0?4", "🇵🇸 جنين والمحافظات الشمالية", "أرضي ثابت ☎️"),
    (r"^(?:\+?970|\+?972|00970|00972)?0?8", "🇵🇸 قطاع غزة وخان يونس", "أرضي ثابت ☎️"),
    (r"^(?:\+?972|00972)?0?50", "🇮🇱 بيليفون (Pelephone)", "محمول 📱"),
    (r"^(?:\+?972|00972)?0?52", "🇮🇱 سلكوم (Cellcom)", "محمول 📱"),
    (r"^(?:\+?972|00972)?0?54", "🇮🇱 بارتنر (Partner/Orange)", "محمول 📱"),
    (r"^(?:\+?972|00972)?0?53", "🇮🇱 هوت موبايل (Hot Mobile)", "محمول 📱"),
    (r"^(?:\+?972|00972)?0?58", "🇮🇱 جولان تليكوم (Golan)", "محمول 📱"),
    (r"^(?:\+?962|00962)?0?7[789]", "🇯🇴 شبكات الأردن (زين / أورنج / أمنية)", "محمول 📱"),
    (r"^(?:\+?1)", "🇺🇸 الولايات المتحدة / كندا", "دولي 🌍")
]

def detect_carrier(phone_str: str) -> tuple:
    if not phone_str:
        return ("غير محدد", "غير معروف")
    clean = re.sub(r"[\s\-\(\)]", "", str(phone_str))
    for pattern, carrier, line_type in CARRIER_RULES:
        if re.search(pattern, clean):
            return (carrier, line_type)
    return ("شبكة محلية / دولية", "هاتف")

# ==========================================
# 🆔 فاحص وتدقيق أرقام الهويات (Luhn Checksum)
# ==========================================
def validate_id_number(id_str: str) -> tuple:
    digits = re.sub(r"\D", "", str(id_str))
    if len(digits) < 7 or len(digits) > 9:
        return False, "طول الرقم غير صحيح (يجب أن يكون 9 أرقام)"
    padded = digits.zfill(9)
    total = 0
    for i, ch in enumerate(padded):
        d = int(ch)
        step = d * (1 if i % 2 == 0 else 2)
        total += (step - 9) if step > 9 else step
    is_valid = (total % 10 == 0)
    return is_valid, "رقم هوية نظامي سليم 100% ✅" if is_valid else "رقم هوية غير صالح رياضياً ⚠️"

# ==========================================
# 🗂️ تصدير vCard للهاتف مباشرة (.vcf)
# ==========================================
def generate_vcard(record: dict) -> str:
    name = safe_first(record.get("n") or record.get("_names"), "جهة اتصال")
    phone = safe_first(record.get("t") or record.get("_phones"), "")
    email = safe_first(record.get("e") or record.get("_emails"), "")
    city = safe_first(record.get("city") or record.get("_cities"), "")
    username = safe_first(record.get("u") or record.get("_usernames"), "")

    vcard = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN;CHARSET=UTF-8:{name}",
        f"N;CHARSET=UTF-8:{name};;;;",
    ]
    if phone: vcard.append(f"TEL;TYPE=CELL,VOICE:{phone}")
    if email: vcard.append(f"EMAIL;TYPE=INTERNET:{email}")
    if city: vcard.append(f"ADR;TYPE=HOME;CHARSET=UTF-8:;;{city};;;;")
    if username: vcard.append(f"NOTE;CHARSET=UTF-8:Username: @{username}")
    vcard.append("END:VCARD")
    return "\n".join(vcard)

# ==========================================
# 🧩 تحليل وتصنيف الحقول الذكي (Smart Record Normalizer)
# ==========================================

# ==========================================
# 🌟 إدارة المفضلة والوسوم (Bookmarks)
# ==========================================
def load_all_bookmarks() -> dict:
    if os.path.exists(BOOKMARKS_FILE):
        try:
            with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_bookmark(user_id: int, record: dict) -> bool:
    with DB_LOCK:
        bms = load_all_bookmarks()
        uid = str(user_id)
        if uid not in bms: bms[uid] = []
        rec_sig = safe_first(record.get("n") or record.get("_names"), "") + "|" + safe_first(record.get("t") or record.get("_phones"), "") + "|" + safe_first(record.get("e") or record.get("_emails"), "")
        for b in bms[uid]:
            b_sig = safe_first(b.get("n") or b.get("_names"), "") + "|" + safe_first(b.get("t") or b.get("_phones"), "") + "|" + safe_first(b.get("e") or b.get("_emails"), "")
            if b_sig == rec_sig: return False
        for b in bms[uid]:
            b_sig = b.get("_names", [""])[0] + "|" + b.get("_phones", [""])[0] + "|" + b.get("_emails", [""])[0]
            if b_sig == rec_sig: return False
        bms[uid].append(record)
        try:
            with open(BOOKMARKS_FILE, "w", encoding="utf-8") as f:
                json.dump(bms, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

# ==========================================
# 🌐 كاشف ومنصات التواصل الاجتماعي (Social Presence)
# ==========================================
def generate_social_links(record: dict) -> list:
    links = []
    phones = record.get("_phones", [])
    usernames = record.get("_usernames", [])
    for p in phones:
        clean_p = re.sub(r"\D", "", str(p))
        if clean_p:
            if clean_p.startswith("05"): clean_p = "970" + clean_p[1:]
            elif clean_p.startswith("5"): clean_p = "970" + clean_p
            links.append(f"📱 *واتساب:* https://wa.me/{clean_p}\n✈️ *تيليجرام:* https://t.me/+{clean_p}")
    for u in usernames:
        clean_u = re.sub(r"^@", "", str(u))
        if clean_u:
            links.append(f"📸 *إنستغرام:* https://instagram.com/{clean_u}\n🎵 *تيك توك:* https://tiktok.com/@{clean_u}\n✈️ *تيليجرام:* https://t.me/{clean_u}")
    return links

# ==========================================
# 🔓 كاشف وفك الهاشات المشفرة (Hash Cracker)
# ==========================================
def identify_and_lookup_hash(hash_str: str) -> tuple:
    clean = hash_str.strip().lower()
    h_type = "غير معروف"
    if len(clean) == 32 and all(c in "0123456789abcdef" for c in clean): h_type = "MD5 أو NTLM"
    elif len(clean) == 40 and all(c in "0123456789abcdef" for c in clean): h_type = "SHA-1"
    elif len(clean) == 64 and all(c in "0123456789abcdef" for c in clean): h_type = "SHA-256"

    common_rainbow = {
        "e10adc3949ba59abbe56e057f20f883e": "123456",
        "25f9e794323b453885f5181f1b624d0b": "123456789",
        "5ebe2294ecd0e0f08eab7690d2a6ee69": "secret",
        "d8578edf8458ce06fbc5bb76a58c5ca4": "qwerty",
        "21232f297a57a5a743894a0e4a801fc3": "admin",
        "fcea920f7412b5da7be0cf6f11aa8db9": "password",
        "7c4a8d09ca3762af61e59520943dc26494f8941b": "123456",
        "88a91439265f2a1b920406fe1f237f9037c15e21": "password"
    }
    cracked = common_rainbow.get(clean)
    return h_type, cracked

# ==========================================
# 🧠 النمط النفسي لكلمات المرور (Password Profiler)
# ==========================================
def analyze_password_psychology(passwords: list) -> dict:
    if not passwords: return {"found": False}
    years = []
    words = []
    patterns = []
    for p in passwords:
        p_str = str(p)
        years.extend(re.findall(r"(19[5-9]\d|20[0-2]\d)", p_str))
        words.extend(re.findall(r"[a-zA-Z]{3,}", p_str))
        if re.search(r"123|abc|qwe|pass|000|111", p_str, re.I): patterns.append("نمط تسلسلي شائع (123 / qwerty)")
        if re.search(r"[!@#$%^&*()_+=\-]", p_str): patterns.append("يستخدم رموز خاصة (!@#$)")

    suggestions = []
    for w in list(set(words))[:3]:
        for y in list(set(years))[:2]:
            suggestions.append(f"{w}@{y}")
            suggestions.append(f"{w}{y}")

    return {
        "found": True,
        "detected_years": list(set(years)),
        "detected_keywords": list(set(words)),
        "patterns": list(set(patterns)),
        "predicted_passwords": suggestions[:6]
    }

# ==========================================
# 🕸️ كاشف شجرة العائلة والأقارب
# ==========================================
def correlate_family_tree(surname: str, max_records: int = 40) -> tuple:
    s_norm = normalize_arabic(surname)
    matches, _ = search_stream_1_3gb(s_norm, "all", max_results=max_records)
    if not matches: return {}, f"لم يتم العثور على أفراد يحملون عائلة `{surname}`"

    by_city = defaultdict(list)
    for r in matches:
        city = safe_first(r.get("city") or r.get("_cities"), "منطقة غير محددة")
        name = safe_first(r.get("n") or r.get("_names"), "شخص")
        phone = safe_first(r.get("t") or r.get("_phones"), "-")
        by_city[city].append(f"• {name} | 📱 `{phone}`")
    return by_city, None

# ==========================================
# 🗺️ التوزيع الجغرافي للمحافظات والمدن
# ==========================================
PALESTINIAN_CITIES = ["القدس", "نابلس", "رام الله", "الخليل", "جنين", "طولكرم", "قلقيلية", "بيت لحم", "أريحا", "سلفيت", "طوباس", "غزة", "خان يونس", "رفح", "دير البلح", "عمان", "إربد", "الزرقاء", "يافا", "حيفا", "عكا", "الناصرة"]

def analyze_geo_distribution(records: list) -> list:
    counts = defaultdict(int)
    total = 0
    for r in records:
        raw = r.get("_all_norm", "")
        for pc in PALESTINIAN_CITIES:
            if normalize_arabic(pc) in raw:
                counts[pc] += 1
                total += 1
                break

    sorted_cities = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    bars = []
    for city, cnt in sorted_cities[:8]:
        pct = (cnt / total * 100) if total > 0 else 0
        bar_len = int(pct / 10)
        bar_str = "█" * bar_len + "░" * (10 - bar_len)
        bars.append(f"• *{city}:* `{cnt}` سجل [{bar_str}] ({pct:.1f}%)")
    return bars

# ==========================================
# 📑 توليد إضبارة تحقيق واستخبارات رقمية
# ==========================================
def generate_investigation_dossier(target: str) -> str:
    records, _ = search_stream_1_3gb(target, "all", max_results=15)
    if not records: return f"⚠️ لم يتم العثور على سجلات كافية لبناء إضبارة عن `{target}`"

    names = list(set(sum([r.get("_names", []) for r in records], [])))
    phones = list(set(sum([r.get("_phones", []) for r in records], [])))
    emails = list(set(sum([r.get("_emails", []) for r in records], [])))
    usernames = list(set(sum([r.get("_usernames", []) for r in records], [])))
    passwords = list(set(sum([r.get("_passwords", []) for r in records], [])))
    cities = list(set(sum([r.get("_cities", []) for r in records], [])))

    carrier_info = "غير متوفر"
    if phones:
        c_name, c_type = detect_carrier(phones[0])
        carrier_info = f"{c_name} ({c_type})"

    id_info = "لم يتم رصد رقم هوية"
    for ph in phones + [target]:
        digs = re.sub(r"\D", "", ph)
        if len(digs) == 9:
            valid, note = validate_id_number(digs)
            id_info = f"`{digs}` - {note}"
            break

    pw_profile = analyze_password_psychology(passwords)
    lines = [
        f"📑 *إضبارة تحقيق واستخبارات رقمية (OSINT Dossier):*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🎯 *الهدف المستعلم عنه:* `{target}`",
        f"👤 *الأسماء المرتبطة:* {', '.join(names[:4]) if names else 'غير محدد'}",
        f"🆔 *معرفات الحسابات:* {', '.join([f'@{u}' for u in usernames[:4]]) if usernames else 'لا يوجد'}",
        f"📱 *أرقام الهواتف:* {', '.join([f'`{p}`' for p in phones[:3]]) if phones else 'لا يوجد'}",
        f"📶 *الشركة المشغلة:* {carrier_info}",
        f"🛡️ *فحص رقم الهوية:* {id_info}",
        f"📧 *عناوين البريد:* {', '.join(emails[:3]) if emails else 'لا يوجد'}",
        f"🏛️ *المحافظة / المدينة:* {', '.join(cities[:3]) if cities else 'غير محدد'}",
        f"🔑 *كلمات المرور المكشوفة:* {', '.join([f'`{p}`' for p in passwords[:4]]) if passwords else 'لا يوجد'}"
    ]
    if pw_profile.get("found"):
        if pw_profile.get("detected_years"): lines.append(f"📅 *سنوات ميلاد / تخرج محتملة:* {', '.join(pw_profile['detected_years'])}")
        if pw_profile.get("predicted_passwords"): lines.append(f"💡 *توقعات كلمات مرور أخرى:* {', '.join([f'`{s}`' for s in pw_profile['predicted_passwords'][:3]])}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 تم استخراج الإضبارة آلياً بناءً على {len(records)} سجل مرتبط.")
    return "\n".join(lines)

# ==========================================
# 📊 التقرير اليومي التلقائي (Daily Admin Digest)
# ==========================================
def generate_daily_digest() -> str:
    users = load_all_users()
    logs = get_recent_logs(200)
    now = time.time()
    today_ts = now - (24 * 3600)

    active_today = [u for u in users.values() if u.get("last_active", 0) >= today_ts]
    today_logs = [l for l in logs if l.get("timestamp", 0) >= today_ts]

    term_counts = defaultdict(int)
    for l in today_logs:
        q = l.get("query", "").strip()
        if q and len(q) > 2: term_counts[q] += 1
    top_5 = sorted(term_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_str = "\n".join([f"  {i+1}. `{t}` ({c} مرة)" for i, (t, c) in enumerate(top_5)]) if top_5 else "  لا توجد استعلامات كافية بعد"

    data_f = resolve_data_file()
    sz_fmt = "0 MB"
    if os.path.exists(data_f):
        sz = os.path.getsize(data_f) / (1024 * 1024)
        sz_fmt = f"{sz:.1f} MB"

    return f"""📊 *التقرير اليومي التلقائي (Daily Admin Digest):*
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 التاريخ: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`
👥 إجمالي المستخدمين في النظام: *{len(users)}* مستخدم
🟢 النشطون خلال 24 ساعة: *{len(active_today)}*
⚡ عمليات البحث المنجزة اليوم: *{len(today_logs)}* استعلام
📂 قاعدة البيانات النشطة: `{data_f}` ({sz_fmt})
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 *أكثر 5 كلمات تم البحث عنها:*
{top_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ السيرفر مستقر وشغال بنسبة جهوزية 100%."""

# ==========================================
# 📂 كاشف ملفات قواعد البيانات المتاحة بالسيرفر
# ==========================================
def list_available_databases() -> list:
    exts = (".json", ".csv", ".txt", ".tsv")
    files = []
    for f in os.listdir("."):
        if f.lower().endswith(exts) and not f.startswith("bot_") and not f.startswith("admin_") and not f.startswith("watchlist") and not f.startswith("custom_") and not f.startswith("search_") and not f.startswith("user_"):
            try:
                sz = os.path.getsize(f)
                sz_mb = sz / (1024 * 1024)
                files.append((f, sz, f"{sz_mb:.1f} MB" if sz_mb >= 1 else f"{sz / 1024:.1f} KB"))
            except Exception: pass
    return files

# ==========================================
# 📥 التنزيل التلقائي لملف البيانات على Render و السحابة
# ==========================================
def download_file_universal(url: str, output_path: str = "data.json") -> tuple:
    url = url.strip()
    if "dropbox.com" in url:
        url = url.replace("dl=0", "dl=1")
        if not url.endswith("dl=1") and "dl=1" not in url:
            url += ("&dl=1" if "?" in url else "?dl=1")
    elif "pixeldrain.com/u/" in url:
        url = url.replace("pixeldrain.com/u/", "pixeldrain.com/api/file/") + "?download"
    elif "pixeldrain.com/api/file/" in url and not url.endswith("?download"):
        url += "?download"
    elif "drive.google.com" in url or "docs.google.com" in url or "drive.usercontent.google.com" in url:
        m = re.search(r"[-_\w]{25,}", url)
        if m:
            file_id = m.group(0)
            url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=900) as resp:
        with open(output_path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024 * 4)
                if not chunk: break
                f.write(chunk)

    try:
        with open(output_path, "rb") as zf_test: hdr = zf_test.read(4)
        if hdr.startswith(b"PK\x03\x04"):
            import zipfile
            with zipfile.ZipFile(output_path, "r") as z:
                for zname in z.namelist():
                    if any(zname.lower().endswith(ext) for ext in (".json", ".csv", ".txt", ".sql")):
                        z.extract(zname, ".")
                        cfg = load_custom_config()
                        cfg["active_data_file"] = zname
                        save_custom_config(cfg)
                        break
    except Exception as ze:
        print(f"Zip extraction note: {ze}")

    return True, "تم التنزيل بنجاح"

def check_and_auto_download_data():
    target = resolve_data_file()
    if os.path.exists(target) and os.path.getsize(target) > 1024 * 1024:
        return

    default_dropbox = "https://www.dropbox.com/scl/fi/dsgx9c0ot6fmzrto39wip/Mahmmod-17m.json?rlkey=e6rztsgqnd9g3th6j7cyrommy&st=phebeuye&dl=1"
    data_url = os.environ.get("DATA_URL", "").strip() or default_dropbox
    if not data_url: return

    print(f"📥 [Cloud Sync] بدء تنزيل ملف الداتا تلقائياً من: {data_url}")
    try:
        ok, msg = download_file_universal(data_url, "data.json")
        if ok and os.path.exists("data.json"):
            sz_mb = os.path.getsize("data.json") / (1024 * 1024)
            print(f"✅ [Cloud Sync] اكتمل تنزيل ملف البيانات بنجاح! الحجم: {sz_mb:.1f} MB")
            if CURRENT_ADMIN_ID > 0:
                tg_send_message(CURRENT_ADMIN_ID, f"✅ *تم اكتمال تنزيل ملف الداتا تلقائياً على سيرفر Render!*\n📂 الحجم: *{sz_mb:.1f} MB*\nالبوت أصبح جاهزاً للاستعلام الفوري.")
    except Exception as e:
        print(f"⚠️ [Cloud Sync] خطأ أثناء تنزيل ملف البيانات: {e}")

def parse_line_to_smart_record(line: str) -> dict:
    line_str = line.strip()
    if not line_str:
        return {}

    # 1. فحص JSON
    if line_str.startswith("{") and line_str.endswith("}"):
        try:
            raw_obj = json.loads(line_str)
            return normalize_raw_object(raw_obj, line_str)
        except Exception:
            pass

    # 2. فحص نمط Combos (user:pass أو email:pass)
    if ":" in line_str and not line_str.startswith("http"):
        parts = [p.strip() for p in line_str.split(":") if p.strip()]
        if len(parts) == 2:
            p0, p1 = parts[0], parts[1]
            if "@" in p0:
                raw_obj = {"email": p0, "password": p1, "username": p0.split("@")[0]}
            else:
                raw_obj = {"username": p0, "password": p1, "name": p0}
            return normalize_raw_object(raw_obj, line_str)
        elif len(parts) >= 3:
            raw_obj = {"username": parts[0], "email": parts[1], "password": parts[2]}
            return normalize_raw_object(raw_obj, line_str)

    # 3. فحص CSV / Delimited
    if "," in line_str:
        parts = [p.strip().strip("\"'") for p in line_str.split(",")]
        raw_obj = {}
        for idx, pt in enumerate(parts):
            if "@" in pt and "email" not in raw_obj:
                raw_obj["email"] = pt
            elif re.search(r"0?5\d{8}", pt) and "phone" not in raw_obj:
                raw_obj["phone"] = pt
            elif idx == 0 and "name" not in raw_obj:
                raw_obj["name"] = pt
            elif "password" not in raw_obj and len(pt) >= 4:
                raw_obj["password"] = pt
            else:
                raw_obj[f"col_{idx+1}"] = pt
        return normalize_raw_object(raw_obj, line_str)

    # 4. استخراج عام بالحقول عبر Regex
    raw_obj = {"raw": line_str}
    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", line_str)
    if emails: raw_obj["email"] = emails[0]
    phones = re.findall(r"(?:\+?\d{1,3}[-.\s]?)?0?5\d{8}", line_str)
    if phones: raw_obj["phone"] = phones[0]
    users = re.findall(r"@([a-zA-Z0-9_.]{3,30})", line_str)
    if users: raw_obj["username"] = users[0]

    return normalize_raw_object(raw_obj, line_str)

def normalize_raw_object(raw_obj: dict, raw_line: str = "") -> dict:
    rec = dict(raw_obj)
    names = set()
    usernames = set()
    emails = set()
    phones = set()
    passwords = set()
    cities = set()
    all_text_parts = []

    # معالجة المفاتيح المختصرة المكتشفة في ملف الداتا (n: name, u: user, e: email, t: phone, id: user_id)
    if "n" in raw_obj and raw_obj["n"]: names.add(str(raw_obj["n"]).strip())
    if "u" in raw_obj and raw_obj["u"]: usernames.add(str(raw_obj["u"]).strip().lstrip("@"))
    if "e" in raw_obj and raw_obj["e"]: emails.add(str(raw_obj["e"]).strip())
    if "t" in raw_obj and raw_obj["t"]: phones.add(str(raw_obj["t"]).strip())
    if "id" in raw_obj and raw_obj["id"]: usernames.add(str(raw_obj["id"]).strip())

    for k, v in raw_obj.items():
        if not v or isinstance(v, (dict, list)) or str(k).startswith("_"):
            continue
        val_str = str(v).strip()
        if not val_str:
            continue
        all_text_parts.append(val_str)
        lk = str(k).lower().replace("_", "").replace("-", "")

        if any(w in lk for w in ("name", "اسم", "fname", "lname", "fullname")):
            names.add(val_str)
        if any(w in lk for w in ("user", "يوزر", "login", "handle", "nick")):
            usernames.add(val_str.lstrip("@"))
        if any(w in lk for w in ("mail", "بريد", "email")):
            emails.add(val_str)
        if any(w in lk for w in ("phone", "mobile", "هاتف", "جوال", "موبايل", "tel")):
            phones.add(val_str)
        if any(w in lk for w in ("pass", "كلمةمرور", "كلمةالسر", "pwd", "hash", "secret")):
            passwords.add(val_str)
        if any(w in lk for w in ("city", "مدينة", "address", "عنوان", "بلد", "منطقة", "محافظة")):
            cities.add(val_str)

        if "@" in val_str and re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", val_str):
            emails.add(val_str)
        if val_str.startswith("@") and len(val_str) >= 3 and " " not in val_str:
            usernames.add(val_str.lstrip("@"))
        digits = re.sub(r"\D", "", val_str)
        if len(digits) in (9, 10, 11, 12, 13) and (digits.startswith("05") or digits.startswith("970") or digits.startswith("972") or digits.startswith("962") or digits.startswith("1")):
            phones.add(val_str)

    if not names:
        for v in raw_obj.values():
            vs = str(v).strip()
            if re.search(r"[\u0600-\u06FF]", vs) and "@" not in vs and ":" not in vs and 3 <= len(vs) <= 40:
                names.add(vs)
                break
        if not names:
            for k, v in raw_obj.items():
                vs = str(v).strip()
                if not vs.isdigit() and "@" not in vs and len(vs) <= 30 and not str(k).startswith("_"):
                    names.add(vs)
                    break

    rec["_names"] = list(names)
    rec["_usernames"] = list(usernames)
    rec["_emails"] = list(emails)
    rec["_phones"] = list(phones)
    rec["_passwords"] = list(passwords)
    rec["_cities"] = list(cities)
    rec["_raw"] = raw_line
    rec["_all_text"] = " ".join(all_text_parts) if all_text_parts else raw_line
    rec["_all_norm"] = normalize_arabic(rec["_all_text"])
    return rec
# ==========================================
# 🚀 محرك البحث المتدفق فائق السرعة لملفات +1.3GB (Zero-RAM Stream)
# ==========================================
def resolve_data_file() -> str:
    # 1. إذا كان data.json موجوداً وحجمه أكبر من 1MB نختاره فوراً وبدون أي تردد
    if os.path.exists("data.json"):
        return "data.json"

    cfg = load_custom_config()
    configured_file = cfg.get("active_data_file", "")
    if configured_file and os.path.exists(configured_file) and os.path.getsize(configured_file) > 1024 * 1024:
        return configured_file

    ignore = {"requirements.txt", "procfile", "dockerfile", "readme.md", "readme_bot_hosting.md"}
    for fname in os.listdir("."):
        if fname.lower() in ignore or fname.startswith(".") or fname.startswith("bot_") or fname.startswith("admin_"):
            continue
        if any(fname.lower().endswith(ext) for ext in (".json", ".csv", ".tsv", ".sql", ".txt")):
            try:
                if os.path.getsize(fname) > 1024 * 1024:
                    return fname
            except Exception:
                pass

    return "data.json"

def search_stream_1_3gb(query: str, mode: str = "all", max_results: int = 2500, abort_event: threading.Event = None, progress_callback=None) -> tuple:
    target_file = resolve_data_file()
    if not os.path.exists(target_file):
        return [], f"⚠️ لم يتم العثور على ملف قاعدة بيانات (.json / .csv / .txt) في المجلد."

    total_bytes = os.path.getsize(target_file)
    total_mb = total_bytes / (1024 * 1024) if total_bytes > 0 else 1.0

    # كشف ترميز الملف تلقائياً
    encoding = "utf-8"
    try:
        with open(target_file, "rb") as f_head:
            sample_bytes = f_head.read(8192)
        if sample_bytes.startswith(b"\xff\xfe") or sample_bytes.startswith(b"\xfe\xff"):
            encoding = "utf-16"
        else:
            try:
                sample_bytes.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                try:
                    sample_bytes.decode("cp1256")
                    encoding = "cp1256"
                except Exception:
                    encoding = "utf-8"
    except Exception:
        encoding = "utf-8"

    q_norm = normalize_arabic(query)
    clean_digits = re.sub(r"\D", "", query)
    tokens = q_norm.split()
    variants = get_bilingual_variants(query)

    results = []
    idx = 0
    BLOCK_SIZE = 1024 * 1024 * 2 # 2MB
    buffer = ""
    bytes_scanned = 0
    last_cb_time = time.time()

    with open(target_file, "r", encoding=encoding, errors="ignore") as f:
        while True:
            if abort_event and abort_event.is_set():
                break

            chunk = f.read(BLOCK_SIZE)
            if not chunk:
                if buffer.strip():
                    rec = parse_line_to_smart_record(buffer)
                    if record_matches(rec, q_norm, clean_digits, tokens, variants, mode):
                        rec["_id"] = idx + 1
                        results.append(rec)
                break

            bytes_scanned += len(chunk.encode(encoding, errors="ignore"))
            now_t = time.time()
            if progress_callback and (now_t - last_cb_time >= 1.3):
                last_cb_time = now_t
                pct = int(min(99, bytes_scanned / total_bytes * 100)) if total_bytes > 0 else 50
                scanned_mb = bytes_scanned / (1024 * 1024)
                try:
                    progress_callback(pct, scanned_mb, total_mb, len(results))
                except Exception:
                    pass

            if "\x00" in chunk:
                chunk = chunk.replace("\x00", "")

            combined = buffer + chunk
            chunk_lower = combined.lower()

            has_match = any(v in chunk_lower for v in variants) or (len(clean_digits) >= 4 and clean_digits in chunk)
            if not has_match:
                buffer = combined[-2048:]
                continue

            # فحص واستخراج الكائنات JSON بسرعة فائقة عبر مواقع الكلمات المباشرة
            if "{" in combined and "}" in combined:
                seen_spans = set()
                # 1. مطابقة صيغ النصوص
                for v in variants:
                    if abort_event and abort_event.is_set(): break
                    start_p = 0
                    v_len = len(v)
                    while True:
                        pos = chunk_lower.find(v, start_p)
                        if pos == -1: break
                        obj_start = combined.rfind("{", max(0, pos - 600), pos)
                        obj_end = combined.find("}", pos, min(len(combined), pos + 600))
                        if obj_start != -1 and obj_end != -1:
                            span = (obj_start, obj_end)
                            if span not in seen_spans:
                                seen_spans.add(span)
                                obj_str = combined[obj_start:obj_end+1]
                                rec = parse_line_to_smart_record(obj_str)
                                if record_matches(rec, q_norm, clean_digits, tokens, variants, mode):
                                    rec["_id"] = idx + 1
                                    rec["_score"] = score_record(rec, q_norm, clean_digits, variants)
                                    results.append(rec)
                                    idx += 1
                                    if len(results) >= max_results: break
                        start_p = pos + v_len
                        if len(results) >= max_results: break

                # 2. مطابقة الأرقام
                if len(clean_digits) >= 4 and clean_digits in combined and len(results) < max_results:
                    start_p = 0
                    cd_len = len(clean_digits)
                    while True:
                        if abort_event and abort_event.is_set(): break
                        pos = combined.find(clean_digits, start_p)
                        if pos == -1: break
                        obj_start = combined.rfind("{", max(0, pos - 600), pos)
                        obj_end = combined.find("}", pos, min(len(combined), pos + 600))
                        if obj_start != -1 and obj_end != -1:
                            span = (obj_start, obj_end)
                            if span not in seen_spans:
                                seen_spans.add(span)
                                obj_str = combined[obj_start:obj_end+1]
                                rec = parse_line_to_smart_record(obj_str)
                                if record_matches(rec, q_norm, clean_digits, tokens, variants, mode):
                                    rec["_id"] = idx + 1
                                    rec["_score"] = score_record(rec, q_norm, clean_digits, variants)
                                    results.append(rec)
                                    idx += 1
                                    if len(results) >= max_results: break
                        start_p = pos + cd_len
                        if len(results) >= max_results: break

                buffer = combined[-1024:]
            else:
                lines = combined.splitlines()
                buffer = lines.pop() if lines else ""

                for line in lines:
                    if abort_event and abort_event.is_set(): break
                    line_str = line.strip()
                    if not line_str: continue

                    line_lower = line_str.lower()
                    if not any(v in line_lower for v in variants) and (not clean_digits or clean_digits not in line_str):
                        continue

                    rec = parse_line_to_smart_record(line_str)
                    if record_matches(rec, q_norm, clean_digits, tokens, variants, mode):
                        rec["_id"] = idx + 1
                        rec["_score"] = score_record(rec, q_norm, clean_digits, variants)
                        results.append(rec)
                        idx += 1
                        if len(results) >= max_results: break

            if len(results) >= max_results:
                break

    results.sort(key=lambda r: r.get("_score", 0), reverse=True)
    return results, None

def record_matches(rec: dict, q_norm: str, clean_digits: str, tokens: list, variants: list, mode: str) -> bool:
    if not rec:
        return False
    raw_lower = rec.get("_raw", "").lower()
    all_norm = rec.get("_all_norm", "")
    all_lower = rec.get("_all_text", "").lower()

    # مطابقة الأرقام
    if len(clean_digits) >= 4:
        if clean_digits in re.sub(r"\D", "", raw_lower) or clean_digits in re.sub(r"\D", "", all_lower):
            return True
        if any(clean_digits[-9:] in re.sub(r"\D", "", p) or clean_digits in re.sub(r"\D", "", p) for p in rec.get("_phones", [])):
            return True

    # مطابقة الصيغ والأسماء والهمزات
    if any(v in all_norm for v in variants) or any(v in raw_lower for v in variants) or any(v in all_lower for v in variants):
        return True

    # مطابقة الكلمات المتعددة
    if len(tokens) > 1 and all(t in all_norm or t in raw_lower or t in all_lower for t in tokens):
        return True

    return False

def score_record(rec: dict, q_norm: str, clean_digits: str, variants: list) -> int:
    score = 0
    names_norm = [normalize_arabic(n) for n in rec.get("_names", [])]
    users_norm = [u.lower() for u in rec.get("_usernames", [])]
    emails_norm = [e.lower() for e in rec.get("_emails", [])]

    if any(n == q_norm for n in names_norm) or any(u == q_norm for u in users_norm) or any(e == q_norm for e in emails_norm):
        score += 1000
    elif any(any(n.startswith(v) for v in variants) for n in names_norm) or any(any(u.startswith(v) for v in variants) for u in users_norm):
        score += 800
    elif len(clean_digits) >= 7 and any(re.sub(r"\D", "", p).endswith(clean_digits[-9:]) for p in rec.get("_phones", [])):
        score += 900
    elif any(any(v in n.split() for v in variants) for n in names_norm):
        score += 700
    else:
        score += 500
    return score

# ==========================================
# 📡 Telegram API Helpers
# ==========================================
def tg_request(method: str, params: dict = None) -> dict:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = None
    headers = {"Content-Type": "application/json"}
    if params:
        data = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "description": str(e)}

def tg_send_message(chat_id: int, text: str, reply_markup: dict = None, parse_mode: str = "Markdown") -> dict:
    params = {
        "chat_id": chat_id,
        "text": text[:4050]
    }
    if reply_markup: params["reply_markup"] = reply_markup
    if parse_mode: params["parse_mode"] = parse_mode
    res = tg_request("sendMessage", params)
    if not res.get("ok") and parse_mode:
        del params["parse_mode"]
        res = tg_request("sendMessage", params)
    return res

def tg_edit_message(chat_id: int, message_id: int, text: str, reply_markup: dict = None, parse_mode: str = "Markdown") -> dict:
    params = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text[:4050]
    }
    if reply_markup and isinstance(reply_markup, dict) and "inline_keyboard" in reply_markup:
        params["reply_markup"] = reply_markup
    if parse_mode:
        params["parse_mode"] = parse_mode

    res = tg_request("editMessageText", params)
    if not res.get("ok"):
        if parse_mode:
            del params["parse_mode"]
            res = tg_request("editMessageText", params)
        if not res.get("ok"):
            res = tg_send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    return res

def tg_send_document(chat_id: int, filename: str, content_bytes: bytes, caption: str = ""):
    boundary = "----FormBoundary" + str(int(time.time()))
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption[:950]}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + content_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "description": str(e)}

def make_progress_bar(percent: int, length: int = 10) -> str:
    clamped = max(0, min(100, int(percent)))
    filled = round((clamped / 100) * length)
    empty = max(0, length - filled)
    return f"[{'█' * filled}{'░' * empty}] {clamped}%"

# ==========================================
# 📄 تنسيق النتائج والبطاقات في الشات (NO TXT FILES)
# ==========================================
RECORDS_PER_PAGE = 10

def format_results_page(query: str, matches: list, page: int = 1, is_aborted: bool = False) -> tuple:
    total_pages = math.ceil(len(matches) / RECORDS_PER_PAGE) or 1
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * RECORDS_PER_PAGE
    end_idx = min(start_idx + RECORDS_PER_PAGE, len(matches))
    page_records = matches[start_idx:end_idx]

    blocks = []
    for i, r in enumerate(page_records, start_idx + 1):
        name = r.get("n") or (r.get("_names")[0] if r.get("_names") else None) or r.get("name") or r.get("full_name") or "غير محدد"
        user = r.get("u") or (r.get("_usernames")[0] if r.get("_usernames") else None) or r.get("username") or r.get("id") or "بدون"
        if user != "بدون" and not user.startswith("@") and not user.isdigit():
            user = f"@{user}"
        mail = r.get("e") or (r.get("_emails")[0] if r.get("_emails") else None) or r.get("email") or "بدون"
        phone = r.get("t") or (r.get("_phones")[0] if r.get("_phones") else None) or r.get("phone") or "بدون"
        pass_str = f"🔑 `{r['_passwords'][0]}`" if r.get("_passwords") else ""
        city_str = f"🏛️ {r['_cities'][0]}" if r.get("_cities") else ""

        carrier_name, line_type = detect_carrier(phone)
        carrier_label = f"📶 {carrier_name} ({line_type})" if phone != "بدون" else ""

        line = [
            f"[#{i}/{len(matches)}] 👤 *{name}* | 🆔 {user}",
            f"📧 `{mail}` | 📱 `{phone}`",
            f"{pass_str} {city_str}".strip(),
            carrier_label
        ]
        blocks.append("\n".join([l for l in line if l]))

    status_tag = "⏹️ *تم إيقاف البحث بطلبك*" if is_aborted else f"{make_progress_bar(100, 10)} مكتمل ✅"
    header = [
        f"🎯 *نتائج البحث المباشرة عن:* `{query}`",
        f"📊 *إجمالي المطابقات:* `{len(matches)}` سجل | 📄 صفحة *{page}* من *{total_pages}*",
        status_tag,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "\n───────────────────\n".join(blocks),
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    inline_rows = []
    nav_row = []
    if page > 1:
        nav_row.append({"text": "◀️ السابق", "callback_data": f"page_{page-1}"})
    nav_row.append({"text": f"📄 {page} / {total_pages}", "callback_data": "page_noop"})
    if page < total_pages:
        nav_row.append({"text": "التالي ▶️", "callback_data": f"page_{page+1}"})
    if nav_row:
        inline_rows.append(nav_row)

    safe_q = urllib.parse.quote(query[:30])
    inline_rows.append([
        {"text": "📊 تصدير Excel", "callback_data": f"export_excel"},
        {"text": "📱 حفظ جهة اتصال (vCard)", "callback_data": f"export_vcard_{start_idx}"}
    ])

    if page_records:
        first_rec = page_records[0]
        sub_row = []
        first_e = first_rec.get("e") or (first_rec.get("_emails")[0] if first_rec.get("_emails") else None)
        first_p = first_rec.get("t") or (first_rec.get("_phones")[0] if first_rec.get("_phones") else None)
        if first_e:
            e_safe = urllib.parse.quote(str(first_e)[:30])
            sub_row.append({"text": "🔍 تفرع بالإيميل", "callback_data": f"pivot_email_{e_safe}"})
        if first_p:
            p_safe = urllib.parse.quote(str(first_p)[:20])
            sub_row.append({"text": "📱 تفرع بالهاتف", "callback_data": f"pivot_phone_{p_safe}"})
        if sub_row:
            inline_rows.append(sub_row)

    inline_rows.append([
        {"text": "🌐 فحص حسابات السوشيال", "callback_data": f"social_links_{start_idx}"},
        {"text": "⭐ حفظ في المفضلة", "callback_data": f"bookmark_add_{start_idx}"}
    ])
    inline_rows.append([
        {"text": "🕸️ شجرة العلاقات", "callback_data": f"quick_tree_{safe_q}"},
        {"text": "📑 إضبارة تحقيق", "callback_data": f"quick_dossier_{safe_q}"}
    ])
    if total_pages > 1:
        inline_rows.append([{"text": "📜 إرسال جميع السجلات في الشات", "callback_data": "send_all_chat"}])

    return "\n".join(header), {"inline_keyboard": inline_rows}

# ==========================================
# 🎮 لوحات المفاتيح والأزرار
# ==========================================
MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "🔍 بحث شامل سريع"}, {"text": "👤 بحث بالاسم (المتشابه)"}],
        [{"text": "🆔 بحث باليوزر (@Username)"}, {"text": "📧 بحث بالإيميل"}],
        [{"text": "🔑 كشف الباسوردات (Combos)"}, {"text": "📱 بحث بالهاتف والدولة"}],
        [{"text": "📋 بحث متعدد (Bulk)"}, {"text": "⚖️ مقارنة هدفين"}],
        [{"text": "🤖 وكيل الذكاء الاصطناعي"}, {"text": "🕸️ شجرة العلاقات"}],
        [{"text": "🏛️ فلتر المدن"}, {"text": "🌍 مفاتيح الدول"}, {"text": "📶 فحص مشغل الخط"}],
        [{"text": "🛡️ فحص وتكرار الباسوردات"}, {"text": "📝 توليد Wordlist"}],
        [{"text": "🔔 قائمة المراقبة"}, {"text": "📑 إضبارة تحقيق"}],
        [{"text": "📸 فاحص إنستغرام"}, {"text": "📊 إحصائيات البوت"}, {"text": "👮‍♂️ لوحة المشرف"}]
    ],
    "resize_keyboard": True
}

# ==========================================
# 👮‍♂️ لوحة تحكم المشرف التفاعلية داخل تيليجرام
# ==========================================
def get_admin_dashboard_reply() -> tuple:
    users = load_all_users()
    total_u = len(users)
    now = time.time()
    active_15m = sum(1 for u in users.values() if (now - u.get("last_active", 0)) < 15 * 60)
    total_queries = sum(u.get("query_count", 0) for u in users.values())
    blocked_count = sum(1 for u in users.values() if u.get("is_blocked", False))

    target_file = resolve_data_file()
    fsize_str = "غير موجود"
    if os.path.exists(target_file):
        mb = os.path.getsize(target_file) / (1024 * 1024)
        fsize_str = f"{mb:.1f} MB" if mb < 1000 else f"{(mb/1024):.2f} GB"

    msg = [
        "👮‍♂️ *لوحة تحكم وإدارة البوت الشاملة (Admin Dashboard)*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"👥 *إجمالي المستخدمين المسجلين:* `{total_u}` مستخدم",
        f"🟢 *المستخدمون النشطون الآن (15 دقيقة):* `{active_15m}` مستخدم",
        f"🔍 *إجمالي عمليات البحث المنفذة:* `{total_queries}` استعلام",
        f"🚫 *المستخدمون المحظورون:* `{blocked_count}` مستخدم",
        f"📂 *ملف قاعدة البيانات الحالي:* `{target_file}` ({fsize_str})",
        f"⏱️ *مدة تشغيل الخادم:* `{int((time.time() - START_TIME)/3600)} ساعة و {int(((time.time() - START_TIME)%3600)/60)} دقيقة`",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "👇 *الأوامر السريعة للمشرف:*",
        "• للإرسال لجميع المستخدمين: `/broadcast <الرسالة>`",
        "• لمراسلة مستخدم معين: `/msg <chat_id> <الرسالة>`",
        "• لحظر مستخدم: `/ban <chat_id>`",
        "• لفك حظر مستخدم: `/unban <chat_id>`",
        "• لنسخ احتياطي كامل: `/backup`",
        "• لتقرير اليوم التلقائي: `/digest`",
        "• لتخصيص الترحيب: `/setwelcome <النص>`",
        "• لإيقاف أي بحث جاري: `/stop`"
    ]

    kb = {
        "inline_keyboard": [
            [{"text": "👥 قائمة المستخدمين والنشطين", "callback_data": "admin_users"}, {"text": "📜 سجل عمليات البحث", "callback_data": "admin_logs"}],
            [{"text": "📢 إرسال رسالة للجميع (Broadcast)", "callback_data": "admin_prompt_broadcast"}, {"text": "💬 مراسلة مستخدم", "callback_data": "admin_prompt_msg"}],
            [{"text": "💾 تحميل نسخة احتياطية (Backup)", "callback_data": "admin_do_backup"}, {"text": "📊 التقرير اليومي (Digest)", "callback_data": "admin_do_digest"}],
            [{"text": "🔄 تحديث الإحصائيات", "callback_data": "admin_refresh"}, {"text": "🌐 لوحة الويب (Port 8080)", "callback_data": "admin_web_url"}]
        ]
    }
    return "\n".join(msg), kb

# ==========================================
# 🤖 معالجة رسائل وأوامر تيليجرام
# ==========================================
USER_SESSIONS = {}  # chat_id -> dict

def handle_update(update: dict):
    global CURRENT_ADMIN_ID

    msg = update.get("message")
    cb = update.get("callback_query")

    chat_id = None
    from_user = None

    if msg:
        chat_id = msg["chat"]["id"]
        from_user = msg.get("from", {})
    elif cb:
        chat_id = cb["message"]["chat"]["id"]
        from_user = cb.get("from", {})

    if not chat_id or not from_user:
        return

    # تسجيل المستخدم وتحديث نشاطه لحظياً
    u = register_user(from_user, msg.get("text", "") if msg else "")
    if u.get("is_blocked") and from_user.get("id") != CURRENT_ADMIN_ID:
        tg_send_message(chat_id, "⛔ تم حظر حسابك من استخدام هذا البوت بواسطة الإدارة.")
        return

    sess = USER_SESSIONS.setdefault(chat_id, {
        "last_mode": "all",
        "last_results": [],
        "last_query": "",
        "current_page": 1
    })

    # 1. معالجة نقرات أزرار Inline Callbacks
    if cb:
        cb_id = cb["id"]
        data = cb.get("data", "")
        msg_id = cb["message"]["message_id"]

        tg_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "جاري المعالجة..."})

        # زر إيقاف البحث الفوري
        if data == "abort_search":
            if chat_id in ACTIVE_SEARCH_ABORTS:
                ACTIVE_SEARCH_ABORTS[chat_id].set()
                tg_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "⏹️ تم إيقاف البحث!"})
            return

        # تنقل الصفحات
        if data.startswith("page_"):
            p_str = data.replace("page_", "")
            if p_str != "noop":
                page_num = int(p_str)
                sess["current_page"] = page_num
                txt, kb = format_results_page(sess["last_query"], sess["last_results"], page_num)
                tg_edit_message(chat_id, msg_id, txt, kb)
            return

        # تصدير إكسل لكافة السجلات (حتى 15000 سجل)
        if data == "export_excel":
            if sess["last_results"]:
                tot = len(sess["last_results"])
                lines = ["\ufeff#,#الاسم,اليوزر,الهاتف,الإيميل,المعرف (ID),البيانات الخام"]
                for i, r in enumerate(sess["last_results"], 1):
                    nm = str(r.get("n") or (r.get("_names")[0] if r.get("_names") else "-")).replace('"', '""')
                    us = str(r.get("u") or (r.get("_usernames")[0] if r.get("_usernames") else "-")).replace('"', '""')
                    ph = str(r.get("t") or (r.get("_phones")[0] if r.get("_phones") else "-")).replace('"', '""')
                    em = str(r.get("e") or (r.get("_emails")[0] if r.get("_emails") else "-")).replace('"', '""')
                    uid = str(r.get("id") or "-").replace('"', '""')
                    raw_txt = str(r.get("_all_text") or "-").replace('"', '""')[:150]
                    lines.append(f'"{i}","{nm}","{us}","{ph}","{em}","{uid}","{raw_txt}"')
                csv_bytes = "\n".join(lines).encode("utf-8-sig")
                tg_send_document(chat_id, f"search_results_{tot}_records.csv", csv_bytes, f"📊 جدول إكسل كامل يضم كافة السجلات المطابقة ({tot} سجل)")
            return

        # تصدير جهة اتصال vCard
        if data.startswith("export_vcard_"):
            idx = int(data.replace("export_vcard_", ""))
            if sess["last_results"] and idx < len(sess["last_results"]):
                rec = sess["last_results"][idx]
                vcard_str = generate_vcard(rec)
                nm = safe_first(rec.get("n") or rec.get("_names"), "contact")
                safe_nm = re.sub(r"\W", "_", nm)[:15]
                tg_send_document(chat_id, f"{safe_nm}.vcf", vcard_str.encode("utf-8"), f"📱 بطاقة اتصال جاهزة للإضافة لهاتفك: {nm}")
            return

        # إرسال جميع السجلات في الشات (مع حماية تيليجرام من الحظر المؤقت FloodWait)
        if data == "send_all_chat":
            if sess["last_results"]:
                total_count = len(sess["last_results"])
                tg_send_message(chat_id, f"📜 *جاري إرسال كافة السجلات المكتشفة ({total_count} سجل) في الشات...*")
                # إذا كانت السجلات أكثر من 200 سجل نرسل أول 200 رسالة ونرفق ملف الإكسل الكامل
                total_p = min(math.ceil(total_count / RECORDS_PER_PAGE), 20)
                for p in range(1, total_p + 1):
                    txt, _ = format_results_page(sess["last_query"], sess["last_results"], p)
                    tg_send_message(chat_id, txt)
                    time.sleep(0.25)
                if total_count > (total_p * RECORDS_PER_PAGE):
                    tg_send_message(chat_id, f"💡 تم إرسال أول {total_p * RECORDS_PER_PAGE} سجل في الشات لتجنب تقييد تيليجرام. لتنزيل كافة السجلات كاملة ({total_count} سجل)، اضغط زر '📊 تصدير Excel' بالأسفل.")
            return

                # لوحة تحكم المشرف (Admin Callbacks)
        if data.startswith("admin_"):
            if from_user.get("id") != CURRENT_ADMIN_ID:
                tg_send_message(chat_id, "⛔ هذا القسم مخصص لمالك البوت فقط.")
                return

            if data == "admin_refresh":
                txt, kb = get_admin_dashboard_reply()
                tg_edit_message(chat_id, msg_id, txt, kb)
            elif data == "admin_users":
                users = load_all_users()
                now = time.time()
                lines = [f"👥 *قائمة مستخدمي البوت المسجلين ({len(users)}):*\n"]
                for uid, udata in sorted(users.items(), key=lambda x: x[1].get("last_active", 0), reverse=True)[:25]:
                    name = udata.get("first_name", "مستخدم")
                    uname = f"@{udata['username']}" if udata.get("username") else "بدون يوزر"
                    is_active = (now - udata.get("last_active", 0)) < 15 * 60
                    status_dot = "🟢" if is_active else "⚪"
                    lines.append(f"{status_dot} *{name}* ({uname}) | ID: `{uid}`\n   • استعلامات: {udata.get('query_count',0)} | آخر بحث: `{udata.get('last_query','-')}`")
                tg_send_message(chat_id, "\n".join(lines))
            elif data == "admin_logs":
                logs = get_recent_logs(15)
                lines = ["📜 *آخر عمليات البحث المنفذة في البوت:*\n"]
                for l in logs:
                    lines.append(f"• `[{l.get('time_str','-')}]` *{l.get('user_name','-')}* (ID: `{l.get('user_id')}`):\n   بحث عن: `{l.get('query','-')}` ⬅ نتائج: *{l.get('matches',0)}* ({l.get('elapsed_ms',0)}ms)")
                tg_send_message(chat_id, "\n".join(lines) if len(lines) > 1 else "لا توجد سجلات بحث مسجلة بعد.")
            elif data == "admin_prompt_broadcast":
                tg_send_message(chat_id, "📢 *لبث رسالة لجميع مستخدمي البوت أرسل:*\n`/broadcast <نص رسالتك هنا>`\n\nمثال:\n`/broadcast تم تحديث قاعدة البيانات وإضافة 100 ألف سجل جديد!`")
            elif data == "admin_prompt_msg":
                tg_send_message(chat_id, "💬 *لمراسلة مستخدم معين أرسل:*\n`/msg <chat_id> <نص رسالتك>`\n\nمثال:\n`/msg 123456789 أهلاً بك، تفضل بالسؤال عن أي معلومة.`")
            elif data == "admin_do_backup":
                b_name = f"backup_{int(time.time())}.zip"
                with zipfile.ZipFile(b_name, "w", zipfile.ZIP_DEFLATED) as z:
                    for f in (USERS_FILE, LOGS_FILE, ADMIN_FILE, WATCHLIST_FILE, CUSTOM_CONFIG_FILE):
                        if os.path.exists(f): z.write(f)
                with open(b_name, "rb") as zf:
                    tg_send_document(chat_id, b_name, zf.read(), "💾 نسخة احتياطية كاملة لبيانات ومستخدمي البوت")
                try: os.remove(b_name)
                except Exception: pass
            elif data == "admin_do_digest":
                digest_text = generate_daily_digest()
                tg_send_message(chat_id, digest_text)
            elif data == "admin_web_url":
                web_url = f"https://datav2-bc3b.onrender.com"
                tg_send_message(chat_id, f"🌐 *رابط لوحة التحكم المباشرة على الويب:*\n{web_url}\n\nأو عبر المنفذ المحلي: `http://localhost:{PORT}/`")
            return

        # فحص منصات التواصل الاجتماعي
        if data.startswith("social_links_"):
            idx = int(data.replace("social_links_", ""))
            if sess["last_results"] and idx < len(sess["last_results"]):
                rec = sess["last_results"][idx]
                s_links = generate_social_links(rec)
                nm = rec.get("n") or (rec.get("_names")[0] if rec.get("_names") else "الهدف")
                if s_links:
                    txt = f"🌐 *روابط فحص الحسابات والمنصات لـ ({nm}):*\n" + "\n───────────────────\n".join(s_links)
                    tg_send_message(chat_id, txt)
                else:
                    tg_send_message(chat_id, f"⚠️ لا توجد أرقام هواتف أو معرفات كافية لتوليد روابط مباشرة لـ {nm}.")
            return

        # حفظ في المفضلة
        if data.startswith("bookmark_add_"):
            idx = int(data.replace("bookmark_add_", ""))
            if sess["last_results"] and idx < len(sess["last_results"]):
                rec = sess["last_results"][idx]
                nm = rec.get("n") or (rec.get("_names")[0] if rec.get("_names") else "سجل")
                if save_bookmark(chat_id, rec):
                    tg_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": f"⭐ تم حفظ ({nm}) في مفضلتك!"})
                else:
                    tg_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "ℹ️ السجل موجود بالفعل في مفضلتك."})
            return

        # شجرة العلاقات
        if data.startswith("quick_tree_"):
            target_q = urllib.parse.unquote(data.replace("quick_tree_", ""))
            tg_send_message(chat_id, f"🕸️ *جاري بناء شجرة العلاقات لـ ({target_q})...*")
            tree, err_t = correlate_family_tree(target_q)
            if err_t:
                tg_send_message(chat_id, err_t)
            else:
                lines = [f"🕸️ *شجرة العلاقات والتوزيع العائلي لـ ({target_q}):*", "━━━━━━━━━━━━━━━━━━━━━━━━━━"]
                for city, members in tree.items():
                    lines.append(f"🏛️ *منطقة {city} ({len(members)} أفراد):*")
                    lines.extend(members[:5])
                    lines.append("──────────────────────────")
                tg_send_message(chat_id, "\n".join(lines))
            return

        # إضبارة تحقيق
        if data.startswith("quick_dossier_"):
            target_q = urllib.parse.unquote(data.replace("quick_dossier_", ""))
            tg_send_message(chat_id, f"📑 *جاري استخراج إضبارة التحقيق لـ ({target_q})...*")
            dossier = generate_investigation_dossier(target_q)
            tg_send_message(chat_id, dossier)
            return

        # تفرع بالإيميل
        if data.startswith("pivot_email_"):
            p_email = urllib.parse.unquote(data.replace("pivot_email_", ""))
            tg_send_message(chat_id, f"🔍 *جاري التفرع التلقائي والبحث بالإيميل:* `{p_email}`")
            sess["last_mode"] = "all"
            handle_update({"message": {"chat": {"id": chat_id}, "from": from_user, "text": p_email}})
            return

        # تفرع بالهاتف
        if data.startswith("pivot_phone_"):
            p_phone = urllib.parse.unquote(data.replace("pivot_phone_", ""))
            tg_send_message(chat_id, f"📱 *جاري التفرع التلقائي والبحث بالهاتف:* `{p_phone}`")
            sess["last_mode"] = "all"
            handle_update({"message": {"chat": {"id": chat_id}, "from": from_user, "text": p_phone}})
            return


        return

    # 2. معالجة رفع وتحديث ملفات البيانات
    if msg and msg.get("document"):
        doc = msg["document"]
        fname = doc.get("file_name", "data.json")
        fsize = doc.get("file_size", 0)

        if from_user.get("id") != CURRENT_ADMIN_ID:
            tg_send_message(chat_id, "⚠️ رفع وتحديث ملفات قاعدة البيانات متاح فقط لمشرف البوت.")
            return

        tg_send_message(chat_id, f"⏳ *جاري استلام وتحميل ملف البيانات:*\n`{fname}` ({(fsize/(1024*1024)):.1f} MB)...")
        file_info = tg_request("getFile", {"file_id": doc["file_id"]})
        if file_info.get("ok") and file_info.get("result", {}).get("file_path"):
            dl_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info['result']['file_path']}"
            try:
                urllib.request.urlretrieve(dl_url, fname)
                global DATA_FILE
                DATA_FILE = fname
                cfg = load_custom_config()
                cfg["active_data_file"] = fname
                save_custom_config(cfg)
                tg_send_message(chat_id, f"✅ *تم بنجاح تثبيت ملف البيانات الجديد كقاعدة بيانات نشطة 24/7!*\n• الملف: `{fname}`\n• جاهز للبحث الفوري بدون استهلاك للرام.")
            except Exception as e:
                tg_send_message(chat_id, f"⚠️ حدث خطأ أثناء حفظ الملف: {e}")
        else:
            tg_send_message(chat_id, f"⚠️ تعذر تحميل الملف مباشرة: حجمه يتجاوز 20MB. للملفات الضخمة (+1.3GB)، ارفعه عبر لوحة Bot-Hosting (Files tab) أو عبر SFTP وسيتعرف عليه البوت فوراً!")
        return

    # 3. معالجة الرسائل النصية
    text = (msg.get("text") or "").strip()
    if not text:
        return

    # أمر إيقاف البحث الفوري
    if text in ("/stop", "⏹️ إيقاف البحث"):
        if chat_id in ACTIVE_SEARCH_ABORTS:
            ACTIVE_SEARCH_ABORTS[chat_id].set()
            tg_send_message(chat_id, "⏹️ تم إرسال أمر إيقاف البحث الفوري.")
        else:
            tg_send_message(chat_id, "ℹ️ لا توجد عملية بحث جارية لإيقافها.")
        return

    # فحص صلاحيات المشرف
    is_admin = (from_user.get("id") == CURRENT_ADMIN_ID)

    if text in ("/admin", "👮‍♂️ لوحة المشرف"):
        if is_admin:
            txt, kb = get_admin_dashboard_reply()
            tg_send_message(chat_id, txt, kb)
        else:
            tg_send_message(chat_id, "⛔ لوحة التحكم مخصصة لمالك البوت فقط.")
        return

    if text.startswith("/broadcast ") or text.startswith("/all "):
        if not is_admin: return
        b_msg = text.split(" ", 1)[1].strip()
        users = load_all_users()
        sent_count = 0
        tg_send_message(chat_id, f"📢 *جاري بدء الإرسال لـ {len(users)} مستخدم...*")
        for uid_str, udata in users.items():
            if not udata.get("is_blocked"):
                res = tg_send_message(int(uid_str), f"📢 *إشعار من إدارة البوت:*\n\n{b_msg}")
                if res.get("ok"): sent_count += 1
                time.sleep(0.04)
        tg_send_message(chat_id, f"✅ *اكتمل الإرسال بنجاح!* تم إيصال الرسالة إلى *{sent_count}* مستخدم.")
        return

    if text.startswith("/msg "):
        if not is_admin: return
        parts = text.split(" ", 2)
        if len(parts) < 3:
            tg_send_message(chat_id, "⚠️ الصيغة: `/msg <chat_id> <الرسالة>`")
            return
        target_uid = int(parts[1])
        target_txt = parts[2]
        res = tg_send_message(target_uid, f"📩 *رسالة خاصة من إدارة البوت:*\n\n{target_txt}")
        if res.get("ok"): tg_send_message(chat_id, f"✅ تم إرسال الرسالة بنجاح للمستخدم `{target_uid}`.")
        else: tg_send_message(chat_id, f"⚠️ تعذر الإرسال: {res.get('description')}")
        return

    if text.startswith("/setwelcome "):
        if not is_admin: return
        new_welcome = text.split(" ", 1)[1].strip()
        cfg = load_custom_config()
        cfg["welcome_text"] = new_welcome
        save_custom_config(cfg)
        tg_send_message(chat_id, "✅ تم تحديث رسالة الترحيب بنجاح!")
        return

    if text in ("/backup", "💾 نسخة احتياطية"):
        if not is_admin: return
        b_name = f"backup_{int(time.time())}.zip"
        with zipfile.ZipFile(b_name, "w", zipfile.ZIP_DEFLATED) as z:
            for f in (USERS_FILE, LOGS_FILE, ADMIN_FILE, WATCHLIST_FILE, CUSTOM_CONFIG_FILE):
                if os.path.exists(f): z.write(f)
        with open(b_name, "rb") as zf:
            tg_send_document(chat_id, b_name, zf.read(), "💾 نسخة احتياطية كاملة لبيانات ومستخدمي البوت")
        try: os.remove(b_name)
        except Exception: pass
        return

    if text.startswith("/ban "):
        if not is_admin: return
        target_uid = int(text.split(" ")[1])
        if block_user(target_uid): tg_send_message(chat_id, f"🚫 تم حظر المستخدم `{target_uid}`.")
        return

    if text.startswith("/unban "):
        if not is_admin: return
        target_uid = int(text.split(" ")[1])
        if unblock_user(target_uid): tg_send_message(chat_id, f"✅ تم فك حظر المستخدم `{target_uid}`.")
        return

    # الترحيب /start
    if text in ("/start", "/help", "ℹ️ طريقة الاستخدام"):
        cfg = load_custom_config()
        custom_welcome = cfg.get("welcome_text", "")
        welcome = [
            custom_welcome if custom_welcome else "🤖 *أهلاً بك في بوت وسيرفر الاستعلامات الشامل 24/7*",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"⚡ خادم سحابي مستقل يعمل على مدار الساعة.",
            f"📂 قاعدة البيانات النشطة: `{resolve_data_file()}`",
            f"🆔 معرف محادثتك: `{chat_id}`",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "👇 *اختر العملية المطلوبة من الأزرار بالأسفل، أو أرسل أي اسم أو رقم مباشرة:*"
        ]
        tg_send_message(chat_id, "\n".join(welcome), MAIN_KEYBOARD)
        return

    # فحص قائمة المراقبة وإرسال تنبيه فوري
    for w in load_watchlist():
        if normalize_arabic(w) in normalize_arabic(text):
            tg_send_message(chat_id, f"🚨 *تنبيه أمني فوري:* الهدف `{w}` مدرج في قائمة المراقبة النشطة!")
            if CURRENT_ADMIN_ID > 0 and CURRENT_ADMIN_ID != chat_id:
                u_tag = f"@{from_user.get('username')}" if from_user.get("username") else str(chat_id)
                tg_send_message(CURRENT_ADMIN_ID, f"🚨 *تنبيه مراقبة:* المستخدم {u_tag} استدعى الهدف المراقب: `{w}`!")
            break

    # أوضاع البحث والأدوات المتقدمة
    if text in ("📋 بحث متعدد (Bulk)", "/bulk"):
        tg_send_message(chat_id, "📋 *أداة البحث المتعدد دفعة واحدة (Bulk Search):*\n\nأرسل قائمة الأسماء أو الأرقام مفصولة بفاصلة أو سطر جديد، مثال:\n`/bulk أحمد علي, محمود خليل, 0599123456`")
        return

    if text.startswith("/bulk "):
        bulk_raw = text.replace("/bulk ", "").strip()
        items = [i.strip() for i in re.split(r"[,،\n]+", bulk_raw) if i.strip()]
        if not items: return
        tg_send_message(chat_id, f"⏳ *جاري البحث المتعدد عن ({len(items)}) أهداف في قاعدة البيانات...*")
        report = [f"📋 *تقرير نتائج البحث المتعدد ({len(items)} أهداف):*\n━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        total_matches = 0
        for it in items[:15]:
            m_res, _ = search_stream_1_3gb(it, "all", max_results=5)
            total_matches += len(m_res)
            report.append(f"🎯 *الهدف:* `{it}` ⬅ عُثر على *{len(m_res)}* سجلات:")
            for r in m_res[:3]:
                nm = safe_first(r.get("n") or r.get("_names"), "-")
                ph = safe_first(r.get("t") or r.get("_phones"), "-")
                em = safe_first(r.get("e") or r.get("_emails"), "-")
                report.append(f"  • {nm} | {ph} | {em}")
            report.append("──────────────────────────")
        tg_send_message(chat_id, "\n".join(report))
        return

    # مقارنة هدفين
    if text in ("⚖️ مقارنة هدفين", "/compare"):
        tg_send_message(chat_id, "⚖️ *أداة المقارنة والتقاطع بين هدفين:*\n\nأرسل الهدفين بالشكل التالي:\n`/compare target1 vs target2`\n\nمثال:\n`/compare محمود vs أحمد`")
        return

    if text.startswith("/compare "):
        raw_comp = text.replace("/compare ", "").strip()
        parts = [p.strip() for p in re.split(r"\s+vs\s+|\s+ضد\s+|,|،", raw_comp, flags=re.I) if p.strip()]
        if len(parts) < 2:
            tg_send_message(chat_id, "⚠️ يرجى كتابة الهدفين مفصولين بـ `vs`، مثال: `/compare أحمد vs علي`")
            return
        t1, t2 = parts[0], parts[1]
        tg_send_message(chat_id, f"⏳ *جاري فحص التقاطعات والروابط المشتركة بين ({t1}) و ({t2})...*")
        r1, _ = search_stream_1_3gb(t1, "all", 20)
        r2, _ = search_stream_1_3gb(t2, "all", 20)

        pass1 = set(sum([r.get("_passwords", []) for r in r1], []))
        pass2 = set(sum([r.get("_passwords", []) for r in r2], []))
        cities1 = set(sum([r.get("_cities", []) for r in r1], []))
        cities2 = set(sum([r.get("_cities", []) for r in r2], []))

        common_pass = pass1.intersection(pass2)
        common_cities = cities1.intersection(cities2)

        comp_lines = [
            f"⚖️ *نتائج المقارنة والتقاطع بين:* `{t1}` و `{t2}`",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"• سجلات ({t1}): `{len(r1)}` سجل",
            f"• سجلات ({t2}): `{len(r2)}` سجل",
            f"• كلمات مرور مشتركة: {', '.join([f'`{p}`' for p in common_pass]) if common_pass else 'لا يوجد'}",
            f"• مدن ومناطق مشتركة: {', '.join(common_cities) if common_cities else 'لا يوجد'}",
            f"• تقييم الارتباط: {'🚨 ارتباط وثيق وخطير' if common_pass else ('🟡 احتمال تشابه جغرافي' if common_cities else '🟢 لا توجد تقاطعات مباشرة')}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        tg_send_message(chat_id, "\n".join(comp_lines))
        return

    # كاشف مشغل الخط
    if text == "📶 فحص مشغل الخط":
        tg_send_message(chat_id, "📶 أرسل رقم الهاتف (مثال: `0599123456` أو `+970568000000`) لكشف الشركة المشغلة ونوع الخط فوراً.")
        return

    # التوزيع الجغرافي للمدن
    if text in ("/geo", "🏛️ فلتر المدن"):
        cities_msg = [
            "🏛️ *التوزيع والفلترة الجغرافية للمحافظات والمدن الفلسطينية والعربية:*",
            "• أرسل `نابلس` أو `09` لفلترة محافظة نابلس",
            "• أرسل `القدس` أو `02` لفلترة القدس الشريف",
            "• أرسل `رام الله` لفلترة رام الله والبيرة",
            "• أرسل `الخليل` لفلترة محافظة الخليل",
            "• أرسل `جنين` أو `04` لفلترة محافظة جنين",
            "• أرسل `طولكرم` لفلترة محافظة طولكرم",
            "• أرسل `غزة` أو `08` لفلترة قطاع غزة وخان يونس",
            "• أرسل `عمان` أو `+962` لفلترة الأردن"
        ]
        tg_send_message(chat_id, "\n".join(cities_msg))
        return

    # أوضاع البحث العادية
        # أمر فحص ملف الداتا الفعلي في السيرفر
    if text in ("/checkdb", "/debug", "🔍 فحص ملف الداتا"):
        data_f = resolve_data_file()
        if not os.path.exists(data_f):
            tg_send_message(chat_id, f"⚠️ الملف `{data_f}` غير موجود بالسيرفر!")
            return

        sz = os.path.getsize(data_f)
        sz_mb = sz / (1024 * 1024)
        sample_lines = []
        try:
            with open(data_f, "r", encoding="utf-8", errors="ignore") as tf:
                for _ in range(6):
                    l = tf.readline()
                    if not l: break
                    clean_l = l.replace("\x00", "").strip()
                    if clean_l: sample_lines.append(clean_l[:140])
        except Exception as e:
            sample_lines.append(f"خطأ بالقراءة: {e}")

        s_text = "\n".join([f"• `{s}`" for s in sample_lines]) if sample_lines else "الملف فارغ أو غير نصي"
        rep = [
            "🔍 *تقرير فحص ملف قاعدة البيانات بالسيرفر:*",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📂 اسم الملف النشط: `{data_f}`",
            f"📊 الحجم الفعلي: *{sz_mb:.1f} MB*",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "👀 *عينة من أول أسطر في الملف:*",
            s_text,
            "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        tg_send_message(chat_id, "\n".join(rep))
        return

    # فحص الملفات المتاحة بالسيرفر
    if text in ("/dbs", "📂 قواعد البيانات"):
        db_files = list_available_databases()
        if not db_files:
            tg_send_message(chat_id, "📂 لا توجد ملفات بيانات حالياً بالسيرفر. جاري تنزيل ملف الداتا في الخلفية...")
        else:
            lines = ["📂 *ملفات البيانات المتاحة بالسيرفر:*", "━━━━━━━━━━━━━━━━━━━━━━━━━━"]
            for f, sz, sz_fmt in db_files:
                active_mark = " (النشط حالياً ✅)" if f == resolve_data_file() else ""
                lines.append(f"• `{f}` - الحجم: {sz_fmt}{active_mark}")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("لتفعيل ملف معين أرسل: `/setdb <اسم الملف>`")
            tg_send_message(chat_id, "\n".join(lines))
        return

    if text.startswith("/setdb "):
        new_db = text.replace("/setdb ", "").strip()
        if not os.path.exists(new_db):
            tg_send_message(chat_id, f"⚠️ الملف `{new_db}` غير موجود حالياً بالسيرفر.")
            return
        cfg = load_custom_config()
        cfg["active_data_file"] = new_db
        save_custom_config(cfg)
        tg_send_message(chat_id, f"✅ تم تفعيل ملف `{new_db}` كقاعدة بيانات نشطة للبحث الفوري!")
        return

    # أمر تحميل ملف الداتا أو إرسال رابط مباشر تلقائياً بدون قيود
    if text.startswith("/downloaddata ") or text.startswith("https://pixeldrain.com/") or "pixeldrain.com/u/" in text or "pixeldrain.com/api/file/" in text:
        dl_url = text.replace("/downloaddata ", "").strip()
        if "pixeldrain.com/u/" in dl_url:
            dl_url = dl_url.replace("pixeldrain.com/u/", "pixeldrain.com/api/file/") + "?download"
        elif "pixeldrain.com/api/file/" in dl_url and not dl_url.endswith("?download"):
            dl_url += "?download"

        tg_send_message(chat_id, f"⏳ *جاري سحب ملف البيانات من Pixeldrain وتثبيته في السيرفر (1.3GB)...*\n🔗 الرابط: `{dl_url}`\n\nستصلك رسالة تأكيد فور اكتمال التنزيل في السيرفر.")
        def _bg_dl():
            try:
                ok, msg = download_file_universal(dl_url, "data.json")
                if ok and os.path.exists("data.json"):
                    sz_mb = os.path.getsize("data.json") / (1024 * 1024)
                    cfg = load_custom_config()
                    cfg["active_data_file"] = "data.json"
                    save_custom_config(cfg)
                    tg_send_message(chat_id, f"✅ *تم اكتمال تنزيل ملف البيانات وتفعيله كقاعدة بيانات نشطة بنجاح!*\n📂 الحجم: *{sz_mb:.1f} MB*\nالبوت أصبح جاهزاً للبحث الفوري 24/7.")
                else:
                    tg_send_message(chat_id, f"⚠️ *فشل التنزيل:* {msg}")
            except Exception as e:
                tg_send_message(chat_id, f"⚠️ *خطأ بالسيرفر:* `{e}`")
        threading.Thread(target=_bg_dl, daemon=True).start()
        return

        # المفضلة وسجل البحث
    if text in ("/bookmarks", "⭐ مفضلتي", "🔖 السجلات المحفوظة"):
        bms = load_all_bookmarks().get(str(chat_id), [])
        if not bms:
            tg_send_message(chat_id, "⭐ مفضلتك فارغة حالياً. يمكنك حفظ أي سجل يظهر في نتائج البحث بالضغط على زر '⭐ حفظ في المفضلة'.")
        else:
            lines = [f"⭐ *سجلاتك المفضلة المحفوظة ({len(bms)}):*\n"]
            for i, b in enumerate(bms, 1):
                nm = b.get("n") or (b.get("_names")[0] if b.get("_names") else "-")
                ph = b.get("t") or (b.get("_phones")[0] if b.get("_phones") else "-")
                em = b.get("e") or (b.get("_emails")[0] if b.get("_emails") else "-")
                lines.append(f"[{i}] 👤 *{nm}*\n   📱 `{ph}` | 📧 `{em}`\n")
            tg_send_message(chat_id, "\n".join(lines))
        return

    if text in ("/history", "🕒 سجل بحثي"):
        logs = [l for l in get_recent_logs(50) if l.get("user_id") == chat_id]
        if not logs:
            tg_send_message(chat_id, "🕒 لا توجد عمليات بحث سابقة مسجلة لك بعد.")
        else:
            lines = [f"🕒 *آخر عمليات بحث قمت بها شخصياً ({len(logs[:10])}):*\n"]
            for l in logs[:10]:
                lines.append(f"• `{l.get('time_str','-')}`: *{l.get('query','-')}* ⬅ *{l.get('matches',0)}* نتيجة")
            tg_send_message(chat_id, "\n".join(lines))
        return
    # أزرار لوحة المفاتيح الأصلية مع حماية كاملة من البحث في نص الزر
    if text in ("🔍 بحث شامل سريع", "🔍 بحث شامل", "بحث شامل", "بحث شامل سريع"):
        sess["last_mode"] = "all"
        tg_send_message(chat_id, "🔍 *نمط البحث الشامل مفعّل!* أرسل أي اسم أو يوزر أو إيميل أو رقم للبحث الفوري:", reply_markup=MAIN_KEYBOARD)
        return
    if text in ("👤 بحث بالاسم (المتشابه)", "بحث بالاسم"):
        sess["last_mode"] = "name"
        tg_send_message(chat_id, "👤 *نمط البحث بالاسم مفعّل!* أرسل اسم الشخص (عربي أو إنجليزي مثل: محمود أو Mahmoud):", reply_markup=MAIN_KEYBOARD)
        return
    if text in ("🆔 بحث باليوزر (@Username)", "بحث باليوزر"):
        sess["last_mode"] = "user"
        tg_send_message(chat_id, "🆔 *نمط البحث باليوزر مفعّل!* أرسل اليوزر (@username):", reply_markup=MAIN_KEYBOARD)
        return
    if text in ("📧 بحث بالإيميل", "بحث بالإيميل", "بحث بالايميل"):
        sess["last_mode"] = "email"
        tg_send_message(chat_id, "📧 *نمط البحث بالإيميل مفعّل!* أرسل عنوان البريد الإلكتروني:", reply_markup=MAIN_KEYBOARD)
        return
    if text in ("📱 بحث بالهاتف والدولة", "بحث بالهاتف"):
        sess["last_mode"] = "phone"
        tg_send_message(chat_id, "📱 *نمط البحث بالهاتف ومفتاح الدولة مفعّل!* أرسل الرقم أو المقدمة (مثل 059 أو +970):", reply_markup=MAIN_KEYBOARD)
        return
    if text in ("🔑 كشف الباسوردات (Combos)", "كشف الباسوردات"):
        sess["last_mode"] = "combos"
        tg_send_message(chat_id, "🔑 *نمط كشف أزواج الباسوردات مفعّل!* أرسل الإيميل أو اليوزر لاستخراج Email:Password المباشرة:", reply_markup=MAIN_KEYBOARD)
        return
    if text in ("📊 إحصائيات البوت", "إحصائيات البوت", "/stats", "الاحصائيات"):
        cnt_users = len(load_all_users())
        cnt_logs = len(get_recent_logs(100))
        target_f = resolve_data_file()
        f_sz = os.path.getsize(target_f) / (1024 * 1024) if os.path.exists(target_f) else 0
        stats_msg = [
            "📊 *إحصائيات نظام البحث:*",
            f"• حجم قاعدة البيانات: *{f_sz:.1f} MB*",
            f"• إجمالي المستخدمين: *{cnt_users}* مستخدم",
            f"• عمليات البحث المنفذة: *{cnt_logs}* عملية",
            "• الحالة: 🟢 متصل ونشط 24/7"
        ]
        tg_send_message(chat_id, "\n".join(stats_msg), reply_markup=MAIN_KEYBOARD)
        return
    if text in ("👮‍♂️ لوحة المشرف", "لوحة المشرف", "/admin"):
        if is_admin_user(from_user.get("id")):
            dash_txt, dash_kb = get_admin_dashboard_reply()
            tg_send_message(chat_id, dash_txt, reply_markup=dash_kb)
        else:
            tg_send_message(chat_id, "⛔ لوحة الإدارة مخصصة للأدمن فقط.")
        return

    # تنفيذ البحث الفعلي
    query = text
    search_mode = sess.get("last_mode", "all")
    if query.startswith("@"): search_mode = "user"
    elif "@" in query and "." in query: search_mode = "email"

    abort_event = threading.Event()
    ACTIVE_SEARCH_ABORTS[chat_id] = abort_event

    stop_kb = {"inline_keyboard": [[{"text": "⏹️ إيقاف البحث فوراً (Stop Search)", "callback_data": "abort_search"}]]}
    stop_kb = {"inline_keyboard": [[{"text": "⏹️ إيقاف البحث فوراً (Stop Search)", "callback_data": "abort_search"}]]}
    prog_res = tg_send_message(chat_id, f"⏳ *جاري فحص قاعدة البيانات...*\n{make_progress_bar(5, 10)} *5%*\n📊 جاري بدء المسح السريع...\n🔍 الهدف: `{query}`", stop_kb)
    prog_id = prog_res.get("result", {}).get("message_id")

    def on_progress(pct, scanned_mb, total_mb, matches_cnt):
        if abort_event and abort_event.is_set(): return
        bar = make_progress_bar(pct, 10)
        p_txt = f"⏳ *جاري فحص قاعدة البيانات (1.3GB)...*\n{bar} *{pct}%*\n📊 تم فحص: *{scanned_mb:.0f} MB* من *{total_mb:.0f} MB*\n🎯 عُثر على: *{matches_cnt}* مطابقات حتى الآن\n🔍 الهدف: `{query}`"
        if prog_id:
            tg_edit_message(chat_id, prog_id, p_txt, stop_kb)

    t_start = time.time()
    results, err = search_stream_1_3gb(query, search_mode, max_results=2000, abort_event=abort_event, progress_callback=on_progress)
    elapsed_ms = (time.time() - t_start) * 1000

    u_name = f"@{from_user.get('username')}" if from_user.get("username") else from_user.get("first_name", str(chat_id))
    append_search_log(chat_id, u_name, query, search_mode, len(results), elapsed_ms)

    was_aborted = abort_event.is_set()
    if chat_id in ACTIVE_SEARCH_ABORTS:
        del ACTIVE_SEARCH_ABORTS[chat_id]

    if err:
        tg_send_message(chat_id, err, MAIN_KEYBOARD)
        return

    if not results:
        target_f = resolve_data_file()
        total_mb = (os.path.getsize(target_f) / (1024 * 1024)) if os.path.exists(target_f) else 1298
        no_res = f"⏹️ *تم إيقاف البحث بواسطة المستخدم* لـ: `{query}`." if was_aborted else f"🔍 لم يتم العثور على أي نتائج مطابقة لـ: `{query}`\n{make_progress_bar(100, 10)} 100% مكتمل (تم فحص {total_mb:.0f} MB كاملة في {elapsed_ms/1000:.1f}s)\n\n💡 جرب البحث بجزء من الاسم أو برقم الهاتف."
        if prog_id:
            tg_edit_message(chat_id, prog_id, no_res)
        else:
            tg_send_message(chat_id, no_res)
        return

    sess["last_results"] = results
    sess["last_query"] = query
    sess["current_page"] = 1

    first_page_txt, first_page_kb = format_results_page(query, results, 1, is_aborted=was_aborted)
    if prog_id:
        tg_edit_message(chat_id, prog_id, first_page_txt, first_page_kb)
    else:
        tg_send_message(chat_id, first_page_txt, first_page_kb)

# ==========================================
# 🌐 خادم الويب ولوحة تحكم المشرف (Port 8080)
# ==========================================
class WebAdminServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/stats":
            self.send_json(self.get_stats_data())
            return
        elif path == "/api/users":
            self.send_json(list(load_all_users().values()))
            return
        elif path == "/api/logs":
            self.send_json(get_recent_logs(50))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        stats = self.get_stats_data()
        html = self.render_admin_html(stats)
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length)

        try: req = json.loads(post_data.decode("utf-8"))
        except Exception: req = {}

        if path == "/api/broadcast":
            msg = req.get("message", "").strip()
            if not msg:
                self.send_json({"ok": False, "error": "الرسالة فارغة"})
                return
            users = load_all_users()
            count = 0
            for uid, udata in users.items():
                if not udata.get("is_blocked"):
                    tg_send_message(int(uid), f"📢 *إشعار من إدارة البوت:*\n\n{msg}")
                    count += 1
                    time.sleep(0.04)
            self.send_json({"ok": True, "sent_count": count})
            return

        elif path == "/api/message":
            chat_id = req.get("chat_id")
            msg = req.get("message", "").strip()
            if not chat_id or not msg:
                self.send_json({"ok": False, "error": "بيانات غير مكتملة"})
                return
            res = tg_send_message(int(chat_id), f"📩 *رسالة خاصة من إدارة البوت:*\n\n{msg}")
            self.send_json(res)
            return

        elif path == "/api/ban":
            user_id = req.get("user_id")
            action = req.get("action", "ban")
            if action == "ban": block_user(int(user_id))
            else: unblock_user(int(user_id))
            self.send_json({"ok": True})
            return

        self.send_json({"ok": False, "error": "Unknown Endpoint"})

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def get_stats_data(self):
        users = load_all_users()
        now = time.time()
        active_15m = sum(1 for u in users.values() if (now - u.get("last_active", 0)) < 15 * 60)
        total_queries = sum(u.get("query_count", 0) for u in users.values())
        target_file = resolve_data_file()
        fsize = os.path.getsize(target_file) if os.path.exists(target_file) else 0

        return {
            "total_users": len(users),
            "active_users": active_15m,
            "total_queries": total_queries,
            "data_file": target_file,
            "data_file_size": fsize,
            "data_file_size_fmt": f"{(fsize/(1024*1024)):.1f} MB" if fsize < 1024**3 else f"{(fsize/(1024**3)):.2f} GB",
            "uptime_seconds": int(time.time() - START_TIME),
            "admin_id": CURRENT_ADMIN_ID
        }

    def render_admin_html(self, stats):
        html = """<!DOCTYPE html>
<html lang="ar" dir="rtl" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>لوحة تحكم خادم بوت تيليجرام 24/7</title>
  <script src="https://cdn.tailwindcss.com/3.4.17"></script>
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
  <style>body { font-family: 'Cairo', sans-serif; background: #030712; color: #f3f4f6; }</style>
</head>
<body class="min-h-screen p-4 sm:p-6 space-y-6 max-w-7xl mx-auto">
  <header class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
    <div class="flex items-center gap-3">
      <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-2xl shadow-lg shadow-sky-500/20">🤖</div>
      <div>
        <h1 class="text-xl font-black text-white">لوحة تحكم وإدارة بوت تيليجرام السحابي 24/7</h1>
        <p class="text-xs text-slate-400">سيرفر معالجة متدفق لقواعد البيانات الضخمة (+1.3GB) بدون استهلاك الرام</p>
      </div>
    </div>
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-3 py-1.5 rounded-xl text-xs font-bold">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> البوت متصل وشغال 24/7
      </span>
      <a href="https://t.me/search_palestine_bot" target="_blank" class="bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold px-4 py-1.5 rounded-xl shadow transition">✈️ فتح البوت</a>
    </div>
  </header>

  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4">
      <span class="text-xs text-slate-400 font-bold block">👥 إجمالي المستخدمين:</span>
      <span class="text-2xl font-black text-white">__TOTAL_USERS__</span>
      <span class="text-[11px] text-slate-500 block">مستخدم مسجل في البوت</span>
    </div>
    <div class="bg-slate-900 border border-emerald-500/30 rounded-2xl p-4">
      <span class="text-xs text-emerald-400 font-bold block">🟢 النشطون في آخر 15 دقيقة:</span>
      <span class="text-2xl font-black text-emerald-400">__ACTIVE_USERS__</span>
      <span class="text-[11px] text-slate-500 block">يتفاعلون في هذه اللحظة</span>
    </div>
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4">
      <span class="text-xs text-slate-400 font-bold block">⚡ عمليات البحث المنجزة:</span>
      <span class="text-2xl font-black text-sky-400">__TOTAL_QUERIES__</span>
      <span class="text-[11px] text-slate-500 block">استعلام في قاعدة البيانات</span>
    </div>
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4">
      <span class="text-xs text-slate-400 font-bold block">📂 ملف البيانات المربوط:</span>
      <span class="text-sm font-black text-amber-300 truncate block">__DATA_FILE__</span>
      <span class="text-[11px] text-emerald-400 font-mono block">الحجم: __DATA_FILE_SIZE_FMT__ (Zero-RAM)</span>
    </div>
  </div>

  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
      <h3 class="text-sm font-bold text-white flex items-center gap-2"><span>📢</span> إرسال رسالة جماعية (Broadcast):</h3>
      <textarea id="broadcastText" rows="3" placeholder="اكتب إعلانك أو رسالتك للجميع هنا..." class="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-sky-500"></textarea>
      <button onclick="sendBroadcast()" class="bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-xs px-5 py-2.5 rounded-xl shadow transition">📢 إرسال للجميع الآن</button>
    </div>
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
      <h3 class="text-sm font-bold text-white flex items-center gap-2"><span>💬</span> مراسلة مستخدم معين:</h3>
      <div class="flex gap-2">
        <input id="directChatId" type="text" placeholder="Chat ID" class="w-1/3 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white font-mono outline-none">
        <input id="directMessageText" type="text" placeholder="نص الرسالة الخاصة..." class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-white outline-none">
      </div>
      <button onclick="sendDirectMsg()" class="bg-sky-600 hover:bg-sky-500 text-white font-extrabold text-xs px-5 py-2.5 rounded-xl shadow transition">💬 إرسال للمستخدم</button>
    </div>
  </div>

  <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
    <div class="flex items-center justify-between border-b border-slate-800 pb-3">
      <h3 class="text-sm font-bold text-white flex items-center gap-2"><span>👥</span> المستخدمون الذين استخدموا البوت ومن نشط حالياً:</h3>
      <button onclick="location.reload()" class="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1 rounded-lg">تحديث اللائحة 🔄</button>
    </div>
    <div class="overflow-x-auto max-h-96">
      <table class="w-full text-right text-xs">
        <thead class="text-slate-400 border-b border-slate-800 font-bold sticky top-0 bg-slate-900">
          <tr>
            <th class="p-2.5">المستخدم</th>
            <th class="p-2.5">Chat ID</th>
            <th class="p-2.5">آخر نشاط</th>
            <th class="p-2.5">الاستعلامات</th>
            <th class="p-2.5">آخر كلمة بحث</th>
            <th class="p-2.5 text-center">الإجراء</th>
          </tr>
        </thead>
        <tbody id="usersTbody" class="divide-y divide-slate-800/60 font-mono"></tbody>
      </table>
    </div>
  </div>

  <script>
    async function loadUsers() {
      const res = await fetch('/api/users');
      const users = await res.json();
      const tbody = document.getElementById('usersTbody');
      const now = Date.now() / 1000;
      users.sort((a,b) => (b.last_active||0) - (a.last_active||0));

      tbody.innerHTML = users.map(u => {
        const isOnline = (now - (u.last_active||0)) < 15 * 60;
        const name = (u.first_name || '') + ' ' + (u.last_name || '');
        const uname = u.username ? '@' + u.username : 'بدون يوزر';
        const dateStr = new Date(u.last_active * 1000).toLocaleTimeString('ar-EG');
        return `
          <tr class="hover:bg-slate-800/40">
            <td class="p-2.5 font-bold font-sans flex items-center gap-1.5">
              <span class="${isOnline ? 'text-emerald-400 animate-pulse' : 'text-slate-600'}">●</span>
              <span>${name}</span> <span class="text-sky-400 text-[11px]">(${uname})</span>
            </td>
            <td class="p-2.5 text-slate-400">${u.id}</td>
            <td class="p-2.5 ${isOnline ? 'text-emerald-400 font-bold' : 'text-slate-400'}">${dateStr}</td>
            <td class="p-2.5 text-amber-300 font-bold">${u.query_count || 0}</td>
            <td class="p-2.5 font-sans truncate max-w-xs text-slate-300">${u.last_query || '-'}</td>
            <td class="p-2.5 text-center flex items-center justify-center gap-1">
              <button onclick="quickMsg('${u.id}')" class="bg-sky-600 hover:bg-sky-500 text-white px-2 py-1 rounded text-[10px]">مراسلة</button>
              <button onclick="toggleBan('${u.id}', ${!u.is_blocked})" class="${u.is_blocked ? 'bg-emerald-600' : 'bg-rose-600'} text-white px-2 py-1 rounded text-[10px]">
                ${u.is_blocked ? 'فك الحظر' : 'حظر'}
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    function quickMsg(chatId) {
      document.getElementById('directChatId').value = chatId;
      document.getElementById('directMessageText').focus();
    }

    async function sendBroadcast() {
      const text = document.getElementById('broadcastText').value.trim();
      if (!text) return alert('اكتب نص الرسالة أولاً');
      if (!confirm('هل أنت متأكد من إرسال هذه الرسالة لجميع المستخدمين؟')) return;
      const res = await fetch('/api/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      const data = await res.json();
      if (data.ok) {
        alert('تم إرسال الرسالة لـ ' + data.sent_count + ' مستخدم بنجاح!');
        document.getElementById('broadcastText').value = '';
      }
    }

    async function sendDirectMsg() {
      const chatId = document.getElementById('directChatId').value.trim();
      const text = document.getElementById('directMessageText').value.trim();
      if (!chatId || !text) return alert('املأ المعرف ونص الرسالة');
      const res = await fetch('/api/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, message: text })
      });
      const data = await res.json();
      if (data.ok) {
        alert('تم إرسال الرسالة للمستخدم بنجاح!');
        document.getElementById('directMessageText').value = '';
      } else {
        alert('فشل الإرسال: ' + (data.description || 'تأكد من المعرف'));
      }
    }

    async function toggleBan(userId, ban) {
      await fetch('/api/ban', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, action: ban ? 'ban' : 'unban' })
      });
      loadUsers();
    }

    loadUsers();
    setInterval(loadUsers, 10000);
  </script>
</body>
</html>"""
        html = html.replace('__TOTAL_USERS__', str(stats.get('total_users', 0)))
        html = html.replace('__ACTIVE_USERS__', str(stats.get('active_users', 0)))
        html = html.replace('__TOTAL_QUERIES__', str(stats.get('total_queries', 0)))
        html = html.replace('__DATA_FILE__', str(stats.get('data_file', 'لا يوجد')))
        html = html.replace('__DATA_FILE_SIZE_FMT__', str(stats.get('data_file_size_fmt', '0 B')))
        return html
    def log_message(self, format, *args):
        return

def start_http_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), WebAdminServerHandler)
        print(f"🌐 لوحة تحكم الويب المدمجة (Web Admin Dashboard) تعمل على المنفذ {PORT} بنجاح!")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ خطأ في تشغيل خادم الويب على المنفذ {PORT}: {e}")

# ==========================================
# 🚀 الحلقة الرئيسية لتشغيل البوت 24/7
# ==========================================
def main():
    threading.Thread(target=start_http_server, daemon=True).start()
    threading.Thread(target=check_and_auto_download_data, daemon=True).start()

    print("==================================================================")
    print("🚀 بدء تشغيل بوت وسيرفر تيليجرام الشامل 24/7 (Universal Data Bot)")
    print(f"• التوكن: {BOT_TOKEN[:10]}... ")
    print(f"• ملف البيانات الحالي: {resolve_data_file()}")
    print(f"• منفذ لوحة الويب: {PORT}")
    print("==================================================================")

    offset = 0
    while True:
        try:
            res = tg_request("getUpdates", {"offset": offset, "timeout": 25})
            if res.get("ok"):
                for upd in res.get("result", []):
                    offset = upd["update_id"] + 1
                    threading.Thread(target=handle_update, args=(upd,), daemon=True).start()
            else:
                time.sleep(3)
        except KeyboardInterrupt:
            print("\n🛑 تم إيقاف البوت.")
            break
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    main()
