from database import db_cursor, now_uz, clear_user_state
from handlers.common import is_blocked, is_admin, ADMIN_IDS, main_menu

def register(bot):
    @bot.message_handler(commands=["start"])
    def start(message):
        uid = message.from_user.id
        username = message.from_user.username or f"user{uid}"
        is_group = message.chat.type in ("group", "supergroup")
        if is_group:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
        if is_blocked(uid):
            bot.send_message(uid, "⛔ Сиз блокландыңыз."); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id FROM students WHERE id=%s", (uid,))
            existing = cursor.fetchone()
        if not existing and not is_admin(uid):
            for aid in ADMIN_IDS:
                try:
                    fn = message.from_user.first_name or ""
                    ln = message.from_user.last_name or ""
                    bot.send_message(aid,
                        f"⚠️ <b>Рұхсатсыз кириу!</b>\n👤 {fn} {ln}\n🔗 @{username}\n🆔 <code>{uid}</code>")
                except: pass
            bot.send_message(uid,
                "⛔ <b>Кириуге рұхсат жоқ!</b>\nБұл бот тек S6-DI адамлары үшын.\nАдминге хабарласыңыз.")
            return
        with db_cursor() as (conn, cursor):
            cursor.execute("UPDATE students SET username=%s,last_active=%s,started=1 WHERE id=%s",
                (username, now_uz(), uid))
            conn.commit()
        clear_user_state(uid)
        bot.send_message(uid,
            "👋 <b>Хош келдиңиз!</b>\nS6-DI-23 группасы сизлерди көргенимнен қууанышлымын.\nБөлимди таңлаңыз:",
            reply_markup=main_menu(uid))

    @bot.message_handler(commands=["help"])
    def help_cmd(message):
        uid = message.from_user.id
        if is_blocked(uid): return
        is_group = message.chat.type in ("group", "supergroup")
        if is_group:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
        text = (
            "📋 <b>Бот командалары:</b>\n\n"
            "/start — Ботты баслау\n"
            "/help — Көмек\n"
            "/ai — AI менен сөйлесиу\n"
            "/info — Бот ҳаққында мағлыумат\n\n"
            "📌 <b>Меню батырмаларын қолланыңыз!</b>"
        )
        bot.send_message(uid, text, reply_markup=main_menu(uid))

    @bot.message_handler(commands=["ai"])
    def ai_cmd(message):
        uid = message.from_user.id
        if is_blocked(uid): return
        is_group = message.chat.type in ("group", "supergroup")
        if is_group:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
        from database import set_user_state
        from telebot import types
        set_user_state(uid, "ai_chat")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("🗑 Тарихты тазалау")
        markup.row("⬅️ Артқа")
        bot.send_message(uid,
            "🤖 <b>AI Көмекши иске қосылды!</b>\n\n"
            "✏️ Сорауыңызды жазыңыз.\n"
            "🌐 Жууаплар қарақалпақша берилетин болады.",
            reply_markup=markup)

    @bot.message_handler(commands=["info"])
    def info_cmd(message):
        uid = message.from_user.id
        if is_blocked(uid): return
        is_group = message.chat.type in ("group", "supergroup")
        if is_group:
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
        text = (
            "🤖 <b>S6-DI-23 Telegram Боты</b>\n\n"
            "👥 Бул бот S6-DI-23 студент группасы үшын исленди.\n\n"
            "⚙️ <b>Мүмкиншиликлер:</b>\n"
            "📅 Сабақ кестеси\n"
            "📚 Оқыу материаллары\n"
            "📷 Галерея\n"
            "📰 Жаңалықлар\n"
            "💰 Контракт ҳалаты\n"
            "📊 Барлау\n"
            "🤖 AI Көмекши\n\n"
            "📌 <b>Версия:</b> 2.0"
        )
        bot.send_message(uid, text, reply_markup=main_menu(uid))

