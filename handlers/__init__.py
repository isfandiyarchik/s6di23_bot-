"""
Барлық handler-ларды тиркеу
"""
def register_all_handlers(bot):
    from handlers.start_handler import register as reg_start
    from handlers.admin_handler import register as reg_admin
    from handlers.schedule_handler import register as reg_schedule
    from handlers.attendance_handler import register as reg_attendance
    from handlers.variants_handler import register as reg_variants
    from handlers.news_handler import register as reg_news
    from handlers.materials_handler import register as reg_materials
    from handlers.gallery_handler import register as reg_gallery
    from handlers.contract_handler import register as reg_contract
    from handlers.contacts_handler import register as reg_contacts
    from handlers.student_handler import register as reg_student
    from handlers.block_handler import register as reg_block
    from handlers.excel_handler import register as reg_excel
    from handlers.ai_handler import register as reg_ai
    from handlers.sabak_handler import register as reg_sabak

    from handlers.group_handler import register as reg_group
    from handlers.exam_handler import register as reg_exam

    reg_start(bot)
    reg_admin(bot)
    reg_schedule(bot)
    reg_attendance(bot)
    reg_variants(bot)
    reg_news(bot)
    reg_materials(bot)
    reg_gallery(bot)
    reg_contract(bot)
    reg_contacts(bot)
    reg_student(bot)
    reg_block(bot)
    reg_excel(bot)
    reg_ai(bot)
    reg_sabak(bot)
    reg_group(bot)
    reg_exam(bot)
