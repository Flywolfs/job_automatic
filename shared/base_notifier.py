"""邮件通知基类 — 子类只需覆盖 EMOJI / THEME_COLOR 等样式属性"""
import json, smtplib, sqlite3
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from . import utils


class BaseNotifier:
    """邮件通知基类"""

    PLATFORM = "base"
    # 子类覆盖：邮件主题前缀、HTML 配色
    EMOJI = "📌"
    THEME_COLOR = "#e65100"
    THEME_BG = "#fff3e0"

    def __init__(self, project_dir: Path, config_path: Path):
        self.project_dir = project_dir
        self.db_path = project_dir / "jobs.db"
        self.config_path = config_path
        self.map_dir = Path.home() / ".hermes/cron/output"
        self.map_prefix = f"{self.PLATFORM.lower()}_" if self.PLATFORM.lower() != "jobsdb" else ""

    # ── 子类可覆盖 ──────────────────────
    @property
    def keywords(self) -> list:
        return ["AI Agent", "AI Developer", "LLM Engineer", "NLP", "Generative AI"]

    @property
    def max_hours(self) -> int:
        return 120

    @property
    def top_n(self) -> int:
        return 15

    # ── 公共流程 ────────────────────────
    def build_and_send(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        now = datetime.now(timezone.utc)

        num = 0
        num_map = {}
        rows_all = {}

        for kw in self.keywords:
            rows = conn.execute("""
                SELECT title, company, location, salary, posted_hours, job_link, applied
                FROM jobs WHERE keyword=? AND is_active=1 AND posted_hours IS NOT NULL AND posted_hours<=?
                    AND date(first_seen) = date('now')
                ORDER BY posted_hours ASC
            """, (kw, self.max_hours)).fetchall()
            rows_all[kw] = rows
            for r in rows[:self.top_n]:
                num += 1
                num_map[str(num)] = {
                    "title": r[0], "company": r[1], "link": r[5],
                    "keyword": kw, "salary": r[3], "posted_hours": r[4],
                }

        # 保存映射
        self._save_map(num_map, now)

        # 构建 HTML
        html = self._build_html(rows_all, now)
        subject = f"{self.EMOJI} {self.PLATFORM} AI 职位 | {now.strftime('%m/%d')}"
        self._send_email(html, subject)
        conn.close()
        print(f"✅ {self.PLATFORM} 邮件已发送: {subject}")

    def _save_map(self, num_map: dict, now: datetime):
        self.map_dir.mkdir(parents=True, exist_ok=True)
        date_str = now.strftime("%Y%m%d")

        for suffix in ["", f"_{date_str}"]:
            path = self.map_dir / f"{self.map_prefix}latest_jobs_map{suffix}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(num_map, f, ensure_ascii=False, indent=2)

    def _build_html(self, rows_all: dict, now: datetime) -> str:
        sections = []
        num = 0
        for kw in self.keywords:
            rows = rows_all.get(kw, [])
            if not rows:
                continue
            rows_html = []
            for r in rows[:self.top_n]:
                num += 1
                applied = r[6] if len(r) > 6 else 0
                badge = '<span style="background:#e8f5e9;color:#2e7d32;padding:2px 6px;border-radius:3px;font-size:12px">✅已申请</span>' if applied else ""
                color = "#888" if applied else "#1a73e8"
                rows_html.append(f"""<tr>
                    <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center">{num}</td>
                    <td style="padding:10px 8px;border-bottom:1px solid #eee">
                        <a href="{r[5]}" style="color:{color};text-decoration:none;font-weight:500">{r[0]}</a>{badge}
                        <div style="font-size:13px;color:#666;margin-top:3px">
                            🏢 {r[1] or '?'} · 📍 {r[2] or '?'} · 🕐 {utils.fmt_time(r[4])}
                            {f' · 💰 {r[3]}' if r[3] else ''}
                        </div>
                    </td>
                </tr>""")

            sections.append(f"""
            <h3 style="background:{self.THEME_BG};padding:10px 16px;margin:20px 0 10px;border-radius:6px;color:{self.THEME_COLOR}">
                🔍 {kw} <span style="font-weight:normal;font-size:14px;color:#666">— {len(rows)} 个今日新职位</span>
            </h3>
            <table style="width:100%;border-collapse:collapse;font-size:14px">
                <thead><tr style="background:#f8f9fa;text-align:left">
                    <th style="padding:8px;width:40px">#</th><th style="padding:8px">职位详情</th>
                </tr></thead>
                <tbody>{"".join(rows_html)}</tbody>
            </table>""")

        return f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;padding:20px">
<div style="max-width:700px;margin:0 auto;background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.08)">
    <h2 style="margin:0 0 4px;color:#333">{self.EMOJI} {self.PLATFORM} AI 职位速递</h2>
    <p style="color:#999;font-size:13px;margin:0 0 20px">{now.strftime('%Y年%m月%d日 %H:%M')}</p>
    {"".join(sections)}
    <div style="margin-top:24px;padding:16px;background:#f9f9f9;border-radius:8px;font-size:13px;color:#888">
        💡 回复「<b>投 #N</b>」即可申请对应编号职位
    </div>
</div>
</body>
</html>"""

    def _send_email(self, html: str, subject: str):
        with open(self.config_path) as f:
            cfg = json.load(f)
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{cfg['sender_name']} <{cfg['sender_email']}>"
        msg["To"] = cfg["recipient"]
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as s:
            s.starttls()
            s.login(cfg["sender_email"], cfg["app_password"])
            s.send_message(msg)
