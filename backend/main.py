"""Job Crawlers Dashboard — FastAPI Backend"""
import asyncio, json, os, re, sqlite3, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── 项目路径 ──────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
JOBSDB_DIR = PROJECT_ROOT / "jobsdb"
CTGOOD_DIR = PROJECT_ROOT / "ctgoodjobs"
sys.path.insert(0, str(PROJECT_ROOT))
from shared import utils

# ── FastAPI app ───────────────────────────
app = FastAPI(title="Job Crawlers Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── 全局状态 ──────────────────────────────
crawl_status: dict = {"running": False, "current": "", "log": []}
apply_status: dict = {"running": False, "current": "", "log": [], "results": []}

# ── 数据模型 ──────────────────────────────
class CrawlRequest(BaseModel):
    keywords: str = "AI Agent,AI Developer,LLM Engineer,NLP,Generative AI"
    salary_from: int = 50000
    salary_to: int = 120000
    platforms: list[str] = ["jobsdb", "ctgoodjobs"]
    count: int = 100

class ApplyRequest(BaseModel):
    job_ids: list[int]
    platform: str = "jobsdb"

# ── 数据库查询 ────────────────────────────
def get_db(platform: str) -> sqlite3.Connection:
    db_path = PROJECT_ROOT / platform / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

# ── SSE 日志流 ────────────────────────────
async def crawl_log_stream(platform: str) -> AsyncGenerator[str, None]:
    """实时推送爬取日志"""
    log_file = PROJECT_ROOT / platform / "crawl.log"
    last_size = log_file.stat().st_size if log_file.exists() else 0

    while crawl_status["running"]:
        if log_file.exists():
            current_size = log_file.stat().st_size
            if current_size > last_size:
                with open(log_file) as f:
                    f.seek(last_size)
                    new_lines = f.read().strip()
                    if new_lines:
                        yield f"data: {json.dumps({'lines': new_lines.split(chr(10))[-10:]})}\n\n"
                last_size = current_size
        await asyncio.sleep(0.5)

    yield f"data: {json.dumps({'done': True, 'summary': crawl_status.get('summary', '')})}\n\n"

async def apply_log_stream() -> AsyncGenerator[str, None]:
    """实时推送申请进度"""
    while apply_status["running"]:
        yield f"data: {json.dumps({'current': apply_status['current'], 'results': apply_status['results'], 'running': True})}\n\n"
        await asyncio.sleep(0.3)
    yield f"data: {json.dumps({'done': True, 'results': apply_status['results'], 'running': False})}\n\n"

# ── 爬取 ──────────────────────────────────
def _run_crawl(platform: str, keywords: str, salary: str, count: int):
    """后台执行爬虫"""
    crawl_status["running"] = True
    crawl_status["current"] = f"{platform} - {keywords}"
    work_dir = JOBSDB_DIR if platform == "jobsdb" else CTGOOD_DIR

    try:
        utils.ensure_env()
        cmd = f"python3 crawl.py --keyword \"{keywords}\" --salary {salary} --count {count}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600, cwd=str(work_dir),
                                env={**os.environ, "NODE_OPTIONS": ""})
        crawl_status["summary"] = result.stdout.split("\n")[-3:] if result.stdout else "no output"
    finally:
        crawl_status["running"] = False
        crawl_status["current"] = ""

@app.post("/api/crawl")
async def start_crawl(req: CrawlRequest):
    if crawl_status["running"]:
        raise HTTPException(400, "爬取正在进行中")
    salary = f"{req.salary_from}-{req.salary_to}"
    for plat in req.platforms:
        threading.Thread(target=_run_crawl, args=(plat, req.keywords, salary, req.count), daemon=True).start()
    return {"status": "started", "platforms": req.platforms, "keywords": req.keywords}

@app.get("/api/crawl/stream")
async def crawl_stream(platform: str = "jobsdb"):
    return StreamingResponse(crawl_log_stream(platform), media_type="text/event-stream")

@app.get("/api/crawl/status")
async def get_crawl_status():
    return crawl_status

