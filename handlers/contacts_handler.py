from database import db_cursor
from handlers.common import (
    is_admin, check_access,
    back_menu, contacts_submenu, main_menu
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "📞 Байланыс")
    @ca
    def show_contacts(message):
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT type,name,phone FROM contacts ORDER BY type,name")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Байланыс мағлұматы жоқ.",
                reply_markup=main_menu(message.from_user.id)); return
        dekanat = [(r[1],r[2]) for r in rows if r[0]=="dekanat"]
        mugallim = [(r[1],r[2]) for r in rows if r[0]=="mugallim"]
        text = "📞 <b>Байланыс</b>\n\n"
        if dekanat:
            text += "🏛 <b>Деканат:</b>\n" + "─"*25 + "\n"
            for name, phone in dekanat:
                text += f"👤 <b>{name}</b>\n📞 <code>{phone}</code>\n" + "─"*25 + "\n"
            text += "\n"
        if mugallim:
            text += "👨‍🏫 <b>Муғаллимлер:</b>\n" + "─"*25 + "\n"
            for name, phone in mugallim:
                text += f"👤 <b>{name}</b>\n📞 <code>{phone}</code>\n" + "─"*25 + "\n"
        bot.send_message(message.chat.id, text, reply_markup=main_menu(message.from_user.id))

    @bot.message_handler(func=lambda m: m.text == "📞 Байланыс басқарыу")
    @ca
    def contacts_management(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        bot.send_message(message.chat.id, "📞 <b>Байланыс басқарыу</b>", reply_markup=contacts_submenu())

    @bot.message_handler(func=lambda m: m.text == "➕ Деканат қосыу")
    @ca
    def add_dekanat_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        msg = bot.send_message(message.chat.id, "🏛 Формат: <code>Аты;Телефон</code>", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: handle_add_contact(m, "dekanat"))

    @bot.message_handler(func=lambda m: m.text == "➕ Муғаллим қосыу")
    @ca
    def add_mugallim_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        msg = bot.send_message(message.chat.id, "👨‍🏫 Формат: <code>Аты;Телефон</code>", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: handle_add_contact(m, "mugallim"))

    def handle_add_contact(message, contact_type):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📞 Байланыс басқарыу", reply_markup=contacts_submenu()); return
        parts = [p.strip() for p in message.text.split(";")]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            msg = bot.send_message(message.chat.id, "❌ Формат: <code>Аты;Телефон</code>", reply_markup=back_menu())
            bot.register_next_step_handler(msg, lambda m: handle_add_contact(m, contact_type)); return
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("INSERT INTO contacts(type,name,phone) VALUES(%s,%s,%s)",
                    (contact_type, parts[0], parts[1]))
                conn.commit()
            icon = "🏛" if contact_type == "dekanat" else "👨‍🏫"
            bot.send_message(message.chat.id, f"✅ {icon} <b>{parts[0]}</b> қосылды!", reply_markup=contacts_submenu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=contacts_submenu())

    @bot.message_handler(func=lambda m: m.text == "❌ Байланыс өшириу")
    @ca
    def delete_contact_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,type,name,phone FROM contacts ORDER BY type,name")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Байланыслар жоқ.", reply_markup=contacts_submenu()); return
        text = "❌ <b>Байланыс өшириу — ID жазыңыз:</b>\n\n"
        for r in rows:
            icon = "🏛" if r[1]=="dekanat" else "👨‍🏫"
            text += f"ID:<code>{r[0]}</code> {icon} {r[2]} | 📞 {r[3]}\n"
        text += "\nID ямаса <code>all</code>:"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_delete_contact)

    def handle_delete_contact(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "📞 Байланыс басқарыу", reply_markup=contacts_submenu()); return
        try:
            with db_cursor() as (conn, cursor):
                if message.text.strip().lower() == "all":
                    cursor.execute("DELETE FROM contacts")
                    d = cursor.rowcount; conn.commit()
                    bot.send_message(message.chat.id, f"✅ {d} байланыс өширилди.", reply_markup=contacts_submenu())
                else:
                    try: cid = int(message.text.strip())
                    except ValueError:
                        msg = bot.send_message(message.chat.id, "❌ ID ямаса all:", reply_markup=back_menu())
                        bot.register_next_step_handler(msg, handle_delete_contact); return
                    cursor.execute("SELECT name FROM contacts WHERE id=%s", (cid,))
                    row = cursor.fetchone()
                    if not row:
                        bot.send_message(message.chat.id, "⚠️ Табылмады.", reply_markup=contacts_submenu()); return
                    cursor.execute("DELETE FROM contacts WHERE id=%s", (cid,))
                    conn.commit()
                    bot.send_message(message.chat.id, f"✅ <b>{row[0]}</b> өширилди.", reply_markup=contacts_submenu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=contacts_submenu())
