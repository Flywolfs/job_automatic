#!/usr/bin/env python3
"""CTGoodJobs 爬虫 — 继承 BaseCrawler"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.base_crawler import BaseCrawler
from shared import utils

EXTRACT_JS = """(function(){var cards=document.querySelectorAll('.job-card');var jobs=[];for(var i=0;i<cards.length;i++){var c=cards[i];var jid=c.getAttribute('data-job-id')||'';var companyEl=c.querySelector('.jc-company');var company=companyEl?companyEl.textContent.trim():'';var posEl=c.querySelector('.jc-position');var title=posEl?(posEl.querySelector('h2')||posEl).textContent.trim():'';var link=posEl?posEl.href:'';var hiEls=c.querySelectorAll('.jc-highlight li');var highlights=[];for(var j=0;j<hiEls.length;j++){highlights.push(hiEls[j].textContent.trim());}var expEl=c.querySelector('.cus-exp');var experience=expEl?expEl.parentElement.textContent.trim():'';var locEl=c.querySelector('.jc-info .col-12');var location=locEl?locEl.textContent.trim():'';var infoCols=c.querySelectorAll('.jc-info .col-6');var salary='';for(var k=0;k<infoCols.length;k++){var t=infoCols[k].textContent.trim();if(t&&!/yr\\b|year|exp/i.test(t)){salary=t;}}var otherEl=c.querySelector('.jc-other div');var posted=otherEl?otherEl.textContent.trim():'';jobs.push({job_id:jid,title:title,link:link,company:company,salary:salary,location:location,experience:experience,posted:posted,highlights:highlights});}return JSON.stringify(jobs);})()"""


class CTGoodJobsCrawler(BaseCrawler):
    PLATFORM = "CTGoodJobs"

    def build_search_url(self, keyword: str, salary: str | None = None) -> str:
        slug = keyword.lower().replace(" ", "-") + "-jobs"
        url = f"https://jobs.ctgoodjobs.hk/jobs/{slug}"
        if salary:
            lo, hi = utils.parse_salary_range(salary)
            url += f"?salary_type=MON&salary_from={lo}&salary_to={hi}"
        return url

    def extract_jobs(self, keyword: str = "", count: int = 100, salary: str | None = None) -> list[dict]:
        stdout, stderr, rc = utils.run_bb(f'bb-browser eval "{EXTRACT_JS}"', 15)
        if rc != 0:
            self.log.error("  ✗ 提取失败: %s", stderr)
            return []
        try: return json.loads(stdout)
        except json.JSONDecodeError:
            self.log.error("  ✗ JSON 解析失败")
            return []

    def crawl(self, keyword: str, count: int = 100, salary: str | None = None):
        """CTGoodJobs 需要先打开页面再提取"""
        self.log.info("  🔍 [%s]", keyword)
        url = self.build_search_url(keyword, salary)
        self.log.info("    → %s", url)

        stdout, stderr, rc = utils.run_bb(f'bb-browser open "{url}"', 30)
        if rc != 0:
            self.log.error("    ✗ 打开失败: %s", stderr)
            return 0, 0
        utils.bb_wait(4000)

        # 滚动加载更多
        for _ in range(min(count // 30 + 1, 4)):
            utils.bb_eval("window.scrollTo(0,document.body.scrollHeight);'ok'", 5)
            utils.bb_wait(2000)

        jobs = self.extract_jobs(keyword, count, salary)
        self.log.info("    提取到 %d 个职位", len(jobs))
        if not jobs: return 0, 0

        from shared import db as dbutil_local
        conn = dbutil_local.init_db(str(self.db_path))
        nc, uc = self._save(conn, jobs, keyword)
        conn.close()
        return nc, uc

    def transform_job(self, raw: dict, keyword: str, now: str) -> dict | None:
        link = raw.get("link", "")
        jid = raw.get("job_id", "")
        if not link or not jid: return None
        return {
            "job_link": link,
            "title": raw.get("title","") or "",
            "company": raw.get("company","") or "",
            "location": raw.get("location","") or "",
            "salary": raw.get("salary","") or "",
            "posted": raw.get("posted","") or "",
            "posted_hours": utils.parse_posted_hours(raw.get("posted","")),
        }


if __name__ == "__main__":
    CTGoodJobsCrawler(Path(__file__).parent).cli()
