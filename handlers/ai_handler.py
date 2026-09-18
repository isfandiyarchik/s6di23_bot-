import logging
import os
import re
import time
from threading import Lock

from database import clear_user_state, get_user_state, set_user_state
from handlers.common import check_access

logger = logging.getLogger(__name__)

_ai_history_lock = Lock()
_ai_chat_history: dict = {}
_ai_last_active: dict = {}
AI_MAX_HISTORY = 20
AI_CONTEXT_SIZE = 10

AI_SYSTEM_PROMPT = (
    "Сен S6-DI-23 студент группасының ақыллы көмекшисең. "
    "БАРЛЫҚ жууапларды тек ҚАРАҚАЛПАҚ тилинде бер. "
    "Пайдаланушы қандай тилде жазса да, жууабыңды тек қарақалпақша жаз. "
    "Жууаплар қысқа, анық, дослык пәнде болсын. "
    "Мысалы: сорау, жууап, оқыўшы, сабақ, билимлендириу т.б."
)


def _md_to_html(text: str) -> str:
    text = re.sub(r"^###?\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__", r"<u>\1</u>", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _ai_try_groq(messages):
    import requests

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY жоқ")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _ai_try_deepseek(messages):
    import requests

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY жоқ")
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def ai_ask(user_id: int, user_message: str) -> str:
    with _ai_history_lock:
        if user_id not in _ai_chat_history:
            _ai_chat_history[user_id] = []
        history_snapshot = list(_ai_chat_history[user_id][-AI_CONTEXT_SIZE:])
        _ai_last_active[user_id] = time.time()

    messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}]
    messages.extend(history_snapshot)
    messages.append({"role": "user", "content": user_message})
    answer = None

    # Тек 1. Groq ҳәм 2. DeepSeek кезеклесиўи
    for fn, args in [
        (_ai_try_groq, (messages,)),
        (_ai_try_deepseek, (messages,)),
    ]:
        try:
            answer = fn(*args)
            break
        except Exception as e:
            logger.error(f"❌ {fn.__name__} қате: {type(e).__name__}: {e}")

    if not answer:
        return (
            "❌ <b>AI уақытынша жұмыс ислемейди.</b>\n\n"
            "Сервислер жууап бермеди.\nКейинирек қайталаңыз."
        )

    with _ai_history_lock:
        _ai_chat_history[user_id].append(
            {"role": "user", "content": user_message}
        )
        _ai_chat_history[user_id].append(
            {"role": "assistant", "content": answer}
        )
        if len(_ai_chat_history[user_id]) > AI_MAX_HISTORY:
            _ai_chat_history[user_id] = _ai_chat_history[user_id][
                -AI_MAX_HISTORY:
            ]

    return answer


def ai_clear_history_mem(user_id: int):
    with _ai_history_lock:
        _ai_chat_history.pop(user_id, None)
        _ai_last_active.pop(user_id, None)


def cleanup_ai_history():
    now_t = time.time()
    with _ai_history_lock:
        inactive = [
            uid for uid, t in _ai_last_active.items() if now_t - t > 7200
        ]
        for uid in inactive:
            _ai_chat_history.pop(uid, None)
            _ai_last_active.pop(uid, None)
    if inactive:
        logger.info(
            f"AI history cleanup: {len(inactive)} пайдаланушы тазаланды"
        )


def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "🤖 AI Көмекши")
    @ca
    def ai_menu(message):
        uid = message.from_user.id
        set_user_state(uid, "ai_chat")
        from telebot import types

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("🗑 Тарихты тазалау")
        markup.row("⬅️ Артқа")
        bot.send_message(
            message.chat.id,
            "🤖 <b>AI Көмекши иске қосылды!</b>\n\n"
            "✏️ Кез-келген сорауыңызды жазыңыз.\n\n"
            "⚡ <i>Groq → DeepSeek (автоматты резерв)</i>",
            reply_markup=markup,
            parse_mode="HTML",
        )

    @bot.message_handler(
        func=lambda m: m.text == "🗑 Тарихты тазалау"
        and get_user_state(m.from_user.id) == "ai_chat"
    )
    @ca
    def ai_clear_cmd(message):
        ai_clear_history_mem(message.from_user.id)
        bot.send_message(
            message.chat.id,
            "✅ <b>AI тарихы тазаланды!</b>\nТаза сөйлесиу басланды.",
            parse_mode="HTML",
        )

    @bot.message_handler(
        content_types=["text"],
        func=lambda m: get_user_state(m.from_user.id) == "ai_chat"
        and m.text not in ("⬅️ Артқа", "🗑 Тарихты тазалау"),
    )
    @ca
    def ai_chat_handler(message):
        text = message.text.strip()
        if not text:
            bot.send_message(message.chat.id, "✏️ Сорауыңызды жазыңыз.")
            return
        bot.send_chat_action(message.chat.id, "typing")
        wait_msg = bot.send_message(
            message.chat.id, "⏳ <i>AI ойланып атыр...</i>", parse_mode="HTML"
        )
        answer = ai_ask(message.from_user.id, text)
        try:
            bot.delete_message(message.chat.id, wait_msg.message_id)
        except Exception:
            pass
        try:
            bot.send_message(
                message.chat.id, f"🤖 {_md_to_html(answer)}", parse_mode="HTML"
            )
        except Exception:
            bot.send_message(message.chat.id, f"🤖 {answer}")
