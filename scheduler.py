import time
import logging
from datetime import datetime, timedelta
from threading import Thread
from database import (
    db_cursor, now_uz, cleanup_old_sessions,
    reminder_already_sent, mark_reminder_sent
)

logger = logging.getLogger(__name__)

DAYS_EN_TO_RU = {
    "Monday": "Понедельник", "Tuesday": "Вторник", "Wednesday": "Среда",
    "Thursday": "Четверг", "Friday": "Пятница", "Saturday": "Суббота", "Sunday": "Воскресенье"
}


def start_scheduler(bot, send_to_students_fn, clean_rate_limit_fn, cleanup_ai_fn):
    """Scheduler-ды daemon thread-та иске қосыу"""
    def _run():
        _last_ping = 0
        _last_minute = -1

        while True:
            try:
                now = now_uz()
                h, m_ = now.hour, now.minute
                current_minute = h * 60 + m_

                # DB ping: әр 4 минут сайын
                ping_now = time.time()
                if ping_now - _last_ping >= 240:
                    try:
                        with db_cursor() as (_, cursor):
                            cursor.execute("SELECT 1")
                        _last_ping = ping_now
                    except Exception as e:
                        logger.warning(f"DB ping қате: {e}")

                if current_minute == _last_minute:
                    time.sleep(15)
                    continue
                _last_minute = current_minute

                # ── Таңғы хабарлама 07:30 ──
                if h == 7 and m_ == 30:
                    key = f"morning_{now.strftime('%Y-%m-%d')}"
                    if not reminder_already_sent(key):
                        try:
                            today = DAYS_EN_TO_RU.get(now.strftime("%A"), "")
                            with db_cursor() as (_, cursor):
                                cursor.execute(
                                    "SELECT subject,time FROM schedule WHERE day=%s ORDER BY time", (today,))
                                lessons = cursor.fetchall()
                            msg_ = f"☀️ <b>Қайырлы таң!</b>\n📅 Бүгин: <b>{today}</b>\n\n"
                            if lessons:
                                msg_ += "📖 <b>Бүгинги сабақлар:</b>\n"
                                for i, r in enumerate(lessons, 1):
                                    msg_ += f"  {i}-пара 🕐 {r[1]} — {r[0]}\n"
                            else:
                                msg_ += "📭 Бүгин сабақ жоқ. Демалыңыз! 🎉"
                            send_to_students_fn(text=msg_)
                            mark_reminder_sent(key)
                            logger.info(f"✅ Азанғы хабарлама жиберилди: {key}")
                        except Exception as e:
                            logger.error(f"Таңғы хабарлама қате: {e}", exc_info=True)

                # ── Туылған күн тексеру 09:00 ──
                elif h == 9 and m_ == 0:
                    today_str = now.strftime("%m-%d")
                    try:
                        with db_cursor() as (_, cursor):
                            cursor.execute(
                                "SELECT id,full_name,birth_date FROM students "
                                "WHERE birth_date IS NOT NULL AND birth_date!=''")
                            students_ = cursor.fetchall()
                        for sid, sname, bd in students_:
                            try:
                                if not bd: continue
                                bd_str = str(bd).strip()[:10]
                                if not bd_str: continue
                                bd_dt = datetime.strptime(bd_str, "%Y-%m-%d")
                                if bd_dt.strftime("%m-%d") != today_str: continue
                                bday_key = f"birthday_{sid}_{now.strftime('%Y-%m-%d')}"
                                if reminder_already_sent(bday_key): continue
                                age = now.year - bd_dt.year
                                send_to_students_fn(
                                    text=(
                                        f"🎂 <b>Бүгин {sname}-ның тууылған күни!</b>\n"
                                        f"🎉 Оған {age} жас толды!\n\n"
                                        "Барлық группа атынан құтлықлаймыз! 🎊"))
                                try:
                                    bot.send_message(sid,
                                        f"🎂 <b>Тууылған күниңиз мүбәрек болсын!</b>\n"
                                        f"🎉 Сізге {age} жас толды!\n\n"
                                        "S6-DI-23 группасы атынан ең жыллы тилеклеримизди жоллаймыз! 🎊")
                                except Exception:
                                    pass
                                mark_reminder_sent(bday_key)
                                logger.info(f"🎂 Тууылған күн хабарламасы: {sname}")
                            except Exception as e:
                                logger.warning(f"Birthday check ({sname}): {e}")
                    except Exception as e:
                        logger.error(f"Birthday scheduler: {e}", exc_info=True)

                # ── Тазалау 03:00 ──
                elif h == 3 and m_ == 0:
                    clean_key = f"cleanup_{now.strftime('%Y-%m-%d')}"
                    if not reminder_already_sent(clean_key):
                        try:
                            cleanup_old_sessions()
                            clean_rate_limit_fn()
                            cleanup_ai_fn()
                            with db_cursor() as (conn, cursor):
                                cursor.execute("DELETE FROM ai_history WHERE updated_at < %s",
                                               (now_uz() - timedelta(days=30),))
                                conn.commit()
                            with db_cursor() as (conn, cursor):
                                cursor.execute("DELETE FROM sent_reminders WHERE sent_at < %s",
                                               (now_uz() - timedelta(days=7),))
                                conn.commit()
                            mark_reminder_sent(clean_key)
                            logger.info("✅ Түнги тазалау жуумақланды")
                        except Exception as e:
                            logger.error(f"Тазалау қате: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"auto_scheduler қате: {e}", exc_info=True)

            time.sleep(15)

    t = Thread(target=_run, daemon=True)
    t.start()
    logger.info("⏰ Scheduler иске қосылды")
    return t
