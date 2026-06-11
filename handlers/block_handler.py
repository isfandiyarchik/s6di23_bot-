from database import db_cursor, now_uz
from handlers.common import (
    is_admin, is_blocked, check_access, check_access_cb,
    add_to_blocked_cache, remove_from_blocked_cache,
    ADMIN_IDS, back_menu, block_submenu, admin_menu
)

def register(bot):
    ca = check_access(bot)
    
    @bot.message_handler(func=lambda m: m.text == "🔒 Блок басқарыу")
    @ca
    def block_management(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        bot.send_message(message.chat.id, "🔒 <b>Блок басқарыу</b>", reply_markup=block_submenu())

    @bot.message_handler(func=lambda m: m.text == "🚫 Студентти блоклау")
    @ca
    def block_user_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        msg = bot.send_message(message.chat.id,
            "🚫 ID жазыңыз:\n(ямаса <code>ID;себеп</code>)", reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_block_user)

    def handle_block_user(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "🔒 Блок басқарыу", reply_markup=block_submenu()); return
        try:
            parts = [p.strip() for p in message.text.split(";")]
            uid = int(parts[0])
            reason = parts[1] if len(parts) > 1 else "Себеп көрсетилмеген"
        except (ValueError, IndexError):
            msg = bot.send_message(message.chat.id, "❌ Дұрыс ID жазыңыз:", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_block_user); return
        if uid in ADMIN_IDS:
            bot.send_message(message.chat.id, "❌ Admin-ди блоклауға болмайды!", reply_markup=block_submenu()); return
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO blocked_users(user_id,reason) VALUES(%s,%s) "
                    "ON CONFLICT(user_id) DO UPDATE SET reason=excluded.reason", (uid, reason))
                conn.commit()
            add_to_blocked_cache(uid)
            bot.send_message(message.chat.id,
                f"✅ <code>{uid}</code> блокланды!\nСебеп: {reason}", reply_markup=block_submenu())
            try: bot.send_message(uid, "⛔ Сиз блокландыңыз. Admin-ге хабарласыңыз.")
            except: pass
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=block_submenu())

    @bot.message_handler(func=lambda m: m.text == "✅ Блоктан шығарыу")
    @ca
    def unblock_user_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT user_id,reason FROM blocked_users")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Блокланған жоқ.", reply_markup=block_submenu()); return
        text = "✅ <b>Блоктан шығарыу — ID жазыңыз:</b>\n\n"
        for r in rows:
            text += f"🆔 <code>{r[0]}</code> — {r[1]}\n"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_unblock_user)

    def handle_unblock_user(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "🔒 Блок басқарыу", reply_markup=block_submenu()); return
        try:
            uid = int(message.text.strip())
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Тек сан ID жазыңыз:", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_unblock_user); return
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("DELETE FROM blocked_users WHERE user_id=%s", (uid,))
                conn.commit()
            remove_from_blocked_cache(uid)
            bot.send_message(message.chat.id,
                f"✅ <code>{uid}</code> блоктан шығарылды!", reply_markup=block_submenu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=block_submenu())

    @bot.message_handler(func=lambda m: m.text == "📋 Блокланғанлар дизими")
    @ca
    def show_blocked_list(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT user_id,reason,blocked_at FROM blocked_users ORDER BY blocked_at DESC")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Блокланған жоқ.", reply_markup=block_submenu()); return
        text = f"🔒 <b>Блокланғанлар ({len(rows)}):</b>\n\n"
        for r in rows:
            text += f"🆔 <code>{r[0]}</code>\n📝 {r[1]}\n📅 {r[2]}\n{'─'*20}\n"
        bot.send_message(message.chat.id, text, reply_markup=block_submenu())
