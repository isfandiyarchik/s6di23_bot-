from database import db_cursor, now_uz
from handlers.common import (
    is_admin, check_access, check_access_cb,
    DAYS_RU, DAYS_EN_TO_RU, MONTHS_RU,
    back_menu, schedule_menu, schedule_admin_submenu, admin_menu, main_menu
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "📅 Сабақ кестеси")
    @ca
    def show_schedule_menu(message):
        bot.send_message(message.chat.id, "📅 <b>Сабақ кестеси</b>\nКүнди таңлаңыз:", reply_markup=schedule_menu())

    @bot.message_handler(func=lambda m: m.text in DAYS_RU)
    @ca
    def show_day_schedule(message):
        day = message.text
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT subject,time FROM schedule WHERE day=%s ORDER BY time", (day,))
            rows = cursor.fetchall()
        today_ru = DAYS_EN_TO_RU.get(now_uz().strftime("%A"), "")
        today_mark = " 📌 <i>(бүгин)</i>" if day == today_ru else ""
        if not rows:
            bot.send_message(message.chat.id, f"📭 <b>{day}{today_mark}</b>\n\nСабақ жоқ.", reply_markup=schedule_menu()); return
        text = f"📅 <b>{day}{today_mark}</b>\n\n"
        for i, r in enumerate(rows, 1):
            text += f"{i}-пара 🕐 <b>{r[1]}</b> — {r[0]}\n"
        bot.send_message(message.chat.id, text, reply_markup=schedule_menu())

    @bot.message_handler(func=lambda m: m.text == "📅 Сабақ басқарыу")
    @ca
    def schedule_management(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        bot.send_message(message.chat.id, "📅 <b>Сабақ басқарыу</b>", reply_markup=schedule_admin_submenu())

    @bot.message_handler(func=lambda m: m.text == "➕ Сабақ қосыу")
    @ca
    def schedule_add_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        msg = bot.send_message(message.chat.id,
            "📝 Формат: <code>Понедельник;Математика;09:00</code>", reply_markup=back_menu())
        bot.register_next_step_handler(msg, add_lesson)

    def add_lesson(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📅 Сабақ басқарыу", reply_markup=schedule_admin_submenu()); return
        try:
            parts = [p.strip() for p in message.text.split(";")]
            if len(parts) != 3 or not all(parts): raise ValueError
            day, subject, time_ = parts
            if day not in DAYS_RU: raise ValueError(f"Күн дұрыс емес: {day}")
            with db_cursor() as (conn, cursor):
                cursor.execute("INSERT INTO schedule(day,subject,time) VALUES(%s,%s,%s)", (day, subject, time_))
                conn.commit()
            bot.send_message(message.chat.id,
                f"✅ <b>{day} | {subject} | {time_}</b> қосылды!", reply_markup=schedule_admin_submenu())
        except ValueError as e:
            msg = bot.send_message(message.chat.id,
                f"❌ <code>Понедельник;Математика;09:00</code>\n({e})", reply_markup=back_menu())
            bot.register_next_step_handler(msg, add_lesson)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=schedule_admin_submenu())

    @bot.message_handler(func=lambda m: m.text == "❌ Сабақ өшириу")
    @ca
    def schedule_delete_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,day,subject,time FROM schedule ORDER BY day,time")
            lessons = cursor.fetchall()
        if not lessons:
            bot.send_message(message.chat.id, "📭 Кесте бос.", reply_markup=schedule_admin_submenu()); return
        text = "📋 <b>Барлық сабақлар:</b>\n\n"
        for r in lessons:
            text += f"ID:{r[0]} | {r[1]} | {r[2]} | {r[3]}\n"
        text += "\n<code>Күн;Уақыт</code> форматында жазыңыз:"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, delete_lesson)

    def delete_lesson(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📅 Сабақ басқарыу", reply_markup=schedule_admin_submenu()); return
        try:
            parts = [p.strip() for p in message.text.split(";")]
            if len(parts) != 2 or not all(parts): raise ValueError
            day, time_ = parts
            with db_cursor() as (conn, cursor):
                cursor.execute("DELETE FROM schedule WHERE day=%s AND time=%s", (day, time_))
                d = cursor.rowcount; conn.commit()
            if d:
                bot.send_message(message.chat.id, f"✅ Өширилди: {day} — {time_}", reply_markup=schedule_admin_submenu())
            else:
                bot.send_message(message.chat.id, "⚠️ Табылмады.", reply_markup=schedule_admin_submenu())
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ <code>Понедельник;09:00</code>", reply_markup=back_menu())
            bot.register_next_step_handler(msg, delete_lesson)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=schedule_admin_submenu())

    @bot.message_handler(func=lambda m: m.text == "✏️ Сабақ өзгертиу")
    @ca
    def schedule_edit_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,day,subject,time FROM schedule ORDER BY day,time")
            lessons = cursor.fetchall()
        if not lessons:
            bot.send_message(message.chat.id, "📭 Кесте бос.", reply_markup=schedule_admin_submenu()); return
        text = "✏️ <b>Сабақ өзгертиу — ID жазыңыз:</b>\n\n"
        for r in lessons:
            text += f"ID:<code>{r[0]}</code> | {r[1]} | {r[2]} | {r[3]}\n"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_schedule_edit_id)

    def handle_schedule_edit_id(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📅 Сабақ басқарыу", reply_markup=schedule_admin_submenu()); return
        try:
            rid = int(message.text.strip())
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Тек сан ID жазыңыз:", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_schedule_edit_id); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,day,subject,time FROM schedule WHERE id=%s", (rid,))
            row = cursor.fetchone()
        if not row:
            bot.send_message(message.chat.id, "⚠️ Табылмады.", reply_markup=schedule_admin_submenu()); return
        text = (f"✏️ <b>Өзгертиу:</b>\n"
                f"📅 {row[1]} | {row[2]} | 🕐 {row[3]}\n\n"
                f"Формат: <code>Күн;Пән;Уақыт</code>\n"
                f"Өзгертпей <b>—</b> жазыңыз.")
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg,
            lambda m: handle_schedule_edit_save(m, rid, row[1], row[2], row[3]))

    def handle_schedule_edit_save(message, rid, old_day, old_subj, old_time):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📅 Сабақ басқарыу", reply_markup=schedule_admin_submenu()); return
        try:
            parts = [p.strip() for p in message.text.split(";")]
            if len(parts) != 3: raise ValueError("3 бөлек болуы керек")
            new_day = parts[0] if parts[0] != "—" else old_day
            new_subj = parts[1] if parts[1] != "—" else old_subj
            new_time = parts[2] if parts[2] != "—" else old_time
            if new_day not in DAYS_RU: raise ValueError(f"Күн дұрыс емес: {new_day}")
            with db_cursor() as (conn, cursor):
                cursor.execute("UPDATE schedule SET day=%s,subject=%s,time=%s WHERE id=%s",
                    (new_day, new_subj, new_time, rid))
                conn.commit()
            bot.send_message(message.chat.id,
                f"✅ Тазаланды!\n📅 {new_day} | {new_subj} | {new_time}",
                reply_markup=schedule_admin_submenu())
        except Exception as e:
            msg = bot.send_message(message.chat.id,
                f"❌ Формат: <code>Күн;Пән;Уақыт</code> ({e})", reply_markup=back_menu())
            bot.register_next_step_handler(msg,
                lambda m: handle_schedule_edit_save(m, rid, old_day, old_subj, old_time))
