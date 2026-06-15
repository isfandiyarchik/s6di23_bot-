"""
Улыума helper функциялар: меню, утилиты, access decorators
"""
import functools
import time
import math
import re
import logging
from threading import Lock, Thread
from datetime import datetime
from collections import deque
from telebot import types, apihelper
from database import db_cursor, now_uz, get_user_state, set_user_state, clear_user_state

logger = logging.getLogger(__name__)

# ── CONSTANTS ─────────────────────────────────────────────────
DAYS_RU = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"]
DAYS_EN_TO_RU = {
    "Monday":"Понедельник","Tuesday":"Вторник","Wednesday":"Среда",
    "Thursday":"Четверг","Friday":"Пятница","Saturday":"Суббота","Sunday":"Воскресенье"}
MONTHS_RU = {
    1:"Январь",2:"Февраль",3:"Март",4:"Апрель",5:"Май",6:"Июнь",
    7:"Июль",8:"Август",9:"Сентябрь",10:"Октябрь",11:"Ноябрь",12:"Декабрь"}
WEEKDAYS_RU = {0:"Понедельник",1:"Вторник",2:"Среда",3:"Четверг",
               4:"Пятница",5:"Суббота",6:"Воскресенье"}
ALLOWED_DELETE_TABLES = {"materials", "gallery", "user_news"}
GALLERY_UPLOAD_BTN = "📤 Жүклеңиз"

# ── ADMIN ─────────────────────────────────────────────────────
def get_admin_ids():
    import os
    env_val = os.environ.get("ADMIN_IDS", "")
    if env_val:
        try:
            return set(int(x.strip()) for x in env_val.split(",") if x.strip())
        except Exception:
            pass
    return {5880534778, 5541976681, 7716121385}

ADMIN_IDS = get_admin_ids()
def is_admin(uid): return uid in ADMIN_IDS

# ── RATE LIMIT ────────────────────────────────────────────────
_rate_limit = {}
_rate_limit_lock = Lock()
RATE_LIMIT_MAX = 50
RATE_LIMIT_WINDOW = 30

def is_rate_limited(uid):
    if is_admin(uid): return False
    now = time.time()
    with _rate_limit_lock:
        h = [t for t in _rate_limit.get(uid, []) if now - t < RATE_LIMIT_WINDOW]
        h.append(now)
        _rate_limit[uid] = h
        return len(h) > RATE_LIMIT_MAX

def clean_rate_limit():
    now = time.time()
    with _rate_limit_lock:
        for uid in list(_rate_limit):
            if all(now - t > RATE_LIMIT_WINDOW * 2 for t in _rate_limit[uid]):
                del _rate_limit[uid]

# ── BLOCKED CACHE ─────────────────────────────────────────────
_blocked_cache: set = set()
_blocked_cache_lock = Lock()
_blocked_cache_loaded = False

def _load_blocked_cache():
    global _blocked_cache_loaded
    if _blocked_cache_loaded: return
    with _blocked_cache_lock:
        if _blocked_cache_loaded: return
        try:
            with db_cursor() as (_, cursor):
                cursor.execute("SELECT user_id FROM blocked_users")
                ids = {r[0] for r in cursor.fetchall()}
            _blocked_cache.clear()
            _blocked_cache.update(ids)
            _blocked_cache_loaded = True
        except Exception as e:
            logger.warning(f"_load_blocked_cache: {e}")

def is_blocked(uid):
    _load_blocked_cache()
    with _blocked_cache_lock:
        return uid in _blocked_cache

def add_to_blocked_cache(uid):
    with _blocked_cache_lock: _blocked_cache.add(uid)

def remove_from_blocked_cache(uid):
    with _blocked_cache_lock: _blocked_cache.discard(uid)

def is_authorized(uid):
    if is_admin(uid): return True
    with db_cursor() as (_, cursor):
        cursor.execute("SELECT id FROM students WHERE id=%s", (uid,))
        return cursor.fetchone() is not None

def _update_last_active(uid):
    try:
        with db_cursor() as (conn, cursor):
            cursor.execute("UPDATE students SET last_active=%s WHERE id=%s", (now_uz(), uid))
            conn.commit()
    except Exception: pass

# ── ACCESS DECORATORS ─────────────────────────────────────────
def check_access(bot):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(message):
            uid = message.from_user.id
            if is_blocked(uid):
                try: bot.send_message(uid, "⛔ Сиз блокландыңыз. Admin-ге хабарласыңыз.")
                except: pass
                return
            if message.text != "/start" and not is_admin(uid) and not is_authorized(uid):
                try: bot.send_message(uid, "⛔ <b>Кириуге рұхсат жоқ!</b>\nАдминге хабарласыңыз.")
                except: pass
                return
            if is_rate_limited(uid):
                try: bot.send_message(uid, "⏳ Тым тез! Бираздан кейин қайталаңыз.")
                except: pass
                return
            if not is_admin(uid): _update_last_active(uid)
            return func(message)
        return wrapper
    return decorator

