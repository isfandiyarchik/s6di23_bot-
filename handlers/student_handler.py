from database import db_cursor, now_uz
from handlers.common import (
    is_admin, check_access,
    parse_birth_date, clean_hemis,
    back_menu, student_submenu, admin_menu,
    _state_cache, _state_cache_lock
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "👤 Студент басқарыу")
    @ca
    def student_management(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        bot.send_message(message.chat.id, "👤 <b>Студент басқарыу</b>", reply_markup=student_submenu())

    @bot.message_handler(func=lambda m: m.text == "➕ Студент қосыу/өзгертиу")
    @ca
    def student_add_or_edit_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,full_name,username FROM students ORDER BY full_name")
            rows = cursor.fetchall()
        header = ("➕ <b>Студент қосыу / Өзгертиу:</b>\n\n🆕 <b>Жаңа қосыу:</b>\n"
                  "<code>таза;ФИО;Тууылған күни;Тел;HEMIS;TelegramID</code>\n\n"
                  "✏️ <b>Өзгертиу:</b> студент ID-ін жазыңыз\n" + "─"*30 + "\n")
        if not rows:
            msg = bot.send_message(message.chat.id, header + "📭 Студентлер жоқ.", reply_markup=back_menu())
            bot.register_next_step_handler(msg, student_add_or_edit); return
        chunks = []; cur = header
        for i, r in enumerate(rows, 1):
            line = f"{i}. 👤 <b>{r[1] or '—'}</b>\n    🆔 <code>{r[0]}</code> | {'@'+r[2] if r[2] else 'username жоқ'}\n"
            if len(cur)+len(line) > 3800: chunks.append(cur); cur = ""
            cur += line
        cur += "─"*30 + "\n⬇️ <b>ID жазыңыз ямаса жаңа студент форматын жибериңиз:</b>"
        chunks.append(cur)
        for chunk in chunks[:-1]: bot.send_message(message.chat.id, chunk)
        msg = bot.send_message(message.chat.id, chunks[-1], reply_markup=back_menu())
        bot.register_next_step_handler(msg, student_add_or_edit)

    def student_add_or_edit(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "👤 Студент басқарыу", reply_markup=student_submenu()); return
        if message.text.strip().lower().startswith(("жаңа;","таза;")):
            parts = [p.strip() for p in message.text.split(";")]
            if len(parts) < 6 or not parts[1] or not parts[5]:
                msg = bot.send_message(message.chat.id,
                    "❌ Формат:\n<code>таза;ФИО;Тууылған күни;Тел;HEMIS;TelegramID</code>", reply_markup=back_menu())
                bot.register_next_step_handler(msg, student_add_or_edit); return
            if not parts[5].lstrip("-").isdigit():
                msg = bot.send_message(message.chat.id, "❌ TelegramID тек сан болуы керек!", reply_markup=back_menu())
                bot.register_next_step_handler(msg, student_add_or_edit); return
            fn = parts[1]
            bd = parse_birth_date(parts[2]) if len(parts) > 2 else ""
            ph = parts[3] if len(parts) > 3 else ""
            hm = parts[4] if len(parts) > 4 else ""
            tg_id = int(parts[5])
            try:
                with db_cursor() as (conn, cursor):
                    cursor.execute("SELECT id,full_name FROM students WHERE id=%s", (tg_id,))
                    ex = cursor.fetchone()
                    if ex:
                        bot.send_message(message.chat.id,
                            f"⚠️ Бұл ID бұрыннан бар!\n👤 {ex[1] or '—'}\n\nӨзгертиу үшын ID: <code>{tg_id}</code>",
                            reply_markup=back_menu())
                        bot.register_next_step_handler(message, student_add_or_edit); return
                    cursor.execute(
                        "INSERT INTO students(id,username,last_active,full_name,birth_date,phone,hemis) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                        (tg_id, None, now_uz(), fn, bd, ph, hm))
                    conn.commit()
                bot.send_message(message.chat.id,
                    f"✅ <b>{fn}</b> қосылды!\n🆔 <code>{tg_id}</code>\n🎓 HEMIS: {hm}\n\n"
                    "📌 Студент ботқа /start берсин.", reply_markup=student_submenu())
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=student_submenu())
            return
        try:
            sid = int(message.text.strip())
        except ValueError:
            msg = bot.send_message(message.chat.id,
                "❌ ID ямаса <code>таза;ФИО;Күн;Тел;HEMIS;TelegramID</code>", reply_markup=back_menu())
            bot.register_next_step_handler(msg, student_add_or_edit); return
        try:
            with db_cursor() as (_, cursor):
                cursor.execute("SELECT id,full_name,birth_date,phone,hemis FROM students WHERE id=%s", (sid,))
                row = cursor.fetchone()
            if not row:
                msg = bot.send_message(message.chat.id, "⚠️ ID табылмады:", reply_markup=back_menu())
                bot.register_next_step_handler(msg, student_add_or_edit); return
            sid, fname, bdate, phone, hemis = row
            text = (f"✏️ <b>Студент:</b>\n"
                    f"👤 {fname or '—'} | 📅 {bdate or '—'} | 📞 {phone or '—'} | 🎓 {hemis or '—'}\n\n"
                    "<code>ФИО;Күн;Тел;HEMIS</code>\nӨзгертпей <b>—</b> жазыңыз.")
            msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
            bot.register_next_step_handler(msg,
                lambda m: student_edit_save(m, sid, fname, bdate, phone, hemis))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=student_submenu())

    def student_edit_save(message, sid, old_fn, old_bd, old_ph, old_hm):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "👤 Студент басқарыу", reply_markup=student_submenu()); return
        try:
            parts = [p.strip() for p in message.text.split(";")]
            if len(parts) != 4: raise ValueError("4 бөлек болуы керек")
            nf = parts[0] if parts[0] != "—" else old_fn
            nb = parse_birth_date(parts[1]) if parts[1] != "—" else old_bd
            np_ = parts[2] if parts[2] != "—" else old_ph
            nh = parts[3] if parts[3] != "—" else old_hm
            with db_cursor() as (conn, cursor):
                cursor.execute(
                    "UPDATE students SET full_name=%s,birth_date=%s,phone=%s,hemis=%s WHERE id=%s",
                    (nf, nb, np_, nh, sid))
                conn.commit()
            bot.send_message(message.chat.id,
                f"✅ <b>{nf}</b> тазаланды!\n🎓 HEMIS: {nh}", reply_markup=student_submenu())
        except Exception as e:
            msg = bot.send_message(message.chat.id,
                f"❌ <code>ФИО;Күн;Тел;HEMIS</code> ({e})", reply_markup=back_menu())
            bot.register_next_step_handler(msg,
                lambda m: student_edit_save(m, sid, old_fn, old_bd, old_ph, old_hm))

    @bot.message_handler(func=lambda m: m.text == "❌ Студент өшириу")
    @ca
    def student_delete_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,full_name,username FROM students ORDER BY full_name")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Студентлер жоқ.", reply_markup=student_submenu()); return
        text = "❌ <b>Студент өшириу — ID жазыңыз:</b>\n\n"
        for r in rows:
            text += f"ID:<code>{r[0]}</code> — {r[1] or '—'} (@{r[2] or '—'})\n"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, delete_student)

    def delete_student(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "👤 Студент басқарыу", reply_markup=student_submenu()); return
        try:
            sid = int(message.text.strip())
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Тек сан ID жазыңыз:", reply_markup=back_menu())
            bot.register_next_step_handler(msg, delete_student); return
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("SELECT full_name FROM students WHERE id=%s", (sid,))
                row = cursor.fetchone()
                if not row:
                    bot.send_message(message.chat.id, "⚠️ Табылмады.", reply_markup=student_submenu()); return
                cursor.execute("DELETE FROM students WHERE id=%s", (sid,))
                cursor.execute("DELETE FROM attendance WHERE student_id=%s", (sid,))
                cursor.execute("DELETE FROM contracts WHERE student_id=%s", (sid,))
                cursor.execute("DELETE FROM contract_payments WHERE student_id=%s", (sid,))
                cursor.execute("DELETE FROM blocked_users WHERE user_id=%s", (sid,))
                cursor.execute("DELETE FROM user_states WHERE user_id=%s", (sid,))
                conn.commit()
            with _state_cache_lock:
                _state_cache.pop(sid, None)
            bot.send_message(message.chat.id, f"✅ <b>{row[0]}</b> өширилди.", reply_markup=student_submenu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=student_submenu())
