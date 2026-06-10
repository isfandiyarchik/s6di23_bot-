import os
import re
import time
import logging
from threading import Lock
from database import get_user_state, set_user_state, clear_user_state
from handlers.common import check_access

logger = logging.getLogger(__name__)

_ai_history_lock = Lock()
_ai_chat_history: dict = {}
_ai_last_active: dict = {}
AI_MAX_HISTORY = 20
AI_CONTEXT_SIZE = 10

AI_SYSTEM_PROMPT = (
    "Сен S6-DI-23 группасының ақыллы көмекшисең. "
    "Сорауларға қысқа, толық және дослық түрде жууап бер. "
    "Пайдаланушы қай тилде жазса, сол тилде жууап бер "
    "(қарақалпақша, қазақша, русский, английский — бари болады)."
)

def _md_to_html(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'__(.+?)__', r'<u>\1</u>', text, flags=re.DOTALL)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return text

def _ai_try_groq(messages):
    import requests
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key: raise ValueError("GROQ_API_KEY жоқ")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"model": "llama-3.3-70b-versatile", "messages": messages,
              "max_tokens": 1000, "temperature": 0.7}, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def _ai_try_openai(messages):
    import requests
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key: raise ValueError("OPENAI_API_KEY жоқ")
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={"model": "gpt-4o-mini", "messages": messages,
              "max_tokens": 1000, "temperature": 0.7}, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def _ai_try_gemini(user_message, history):
    import requests
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key: raise ValueError("GOOGLE_API_KEY жоқ")
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={"system_instruction": {"parts": [{"text": AI_SYSTEM_PROMPT}]},
              "contents": contents,
              "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.7}}, timeout=30)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

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
    for fn, args in [
        (_ai_try_groq, (messages,)),
        (_ai_try_openai, (messages,)),
        (_ai_try_gemini, (user_message, history_snapshot)),
    ]:
        try: answer = fn(*args); break
        except Exception as e:
            logger.error(f"❌ {fn.__name__} қате: {type(e).__name__}: {e}")
    if not answer:
        return ("❌ <b>AI уақытша жұмыс ислемейди.</b>\n\n"
                "Барлық 3 сервис жууап бермеди.\nКейинирек қайталаңыз.")
    with _ai_history_lock:
        _ai_chat_history[user_id].append({"role": "user", "content": user_message})
        _ai_chat_history[user_id].append({"role": "assistant", "content": answer})
        if len(_ai_chat_history[user_id]) > AI_MAX_HISTORY:
            _ai_chat_history[user_id] = _ai_chat_history[user_id][-AI_MAX_HISTORY:]
    return answer

def ai_clear_history_mem(user_id: int):
    with _ai_history_lock:
        _ai_chat_history.pop(user_id, None)
        _ai_last_active.pop(user_id, None)

def cleanup_ai_history():
    now_t = time.time()
    with _ai_history_lock:
        inactive = [uid for uid, t in _ai_last_active.items() if now_t - t > 7200]
        for uid in inactive:
            _ai_chat_history.pop(uid, None)
            _ai_last_active.pop(uid, None)
    if inactive:
        logger.info(f"AI history cleanup: {len(inactive)} пайдаланушы тазаланды")

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
        bot.send_message(message.chat.id,
            "🤖 <b>AI Көмекши иске қосылды!</b>\n\n"
            "✏️ Кез-келген сорауыңызды жазыңыз.\n"
            "🌐 Қай тилде жазсаңыз, сол тилде жууап береди.\n\n"
            "⚡ <i>Groq → OpenAI → Gemini (автоматты резерв)</i>",
            reply_markup=markup)

    @bot.message_handler(func=lambda m: m.text == "🗑 Тарихты тазалау"
                         and get_user_state(m.from_user.id) == "ai_chat")
    @ca
    def ai_clear_cmd(message):
        ai_clear_history_mem(message.from_user.id)
        bot.send_message(message.chat.id,
            "✅ <b>AI тарихы тазаланды!</b>\nТаза сөйлесту басланды.")

    @bot.message_handler(
        content_types=["text"],
        func=lambda m: get_user_state(m.from_user.id) == "ai_chat"
                       and m.text not in ("⬅️ Артқа", "🗑 Тарихты тазалау"))
    @ca
    def ai_chat_handler(message):
        text = message.text.strip()
        if not text:
            bot.send_message(message.chat.id, "✏️ Сұрауыңызды жазыңыз."); return
        bot.send_chat_action(message.chat.id, "typing")
        wait_msg = bot.send_message(message.chat.id, "⏳ <i>AI ойланып атыр...</i>")
        answer = ai_ask(message.from_user.id, text)
        try: bot.delete_message(message.chat.id, wait_msg.message_id)
        except: pass
        try: bot.send_message(message.chat.id, f"🤖 {_md_to_html(answer)}", parse_mode="HTML")
        except: bot.send_message(message.chat.id, f"🤖 {answer}")
