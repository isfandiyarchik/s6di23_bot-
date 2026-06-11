from database import db_cursor, now_uz
from handlers.common import (
    is_admin, check_access, send_long_message, date_to_ru,
    back_menu, contract_submenu, main_menu
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "💰 Контракт")
    @ca
    def show_contract_user(message):
        uid = message.from_user.id
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT total_amount,note FROM contracts WHERE student_id=%s", (uid,))
            contract = cursor.fetchone()
            if not contract:
                bot.send_message(message.chat.id,
                    "📭 Контрактыңыз орнатылмаған.\nАдминге хабарласыңыз.",
                    reply_markup=main_menu(uid)); return
            total = contract[0]; note = contract[1] or ""
            cursor.execute("SELECT COALESCE(SUM(amount),0) FROM contract_payments WHERE student_id=%s", (uid,))
            paid = float(cursor.fetchone()[0])
            remaining = total - paid
            cursor.execute("SELECT amount,date,note FROM contract_payments WHERE student_id=%s ORDER BY date DESC", (uid,))
            payments = cursor.fetchall()
            cursor.execute("""
                SELECT s.full_name,s.id,c.total_amount,COALESCE(SUM(p.amount),0) as paid
                FROM students s JOIN contracts c ON c.student_id=s.id
                LEFT JOIN contract_payments p ON p.student_id=s.id
                WHERE s.full_name IS NOT NULL
                GROUP BY s.full_name,s.id,c.total_amount ORDER BY s.full_name""")
            all_contracts = cursor.fetchall()
        percent = int((paid/total)*100) if total > 0 else 0
        bar = "🟩"*(percent//10) + "⬜"*(10-percent//10)
        text = f"💰 <b>Мениң контрактым</b>\n{'─'*30}\n"
        if note: text += f"📝 {note}\n"
        text += (f"\n💵 Ұлыума: <b>{total:,.0f} сум</b>\n✅ Төленди: <b>{paid:,.0f} сум</b>\n"
                 f"⏳ Қалды: <b>{remaining:,.0f} сум</b>\n{bar} <b>{percent}%</b>\n{'─'*30}\n")
        if payments:
            text += "\n📜 <b>Төлем тарихы:</b>\n"
            for p in payments:
                p_note = f" — {p[2]}" if p[2] else ""
                text += f"  ✅ {date_to_ru(p[1])} | <b>{p[0]:,.0f} сум</b>{p_note}\n"
        else:
            text += "\n📭 Төлем тарихы жоқ.\n"
        if all_contracts:
            text += f"\n{'─'*30}\n📋 <b>Группаның жағдайы ({len(all_contracts)} студент):</b>\n\n"
            for r in all_contracts:
                s_remain = r[2] - float(r[3])
                s_pct = int((float(r[3])/r[2])*100) if r[2] > 0 else 0
                s_bar = "🟩"*(s_pct//10) + "⬜"*(10-s_pct//10)
                me = " 👈 <i>сиз</i>" if r[1] == uid else ""
                if s_remain <= 0:
                    text += f"✅ <b>{r[0]}</b>{me}\n   {s_bar} <b>100%</b> — Толық төленди\n\n"
                else:
                    text += f"⏳ <b>{r[0]}</b>{me}\n   {s_bar} <b>{s_pct}%</b>\n   Қалды: <b>{s_remain:,.0f} сум</b>\n\n"
        send_long_message(bot, message.chat.id, text, reply_markup=main_menu(uid))

    @bot.message_handler(func=lambda m: m.text == "💰 Контракт басқарыу")
    @ca
    def contract_management(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        bot.send_message(message.chat.id, "💰 <b>Контракт басқарыу</b>", reply_markup=contract_submenu())

    @bot.message_handler(func=lambda m: m.text == "💰 Контракт киргизиу")
    @ca
    def contract_set_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT id,full_name FROM students WHERE full_name IS NOT NULL ORDER BY full_name")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Студентлер жоқ.", reply_markup=contract_submenu()); return
        text = "💰 <b>Контракт киргизиу:</b>\nФормат: <code>TelegramID;Сумма;Ескертиу</code>\n\n📋 <b>Студентлер:</b>\n"
        for r in rows: text += f"🆔 <code>{r[0]}</code> — {r[1]}\n"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_contract_set)

    def handle_contract_set(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "💰 Контракт басқарыу", reply_markup=contract_submenu()); return
        parts = [p.strip() for p in message.text.split(";")]
        if len(parts) < 2 or not parts[0].lstrip("-").isdigit():
            msg = bot.send_message(message.chat.id,
                "❌ Формат: <code>TelegramID;Сумма;Ескертиу</code>", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_contract_set); return
        try:
            sid = int(parts[0])
            amount = float(parts[1].replace(" ","").replace(",",""))
            note = parts[2] if len(parts) > 2 else ""
        except ValueError as e:
            msg = bot.send_message(message.chat.id, f"❌ Формат қатеси: {e}", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_contract_set); return
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("SELECT full_name FROM students WHERE id=%s", (sid,))
                row = cursor.fetchone()
                if not row:
                    msg = bot.send_message(message.chat.id, "⚠️ Студент табылмады.", reply_markup=back_menu())
                    bot.register_next_step_handler(msg, handle_contract_set); return
                cursor.execute(
                    "INSERT INTO contracts(student_id,total_amount,note) VALUES(%s,%s,%s) "
                    "ON CONFLICT(student_id) DO UPDATE SET total_amount=excluded.total_amount,note=excluded.note",
                    (sid, amount, note))
                conn.commit(); name = row[0]
            bot.send_message(message.chat.id,
                f"✅ <b>{name}</b>\n💵 Контракт: <b>{amount:,.0f} сум</b>", reply_markup=contract_submenu())
            try:
                bot.send_message(sid,
                    f"💰 <b>Контрактыңыз киргизилди!</b>\n💵 Ұлыума: <b>{amount:,.0f} сум</b>"
                    + (f"\n📝 {note}" if note else ""))
            except: pass
        except Exception as e:
            msg = bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_contract_set)

    @bot.message_handler(func=lambda m: m.text == "➕ Төлем қосыу")
    @ca
    def payment_add_start(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("""
                SELECT s.id,s.full_name,c.total_amount,COALESCE(SUM(p.amount),0) as paid
                FROM students s JOIN contracts c ON c.student_id=s.id
                LEFT JOIN contract_payments p ON p.student_id=s.id
                WHERE s.full_name IS NOT NULL
                GROUP BY s.id,s.full_name,c.total_amount ORDER BY s.full_name""")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Контракт киргизилген студент жоқ.", reply_markup=contract_submenu()); return
        text = "➕ <b>Төлем қосыу:</b>\nФормат: <code>TelegramID;Сумма;Ескертиу</code>\n\n📋 <b>Контрактлар:</b>\n"
        for r in rows:
            rem = r[2] - float(r[3])
            text += f"{'✅' if rem<=0 else '⏳'} <code>{r[0]}</code> — {r[1]}\n   Қалды: <b>{rem:,.0f} сум</b>\n"
        msg = bot.send_message(message.chat.id, text, reply_markup=back_menu())
        bot.register_next_step_handler(msg, handle_payment_add)

    def handle_payment_add(message):
        if not is_admin(message.from_user.id): return
        if not message.text or message.text == "⬅️ Артқа":
            bot.send_message(message.chat.id, "💰 Контракт басқарыу", reply_markup=contract_submenu()); return
        parts = [p.strip() for p in message.text.split(";")]
        if len(parts) < 2 or not parts[0].lstrip("-").isdigit():
            msg = bot.send_message(message.chat.id,
                "❌ Формат: <code>TelegramID;Сумма;Ескертиу</code>", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_payment_add); return
        try:
            sid = int(parts[0])
            amount = float(parts[1].replace(" ","").replace(",",""))
            note = parts[2] if len(parts) > 2 else ""
        except ValueError as e:
            msg = bot.send_message(message.chat.id, f"❌ Формат қатеси: {e}", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_payment_add); return
        ds = now_uz().strftime("%Y-%m-%d")
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute("SELECT full_name FROM students WHERE id=%s", (sid,))
                sr = cursor.fetchone()
                cursor.execute("SELECT total_amount FROM contracts WHERE student_id=%s", (sid,))
                cr = cursor.fetchone()
                if not sr or not cr:
                    msg = bot.send_message(message.chat.id, "⚠️ Студент ямаса контракт табылмады.", reply_markup=back_menu())
                    bot.register_next_step_handler(msg, handle_payment_add); return
                cursor.execute("INSERT INTO contract_payments(student_id,amount,date,note) VALUES(%s,%s,%s,%s)",
                    (sid, amount, ds, note))
                cursor.execute("SELECT COALESCE(SUM(amount),0) FROM contract_payments WHERE student_id=%s", (sid,))
                paid = float(cursor.fetchone()[0])
                total = cr[0]; rem = total - paid
                conn.commit(); name = sr[0]
            bot.send_message(message.chat.id,
                f"✅ Төлем қосылды!\n👤 <b>{name}</b>\n💵 {amount:,.0f} сум\n⏳ Қалды: <b>{rem:,.0f} сум</b>",
                reply_markup=contract_submenu())
            try:
                pct = int((paid/total)*100) if total > 0 else 0
                bar = "🟩"*(pct//10) + "⬜"*(10-pct//10)
                bot.send_message(sid,
                    f"💰 <b>Төлем қабылланды!</b>\n📅 {date_to_ru(ds)}\n{'─'*25}\n"
                    f"✅ Төленди: <b>{amount:,.0f} сум</b>\n⏳ Қалды: <b>{rem:,.0f} сум</b>\n\n{bar} {pct}%")
            except: pass
        except Exception as e:
            msg = bot.send_message(message.chat.id, f"❌ DB қатеси: {e}", reply_markup=back_menu())
            bot.register_next_step_handler(msg, handle_payment_add)

    @bot.message_handler(func=lambda m: m.text == "📋 Барлық контрактлар")
    @ca
    def show_all_contracts(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return
        with db_cursor() as (_, cursor):
            cursor.execute("""
                SELECT s.full_name,c.total_amount,COALESCE(SUM(p.amount),0) as paid
                FROM students s JOIN contracts c ON c.student_id=s.id
                LEFT JOIN contract_payments p ON p.student_id=s.id
                WHERE s.full_name IS NOT NULL
                GROUP BY s.full_name,c.total_amount ORDER BY s.full_name""")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Контрактлар жоқ.", reply_markup=contract_submenu()); return
        ts = sum(r[1] for r in rows); ps = sum(float(r[2]) for r in rows)
        text = (f"📋 <b>Барлық контрактлар ({len(rows)}):</b>\n"
                f"💵 Ұлыума: <b>{ts:,.0f}</b>\n✅ Түскен: <b>{ps:,.0f}</b>\n"
                f"⏳ Қалды: <b>{ts-ps:,.0f} сум</b>\n{'─'*30}\n\n")
        for r in rows:
            rem = r[1] - float(r[2])
            status = "✅ Толық" if rem <= 0 else f"⏳ Қалды: {rem:,.0f}"
            text += f"👤 <b>{r[0]}</b>\n   💵 {r[1]:,.0f} | ✅ {float(r[2]):,.0f} | {status}\n\n"
        send_long_message(bot, message.chat.id, text, reply_markup=contract_submenu())

