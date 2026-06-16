"""
Имтихан күнлери + Тапсырмалар/Дедлайн бөлими
"""
import logging
from datetime import datetime
from telebot import types
from database import db_cursor, now_uz
from handlers.common import (
    is_admin, check_access, check_access_cb,
    back_menu, admin_menu, main_menu
)

logger = logging.getLogger(__name__)

# ── МЕНЮ ─────────────────────────────────────────────────────
def exam_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📝 Имтиханлар", "📋 Тапсырмалар")
    m.row("⬅️ Артқа")
    return m

def exam_admin_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Имтихан қосыу", "🗑 Имтихан өшириу")
    m.row("➕ Тапсырма қосыу", "🗑 Тапсырма өшириу")
    m.row("⬅️ Админге қайтыу")
    return m


def register(bot):
    ca = check_access(bot)

    # ── СТУДЕНТ БӨЛІМІ ────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "📝 Имтиханлар менен тапсырмалар")
    @ca
    def exam_section(message):
        bot.send_message(message.chat.id,
            "📝 <b>Имтиханлар менен тапсырмалар</b>\n\nБөлимди таңлаңыз:",
            reply_markup=exam_menu())

    @bot.message_handler(func=lambda m: m.text == "📝 Имтиханлар")
    @ca
    def show_exams(message):
        now = now_uz()
        with db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT id,subject,exam_date,exam_time,location,note "
                "FROM exams WHERE exam_date >= %s ORDER BY exam_date,exam_time",
                (now.strftime("%Y-%m-%d"),))
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id,
                "📭 Жақын арада имтихан жоқ.",
                reply_markup=exam_menu()); return

        text = "📝 <b>Жақындағы имтиханлар:</b>\n\n"
        for r in rows:
            exam_dt = datetime.strptime(r[2], "%Y-%m-%d")
            days_left = (exam_dt.date() - now.date()).days
            if days_left == 0: badge = "🔴 <b>БҮГИН!</b>"
            elif days_left == 1: badge = "🟠 <b>ЕРТЕҢ!</b>"
            elif days_left <= 3: badge = f"🟡 <b>{days_left} күн қалды</b>"
            else: badge = f"🟢 {days_left} күн қалды"
            text += (f"{'─'*25}\n"
                     f"📖 <b>{r[1]}</b>\n"
                     f"📅 {exam_dt.strftime('%d.%m.%Y')} {r[3] or ''}\n"
                     f"📍 {r[4] or '—'}\n"
                     f"⏳ {badge}\n")
            if r[5]: text += f"📌 {r[5]}\n"
        text += "─"*25

        bot.send_message(message.chat.id, text, reply_markup=exam_menu())

    @bot.message_handler(func=lambda m: m.text == "📋 Тапсырмалар")
    @ca
    def show_tasks(message):
        now = now_uz()
        with db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT id,subject,title,deadline,note "
                "FROM tasks WHERE deadline >= %s ORDER BY deadline",
                (now.strftime("%Y-%m-%d"),))
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id,
                "📭 Белсенди тапсырма жоқ.",
                reply_markup=exam_menu()); return

        text = "📋 <b>Тапсырмалар / Дедлайнлар:</b>\n\n"
        for r in rows:
            dl_dt = datetime.strptime(r[3], "%Y-%m-%d")
            days_left = (dl_dt.date() - now.date()).days
            if days_left < 0: badge = "❌ <b>Уақты өтти!</b>"
            elif days_left == 0: badge = "🔴 <b>БҮГИН тапсыру керек!</b>"
            elif days_left == 1: badge = "🟠 <b>ЕРТЕҢ дедлайн!</b>"
            elif days_left <= 3: badge = f"🟡 <b>{days_left} күн қалды</b>"
            else: badge = f"🟢 {days_left} күн қалды"
            text += (f"{'─'*25}\n"
                     f"📖 <b>{r[1]}</b>\n"
                     f"📌 {r[2]}\n"
                     f"📅 Дедлайн: {dl_dt.strftime('%d.%m.%Y')}\n"
                     f"⏳ {badge}\n")
            if r[4]: text += f"💬 {r[4]}\n"
        text += "─"*25

        bot.send_message(message.chat.id, text, reply_markup=exam_menu())

    # ── ADMIN БӨЛІМІ ─────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "📝 Имтихан/Тапсырма басқарыу")
    @ca
    def exam_admin(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        bot.send_message(message.chat.id,
            "📝 <b>Имтихан/Тапсырма басқарыу</b>",
            reply_markup=exam_admin_menu())

    # ── ЕМТИХАН ҚОСЫУ ────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "➕ Имтихан қосыу")
    @ca
    def add_exam_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        msg = bot.send_message(message.chat.id,
            "➕ <b>Имтихан қосыу:</b>\n\n"
            "Формат: <code>Пән;Күни;Уақыты;Орны;Ескертиу</code>\n\n"
            "Мысал: <code>Информатика;2026-06-20;09:00;303 аудитория;Телефон рұхсат</code>\n\n"
            "⚠️ Күн форматы: <code>ЖЖЖЖ-АА-КК</code>",
            reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_add_exam)

    def handle_add_exam(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📝 Имтихан/Тапсырма басқарыу",
                reply_markup=exam_admin_menu()); return
        parts = [p.strip() for p in message.text.split(";")]
        if len(parts) < 2:
            msg = bot.send_message(message.chat.id,
                "❌ Формат: <code>Пән;Күни;Уақыты;Орны;Ескертиу</code>",
                reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_add_exam); return
        subject = parts[0]
        exam_date = parts[1]
        exam_time = parts[2] if len(parts) > 2 else ""
        location = parts[3] if len(parts) > 3 else ""
        note = parts[4] if len(parts) > 4 else ""
        # Күн форматын тексер
        try:
            datetime.strptime(exam_date, "%Y-%m-%d")
        except ValueError:
            msg = bot.send_message(message.chat.id,
                "❌ Күн форматы дұрыс емес! <code>ЖЖЖЖ-АА-КК</code> (мысал: 2026-06-20)",
                reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_add_exam); return
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO exams(subject,exam_date,exam_time,location,note) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (subject, exam_date, exam_time, location, note))
                conn.commit()
            bot.send_message(message.chat.id,
                f"✅ Имтихан қосылды!\n📖 {subject}\n📅 {exam_date} {exam_time}",
                reply_markup=exam_admin_menu())
            # Барлық студентке хабарлама
            from handlers.common import send_to_students
            send_to_students(bot,
                text=(f"📝 <b>Таза имтихан қосылды!</b>\n\n"
                      f"📖 <b>{subject}</b>\n"
                      f"📅 {exam_date} {exam_time}\n"
                      f"📍 {location or '—'}\n"
                      + (f"💬 {note}" if note else "")))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}",
                reply_markup=exam_admin_menu())

    # ── ТАПСЫРМА ҚОСЫУ ───────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "➕ Тапсырма қосыу")
    @ca
    def add_task_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        msg = bot.send_message(message.chat.id,
            "➕ <b>Тапсырма қосыу:</b>\n\n"
            "Формат: <code>Пән;Тапсырма аты;Дедлайн;Ескертиу</code>\n\n"
            "Мысал: <code>Паннен;Оз бетинше жұмысы;2026-06-18;1-3 тапсырма</code>\n\n"
            "⚠️ Дедлайн форматы: <code>ЖЖЖЖ-АА-КК</code>",
            reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_add_task)

    def handle_add_task(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📝 Имтихан/Тапсырма басқарыу",
                reply_markup=exam_admin_menu()); return
        parts = [p.strip() for p in message.text.split(";")]
        if len(parts) < 3:
            msg = bot.send_message(message.chat.id,
                "❌ Формат: <code>Пән;Тапсырма;Дедлайн;Ескертиу</code>",
                reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_add_task); return
        subject = parts[0]
        title = parts[1]
        deadline = parts[2]
        note = parts[3] if len(parts) > 3 else ""
        try:
            datetime.strptime(deadline, "%Y-%m-%d")
        except ValueError:
            msg = bot.send_message(message.chat.id,
                "❌ Дедлайн форматы дұрыс емес! <code>ЖЖЖЖ-АА-КК</code>",
                reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_add_task); return
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO tasks(subject,title,deadline,note) "
                    "VALUES(%s,%s,%s,%s)",
                    (subject, title, deadline, note))
                conn.commit()
            bot.send_message(message.chat.id,
                f"✅ Тапсырма қосылды!\n📖 {subject}\n📌 {title}\n📅 {deadline}",
                reply_markup=exam_admin_menu())
            from handlers.common import send_to_students
            send_to_students(bot,
                text=(f"📋 <b>Таза тапсырма!</b>\n\n"
                      f"📖 <b>{subject}</b>\n"
                      f"📌 {title}\n"
                      f"📅 Дедлайн: {deadline}\n"
                      + (f"💬 {note}" if note else "")))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}",
                reply_markup=exam_admin_menu())

    # ── ӨШІРУ ────────────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "🗑 Имтихан өшириу")
    @ca
    def delete_exam_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,subject,exam_date FROM exams ORDER BY exam_date")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Имтихан жоқ.",
                reply_markup=exam_admin_menu()); return
        text = "🗑 <b>Имтихан өшириу — ID жазыңыз:</b>\n\n"
        for r in rows:
            text += f"ID:<code>{r[0]}</code> | {r[1]} | {r[2]}\n"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_delete_exam)

    def handle_delete_exam(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📝 Имтихан/Тапсырма басқарыу",
                reply_markup=exam_admin_menu()); return
        try:
            rid = int(message.text.strip())
            with db_cursor() as (conn, cursor):
                cursor.execute("SELECT subject FROM exams WHERE id=%s", (rid,))
                row = cursor.fetchone()
                if not row:
                    bot.send_message(message.chat.id, "⚠️ Табылмады.",
                        reply_markup=exam_admin_menu()); return
                cursor.execute("DELETE FROM exams WHERE id=%s", (rid,))
                conn.commit()
            bot.send_message(message.chat.id,
                f"✅ <b>{row[0]}</b> имтихан өширилди.",
                reply_markup=exam_admin_menu())
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Тек сан ID жазыңыз:",
                reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_delete_exam)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}",
                reply_markup=exam_admin_menu())

    @bot.message_handler(func=lambda m: m.text == "🗑 Тапсырма өшириу")
    @ca
    def delete_task_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,subject,title,deadline FROM tasks ORDER BY deadline")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Тапсырма жоқ.",
                reply_markup=exam_admin_menu()); return
        text = "🗑 <b>Тапсырма өшириу — ID жазыңыз:</b>\n\n"
        for r in rows:
            text += f"ID:<code>{r[0]}</code> | {r[1]} | {r[2]} | {r[3]}\n"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_delete_task)

    def handle_delete_task(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📝 Имтихан/Тапсырма басқарыу",
                reply_markup=exam_admin_menu()); return
        try:
            rid = int(message.text.strip())
            with db_cursor() as (conn, cursor):
                cursor.execute("SELECT title FROM tasks WHERE id=%s", (rid,))
                row = cursor.fetchone()
                if not row:
                    bot.send_message(message.chat.id, "⚠️ Табылмады.",
                        reply_markup=exam_admin_menu()); return
                cursor.execute("DELETE FROM tasks WHERE id=%s", (rid,))
                conn.commit()
            bot.send_message(message.chat.id,
                f"✅ <b>{row[0]}</b> тапсырмасы өширилди.",
                reply_markup=exam_admin_menu())
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Тек сан ID жазыңыз:",
                reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_delete_task)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}",
                reply_markup=exam_admin_menu())
