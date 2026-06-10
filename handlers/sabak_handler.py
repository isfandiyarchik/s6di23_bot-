from datetime import timedelta
from database import db_cursor, now_uz, get_user_state, set_user_state, clear_user_state
from handlers.common import (
    is_admin, check_access, user_step_check,
    DAYS_EN_TO_RU, ADMIN_IDS,
    back_menu, sabak_menu, main_menu, sebep_file_menu
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "📊 Сабақ/Ертеңге")
    @ca
    def sabak_ertenge(message):
        today = DAYS_EN_TO_RU.get(now_uz().strftime("%A"), "")
        tomorrow = DAYS_EN_TO_RU.get((now_uz() + timedelta(days=1)).strftime("%A"), "")
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT subject,time FROM schedule WHERE day=%s ORDER BY time", (today,))
            today_lessons = cursor.fetchall()
            cursor.execute("SELECT subject,time FROM schedule WHERE day=%s ORDER BY time", (tomorrow,))
            tomorrow_lessons = cursor.fetchall()
        text = "📊 <b>Сабақ хабары</b>\n\n"
        text += f"📅 <b>Бүгин — {today}:</b>\n"
        if today_lessons:
            for i, r in enumerate(today_lessons, 1):
                text += f"  {i}-пара 🕐 {r[1]} — {r[0]}\n"
        else:
            text += "  📭 Сабақ жоқ\n"
        text += f"\n📅 <b>Ертең — {tomorrow}:</b>\n"
        if tomorrow_lessons:
            for i, r in enumerate(tomorrow_lessons, 1):
                text += f"  {i}-пара 🕐 {r[1]} — {r[0]}\n"
        else:
            text += "  📭 Сабақ жоқ\n"
        bot.send_message(message.chat.id, text, reply_markup=sabak_menu())

    @bot.message_handler(func=lambda m: m.text == "✅ Бараман")
    @ca
    def sabak_keledi(message):
        bot.send_message(message.chat.id,
            "✅ Яқшы! Жолыңыз болсын! Сабаққа уақытында келиңиз! 🙏",
            reply_markup=main_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: m.text == "❌ Себеп бар")
    @ca
    def sabak_kelmeydi(message):
        uid = message.from_user.id
        set_user_state(uid, "sebep_text")
        msg = bot.send_message(message.chat.id, "❌ <b>Себебиңизди жазыңыз:</b>", reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_sebep_text)

    def handle_sebep_text(message):
        if not user_step_check(bot, message): return
        uid = message.from_user.id
        if not message.text or message.text == "⬅️ Артқа":
            clear_user_state(uid)
            bot.send_message(message.chat.id, "📊 Сабақ/Ертеңге", reply_markup=sabak_menu()); return
        sebep_text = message.text
        set_user_state(uid, f"sebep_file:{sebep_text}")
        msg = bot.send_message(message.chat.id,
            "📎 Файл/фото жибере аласыз (дәлел үшын):", reply_markup=sebep_file_menu())
        bot.register_next_step_handler(msg, lambda m: handle_sebep_file(m, sebep_text))

    def handle_sebep_file(message, sebep_text):
        if not user_step_check(bot, message): return
        uid = message.from_user.id
        un = message.from_user.username or f"user{uid}"
        fn = message.from_user.first_name or ""
        ln = message.from_user.last_name or ""
        clear_user_state(uid)
        file_id = file_type = None
        if message.document:
            file_id = message.document.file_id; file_type = "document"
        elif message.photo:
            file_id = message.photo[-1].file_id; file_type = "photo"
        elif message.text and message.text == "⏭ Өткизип жибериу":
            pass
        elif message.text and message.text == "⬅️ Артқа":
            set_user_state(uid, "sebep_text")
            msg = bot.send_message(message.chat.id,
                "❌ <b>Себебиңизди қайта жазыңыз:</b>", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_sebep_text); return
        admin_text = (
            f"⚠️ <b>Сабаққа келе алмайтын студент:</b>\n\n"
            f"👤 {fn} {ln}\n🔗 @{un}\n🆔 <code>{uid}</code>\n\n"
            f"📝 <b>Себеп:</b>\n{sebep_text}")
        for aid in ADMIN_IDS:
            try:
                bot.send_message(aid, admin_text)
                if file_id and file_type == "photo":
                    bot.send_photo(aid, file_id, caption="📎 Дәлел")
                elif file_id and file_type == "document":
                    bot.send_document(aid, file_id, caption="📎 Дәлел")
            except: pass
        bot.send_message(message.chat.id,
            "✅ <b>Себебиңиз жиберилди!</b>\nАдминлер хабарланды.",
            reply_markup=main_menu(uid))

