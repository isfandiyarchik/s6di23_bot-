"""
Chart handler — диаграммалар
- Барлау диаграммасы (студент қатнасы %)
- Контракт диаграммасы (төлем прогреси)
"""
import io
import logging
from handlers.common import is_admin, check_access, admin_menu, attendance_submenu, contract_submenu
from database import db_cursor

logger = logging.getLogger(__name__)


def generate_attendance_chart(students_data):
    """Барлау диаграммасы — horizontal bar chart"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np

        names = [d[0] for d in students_data]
        percents = [d[1] for d in students_data]

        fig, ax = plt.subplots(figsize=(10, max(6, len(names) * 0.5)))
        colors = ['#2ecc71' if p >= 80 else '#f39c12' if p >= 60 else '#e74c3c' for p in percents]

        bars = ax.barh(names, percents, color=colors, edgecolor='white', height=0.6)

        # % белгисин қос
        for bar, pct in zip(bars, percents):
            ax.text(min(pct + 1, 95), bar.get_y() + bar.get_height()/2,
                    f'{pct:.1f}%', va='center', ha='left', fontsize=9, fontweight='bold')

        ax.set_xlabel('Қатнасы %', fontsize=11)
        ax.set_title('📊 Студентлердиң барлауға қатнасы', fontsize=13, fontweight='bold', pad=15)
        ax.set_xlim(0, 105)
        ax.axvline(x=80, color='green', linestyle='--', alpha=0.5, linewidth=1)
        ax.axvline(x=60, color='orange', linestyle='--', alpha=0.5, linewidth=1)

        # Легенда
        green = mpatches.Patch(color='#2ecc71', label='≥80% — Жақсы')
        orange = mpatches.Patch(color='#f39c12', label='60-79% — Орташа')
        red = mpatches.Patch(color='#e74c3c', label='<60% — Томен')
        ax.legend(handles=[green, orange, red], loc='lower right', fontsize=9)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.error(f"generate_attendance_chart: {e}", exc_info=True)
        return None


def generate_contract_chart(contracts_data):
    """Контракт диаграммасы — стэкланған horizontal bar"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np

        names = [d[0] for d in contracts_data]
        totals = [d[1] for d in contracts_data]
        paids = [d[2] for d in contracts_data]
        remainings = [d[1] - d[2] for d in contracts_data]
        percents = [int((d[2]/d[1])*100) if d[1] > 0 else 0 for d in contracts_data]

        fig, ax = plt.subplots(figsize=(12, max(6, len(names) * 0.55)))
        y = range(len(names))

        # Стэкланған bar
        bars_paid = ax.barh(list(y), paids, color='#2ecc71', height=0.6,
                            label='Төленди', edgecolor='white')
        bars_rem = ax.barh(list(y), remainings, left=paids, color='#e74c3c',
                           height=0.6, label='Қалды', edgecolor='white')

        ax.set_yticks(list(y))
        ax.set_yticklabels(names, fontsize=9)
        ax.set_xlabel("Сум", fontsize=11)
        ax.set_title("💰 Студентлердиң контракт төлем жағдайы",
                     fontsize=13, fontweight='bold', pad=15)

        # % белгисин қос
        for i, (p, t) in enumerate(zip(paids, totals)):
            pct = int((p/t)*100) if t > 0 else 0
            ax.text(t + t*0.01, i, f'{pct}%', va='center',
                    fontsize=9, fontweight='bold',
                    color='#2ecc71' if pct >= 100 else '#e74c3c')

        ax.legend(loc='lower right', fontsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # X axis форматтау
        ax.xaxis.set_major_formatter(
            plt.FuncFormatter(lambda x, p: f"{int(x):,}".replace(",", " ")))

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.error(f"generate_contract_chart: {e}", exc_info=True)
        return None


def generate_student_contract_chart(student_name, total, paid):
    """Жеке студент контракт диаграммасы — pie chart"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        remaining = total - paid
        if remaining < 0: remaining = 0
        pct = int((paid / total) * 100) if total > 0 else 0

        fig, ax = plt.subplots(figsize=(7, 6))

        if paid >= total:
            sizes = [100]
            colors = ['#2ecc71']
            labels = [f'Толық төленди\n{total:,.0f} сум']
            explode = [0]
        else:
            sizes = [paid, remaining]
            colors = ['#2ecc71', '#e74c3c']
            labels = [f'Төленди\n{paid:,.0f} сум', f'Қалды\n{remaining:,.0f} сум']
            explode = [0.05, 0]

        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors,
            explode=explode, autopct='%1.1f%%',
            startangle=90, textprops={'fontsize': 10})

        for autotext in autotexts:
            autotext.set_fontweight('bold')

        ax.set_title(f"💰 {student_name}\nКонтракт: {total:,.0f} сум",
                     fontsize=12, fontweight='bold', pad=15)

        # Орталықта % көрсет
        ax.text(0, 0, f'{pct}%', ha='center', va='center',
                fontsize=22, fontweight='bold',
                color='#2ecc71' if pct >= 100 else '#2c3e50')

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.error(f"generate_student_contract_chart: {e}", exc_info=True)
        return None


def register(bot):
    ca = check_access(bot)

    # ── БАРЛАУ ДИАГРАММАСЫ (admin) ────────────────────────────
    @bot.message_handler(func=lambda m: m.text == "📊 Барлау диаграммасы")
    @ca
    def attendance_chart(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return

        bot.send_chat_action(message.chat.id, "upload_photo")

        with db_cursor() as (_, cursor):
            cursor.execute("""
                SELECT
                    student_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) as present
                FROM attendance
                GROUP BY student_name
                ORDER BY student_name
            """)
            rows = cursor.fetchall()

        if not rows:
            bot.send_message(message.chat.id,
                "📭 Барлау данныйлары жоқ.", reply_markup=attendance_submenu()); return

        students_data = []
        for name, total, present in rows:
            pct = (present / total * 100) if total > 0 else 0
            students_data.append((name, round(pct, 1)))

        # Процент бойынша сорттау
        students_data.sort(key=lambda x: x[1], reverse=True)

        buf = generate_attendance_chart(students_data)
        if buf:
            buf.name = "attendance_chart.png"
            bot.send_photo(message.chat.id, buf,
                caption=f"📊 <b>Барлау диаграммасы</b>\n{len(students_data)} студент",
                reply_markup=attendance_submenu())
        else:
            bot.send_message(message.chat.id,
                "❌ Диаграмма исленбеди. matplotlib орнатылған ба?",
                reply_markup=attendance_submenu())

    # ── КОНТРАКТ ДИАГРАММАСЫ (admin) ─────────────────────────
    @bot.message_handler(func=lambda m: m.text == "📊 Контракт диаграммасы")
    @ca
    def contract_chart(message):
        if not is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "🚫"); return

        bot.send_chat_action(message.chat.id, "upload_photo")

        with db_cursor() as (_, cursor):
            cursor.execute("""
                SELECT s.full_name, c.total_amount,
                    COALESCE(SUM(p.amount), 0) as paid
                FROM students s
                JOIN contracts c ON c.student_id = s.id
                LEFT JOIN contract_payments p ON p.student_id = s.id
                WHERE s.full_name IS NOT NULL
                GROUP BY s.full_name, c.total_amount
                ORDER BY s.full_name
            """)
            rows = cursor.fetchall()

        if not rows:
            bot.send_message(message.chat.id,
                "📭 Контракт данныйлары жоқ.", reply_markup=contract_submenu()); return

        contracts_data = [(r[0], float(r[1]), float(r[2])) for r in rows]

        buf = generate_contract_chart(contracts_data)
        if buf:
            buf.name = "contract_chart.png"
            bot.send_photo(message.chat.id, buf,
                caption=f"💰 <b>Контракт диаграммасы</b>\n{len(contracts_data)} студент",
                reply_markup=contract_submenu())
        else:
            bot.send_message(message.chat.id,
                "❌ Диаграмма исленбеди. matplotlib орнатылған ба?",
                reply_markup=contract_submenu())

    # ── ЖЕКЕ СТУДЕНТ КОНТРАКТ ДИАГРАММАСЫ ────────────────────
    @bot.message_handler(func=lambda m: m.text == "📊 Контракт графиги")
    @ca
    def my_contract_chart(message):
        uid = message.from_user.id
        bot.send_chat_action(message.chat.id, "upload_photo")

        with db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT full_name FROM students WHERE id=%s", (uid,))
            row = cursor.fetchone()
            if not row:
                bot.send_message(message.chat.id, "❌ Студент табылмады."); return
            sname = row[0]

            cursor.execute(
                "SELECT total_amount FROM contracts WHERE student_id=%s", (uid,))
            cr = cursor.fetchone()
            if not cr:
                bot.send_message(message.chat.id,
                    "📭 Контрактыңыз орнатылмаған."); return
            total = float(cr[0])

            cursor.execute(
                "SELECT COALESCE(SUM(amount),0) FROM contract_payments WHERE student_id=%s",
                (uid,))
            paid = float(cursor.fetchone()[0])

        buf = generate_student_contract_chart(sname, total, paid)
        if buf:
            buf.name = "my_contract.png"
            remaining = total - paid
            pct = int((paid/total)*100) if total > 0 else 0
            bot.send_photo(message.chat.id, buf,
                caption=(f"💰 <b>{sname}</b>\n"
                         f"✅ Төленди: <b>{paid:,.0f} сум</b>\n"
                         f"⏳ Қалды: <b>{remaining:,.0f} сум</b>\n"
                         f"📊 Прогресс: <b>{pct}%</b>"))
        else:
            bot.send_message(message.chat.id, "❌ Диаграмма исленбеди.")
