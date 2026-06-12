from database import db_cursor, now_uz
from handlers.common import (
    is_admin, check_access, user_step_check,
    send_to_students, send_long_message,
    get_online_status, _is_online,
    get_birthday_info, clean_hemis,
    ALLOWED_DELETE_TABLES,
    back_menu, admin_menu, delete_submenu, main_menu
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "👮 Админ панель")
    @ca
    def admin_panel(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫 Сиз админ емессиз!"); return
        bot.send_message(message.chat.id, "👮 <b>Админ панель</b>", reply_markup=admin_menu())

    @bot.message_handler(func=lambda m: m.text == "⬅️ Артқа")
    @ca
    def go_back(message):
        uid = message.from_user.id
        from database import get_user_state, clear_user_state, set_user_state
        from handlers.common import (
            materials_menu, gallery_menu, sabak_menu,
            panler_admin_submenu
        )
        mode = get_user_state(uid)
        clear_user_state(uid)
        try:
            if mode == "materials":
                bot.send_message(message.chat.id, "📚 Сабақ материаллары", reply_markup=materials_menu())
            elif mode == "gallery":
                bot.send_message(message.chat.id, "📷 Фото/Видео", reply_markup=gallery_menu())
            elif mode == "ai_chat":
                bot.send_message(message.chat.id, "🏠 Бас меню", reply_markup=main_menu(uid))
            elif mode and mode.startswith("variant:") and is_admin(uid):
                bot.send_message(message.chat.id, "📖 Пән басқарыу", reply_markup=panler_admin_submenu())
            elif mode == "sebep_text":
                bot.send_message(message.chat.id, "📊 Сабақ/Ертеңге", reply_markup=sabak_menu())
            elif mode and mode.startswith("sebep_file:"):
                set_user_state(uid, "sebep_text")
                bot.send_message(message.chat.id, "❌ <b>Себебиңизди қайта жазыңыз:</b>", reply_markup=back_menu())
            else:
                bot.send_message(message.chat.id, "🏠 Бас меню", reply_markup=main_menu(uid))
        except Exception as e:
            try: bot.send_message(message.chat.id, "🏠 Бас меню", reply_markup=main_menu(uid))
            except: pass

    @bot.message_handler(func=lambda m: m.text == "⬅️ Админге қайтыу")
    @ca
    def go_back_admin(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫", reply_markup=main_menu(message.from_user.id)); return
        from database import clear_user_state
        clear_user_state(message.from_user.id)
        bot.send_message(message.chat.id, "👮 <b>Админ панель</b>", reply_markup=admin_menu())

    @bot.message_handler(func=lambda m: m.text in [
        "👥 Студентлер","❗ Сабақ болмайды","📈 Статистика","📩 Ус/Ша келген"])
    @ca
    def admin_panel_actions(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫 Сиз админ емессиз!"); return

        if message.text == "👥 Студентлер":
            with db_cursor() as (_, cursor):
                cursor.execute(
                    "SELECT id,username,last_active,full_name FROM students WHERE started=1 ORDER BY last_active DESC")
                sr = cursor.fetchall()
                cursor.execute(
                    "SELECT id,full_name FROM students WHERE started=0 OR started IS NULL ORDER BY full_name")
                nsr = cursor.fetchall()
            now_t = now_uz()
            oc = sum(1 for r in sr if _is_online(r[2], now_t))
            text = (f"👥 <b>Студентлер дизими</b>\n✅ Ботқа кирген: <b>{len(sr)}</b>\n"
                    f"🟢 Онлайн: <b>{oc}</b> | 🔴 Офлайн: <b>{len(sr)-oc}</b>\n{'─'*30}\n\n")
            if sr:
                text += "📲 <b>Ботқа киргенлер:</b>\n\n"
                for i, r in enumerate(sr, 1):
                    uname = f"@{r[1]}" if r[1] else "—"
                    name = r[3] or uname
                    text += f"{i}. {get_online_status(r[2])}\n   👤 <b>{name}</b>\n   🔗 {uname}\n\n"
            else:
                text += "📭 Еле хеш ким ботқа кирмеген.\n\n"
            if nsr:
                text += f"{'─'*30}\n⏳ <b>Ботқа кирмегенлер ({len(nsr)}):</b>\n"
                for r in nsr:
                    text += f"  • {r[1] or '—'} (ID: <code>{r[0]}</code>)\n"
            send_long_message(bot, message.chat.id, text, reply_markup=admin_menu())

        elif message.text == "📈 Статистика":
            with db_cursor() as (_, cursor):
                cursor.execute("SELECT COUNT(*) FROM students"); s=cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM schedule"); l=cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM user_news"); n=cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM materials"); mat=cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM gallery"); g=cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM suggestions"); sg=cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(DISTINCT date) FROM attendance"); ad=cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM blocked_users"); bl=cursor.fetchone()[0]
            sep1 = "═" * 25
            sep2 = "─" * 25
            stat_text = (
                f"📈 <b>СТАТИСТИКА</b>\n{sep1}\n\n"
                f"👥 Студентлер:    <b>{s}</b>\n"
                f"{sep2}\n"
                f"📅 Сабақлар:      <b>{l}</b>\n"
                f"📰 Жаңалықлар:   <b>{n}</b>\n"
                f"📚 Материаллар:  <b>{mat}</b>\n"
                f"🎞 Галерея:       <b>{g}</b>\n"
                f"{sep2}\n"
                f"💡 Ұсыныслар:     <b>{sg}</b>\n"
                f"📊 Барлау күни:   <b>{ad}</b>\n"
                f"🔒 Блокланған:    <b>{bl}</b>\n"
                f"{sep1}"
            )
            bot.send_message(message.chat.id, stat_text, reply_markup=admin_menu())

        elif message.text == "📩 Ус/Ша келген":
            with db_cursor() as (_, cursor):
                cursor.execute(
                    "SELECT s.content,s.user_id,s.date,st.username "
                    "FROM suggestions s LEFT JOIN students st ON s.user_id=st.id ORDER BY s.date DESC")
                rows = cursor.fetchall()
            if not rows:
                bot.send_message(message.chat.id, "📭 Жоқ.", reply_markup=admin_menu()); return
            chunks = []; cur = f"📩 <b>Ұсыныс/Шағымлар ({len(rows)}):</b>\n\n"
            for r in rows:
                entry = (f"👤 {'@'+r[3] if r[3] else 'Белгісіз'} | <code>{r[1]}</code>\n"
                         f"🕐 {r[2]}\n💬 {r[0]}\n{'─'*25}\n")
                if len(cur)+len(entry)>3800: chunks.append(cur); cur=""
                cur += entry
            if cur: chunks.append(cur)
            for i, chunk in enumerate(chunks):
                bot.send_message(message.chat.id, chunk,
                    reply_markup=admin_menu() if i==len(chunks)-1 else None)

        elif message.text == "❗ Сабақ болмайды":
            send_to_students(bot, text="❗ <b>Назер аударыңыз!</b>\nБүгин сабақ болмайды!")
            bot.send_message(message.chat.id, "✅ Жиберилди!", reply_markup=admin_menu())

    # ── СПИСОК ────────────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "📋 Список")
    @ca
    def show_student_list(message):
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT full_name,birth_date,phone,hemis FROM students ORDER BY full_name")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Список бос.", reply_markup=main_menu(message.from_user.id)); return
        HEMIS_URL = "https://student.nukusii.uz/dashboard/login"
        from telebot import types
        chunks = []
        cur = (f"📋 <b>Студентлер дизими ({len(rows)}):</b>\n"
               f"🎓 <a href='{HEMIS_URL}'>HEMIS Кабинетке кириу →</a>\n\n")
        for i, row in enumerate(rows, 1):
            full_name = row[0] or "—"
            hemis_d = f"<code>{clean_hemis(row[3])}</code>" if clean_hemis(row[3]) else "—"
            phone_d = f"<code>{row[2]}</code>" if row[2] else "—"
            days_left, _ = get_birthday_info(row[1])
            if days_left == 0: prefix="🎂 "; bd_label="🎂 <b>Бүгин тууылған күни!!!</b>"
            elif days_left == 1: prefix="🔔 "; bd_label="🔔 <b>Ертең тууылған күни!</b>"
            elif days_left is not None and days_left<=7: prefix="⏳ "; bd_label=f"⏳ {days_left} күннен кейін туылған күні"
            else: prefix=""; bd_label=None
            entry = f"{'─'*25}\n{prefix}{i2}. <b>{full_name}</b>\n📅 {row[1] or '—'}"
            if bd_label: entry += f"\n{bd_label}"
            entry += f"\n📞 {phone_d}\n🎓 HEMIS: {hemis_d}\n"
            if len(cur)+len(entry)>3800: chunks.append(cur); cur=""
            cur += entry
        if cur: chunks.append(cur)
        hemis_mk = types.InlineKeyboardMarkup()
        hemis_mk.add(types.InlineKeyboardButton("🎓 HEMIS Кабинетке кириу", url=HEMIS_URL))
        for i, chunk in enumerate(chunks):
            if i==len(chunks)-1:
                bot.send_message(message.chat.id, chunk, reply_markup=hemis_mk, disable_web_page_preview=True)
            else:
                bot.send_message(message.chat.id, chunk)
        bot.send_message(message.chat.id, "🏠 Меню:", reply_markup=main_menu(message.from_user.id))

    # ── ҰСЫНЫС ────────────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "💡 Ұсыныс / Шағым")
    @ca
    def suggestion_start(message):
        msg = bot.send_message(message.chat.id,
            "💡 <b>Ұсыныс ямаса шағымыңызды жазыңыз:</b>", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: handle_suggestion(m))

    def handle_suggestion(message):
        if not user_step_check(bot, message): return
        if not message.text:
            msg = bot.send_message(message.chat.id, "✍️ Текст жибериңиз:", reply_markup=back_menu())
            bot.register_next_step_handler(msg, lambda m: handle_suggestion(m)); return
        if message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "🏠 Бас меню", reply_markup=main_menu(message.from_user.id)); return
        if len(message.text) > 1000:
            msg = bot.send_message(message.chat.id, "❌ Текст тым ұзын (макс 1000 таңба).", reply_markup=back_menu())
            bot.register_next_step_handler(msg, lambda m: handle_suggestion(m)); return
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("INSERT INTO suggestions(content,user_id) VALUES(%s,%s)",
                    (message.text, message.from_user.id))
                conn.commit()
            bot.send_message(message.chat.id, "✅ Жиберилди! Рахмет!", reply_markup=main_menu(message.from_user.id))
            from handlers.common import ADMIN_IDS
            for aid in ADMIN_IDS:
                try:
                    fn=message.from_user.first_name or ""; ln=message.from_user.last_name or ""
                    un=f"@{message.from_user.username}" if message.from_user.username else "username жоқ"
                    bot.send_message(aid,
                        f"💡 <b>Таза ұсыныс/шағым:</b>\n\n{message.text}\n\n"
                        f"👤 {fn} {ln}\n🔗 {un}\n🆔 <code>{message.from_user.id}</code>")
                except: pass
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Қате: {e}", reply_markup=main_menu(message.from_user.id))

    # ── ӨШІРУ ──────────────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "🗑 Өшириу")
    @ca
    def delete_management(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        bot.send_message(message.chat.id, "🗑 <b>Өшириу бөлими</b>", reply_markup=delete_submenu())

    @bot.message_handler(func=lambda m: m.text == "🗑 Материал өшириу")
    @ca
    def delete_material_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,file_type,uploader_username,date FROM materials ORDER BY date DESC")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Материаллар жоқ.", reply_markup=delete_submenu()); return
        text = "🗑 <b>Материалларды өшириу:</b>\n\n"
        for r in rows:
            text += f"ID:<code>{r[0]}</code> | {r[1]} | {'@'+r[2] if r[2] else '—'} | {r[3]}\n"
        text += "\n\nID ямаса <code>all</code> жазыңыз:"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: _delete_table_item(m, "materials"))

    @bot.message_handler(func=lambda m: m.text == "🗑 Фото/Видео өшириу")
    @ca
    def delete_gallery_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,file_type,uploader_username,date FROM gallery ORDER BY date DESC")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Галерея бос.", reply_markup=delete_submenu()); return
        text = "🗑 <b>Фото/Видео өшириу:</b>\n\n"
        for r in rows:
            text += f"ID:<code>{r[0]}</code> | {r[1]} | {'@'+r[2] if r[2] else '—'} | {r[3]}\n"
        text += "\n\nID ямаса <code>all</code> жазыңыз:"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: _delete_table_item(m, "gallery"))

    @bot.message_handler(func=lambda m: m.text == "🗑 Жаңалық өшириу")
    @ca
    def delete_news_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,author_username,date,content FROM user_news ORDER BY date DESC")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Жаңалықлар жоқ.", reply_markup=delete_submenu()); return
        text = "🗑 <b>Жаңалықларды өшириу:</b>\n\n"
        for r in rows:
            uname = f"@{r[1]}" if r[1] else "Белгісіз"
            preview = r[3][:40]+"..." if len(r[3])>40 else r[3]
            text += f"ID:<code>{r[0]}</code> | {uname}\n📌 {preview}\n{'─'*20}\n"
        text += "\n\nID ямаса <code>all</code> жазыңыз:"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: _delete_table_item(m, "user_news"))

    def _delete_table_item(message, table):
        if not is_admin(message.from_user.id): return
        if table not in ALLOWED_DELETE_TABLES:
            bot.send_message(message.chat.id, "❌ Қате: рұхсатсыз операция.", reply_markup=delete_submenu()); return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "🗑 Өшириу бөлими", reply_markup=delete_submenu()); return
        try:
            with db_cursor() as (conn, cursor):
                if message.text.strip().lower() == "all":
                    cursor.execute(f"DELETE FROM {table}")
                    d=cursor.rowcount; conn.commit()
                    bot.send_message(message.chat.id, f"✅ {d} жазба өширилди.", reply_markup=delete_submenu())
                else:
                    try: rid=int(message.text.strip())
                    except ValueError:
                        msg=bot.send_message(message.chat.id,
                            "❌ ID ямаса <code>all</code> жазыңыз:", reply_markup=back_menu())
                        bot.register_next_step_handler(msg, lambda m: _delete_table_item(m,table)); return
                    cursor.execute(f"SELECT id FROM {table} WHERE id=%s",(rid,))
                    if not cursor.fetchone():
                        bot.send_message(message.chat.id, "⚠️ Табылмады.", reply_markup=delete_submenu()); return
                    cursor.execute(f"DELETE FROM {table} WHERE id=%s",(rid,))
                    conn.commit()
                    bot.send_message(message.chat.id, f"✅ ID:{rid} өширилди.", reply_markup=delete_submenu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=delete_submenu())
