"""
S6-DI-23 Telegram Bot — Негизги файл
Иске қосыу: python main.py
"""
import os
import logging
import time
from threading import Thread

import telebot
from telebot import apihelper
from flask import Flask

from database import init_db, now_uz
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── BOT & FLASK ───────────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set!")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

@app.route("/")
def home(): return "Bot is alive", 200

@app.route("/health")
def health(): return {"status": "ok", "time": str(now_uz())}, 200

@app.route("/ping")
def ping(): return "pong", 200

# ── INIT ─────────────────────────────────────────────────────
init_db()

# ── HANDLERS IMPORT ───────────────────────────────────────────
# Барлық handler-ларды bot-қа тіркейміз
from handlers import register_all_handlers
register_all_handlers(bot)

# ── SCHEDULER ────────────────────────────────────────────────
from handlers.common import clean_rate_limit, send_to_students as _send_fn

def _send_to_students_wrapper(**kwargs):
    _send_fn(bot, **kwargs)

# AI cleanup функциясы
from handlers.ai_handler import cleanup_ai_history

start_scheduler(
    bot=bot,
    send_to_students_fn=_send_to_students_wrapper,
    clean_rate_limit_fn=clean_rate_limit,
    cleanup_ai_fn=cleanup_ai_history
)

# ── MAIN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    def run_bot():
        while True:
            try:
                bot.infinity_polling(
                    skip_pending=True,
                    timeout=60,
                    long_polling_timeout=30,
                )
            except apihelper.ApiException as e:
                if "409" in str(e):
                    logger.warning("409 Conflict — 30 сек күтемен...")
                    time.sleep(30)
                else:
                    logger.error(f"Telegram API қате: {e}")
                    time.sleep(10)
            except ConnectionError as e:
                logger.warning(f"Байланыс үзилди: {e}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Polling қате: {e}", exc_info=True)
                time.sleep(5)

    Thread(target=run_bot, daemon=True).start()
    logger.info("🤖 S6-DI-23 Bot иске қосылды!")

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
