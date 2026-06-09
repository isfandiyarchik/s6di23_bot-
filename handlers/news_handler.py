from database import db_cursor, now_uz
from handlers.common import (
    is_admin, check_access, user_step_check,
    send_to_students, ADMIN_IDS,
    back_menu, news_menu, main_menu
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "📰 Жаңалықлар")
    @ca
    def show_news_menu(message):
        bot.send_message(message.chat.id, "📰 <b>Жаңалықлар бөлими</b>", reply_markup=news_menu())

    @bot.message_handler(func=lambda m: m.text == "✍️ Жазыңыз")
    @ca
    def write_news(message):
        msg = bot.send_message(message.chat.id, "✍️ <b>Жаңалығыңызды жазыңыз:</b>", reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_user_news)

    def handle_user_news(message):
        if not user_step_check(bot, message): return
        if not message.text:
            msg = bot.send_message(message.chat.id, "✍️ Тек текст жибериңиз:", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_user_news); return
        if message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📰 Жаңалықлар", reply_markup=news_menu()); return
        if len(message.text) > 2000:
            msg = bot.send_message(message.chat.id, "❌ Текст тым ұзын (макс 2000 таңба).", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_user_news); return
        uid = message.from_user.id
        username = message.from_user.username or f"user{uid}"
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("INSERT INTO user_news(content,author_id,author_username) VALUES(%s,%s,%s)",
                    (message.text, uid, username))
                conn.commit()
            send_to_students(bot,
                text=f"📰 <b>Таза хабарлама!</b>\n\n👤 <b>@{username}</b>:\n\n{message.text}",
                exclude_id=uid)
            bot.send_message(message.chat.id, "✅ Жиберилди!", reply_markup=news_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Қате: {e}", reply_markup=news_menu())

    @bot.message_handler(func=lambda m: m.text == "🗂 Архив Жаңалықлар")
    @ca
    def show_news_archive(message):
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT content,author_username,date FROM user_news ORDER BY date DESC")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Архив бос.", reply_markup=news_menu()); return
        chunks = []
        cur = "🗂 <b>Архив жаңалықлар:</b>\n\n"
        for r in rows:
            entry = f"👤 <b>@{r[1]}</b>\n📌 {r[0]}\n🕐 {r[2]}\n{'─'*25}\n"
            if len(cur) + len(entry) > 3800:
                chunks.append(cur); cur = ""
            cur += entry
        if cur: chunks.append(cur)
        for i, chunk in enumerate(chunks):
            bot.send_message(message.chat.id, chunk,
                reply_markup=news_menu() if i == len(chunks)-1 else None)
