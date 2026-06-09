from database import db_cursor, now_uz, get_user_state, set_user_state
from handlers.common import (
    is_admin, check_access, send_to_students,
    is_already_processed, send_saved_once,
    back_menu, materials_menu
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "📚 Сабақ материаллары")
    @ca
    def show_materials_menu(message):
        bot.send_message(message.chat.id, "📚 <b>Сабақ материаллары</b>", reply_markup=materials_menu())

    @bot.message_handler(func=lambda m: m.text == "📥 Мат жүклеңиз")
    @ca
    def upload_material_start(message):
        set_user_state(message.from_user.id, "materials")
        bot.send_message(message.chat.id,
            "📥 <b>Файл ямаса фото жибериңиз:</b>\nТайын болғанда <b>⬅️ Артқа</b> басыңыз.",
            reply_markup=back_menu())

    @bot.message_handler(content_types=["document"],
        func=lambda m: get_user_state(m.from_user.id) == "materials")
    @ca
    def handle_upload_document(message):
        if is_already_processed(message.message_id): return
        uid = message.from_user.id
        username = message.from_user.username or f"user{uid}"
        file_id = message.document.file_id
        file_name = message.document.file_name or "Файл"
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO materials(file_id,file_type,uploader_id,uploader_username) VALUES(%s,%s,%s,%s)",
                    (file_id, "document", uid, username))
                conn.commit()
            send_to_students(bot, file_id=file_id, file_type="document",
                text=f"📚 <b>Таза материал!</b>\n👤 @{username}\n📎 {file_name}", exclude_id=uid)
            send_saved_once(bot, message.chat.id, uid)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Қате: {e}")

    @bot.message_handler(content_types=["photo"],
        func=lambda m: get_user_state(m.from_user.id) == "materials")
    @ca
    def handle_upload_photo_mat(message):
        if is_already_processed(message.message_id): return
        uid = message.from_user.id
        username = message.from_user.username or f"user{uid}"
        file_id = message.photo[-1].file_id
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO materials(file_id,file_type,uploader_id,uploader_username) VALUES(%s,%s,%s,%s)",
                    (file_id, "photo", uid, username))
                conn.commit()
            send_to_students(bot, file_id=file_id, file_type="photo",
                text=f"📚 <b>Таза материал!</b>\n👤 @{username}", exclude_id=uid)
            send_saved_once(bot, message.chat.id, uid)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Қате: {e}")

    @bot.message_handler(content_types=["video","audio","voice","sticker"],
        func=lambda m: get_user_state(m.from_user.id) == "materials")
    @ca
    def handle_upload_wrong_materials(message):
        bot.send_message(message.chat.id, "⚠️ Тек файл ямаса фото!")

    @bot.message_handler(func=lambda m: m.text == "🗂 Архив материаллар")
    @ca
    def show_materials_archive(message):
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT file_id,file_type,date,uploader_username FROM materials ORDER BY date DESC")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Архив бос.", reply_markup=materials_menu()); return
        bot.send_message(message.chat.id, f"🗂 <b>Барлығы: {len(rows)}</b>\n\nЖүклеуде...")
        for r in rows:
            uname = f"@{r[3]}" if r[3] else "Белгисиз"
            cap = f"👤 {uname}\n🕐 {r[2]}"
            try:
                if r[1] == "document": bot.send_document(message.chat.id, r[0], caption=cap)
                elif r[1] == "photo": bot.send_photo(message.chat.id, r[0], caption=cap)
            except: continue
        bot.send_message(message.chat.id, "✅ Тайын.", reply_markup=materials_menu())