def check_access_cb(bot):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(call):
            uid = call.from_user.id
            if is_blocked(uid):
                bot.answer_callback_query(call.id, "⛔ Сиз блокландыңыз."); return
            if not is_admin(uid) and not is_authorized(uid):
                bot.answer_callback_query(call.id, "⛔ Рұхсат жоқ!"); return
            if not is_admin(uid): _update_last_active(uid)
            return func(call)
        return wrapper
    return decorator

def user_step_check(bot, message):
    uid = message.from_user.id
    if is_blocked(uid):
        try: bot.send_message(uid, "⛔ Сиз блокландыңыз.")
        except: pass
        return False
    if not is_authorized(uid) and not is_admin(uid):
        try: bot.send_message(uid, "⛔ Рұхсат жоқ!")
        except: pass
        return False
    return True

# ── HELPERS ───────────────────────────────────────────────────
def clean_hemis(val):
    if val is None: return ""
    if isinstance(val, float) and math.isnan(val): return ""
    s = str(val).strip()
    if s in ("None", "nan", ""): return ""
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit(): return s[:-2]
    return s

def parse_birth_date(val):
    if val is None: return ""
    if hasattr(val, 'strftime'):
        try: return val.strftime("%Y-%m-%d")
        except: return ""
    s = str(val).strip()
    if not s or s in ("None", "nan", ""): return ""
    for fmt in ("%Y-%m-%d","%d.%m.%Y","%d/%m/%Y","%Y/%m/%d","%m/%d/%Y","%d-%m-%Y","%Y%m%d"):
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except: pass
    return s

def get_birthday_info(birth_date_str):
    try:
        if not birth_date_str: return None, None
        s = str(birth_date_str).strip()
        if not s or s in ("None", "nan", ""): return None, None
        bd = datetime.strptime(s[:10], "%Y-%m-%d")
        today = now_uz().date()
        try: this_year_bd = bd.replace(year=today.year).date()
        except ValueError: this_year_bd = bd.replace(year=today.year, day=28).date()
        if this_year_bd == today: return 0, today
        if this_year_bd < today:
            try: this_year_bd = bd.replace(year=today.year + 1).date()
            except ValueError: this_year_bd = bd.replace(year=today.year + 1, day=28).date()
        return (this_year_bd - today).days, this_year_bd
    except Exception: return None, None

def date_to_ru(ds):
    try:
        dt = datetime.strptime(str(ds)[:10], "%Y-%m-%d")
        return f"{WEEKDAYS_RU[dt.weekday()]}, {dt.day} {MONTHS_RU[dt.month]}"
    except: return str(ds)

def get_online_status(la):
    try:
        last = la if isinstance(la, datetime) else datetime.strptime(str(la)[:19], "%Y-%m-%d %H:%M:%S")
        d = max((now_uz() - last).total_seconds(), 0)
        if d < 900: return "🟢 Онлайн"
        elif d < 3600: return f"🟡 {int(d//60)} мин бұрын"
        elif d < 86400: return f"🔴 {int(d//3600)} сағ бұрын"
        else: return f"🔴 {int(d//86400)} күн бұрын"
    except: return "⚪ Белгісіз"

def _is_online(la, now_t):
    try:
        last = la if isinstance(la, datetime) else datetime.strptime(str(la)[:19], "%Y-%m-%d %H:%M:%S")
        return (now_t - last).total_seconds() < 900
    except: return False

# ── MENUS ─────────────────────────────────────────────────────
def main_menu(uid=None):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📰 Жаңалықлар", "📚 Сабақ материаллары")
    m.row("📷 Фото/Видео", "📅 Сабақ кестеси")
    m.row("💡 Ұсыныс / Шағым", "📋 Список")
    m.row("📞 Байланыс", "💰 Контракт")
    m.row("📖 Пәнлер", "📊 Сабақ/Ертеңге")
    m.row("📊 Мениң барлауым")
    m.row("🤖 AI Көмекши")
    if uid and is_admin(uid): m.row("👮 Админ панель")
    return m

def back_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("⬅️ Артқа")
    return m

def admin_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("👥 Студентлер", "👤 Студент басқарыу")
    m.row("📊 Excel басқарыу", "📊 Барлау басқарыу")
    m.row("📅 Сабақ басқарыу", "❗ Сабақ болмайды")
    m.row("📈 Статистика", "📩 Ус/Ша келген")
    m.row("🗑 Өшириу", "📞 Байланыс басқарыу")
    m.row("💰 Контракт басқарыу", "📖 Пән басқарыу")
    m.row("🔒 Блок басқарыу")
    m.row("⬅️ Артқа")
    return m

def schedule_admin_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Сабақ қосыу", "❌ Сабақ өшириу")
    m.row("✏️ Сабақ өзгертиу")
    m.row("⬅️ Админге қайтыу")
    return m

