"""
Таза оқыу жылы handler-ы
- Барлауды архивке сақлап тазартады
- Контрактларды тазартады
- Студентлерге хабарлама жибереди
"""
import logging
from datetime import datetime
from database import db_cursor, now_uz
from handlers.common import (
    is_admin, check_access, admin_menu, back_menu, send_to_students
)

logger = logging.getLogger(__name__)


def new_year_admin_menu():
    from telebot import types
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🎓 Таза оқыу жылын баслау")
    m.row("📊 Барлауды тазартыу (жеке)")
    m.row("💰 Контрактларды тазартыу (жеке)")
    m.row("⬅️ Админге қайтыу")
    return m


def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "🎓 Таза оқыу жылы")
    @ca
    def new_year_menu(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        year = now_uz().year
        bot.send_message(message.chat.id,
            f"🎓 <b>Таза оқыу жылы басқарыуы</b>\n\n"
            f"📅 Усы жыл: <b>{year}-{year+1}</b>\n\n"
            f"⚠️ <b>Ескертиу:</b>\n"
            f"• Барлауды тазартқанда — данныйлар <b>архивке</b> сақланады\n"
            f"• Контрактларды тазартқанда — төлем тарихы <b>өшириледи</b>\n"
            f"• Бұл әрекетлер <b>қайтарылмайды!</b>",
            reply_markup=new_year_admin_menu())

    @bot.message_handler(func=lambda m: m.text == "🎓 Таза оқыу жылын баслау")
    @ca
    def start_new_year(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        year = now_uz().year
        # Растау сұрау
        from telebot import types
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "✅ Ауа, жаңа жылды баслау",
                callback_data=f"new_year_confirm_{year}"),
            types.InlineKeyboardButton(
                "❌ Жоқ, болдырма",
                callback_data="new_year_cancel"))
        bot.send_message(message.chat.id,
            f"⚠️ <b>Раслаңыз!</b>\n\n"
            f"🎓 <b>{year}-{year+1} оқыу жылын баслау</b>\n\n"
            f"Бұл әрекет:\n"
            f"• 📊 Барлауды архивке сақлайды және тазартады\n"
            f"• 💰 Контракт төлемлерин тазартады\n"
            f"• 📨 Барлық студентке хабарлама жибереди\n\n"
            f"Жалғастырасыз ба?",
            reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("new_year_confirm_"))
    def new_year_confirmed(call):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "🚫"); return
        year = int(call.data.split("_")[-1])
        bot.answer_callback_query(call.id, "⏳ Таза оқыу жылы басланыуда...")
        bot.edit_message_text(
            "⏳ <b>Таза оқыу жылы тайарланыуда...</b>",
            call.message.chat.id, call.message.message_id)

        results = []
        errors = []

        # 1. Барлауды archive кестесине сақла
        try:
            with db_cursor() as (conn, cursor):
                # archive_attendance кестесі бар ма тексер
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS archive_attendance (
                        id SERIAL PRIMARY KEY,
                        study_year TEXT,
                        date TEXT, para INTEGER, subject TEXT,
                        student_id BIGINT, student_name TEXT,
                        status TEXT, archived_at TIMESTAMP DEFAULT NOW())
                """)
                # Барлауды архивке көшір
                cursor.execute("""
                    INSERT INTO archive_attendance
                        (study_year, date, para, subject, student_id, student_name, status)
                    SELECT %s, date, para, subject, student_id, student_name, status
                    FROM attendance
                """, (f"{year-1}-{year}",))
                archived = cursor.rowcount
                # Барлауды тазарт
                cursor.execute("DELETE FROM attendance")
                # Attendance sessions тазарт
                cursor.execute("DELETE FROM attendance_sessions")
                conn.commit()
            results.append(f"✅ Барлау: {archived} жазба архивке сақланды")
        except Exception as e:
            errors.append(f"❌ Барлау: {e}")
            logger.error(f"new_year attendance: {e}", exc_info=True)

        # 2. Контракт төлемлерин тазарт (контракт суммасы қалады)
        try:
            with db_cursor() as (conn, cursor):
                # Контракт төлемлерин архивке сақла
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS archive_contract_payments (
                        id SERIAL PRIMARY KEY,
                        study_year TEXT,
                        student_id BIGINT, amount REAL,
                        date TEXT, note TEXT,
                        archived_at TIMESTAMP DEFAULT NOW())
                """)
                cursor.execute("""
                    INSERT INTO archive_contract_payments
                        (study_year, student_id, amount, date, note)
                    SELECT %s, student_id, amount, date, note
                    FROM contract_payments
                """, (f"{year-1}-{year}",))
                archived_pay = cursor.rowcount
                # Контракт төлемлерин тазарт
                cursor.execute("DELETE FROM contract_payments")
                # Контракт суммаларын да тазарт (жаңа жылға жаңа сумма қойылады)
                cursor.execute("DELETE FROM contracts")
                conn.commit()
            results.append(f"✅ Контракт: {archived_pay} төлем архивке сақланды")
        except Exception as e:
            errors.append(f"❌ Контракт: {e}")
            logger.error(f"new_year contract: {e}", exc_info=True)

        # 3. Емтихан және тапсырмаларды тазарт
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("DELETE FROM exams")
                cursor.execute("DELETE FROM tasks")
                conn.commit()
            results.append("✅ Имтиханлар менен тапсырмалар тазартылды")
        except Exception as e:
            errors.append(f"❌ Имтихан/Тапсырма: {e}")

        # 4. Sent reminders тазарт
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("DELETE FROM sent_reminders")
                conn.commit()
            results.append("✅ Ескертиулер тазартылды")
        except Exception as e:
            errors.append(f"❌ Ескертиулер: {e}")

        # 5. Студентлерге хабарлама жибер
        try:
            send_to_students(bot,
                text=(f"🎓 <b>Таза {year}-{year+1} оқыу жылы мүбәрек болсын!</b>\n\n"
                      f"✨ Бұл жылда табыслар менен жетискенликлер тилеймиз!\n\n"
                      f"📚 Оқыу жылы тазадан басланды — алға! 💪"))
            results.append("✅ Студентлерге хабарлама жиберилди")
        except Exception as e:
            errors.append(f"❌ Хабарлама: {e}")

        # Нәтиже
        sep = "─" * 30
        result_text = (
            f"🎓 <b>{year}-{year+1} оқыу жылы басланды!</b>\n{sep}\n\n"
            + "\n".join(results))
        if errors:
            result_text += f"\n\n{sep}\n⚠️ <b>Қателер:</b>\n" + "\n".join(errors)

        try:
            bot.edit_message_text(result_text,
                call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except:
            bot.send_message(call.message.chat.id, result_text)

        bot.send_message(call.message.chat.id,
            "✅ Таза оқыу жылы тайын!\n\n"
            "📌 Енди:\n"
            "1. Әр студентке таза контракт суммасын қосыңыз\n"
            "2. Сабақ кестесин тазартыңыз",
            reply_markup=admin_menu())

    @bot.callback_query_handler(func=lambda c: c.data == "new_year_cancel")
    def new_year_cancelled(call):
        bot.answer_callback_query(call.id, "❌ Болмады")
        bot.edit_message_text("❌ <b>Таза оқыу жылы болмады.</b>",
            call.message.chat.id, call.message.message_id)

    # ── ЖЕКЕ: тек барлауды тазарту ───────────────────────────
    @bot.message_handler(func=lambda m: m.text == "📊 Барлауды тазартыу (жеке)")
    @ca
    def clear_attendance_only(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        from telebot import types
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Ауа", callback_data="clear_att_confirm"),
            types.InlineKeyboardButton("❌ Яқ", callback_data="new_year_cancel"))
        bot.send_message(message.chat.id,
            "⚠️ Барлауды тазартасыз ба?\nДанныйлар архивке сақланды.",
            reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data == "clear_att_confirm")
    def clear_att_confirmed(call):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "🚫"); return
        year = now_uz().year
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS archive_attendance (
                        id SERIAL PRIMARY KEY, study_year TEXT,
                        date TEXT, para INTEGER, subject TEXT,
                        student_id BIGINT, student_name TEXT,
                        status TEXT, archived_at TIMESTAMP DEFAULT NOW())
                """)
                cursor.execute("""
                    INSERT INTO archive_attendance
                        (study_year, date, para, subject, student_id, student_name, status)
                    SELECT %s, date, para, subject, student_id, student_name, status
                    FROM attendance
                """, (f"{year-1}-{year}",))
                cnt = cursor.rowcount
                cursor.execute("DELETE FROM attendance")
                cursor.execute("DELETE FROM attendance_sessions")
                conn.commit()
            bot.answer_callback_query(call.id, "✅ Тазартылды!")
            bot.edit_message_text(
                f"✅ Барлау тазартылды!\n📦 {cnt} жазба архивке сақланды.",
                call.message.chat.id, call.message.message_id)
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ Қате!")
            bot.edit_message_text(f"❌ Қате: {e}",
                call.message.chat.id, call.message.message_id)

    # ── ЖЕКЕ: тек контракттарды тазарту ─────────────────────
    @bot.message_handler(func=lambda m: m.text == "💰 Контрактларды тазартыу (жеке)")
    @ca
    def clear_contracts_only(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        from telebot import types
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Ауа", callback_data="clear_cont_confirm"),
            types.InlineKeyboardButton("❌ Яқ", callback_data="new_year_cancel"))
        bot.send_message(message.chat.id,
            "⚠️ Контракт төлемлерин тазартасыз ба?\nАрхивке сақланды.",
            reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data == "clear_cont_confirm")
    def clear_cont_confirmed(call):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "🚫"); return
        year = now_uz().year
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS archive_contract_payments (
                        id SERIAL PRIMARY KEY, study_year TEXT,
                        student_id BIGINT, amount REAL,
                        date TEXT, note TEXT,
                        archived_at TIMESTAMP DEFAULT NOW())
                """)
                cursor.execute("""
                    INSERT INTO archive_contract_payments
                        (study_year, student_id, amount, date, note)
                    SELECT %s, student_id, amount, date, note
                    FROM contract_payments
                """, (f"{year-1}-{year}",))
                cnt = cursor.rowcount
                cursor.execute("DELETE FROM contract_payments")
                cursor.execute("DELETE FROM contracts")
                conn.commit()
            bot.answer_callback_query(call.id, "✅ Тазартылды!")
            bot.edit_message_text(
                f"✅ Контракт төлемлери тазартылды!\n📦 {cnt} төлем архивке сақланды.",
                call.message.chat.id, call.message.message_id)
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ Қате!")
            bot.edit_message_text(f"❌ Қате: {e}",
                call.message.chat.id, call.message.message_id)
