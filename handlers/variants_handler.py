from telebot import types
from database import db_cursor
from handlers.common import (
    is_admin, check_access, check_access_cb,
    back_menu, panler_admin_submenu, main_menu,
    set_user_state, clear_user_state
)
from database import set_user_state, clear_user_state

def register(bot):
    ca = check_access(bot)
    cacb = check_access_cb(bot)

    @bot.message_handler(func=lambda m: m.text == "📖 Пәнлер")
    @ca
    def show_variants_menu(message):
        with db_cursor() as (_,cursor):
            cursor.execute("SELECT subject,COUNT(*) as cnt FROM test_variants GROUP BY subject ORDER BY subject")
            rows=cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id,"📭 Еле вариант жүклемеген.",
                reply_markup=main_menu(message.from_user.id)); return
        markup=types.InlineKeyboardMarkup()
        for subj,cnt in rows:
            markup.add(types.InlineKeyboardButton(text=f"📖 {subj} ({cnt})",callback_data=f"var_subj_{subj}"))
        bot.send_message(message.chat.id,"📖 <b>Пәнлер</b>\n\nПәнди таңлаңыз:",reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("var_subj_"))
    @cacb
    def show_variants_by_subject(call):
        subj=call.data.replace("var_subj_","")
        with db_cursor() as (_,cursor):
            cursor.execute(
                "SELECT id,file_name,file_type,date FROM test_variants WHERE subject=%s ORDER BY date DESC",(subj,))
            rows=cursor.fetchall()
        if not rows:
            bot.answer_callback_query(call.id,"Бұл пәнде файл жоқ."); return
        markup=types.InlineKeyboardMarkup()
        for r in rows:
            icon={"photo":"🖼","document":"📄","video":"🎬"}.get(r[2],"📎")
            name=r[1] or f"Файл #{r[0]}"
            markup.add(types.InlineKeyboardButton(text=f"{icon} {name}",callback_data=f"var_file_{r[0]}"))
        markup.add(types.InlineKeyboardButton("◀️ Артқа",callback_data="var_back"))
        bot.edit_message_text(f"📖 <b>{subj}</b>\n\nФайлды таңлаңыз:",
            call.message.chat.id,call.message.message_id,reply_markup=markup,parse_mode="HTML")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("var_file_"))
    @cacb
    def send_variant_file(call):
        try: vid=int(call.data.replace("var_file_",""))
        except:
            bot.answer_callback_query(call.id,"Қате ID."); return
        with db_cursor() as (_,cursor):
            cursor.execute(
                "SELECT file_id,file_type,file_name,subject FROM test_variants WHERE id=%s",(vid,))
            row=cursor.fetchone()
        if not row:
            bot.answer_callback_query(call.id,"Файл табылмады."); return
        file_id,file_type,file_name,subject=row
        cap=f"📖 <b>{subject}</b>\n📎 {file_name or ''}"
        try:
            if file_type=="photo": bot.send_photo(call.message.chat.id,file_id,caption=cap)
            elif file_type=="video": bot.send_video(call.message.chat.id,file_id,caption=cap)
            else: bot.send_document(call.message.chat.id,file_id,caption=cap)
            bot.answer_callback_query(call.id,"✅ Жиберилди!")
        except Exception as e:
            bot.answer_callback_query(call.id,f"❌ Қате: {e}")

    @bot.callback_query_handler(func=lambda c: c.data == "var_back")
    @cacb
    def variants_back(call):
        with db_cursor() as (_,cursor):
            cursor.execute("SELECT subject,COUNT(*) as cnt FROM test_variants GROUP BY subject ORDER BY subject")
            rows=cursor.fetchall()
        if not rows:
            bot.edit_message_text("📭 Пәнлер жоқ.",call.message.chat.id,call.message.message_id); return
        markup=types.InlineKeyboardMarkup()
        for subj,cnt in rows:
            markup.add(types.InlineKeyboardButton(text=f"📖 {subj} ({cnt})",callback_data=f"var_subj_{subj}"))
        bot.edit_message_text("📖 <b>Пәнлер</b>\n\nПәнди таңлаңыз:",
            call.message.chat.id,call.message.message_id,reply_markup=markup,parse_mode="HTML")
        bot.answer_callback_query(call.id)

    # ── ПӘН БАСҚАРЫУ ──────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "📖 Пән басқарыу")
    @ca
    def panler_admin(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id,"🚫"); return
        bot.send_message(message.chat.id,"📖 <b>Пән басқарыу</b>",reply_markup=panler_admin_submenu())

    @bot.message_handler(func=lambda m: m.text == "➕ Пән қосыу")
    @ca
    def add_variant_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id,"🚫"); return
        msg=bot.send_message(message.chat.id,"📖 <b>Пәнниң атын жазыңыз:</b>",reply_markup=back_menu())
        bot.register_next_step_handler(msg,handle_variant_subject)

    def handle_variant_subject(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text=="⬅️ Артқа":
            bot.send_message(message.chat.id,"📖 Пән басқарыу",reply_markup=panler_admin_submenu()); return
        subject=message.text.strip()
        if len(subject)<2 or len(subject)>100:
            msg=bot.send_message(message.chat.id,"❌ Пән атын дұрыс жазыңыз (2-100 таңба):",reply_markup=back_menu())
            bot.register_next_step_handler(msg,handle_variant_subject); return
        set_user_state(message.from_user.id,f"variant:{subject}")
        msg=bot.send_message(message.chat.id,f"📤 <b>{subject}</b>\n\nФайл жибериңиз:",reply_markup=back_menu())
        bot.register_next_step_handler(msg,lambda m: handle_variant_file(m,subject))

    def handle_variant_file(message,subject):
        if not is_admin(message.from_user.id): return
        if message.text and message.text=="⬅️ Артқа":
            clear_user_state(message.from_user.id)
            bot.send_message(message.chat.id,"📖 Пән басқарыу",reply_markup=panler_admin_submenu()); return
        uid=message.from_user.id
        file_id=file_type=file_name=None
        if message.document:
            file_id=message.document.file_id; file_type="document"
            file_name=message.document.file_name or "Файл"
        elif message.photo:
            file_id=message.photo[-1].file_id; file_type="photo"; file_name="Фото"
        elif message.video:
            file_id=message.video.file_id; file_type="video"
            file_name=message.video.file_name or "Видео"
        else:
            msg=bot.send_message(message.chat.id,"⚠️ Файл, фото ямаса видео жибериңиз:",reply_markup=back_menu())
            bot.register_next_step_handler(msg,lambda m: handle_variant_file(m,subject)); return
        try:
            with db_cursor() as (conn,cursor):
                cursor.execute(
                    "INSERT INTO test_variants(subject,file_id,file_type,file_name,uploader_id) VALUES(%s,%s,%s,%s,%s)",
                    (subject,file_id,file_type,file_name,uid))
                conn.commit()
            clear_user_state(uid)
            bot.send_message(message.chat.id,f"✅ <b>{subject}</b>\n📎 {file_name} қосылды!",
                reply_markup=panler_admin_submenu())
        except Exception as e:
            bot.send_message(message.chat.id,f"❌ DB қатеси: {e}",reply_markup=panler_admin_submenu())

    @bot.message_handler(func=lambda m: m.text == "📎 Пәнге файл қосыу")
    @ca
    def add_file_to_existing_subject(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id,"🚫"); return
        with db_cursor() as (_,cursor):
            cursor.execute("SELECT subject,COUNT(*) as cnt FROM test_variants GROUP BY subject ORDER BY subject")
            rows=cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id,"📭 Еле пән жоқ.",reply_markup=panler_admin_submenu()); return
        markup=types.InlineKeyboardMarkup()
        for subj,cnt in rows:
            markup.add(types.InlineKeyboardButton(
                text=f"📖 {subj} ({cnt} файл)",callback_data=f"addfile_subj_{subj}"))
        bot.send_message(message.chat.id,"📎 <b>Қай пәнге файл қосасыз?</b>",reply_markup=markup)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("addfile_subj_"))
    @cacb
    def addfile_subject_selected(call):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id,"🚫"); return
        subject=call.data.replace("addfile_subj_","")
        bot.answer_callback_query(call.id)
        with db_cursor() as (_,cursor):
            cursor.execute("SELECT COUNT(*) FROM test_variants WHERE subject=%s",(subject,))
            cnt=cursor.fetchone()[0]
        markup=types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⏭ Тайын"); markup.row("⬅️ Артқа")
        msg=bot.send_message(call.message.chat.id,
            f"📖 <b>{subject}</b> — ағымда {cnt} файл бар.\n\n"
            "📤 Файл жибериңиз.\n<i>Бари жиберилгеннен кейин <b>⏭ Тайын</b> басыңыз.</i>",
            reply_markup=markup)
        bot.register_next_step_handler(msg,lambda m: handle_addfile_loop(m,subject))

    def handle_addfile_loop(message,subject):
        if not is_admin(message.from_user.id): return
        if message.text and message.text=="⬅️ Артқа":
            bot.send_message(message.chat.id,"📖 Пән басқарыу",reply_markup=panler_admin_submenu()); return
        if message.text and message.text=="⏭ Тайын":
            with db_cursor() as (_,cursor):
                cursor.execute("SELECT COUNT(*) FROM test_variants WHERE subject=%s",(subject,))
                total=cursor.fetchone()[0]
            bot.send_message(message.chat.id,
                f"✅ <b>{subject}</b> пәни тазаланды!\n📂 Барлығы: <b>{total} файл</b>",
                reply_markup=panler_admin_submenu()); return
        file_id=file_type=file_name=None
        if message.document:
            file_id=message.document.file_id; file_type="document"
            file_name=message.document.file_name or "Файл"
        elif message.photo:
            file_id=message.photo[-1].file_id; file_type="photo"; file_name="Фото"
        elif message.video:
            file_id=message.video.file_id; file_type="video"
            file_name=message.video.file_name or "Видео"
        else:
            markup=types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⏭ Тайын"); markup.row("⬅️ Артқа")
            msg=bot.send_message(message.chat.id,"⚠️ Тек файл, фото ямаса видео жибериңиз:",reply_markup=markup)
            bot.register_next_step_handler(msg,lambda m: handle_addfile_loop(m,subject)); return
        try:
            with db_cursor() as (conn,cursor):
                cursor.execute(
                    "INSERT INTO test_variants(subject,file_id,file_type,file_name,uploader_id) VALUES(%s,%s,%s,%s,%s)",
                    (subject,file_id,file_type,file_name,message.from_user.id))
                conn.commit()
            markup=types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("⏭ Тайын"); markup.row("⬅️ Артқа")
            msg=bot.send_message(message.chat.id,
                f"✅ <b>{file_name}</b> қосылды!\nКелесини жибериңиз ямаса <b>⏭ Тайын</b>:",reply_markup=markup)
            bot.register_next_step_handler(msg,lambda m: handle_addfile_loop(m,subject))
        except Exception as e:
            bot.send_message(message.chat.id,f"❌ DB қатеси: {e}",reply_markup=panler_admin_submenu())

    @bot.message_handler(func=lambda m: m.text == "✏️ Пән атын өзгертиу")
    @ca
    def edit_variant_subject_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id,"🚫"); return
        with db_cursor() as (_,cursor):
            cursor.execute("SELECT DISTINCT subject FROM test_variants ORDER BY subject")
            rows=cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id,"📭 Пәнлер жоқ.",reply_markup=panler_admin_submenu()); return
        text="✏️ <b>Қай пәнниң атын өзгертесиз?</b>\n\nПәнниң атын жазыңыз (тап солай):\n\n"
        for i,r in enumerate(rows,1): text+=f"{i}. <b>{r[0]}</b>\n"
        msg=bot.send_message(message.chat.id,text,reply_markup=back_menu())
        bot.register_next_step_handler(msg,handle_variant_subject_edit_old)

    def handle_variant_subject_edit_old(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text=="⬅️ Артқа":
            bot.send_message(message.chat.id,"📖 Пән басқарыу",reply_markup=panler_admin_submenu()); return
        old_subject=message.text.strip()
        with db_cursor() as (_,cursor):
            cursor.execute("SELECT COUNT(*) FROM test_variants WHERE subject=%s",(old_subject,))
            cnt=cursor.fetchone()[0]
        if cnt==0:
            msg=bot.send_message(message.chat.id,"⚠️ Бұл атта пән табылмады. Қайта жазыңыз:",reply_markup=back_menu())
            bot.register_next_step_handler(msg,handle_variant_subject_edit_old); return
        msg=bot.send_message(message.chat.id,
            f"✏️ <b>{old_subject}</b> — {cnt} файл\n\nТаза атын жазыңыз:",reply_markup=back_menu())
        bot.register_next_step_handler(msg,lambda m: handle_variant_subject_edit_save(m,old_subject))

    def handle_variant_subject_edit_save(message,old_subject):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text=="⬅️ Артқа":
            bot.send_message(message.chat.id,"📖 Пән басқарыу",reply_markup=panler_admin_submenu()); return
        new_subject=message.text.strip()
        if len(new_subject)<2 or len(new_subject)>100:
            msg=bot.send_message(message.chat.id,"❌ 2-100 таңба болыуы керек:",reply_markup=back_menu())
            bot.register_next_step_handler(msg,lambda m: handle_variant_subject_edit_save(m,old_subject)); return
        try:
            with db_cursor() as (conn,cursor):
                cursor.execute("UPDATE test_variants SET subject=%s WHERE subject=%s",(new_subject,old_subject))
                cnt=cursor.rowcount; conn.commit()
            bot.send_message(message.chat.id,
                f"✅ <b>{old_subject}</b> → <b>{new_subject}</b>\n{cnt} файл тазаланды!",
                reply_markup=panler_admin_submenu())
        except Exception as e:
            bot.send_message(message.chat.id,f"❌ DB қатеси: {e}",reply_markup=panler_admin_submenu())

    @bot.message_handler(func=lambda m: m.text == "🗑 Пән өшириу")
    @ca
    def delete_variant_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id,"🚫"); return
        with db_cursor() as (_,cursor):
            cursor.execute("SELECT id,subject,file_name,file_type FROM test_variants ORDER BY subject")
            rows=cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id,"📭 Вариантлар жоқ.",reply_markup=panler_admin_submenu()); return
        text="🗑 <b>Пән/вариант өшириу:</b>\n\n"
        for r in rows:
            icon={"photo":"🖼","document":"📄","video":"🎬"}.get(r[3],"📎")
            text+=f"ID:<code>{r[0]}</code> | {r[1]} | {icon} {r[2] or '—'}\n"
        text+="\nID ямаса <code>all</code> жазыңыз:"
        msg=bot.send_message(message.chat.id,text,reply_markup=back_menu())
        bot.register_next_step_handler(msg,handle_delete_variant)

    def handle_delete_variant(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text=="⬅️ Артқа":
            bot.send_message(message.chat.id,"📖 Пән басқарыу",reply_markup=panler_admin_submenu()); return
        try:
            with db_cursor() as (conn,cursor):
                if message.text.strip().lower()=="all":
                    cursor.execute("DELETE FROM test_variants")
                    d=cursor.rowcount; conn.commit()
                    bot.send_message(message.chat.id,f"✅ {d} вариант өширилди.",reply_markup=panler_admin_submenu())
                else:
                    try: rid=int(message.text.strip())
                    except ValueError:
                        msg=bot.send_message(message.chat.id,
                            "❌ ID ямаса <code>all</code> жазыңыз:",reply_markup=back_menu())
                        bot.register_next_step_handler(msg,handle_delete_variant); return
                    cursor.execute("SELECT file_name,subject FROM test_variants WHERE id=%s",(rid,))
                    row=cursor.fetchone()
                    if not row:
                        bot.send_message(message.chat.id,"⚠️ Табылмады.",reply_markup=panler_admin_submenu()); return
                    cursor.execute("DELETE FROM test_variants WHERE id=%s",(rid,))
                    conn.commit()
                    bot.send_message(message.chat.id,
                        f"✅ <b>{row[1]} — {row[0]}</b> өширилди.",reply_markup=panler_admin_submenu())
        except Exception as e:
            bot.send_message(message.chat.id,f"❌ DB қатеси: {e}",reply_markup=panler_admin_submenu())
