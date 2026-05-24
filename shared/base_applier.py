"""申请基类 — 子类只需实现 detect_mode() 和 execute_apply()"""
import json, re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from . import utils


class BaseApplier:
    """自动申请基类"""

    PLATFORM = "base"
    MAP_PREFIX = ""  # 映射文件前缀

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.db_path = project_dir / "jobs.db"
        self.map_dir = Path.home() / ".hermes/cron/output"

    @property
    def map_file(self) -> Path:
        return self.map_dir / f"{self.MAP_PREFIX}latest_jobs_map.json"

    # ── 子类必须覆盖 ────────────────────
    def detect_mode(self) -> str:
        """检测申请模式，返回 'auto' | 'external' | 'unknown'"""
        raise NotImplementedError

    def execute_apply(self) -> bool:
        """执行申请流程，返回是否成功"""
        raise NotImplementedError

    # ── 公共流程 ────────────────────────
    def apply(self, job_url: str, job_title: str) -> tuple:
        """返回 (result, last_apply_status): result='success'|'failed'|'skipped'|'external'"""
        print(f"🎯 {job_title[:60]}")

        if self.PLATFORM not in job_url.lower():
            print("  ⚠️ 外链，需自行申请")
            return ("external", "external")

        utils.bb_open(job_url)
        utils.bb_wait(4000)

        mode = self.detect_mode()
        print(f"  ① 模式: {mode}")

        if mode == "external":
            print("  ⚠️ 外部申请，需手动处理")
            self._mark_external(job_url)
            utils.bb_close()
            return ("external", "external")

        if mode == "unknown":
            print("  ⚠️ 找不到申请入口")
            return ("skipped", "skipped")

        ok = self.execute_apply()
        utils.bb_close()
        return ("success" if ok else "failed", "success" if ok else "failed")

    def _mark_external(self, job_url: str):
        conn = sqlite3.connect(str(self.db_path))
        try: conn.execute("ALTER TABLE jobs ADD COLUMN last_apply_status TEXT")
        except sqlite3.OperationalError: pass
        m = re.search(r'/job/(\d+)', job_url)
        jid = m.group(1) if m else job_url.split("/")[-1]
        conn.execute("UPDATE jobs SET can_auto_apply=0, last_apply_status='external' WHERE job_link LIKE ?", (f"%{jid}%",))
        conn.commit()
        conn.close()

    def _record_applied(self, job_url: str):
        conn = sqlite3.connect(str(self.db_path))
        now = datetime.now(timezone.utc).isoformat()
        try: conn.execute("ALTER TABLE jobs ADD COLUMN last_apply_status TEXT")
        except sqlite3.OperationalError: pass
        conn.execute("UPDATE jobs SET applied=1, applied_at=?, progress='applied', last_apply_status='applied' WHERE job_link=?",
                     (now, job_url))
        conn.commit()
        conn.close()

    def _set_status(self, job_url: str, status: str):
        conn = sqlite3.connect(str(self.db_path))
        try: conn.execute("ALTER TABLE jobs ADD COLUMN last_apply_status TEXT")
        except sqlite3.OperationalError: pass
        conn.execute("UPDATE jobs SET last_apply_status=? WHERE job_link=?", (status, job_url))
        conn.commit()
        conn.close()

    # ── CLI ────────────────────────────
    def cli(self):
        if len(sys.argv) < 2:
            print(f"用法: python3 apply_job.py <number>  |  python3 apply_job.py --link <url>")
            sys.exit(1)

        if sys.argv[1] == "--link":
            job_url = sys.argv[2]
            num_ref = ""
            job_title = self._lookup_title(job_url)
        else:
            num_ref = sys.argv[1]
            with open(self.map_file) as f:
                mapping = json.load(f)
            if num_ref not in mapping:
                print(f"❌ #{num_ref} 不存在")
                sys.exit(1)
            job = mapping[num_ref]
            job_url = job["link"]
            job_title = job["title"]

        result, status = self.apply(job_url, job_title)

        self._set_status(job_url, status)
        if result == "success":
            self._record_applied(job_url)
            print(f"✅ #{num_ref} → applied" if num_ref else "✅ applied")
        elif result == "external":
            print(f"⏭️ #{num_ref} 外链，已标记" if num_ref else "⏭️ 外链，已标记")
        else:
            print(f"❌ #{num_ref} {status}" if num_ref else f"❌ {status}")

    def _lookup_title(self, job_url: str) -> str:
        conn = sqlite3.connect(str(self.db_path))
        r = conn.execute("SELECT title FROM jobs WHERE job_link=?", (job_url,)).fetchone()
        conn.close()
        return r[0] if r else "Unknown"
