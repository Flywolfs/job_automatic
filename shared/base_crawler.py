"""爬虫基类 — 子类只需实现 extract_jobs() 和 build_search_url()"""
import argparse, json, logging, sys
from datetime import datetime, timezone
from pathlib import Path
from . import utils, db as dbutil


class BaseCrawler:
    """平台爬虫基类"""
    
    # 子类必须定义
    PLATFORM = "base"

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.db_path = project_dir / "jobs.db"
        self.log_path = project_dir / "crawl.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)-5s] %(message)s",
            handlers=[logging.FileHandler(self.log_path), logging.StreamHandler()],
        )
        self.log = logging.getLogger(f"{self.PLATFORM}_crawler")
        utils.ensure_env()

    # ── 子类必须覆盖 ────────────────────
    def build_search_url(self, keyword: str, salary: str | None = None) -> str:
        """构造搜索页 URL"""
        raise NotImplementedError

    def extract_jobs(self, keyword: str = "", count: int = 100, salary: str | None = None) -> list[dict]:
        """从当前浏览器页面提取职位数据，返回 list of dict"""
        raise NotImplementedError

    def transform_job(self, raw: dict, keyword: str, now: str) -> dict | None:
        """将原始数据标准化为 DB 列"""
        raise NotImplementedError

    # ── 公共流程 ────────────────────────
    def crawl(self, keyword: str, count: int = 100, salary: str | None = None):
        self.log.info("  🔍 [%s]", keyword)
        jobs = self.extract_jobs(keyword, count, salary)
        self.log.info("    提取到 %d 个职位", len(jobs))

        if not jobs:
            return 0, 0

        conn = dbutil.init_db(str(self.db_path))
        new_count, updated_count = self._save(conn, jobs, keyword)
        conn.close()
        return new_count, updated_count

    def _save(self, conn, jobs: list, keyword: str):
        now = datetime.now(timezone.utc).isoformat()
        new_count = updated_count = 0

        for job in jobs:
            t = self.transform_job(job, keyword, now)
            if not t: continue
            link = t["job_link"]

            if conn.execute("SELECT id FROM jobs WHERE job_link=?", (link,)).fetchone():
                conn.execute(
                    "UPDATE jobs SET title=?,company=?,location=?,salary=?,posted_hours=?,last_seen=?,is_active=1 WHERE job_link=?",
                    (t["title"], t["company"], t["location"], t["salary"], t["posted_hours"], now, link)
                )
                updated_count += 1
            else:
                conn.execute(
                    "INSERT INTO jobs (job_link,title,company,location,salary,posted,posted_hours,keyword,first_seen,last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (link, t["title"], t["company"], t["location"], t["salary"], t.get("posted",""), t["posted_hours"], keyword, now, now)
                )
                new_count += 1

        conn.execute("UPDATE jobs SET is_active=0 WHERE last_seen < datetime('now','-30 days')")
        conn.execute("INSERT INTO crawl_log (crawled_at,keyword,total_fetched,new_jobs,updated_jobs) VALUES (?,?,?,?,?)",
                     (now, keyword, len(jobs), new_count, updated_count))
        conn.commit()
        self.log.info("    ✅ 新 %d / 更新 %d", new_count, updated_count)
        return new_count, updated_count

    # ── CLI ────────────────────────────
    def cli(self):
        parser = argparse.ArgumentParser(description=f"{self.PLATFORM} 爬虫")
        parser.add_argument("--keyword", default="AI Agent", help="关键词（逗号分隔）")
        parser.add_argument("--count", type=int, default=100)
        parser.add_argument("--salary", help="月薪范围")
        parser.add_argument("--report", action="store_true")
        args = parser.parse_args()

        if args.report:
            conn = dbutil.init_db(str(self.db_path))
            total, today, ext, applied, unknown = dbutil.stats(conn)
            self.log.info("📊 %s | 活跃: %d | 今日新: %d | 已申: %d | 外链: %d | 待处理: %d",
                          self.PLATFORM, total, today, applied, ext, unknown)
            conn.close()
            return

        keywords = [k.strip() for k in args.keyword.split(",")]
        session_start = datetime.now(timezone.utc)  # 爬取会话起始时间戳

        self.log.info("🚀 %s 爬虫 | 关键词: %s | 薪资: %s | 目标: %d",
                      self.PLATFORM, keywords, args.salary or "不限", args.count)

        for kw in keywords:
            self.crawl(kw, args.count, args.salary)

        # ── 爬取后维护 ──
        conn = dbutil.init_db(str(self.db_path))
        session_start_str = session_start.strftime("%Y-%m-%d %H:%M:%S")

        # 1. Aging: 本轮未爬到的 job，posted_hours 按流逝时间递增
        aged = conn.execute("""
            UPDATE jobs SET posted_hours = posted_hours +
                CAST((julianday('now') - julianday(last_seen)) * 24 AS INTEGER)
            WHERE is_active = 1
              AND posted_hours IS NOT NULL
              AND last_seen < ?
        """, (session_start_str,)).rowcount
        self.log.info("🕐 Aging: %d 个未命中 job 的 posted_hours 已更新", aged)

        # 2. 超过 20 天（480h）标记失效
        expired = conn.execute(
            "UPDATE jobs SET is_active = 0 WHERE is_active = 1 AND posted_hours > 480"
        ).rowcount
        if expired:
            self.log.info("🗑️ 失效: %d 个 job 超过 20 天，标记 is_active=0", expired)

        conn.commit()
        total, today, ext, applied, unknown = dbutil.stats(conn)
        self.log.info("📊 完成 | 活跃: %d | 今日新: %d | 已申: %d | 外链: %d | 待处理: %d",
                      total, today, applied, ext, unknown)
        conn.close()


def main():
    """子类调用: JobsDBCrawler(project_dir).cli()"""
    raise NotImplementedError("Use platform-specific subclass")
