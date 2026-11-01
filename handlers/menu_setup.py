"""
Telegram менюин (☰ командалар дизими) кодтан орнатыу.
BotFather-дағы Menu Button (HEMIS web-app) пен ески тил/scope дизимлерин
қайта жазады, сонлықтан меню хәр қашан дұрыс көринеди.
"""
import logging
from telebot import types

logger = logging.getLogger(__name__)

COMMANDS = [
    ("start", "🏠 Ботты баслау"),
    ("ai", "🤖 AI Көмекши"),
    ("hemis", "🎓 HEMIS кабинет"),
    ("contacts", "📞 Байланыс"),
    ("contract", "💰 Контракт"),
]
# None = тилге байланыссыз. Telegram тилге арналған дизимди биринши көрсетеди,
# сонлықтан ески дизим қалып қоймас үшын негизги тиллерди де жазамыз.
LANGS = [None, "ru", "kk", "uz", "en"]


def _cmds():
    return [types.BotCommand(c, d) for c, d in COMMANDS]


def setup_all_menus(bot, chat_id=None):
    """Менюди орнатады. Қайтарады: [(ok: bool, тема: str), ...]
    chat_id берилсе — сол чатқа арнайы (ең жоғары басымлылық) орнатады."""
    report = []

    # 1) Командалар: default және all_private_chats scope, хәр тил үшын
    for sname, scope in (("default", None),
                         ("private", types.BotCommandScopeAllPrivateChats())):
        for lang in LANGS:
            label = f"{sname}/{lang or 'any'}"
            try:
                bot.set_my_commands(_cmds(), scope=scope, language_code=lang)
                report.append((True, f"commands {label}"))
            except Exception as e:
                report.append((False, f"commands {label}: {e}"))

    # 2) Menu Button: HEMIS web-app орнына командалар дизими
    try:
        bot.set_chat_menu_button(menu_button=types.MenuButtonCommands())
        report.append((True, "menu button (default)"))
    except Exception as e:
        report.append((False, f"menu button (default): {e}"))

    # 3) Точно чат үшын (клиентке тезлеу жетеди)
    if chat_id is not None:
        try:
            bot.set_chat_menu_button(chat_id=chat_id,
                                     menu_button=types.MenuButtonCommands())
            report.append((True, "menu button (чат)"))
        except Exception as e:
            report.append((False, f"menu button (чат): {e}"))
        try:
            bot.set_my_commands(_cmds(), scope=types.BotCommandScopeChat(chat_id))
            report.append((True, "commands (чат)"))
        except Exception as e:
            report.append((False, f"commands (чат): {e}"))

    return report


def read_state(bot, chat_id):
    """Telegram хазир не көрсетип тұрғанын оқиды (диагностика үшын)."""
    state = {}
    try:
        mb = bot.get_chat_menu_button(chat_id=chat_id)
        state["button"] = getattr(mb, "type", "?")
    except Exception as e:
        state["button"] = f"қате: {e}"
    try:
        cmds = bot.get_my_commands()
        state["commands"] = [c.command for c in cmds]
    except Exception as e:
        state["commands"] = f"қате: {e}"
    return state


def ensure_chat_menu(bot, chat_id):
    """/start гезинде: тек усы чаттың менюин дүзетеди (2 API шақырым)."""
    try:
        bot.set_chat_menu_button(chat_id=chat_id,
                                 menu_button=types.MenuButtonCommands())
        bot.set_my_commands(_cmds(), scope=types.BotCommandScopeChat(chat_id))
    except Exception as e:
        logger.warning(f"ensure_chat_menu({chat_id}): {e}")