def panler_admin_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Пән қосыу")
    m.row("📎 Пәнге файл қосыу")
    m.row("✏️ Пән атын өзгертиу")
    m.row("🗑 Пән өшириу")
    m.row("⬅️ Админге қайтыу")
    return m

def contacts_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Деканат қосыу", "➕ Муғаллим қосыу")
    m.row("❌ Байланыс өшириу")
    m.row("⬅️ Админге қайтыу")
    return m

def contract_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("💰 Контракт киргизиу", "➕ Төлем қосыу")
    m.row("📋 Барлық контрактлар")
    m.row("⬅️ Админге қайтыу")
    return m

def delete_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🗑 Материал өшириу", "🗑 Фото/Видео өшириу")
    m.row("🗑 Жаңалық өшириу")
    m.row("⬅️ Админге қайтыу")
    return m

def student_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Студент қосыу/өзгертиу")
    m.row("❌ Студент өшириу")
    m.row("⬅️ Админге қайтыу")
    return m

def excel_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📥 Excel жүклеу", "📤 Excel импорт")
    m.row("⬅️ Админге қайтыу")
    return m

def attendance_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📊 Барлау", "📅 Барлау тарийхы")
    m.row("📈 Барлау статистикасы")
    m.row("⬅️ Админге қайтыу")
    return m

def block_submenu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🚫 Студентти блоклау")
    m.row("✅ Блоктан шығарыу")
    m.row("📋 Блокланғанлар дизими")
    m.row("⬅️ Админге қайтыу")
    return m

def news_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("✍️ Жазыңыз", "🗂 Архив Жаңалықлар")
    m.row("⬅️ Артқа")
    return m

def materials_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📥 Мат жүклеңиз", "🗂 Архив материаллар")
    m.row("⬅️ Артқа")
    return m

def gallery_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row(GALLERY_UPLOAD_BTN, "🎞 S6-DI естелиги")
    m.row("⬅️ Артқа")
    return m

def schedule_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("Понедельник", "Вторник", "Среда")
    m.row("Четверг", "Пятница", "Суббота")
    m.row("Воскресенье")
    m.row("⬅️ Артқа")
    return m

def sabak_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("✅ Бараман", "❌ Себеп бар")
    m.row("⬅️ Артқа")
    return m

def sebep_file_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("⏭ Өткизип жибериу")
    m.row("⬅️ Артқа")
    return m

# ── SEND HELPERS ──────────────────────────────────────────────
def send_long_message(bot, chat_id, text, reply_markup=None, chunk_size=3800):
    if len(text) <= chunk_size:
        bot.send_message(chat_id, text, reply_markup=reply_markup)
        return
    lines = text.split("\n"); parts = []; cur = ""
    for line in lines:
        if len(cur) + len(line) + 1 > chunk_size:
            if cur: parts.append(cur)
            cur = line
        else:
            cur = cur + "\n" + line if cur else line
    if cur: parts.append(cur)
    for i, p in enumerate(parts):
        bot.send_message(chat_id, p, reply_markup=reply_markup if i == len(parts)-1 else None)

def send_to_students(bot, text=None, file_id=None, file_type=None, exclude_id=None):
    with db_cursor() as (_, cursor):
        if exclude_id:
            cursor.execute("SELECT id FROM students WHERE started=1 AND id!=%s", (exclude_id,))
        else:
            cursor.execute("SELECT id FROM students WHERE started=1")
        rows = cursor.fetchall()

    def _do():
        deactivated = []
        for (sid,) in rows:
            try:
                if file_id and file_type == "photo": bot.send_photo(sid, file_id, caption=text)
                elif file_id and file_type == "document": bot.send_document(sid, file_id, caption=text)
                elif file_id and file_type == "video": bot.send_video(sid, file_id, caption=text)
                elif text: bot.send_message(sid, text)
                time.sleep(0.05)
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ["blocked","403","chat not found","deactivated","forbidden"]):
                    deactivated.append(sid)
                else: logger.warning(f"send_to_students({sid}): {e}")
        if deactivated:
            try:
                with db_cursor() as (conn2, cur2):
                    for sid in deactivated:
                        cur2.execute("UPDATE students SET started=0 WHERE id=%s", (sid,))
                    conn2.commit()
            except Exception as e:
                logger.warning(f"deactivated update: {e}")

    Thread(target=_do, daemon=True).start()

_processed_messages = deque(maxlen=500)
_processed_lock = Lock()

def is_already_processed(mid):
    with _processed_lock:
        if mid in _processed_messages: return True
        _processed_messages.append(mid); return False

_last_saved = {}
_last_saved_lock = Lock()

def send_saved_once(bot, chat_id, uid):
    now = time.time()
    with _last_saved_lock:
        send = now - _last_saved.get(uid, 0) > 30
        if send: _last_saved[uid] = now
    if send: bot.send_message(chat_id, "✅ <b>Сақланды!</b>")
