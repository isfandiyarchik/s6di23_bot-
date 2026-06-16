"""
Группа чаты handler-ы
Группа чатында жұмыс ислейтин командалар
"""
import os
import logging
from telebot import types
from database import db_cursor, now_uz
from handlers.common import (
    is_admin, DAYS_EN_TO_RU, MONTHS_RU, WEEKDAYS_RU,
    date_to_ru
)

logger = logging.getLogger(__name__)

def get_group_id():
    val = os.environ.get("GROUP_CHAT_ID", "")
    try:
        return int(val) if val else None
    except:
        return None


def send_to_group(bot, text, parse_mode="HTML"):
    """Группа чатына хабарлама жибериу"""
    gid = get_group_id()
    if not gid:
        return False
    try:
        bot.send_message(gid, text, parse_mode=parse_mode)
        return True
    except Exception as e:
        logger.warning(f"send_to_group: {e}")
        return False


def register(bot):

    @bot.message_handler(
        commands=["кесте", "kesте", "schedule"],
        func=lambda m: m.chat.type in ("group", "supergroup"))
    def group_schedule(message):
        """Группа чатында бүгинги сабақ кесте"""
        today = DAYS_EN_TO_RU.get(now_uz().strftime("%A"), "")
        with db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT subject,time FROM schedule WHERE day=%s ORDER BY time", (today,))
            lessons = cursor.fetchall()
        if not lessons:
            bot.reply_to(message, f"📭 Бүгин ({today}) сабақ жоқ.")
            return
        text = f"📅 <b>Бүгинги сабақ кесте — {today}</b>\n\n"
        for i, (subject, time_) in enumerate(lessons, 1):
            text += f"{i}-пара 🕐 <b>{time_}</b> — {subject}\n"
        bot.reply_to(message, text)

    @bot.message_handler(
        commands=["ертең", "erten", "tomorrow"],
        func=lambda m: m.chat.type in ("group", "supergroup"))
    def group_tomorrow(message):
        """Группа чатында ертенги сабақ кесте"""
        from datetime import timedelta
        tomorrow = DAYS_EN_TO_RU.get(
            (now_uz() + timedelta(days=1)).strftime("%A"), "")
        with db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT subject,time FROM schedule WHERE day=%s ORDER BY time", (tomorrow,))
            lessons = cursor.fetchall()
        if not lessons:
            bot.reply_to(message, f"📭 Ертең ({tomorrow}) сабақ жоқ.")
            return
        text = f"📅 <b>Ертенги сабақ кесте — {tomorrow}</b>\n\n"
        for i, (subject, time_) in enumerate(lessons, 1):
            text += f"{i}-пара 🕐 <b>{time_}</b> — {subject}\n"
        bot.reply_to(message, text)

    @bot.message_handler(
        commands=["список", "spisok", "list"],
        func=lambda m: m.chat.type in ("group", "supergroup"))
    def group_student_list(message):
        """Группа чатында студентлер дизими"""
        with db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT full_name FROM students "
                "WHERE full_name IS NOT NULL ORDER BY full_name")
            rows = cursor.fetchall()
        if not rows:
            bot.reply_to(message, "📭 Список бос.")
            return
        text = f"📋 <b>Студентлер дизими ({len(rows)}):</b>\n\n"
        for i, (name,) in enumerate(rows, 1):
            text += f"{i}. {name}\n"
        bot.reply_to(message, text)

    @bot.message_handler(
        commands=["жаңалық", "news"],
        func=lambda m: m.chat.type in ("group", "supergroup"))
    def group_latest_news(message):
        """Группа чатында соңғы жаңалық"""
        with db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT content,author_username,date FROM user_news "
                "ORDER BY date DESC LIMIT 3")
            rows = cursor.fetchall()
        if not rows:
            bot.reply_to(message, "📭 Жаңалық жоқ.")
            return
        text = "📰 <b>Соңғы жаңалықлар:</b>\n\n"
        for r in rows:
            text += f"👤 @{r[1]}\n📌 {r[0]}\n🕐 {r[2]}\n{'─'*20}\n"
        bot.reply_to(message, text)

    @bot.message_handler(
        commands=["помощь", "help", "көмек"],
        func=lambda m: m.chat.type in ("group", "supergroup"))
    def group_help(message):
        """Группа чатында командалар дизими"""
        text = (
            "🤖 <b>Бот командалары (группа чаты):</b>\n\n"
            "/кесте — Бүгинги сабақ кестеси\n"
            "/ертең — Ертеңги сабақ кестеси\n"
            "/список — Студентлер дизими\n"
            "/жаңалық — Соңғы жаңалықлар\n"
            "/көмек — Командалар дизими\n\n"
            "📌 Толық мүмкинликлер үшын ботқа жеке жазыңыз!"
        )
        bot.reply_to(message, text)

    # Группа чатына қосылған гезде сәлем
    @bot.message_handler(
        content_types=["new_chat_members"],
        func=lambda m: m.chat.type in ("group", "supergroup"))
    def group_new_member(message):
        for member in message.new_chat_members:
            if member.id == bot.get_me().id:
                # Бот қосылды — adminге ID жібер
                from handlers.common import ADMIN_IDS
                for aid in ADMIN_IDS:
                    try:
                        bot.send_message(aid,
                            f"✅ <b>Бот группа чатына қосылды!</b>\n\n"
                            f"📛 Группа: <b>{message.chat.title}</b>\n"
                            f"🆔 GROUP_CHAT_ID: <code>{message.chat.id}</code>\n\n"
                            f"Render → Environment → GROUP_CHAT_ID-ге усы санды қос!")
                    except: pass
                bot.send_message(message.chat.id,
                    "👋 <b>Сәлем, S6-DI-23!</b>\n\n"
                    "Мен сизлердиң группа ботыңызбан! 🤖\n\n"
                    "Командалар үшын /көмек басыңыз.")
            else:
                name = member.first_name or "Студент"
                bot.send_message(message.chat.id,
                    f"👋 <b>{name}</b> группаға хош келдиң! 🎉")
