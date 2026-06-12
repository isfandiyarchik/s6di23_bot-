from database import db_cursor, now_uz, clear_user_state
from handlers.common import is_blocked, is_admin, ADMIN_IDS, main_menu

def register(bot):
    @bot.message_handler(commands=["start"])
    def start(message):
        uid = message.from_user.id
        username = message.from_user.username or f"user{uid}"
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
            "👋 <b>Хош келдиңиз!</b>\nS6-DI-23 группасы сизлерди көргенимнен қууанышлыман.\nБөлимди таңлаңыз:",
            reply_markup=main_menu(uid))

