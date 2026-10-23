from database import db_cursor, now_uz, get_user_state, set_user_state
from handlers.common import (
    is_admin, check_access, send_to_students,
    is_already_processed, send_saved_once,
    GALLERY_UPLOAD_BTN, back_menu, gallery_menu
)

def register(bot):
    ca = check_access(bot)

    @bot.message_handler(func=lambda m: m.text == "📷 Фото/Видео")
    @ca
    def show_gallery_menu(message):
        bot.send_message(message.chat.id, "📷 <b>Фото/Видео бөлими</b>", reply_markup=gallery_menu())

    @bot.message_handler(func=lambda m: m.text == GALLERY_UPLOAD_BTN)
    @ca
    def gallery_upload_start(message):
        set_user_state(message.from_user.id, "gallery")
        bot.send_message(message.chat.id,
            "📤 <b>Фото ямаса видео жибериңиз:</b>\nТайын болғанда <b>⬅️ Артқа</b> басыңыз.",
            reply_markup=back_menu())

    @bot.message_handler(content_types=["photo"],
        func=lambda m: get_user_state(m.from_user.id) == "gallery")
    @ca
    def handle_gallery_photo(message):
        if is_already_processed(message.message_id): return
        uid = message.from_user.id
        username = message.from_user.username or f"user{uid}"
        file_id = message.photo[-1].file_id
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO gallery(file_id,file_type,uploader_id,uploader_username) VALUES(%s,%s,%s,%s)",
                    (file_id, "photo", uid, username))
                conn.commit()
            send_to_students(bot, file_id=file_id, file_type="photo",
                text=f"🎞 <b>S6-DI естелиги!</b>\n👤 @{username}", exclude_id=uid)
            send_saved_once(bot, message.chat.id, uid)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Қате: {e}")

    @bot.message_handler(content_types=["video"],
        func=lambda m: get_user_state(m.from_user.id) == "gallery")
    @ca
    def handle_gallery_video(message):
        if is_already_processed(message.message_id): return
        uid = message.from_user.id
        username = message.from_user.username or f"user{uid}"
        file_id = message.video.file_id
        try:
            with db_cursor() as (conn, cursor):
                cursor.execute(
                    "INSERT INTO gallery(file_id,file_type,uploader_id,uploader_username) VALUES(%s,%s,%s,%s)",
                    (file_id, "video", uid, username))
                conn.commit()
            send_to_students(bot, file_id=file_id, file_type="video",
                text=f"🎞 <b>S6-DI естелиги!</b>\n👤 @{username}", exclude_id=uid)
            send_saved_once(bot, message.chat.id, uid)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Қате: {e}")

    @bot.message_handler(content_types=["document","audio","voice","sticker"],
        func=lambda m: get_user_state(m.from_user.id) == "gallery")
    @ca
    def handle_upload_wrong_gallery(message):
        bot.send_message(message.chat.id, "⚠️ Тек фото ямаса видео!")

    @bot.message_handler(func=lambda m: m.text == "🎞 S6-DI естелиги")
    @ca
    def show_gallery_view(message):
        with db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT file_id,file_type,date,uploader_username FROM gallery ORDER BY date DESC")
            rows = cursor.fetchall()
        if not rows:
            bot.send_message(message.chat.id, "📭 Галерея бос.",
                reply_markup=gallery_menu()); return

        # Фото топтап медиа группасы ретінде жіберу
        photos = [(r[0], r[1], r[2], r[3]) for r in rows if r[1] == "photo"]
        videos = [(r[0], r[1], r[2], r[3]) for r in rows if r[1] == "video"]

        bot.send_message(message.chat.id,
            f"🎞 <b>S6-DI-23 естелиги</b>\n"
            f"📸 Фото: {len(photos)} | 🎬 Видео: {len(videos)}")

        # Фотоларды медиа группасымен жібер (10-дан)
        from telebot.types import InputMediaPhoto, InputMediaVideo
        all_media = rows[:50]  # Макс 50

        chunk_size = 10
        for i in range(0, len(all_media), chunk_size):
            chunk = all_media[i:i+chunk_size]
            media_group = []
            for r in chunk:
                file_id, file_type, date, uname = r[0], r[1], r[2], r[3]
                uploader = f"@{uname}" if uname else "S6-DI-23"
                caption = f"👤 {uploader}\n📅 {date}" if len(media_group) == 0 else None
                try:
                    if file_type == "photo":
                        media_group.append(InputMediaPhoto(file_id, caption=caption))
                    elif file_type == "video":
                        media_group.append(InputMediaVideo(file_id, caption=caption))
                except Exception:
                    continue
            if media_group:
                try:
                    bot.send_media_group(message.chat.id, media_group)
                except Exception as e:
                    # Медиа группасы жұмыс ислемесе — жекеме жибер
                    for r in chunk:
                        try:
                            uname = f"@{r[3]}" if r[3] else "Белгисиз"
                            cap = f"👤 {uname}\n📅 {r[2]}"
                            if r[1] == "photo":
                                bot.send_photo(message.chat.id, r[0], caption=cap)
                            elif r[1] == "video":
                                bot.send_video(message.chat.id, r[0], caption=cap)
                        except Exception:
                            continue

        bot.send_message(message.chat.id, "✅ Тайын!", reply_markup=gallery_menu())