# ── 职位列表 ──────────────────────────────
@app.get("/api/jobs")
async def list_jobs(
    platform: str = "jobsdb",
    keyword: str = "",
    status: str = "",
    time_range: str = "",
    page: int = 1,
    per_page: int = 20,
    sort: str = "posted_hours",
    order: str = "asc",
):
    conn = get_db(platform)
    where = ["is_active=1"]
    params = []

    if keyword:
        where.append("keyword=?")
        params.append(keyword)
    if status == "applied":
        where.append("applied=1")
    elif status == "pending":
        where.append("applied=0 AND last_apply_status IS NULL")
    elif status == "external":
        where.append("can_auto_apply=0")
    elif status == "unknown_questions":
        where.append("last_apply_status='unknown_questions'")
    elif status == "failed":
        where.append("last_apply_status='failed'")

    # 时间范围过滤（基于 posted_hours）
    if time_range == "5d":
        where.append("posted_hours IS NOT NULL AND posted_hours <= 120")
    elif time_range == "5-10d":
        where.append("posted_hours > 120 AND posted_hours <= 240")
    elif time_range == "10-20d":
        where.append("posted_hours > 240 AND posted_hours <= 480")
    elif time_range == "20d+":
        where.append("posted_hours > 480")

    allowed_sort = {"posted_hours", "salary", "title", "company"}
    sort_col = sort if sort in allowed_sort else "posted_hours"
    dir_clause = "DESC" if order == "desc" else "ASC"

    # 总数
    count = conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where)}", params).fetchone()[0]

    # 分页
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT id,title,company,location,salary,posted_hours,job_link,keyword,applied,last_apply_status,can_auto_apply,applied_at "
        f"FROM jobs WHERE {' AND '.join(where)} ORDER BY {sort_col} {dir_clause} LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    conn.close()
    return {
        "total": count, "page": page, "per_page": per_page,
        "jobs": [dict(r) for r in rows],
        "keywords_available": _get_keywords(platform),
    }

def _get_keywords(platform: str):
    conn = get_db(platform)
    rows = conn.execute("SELECT DISTINCT keyword FROM jobs WHERE is_active=1 ORDER BY keyword").fetchall()
    conn.close()
    return [r[0] for r in rows]

# ── 申请 ──────────────────────────────────
def _run_apply(platform: str, job_ids: list[int]):
    """后台执行申请"""
    apply_status["running"] = True
    apply_status["results"] = []
    conn = get_db(platform)
    work_dir = JOBSDB_DIR if platform == "jobsdb" else CTGOOD_DIR

    for i, jid in enumerate(job_ids):
        row = conn.execute("SELECT job_link,title FROM jobs WHERE id=?", (jid,)).fetchone()
        if not row: continue
        link, title = row

        apply_status["current"] = f"[{i+1}/{len(job_ids)}] {title[:50]}"

        try:
            utils.ensure_env()
            cmd = f"python3 apply_job.py --link \"{link}\""
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120, cwd=str(work_dir),
                                    env={**os.environ, "NODE_OPTIONS": ""})

            output = result.stdout.strip()
            success = "✅" in output and "applied" in output.lower()
            apply_status["results"].append({
                "id": jid, "title": title, "success": success, "output": output[-200:],
            })
        except subprocess.TimeoutExpired:
            apply_status["results"].append({"id": jid, "title": title, "success": False, "output": "timeout"})

    conn.close()
    apply_status["running"] = False

@app.post("/api/apply")
async def start_apply(req: ApplyRequest):
    if apply_status["running"]:
        raise HTTPException(400, "申请正在进行中")
    threading.Thread(target=_run_apply, args=(req.platform, req.job_ids), daemon=True).start()
    return {"status": "started", "count": len(req.job_ids)}

@app.get("/api/apply/stream")
async def apply_stream():
    return StreamingResponse(apply_log_stream(), media_type="text/event-stream")

@app.get("/api/apply/status")
async def get_apply_status():
    return apply_status

# ── 统计 ──────────────────────────────────
@app.get("/api/stats")
async def get_stats(platform: str = "jobsdb"):
    conn = get_db(platform)
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    today = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND date(first_seen)=date('now')").fetchone()[0]
    applied = conn.execute("SELECT COUNT(*) FROM jobs WHERE applied=1").fetchone()[0]
    external = conn.execute("SELECT COUNT(*) FROM jobs WHERE can_auto_apply=0").fetchone()[0]
    unknown = conn.execute("SELECT COUNT(*) FROM jobs WHERE last_apply_status='unknown_questions'").fetchone()[0]
    conn.close()
    return {"total": total, "today_new": today, "applied": applied, "external": external, "unknown_questions": unknown}

# ── 配置 ──────────────────────────────────
@app.get("/api/config")
async def get_config():
    return {
        "keywords": "AI Agent,AI Developer,LLM Engineer,NLP,Generative AI",
        "salary_from": 50000, "salary_to": 120000,
        "platforms": ["jobsdb", "ctgoodjobs"],
        "count": 100,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8899)
