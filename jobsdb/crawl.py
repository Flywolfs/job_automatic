#!/usr/bin/env python3
"""JobsDB 爬虫 — 继承 BaseCrawler，使用 bb-browser site adapter"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.base_crawler import BaseCrawler
from shared import utils


class JobsDBCrawler(BaseCrawler):
    PLATFORM = "JobsDB"

    def build_search_url(self, keyword: str, salary: str | None = None) -> str:
        return f"https://hk.jobsdb.com/jobs?keyword={keyword.replace(' ','+')}"

    def extract_jobs(self, keyword: str = "", count: int = 100, salary: str | None = None) -> list[dict]:
        """使用 bb-browser site jobsdb/search adapter"""
        cmd = f"bb-browser site jobsdb/search \"{keyword}\" {count}"
        if salary:
            cmd += f" {salary}"
        stdout, stderr, rc = utils.run_bb(cmd, 60)
        if rc != 0:
            self.log.error("  ✗ adapter 失败: %s", stderr)
            return []
        try:
            data = json.loads(stdout)
            return data.get("jobs", [])
        except json.JSONDecodeError:
            self.log.error("  ✗ JSON 解析失败")
            return []

    def transform_job(self, raw: dict, keyword: str, now: str) -> dict | None:
        link = raw.get("link", "")
        if not link: return None
        return {
            "job_link": link,
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "location": raw.get("location", ""),
            "salary": raw.get("salary", ""),
            "posted": raw.get("posted", ""),
            "posted_hours": utils.parse_posted_hours(raw.get("posted", "")),
        }


if __name__ == "__main__":
    JobsDBCrawler(Path(__file__).parent).cli()
