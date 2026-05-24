#!/usr/bin/env python3
"""
JobsDB 自动申请脚本 v2.1
- 外链跳转 → 通知用户
- 问答 → known answers + longest strategy for experience
- 封面 → base64 upload via label click
"""
import json, os, sqlite3, subprocess, sys, re, base64
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "jobs.db"
MAP_FILE = Path.home() / ".hermes/cron/output/latest_jobs_map.json"
QA_FILE = PROJECT_DIR / "question_answers.json"
UNKNOWN_QA_FILE = PROJECT_DIR / "unknown_questions.json"
COVER_PATH = Path.home() / "Documents/CV_2026/cover_letter.pdf"
BB = "bb-browser"


def run_bb(cmd: str, timeout: int = 30) -> str:
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
    return r.stdout + r.stderr


def bb_eval(js: str, timeout: int = 15) -> str:
    return run_bb(f'{BB} eval "{js}"', timeout)


def bb_wait(ms: int = 2000):
    run_bb(f"{BB} wait {ms}")


def bb_open(url: str):
    run_bb(f"{BB} open {url}")


def bb_close():
    run_bb(f"{BB} close")


def load_known_answers() -> dict:
    if QA_FILE.exists():
        with open(QA_FILE) as f:
            return json.load(f)
    return {}


def save_unknown(unknown: list):
    existing = []
    if UNKNOWN_QA_FILE.exists():
        with open(UNKNOWN_QA_FILE) as f:
            try: existing = json.load(f)
            except: pass
    existing.append({"date": datetime.now(timezone.utc).isoformat(), "questions": unknown})
    with open(UNKNOWN_QA_FILE, "w") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def answer_questions() -> list[str]:
    """回答雇主问题，返回未知问题列表"""
    result = bb_eval("""
    (function(){
        var sels = document.querySelectorAll('select');
        var selectList = [];
        for(var i=0;i<sels.length;i++){
            var s = sels[i];
            var opts = [];
            for(var j=0;j<s.options.length;j++){opts.push({val:s.options[j].value,text:s.options[j].text.trim()});}
            selectList.push({id:s.id,visible:!!s.offsetParent,options:opts});
        }
        var fss = document.querySelectorAll('fieldset');
        var fsList = [];
        for(var k=0;k<fss.length;k++){
            var f = fss[k];
            var legend = f.querySelector('legend');
            var radios = f.querySelectorAll('input[type=radio]');
            var rList = [];
            for(var m=0;m<radios.length;m++){
                rList.push({value:radios[m].value,label:(radios[m].parentElement?radios[m].parentElement.textContent:'').trim().substring(0,80)});
            }
            fsList.push({legend:legend?legend.textContent.trim().substring(0,80):'',radios:rList});
        }
        return JSON.stringify({selects:selectList,fieldsets:fsList});
    })()
    """)
    try: data = json.loads(result)
    except: return ["parse error"]

    known = load_known_answers()
    unknown = []

    for fs in data.get("fieldsets", []):
        legend = (fs.get("legend") or "").lower()
        matched = False
        for key, cfg in known.items():
            for pat in cfg.get("patterns", []):
                if not re.search(pat, legend, re.IGNORECASE): continue
                strategy = cfg.get("answer_strategy", "exact")
                if strategy == "longest":
                    last_r = fs["radios"][-1]
                else:
                    last_r = next((r for r in fs["radios"] if r["value"] == cfg.get("answer_value", "")), None)
                if last_r:
                    v = last_r["value"]
                    bb_eval(f"""(function(){{var r=document.querySelector('input[value="{v}"]');if(r){{r.checked=true;r.dispatchEvent(new Event('change',{{bubbles:true}}));}}}})())""")
                    matched = True
                break
            if matched: break
        if not matched:
            unknown.append(f"RADIO: {legend}")

    for s in data.get("selects", []):
        if not s.get("visible"): continue
        sid = s["id"]
        # 用 options 文本辅助匹配（ID 每次不同，但选项内容固定）
        opts_text = " ".join(o["text"] for o in s.get("options", [])[:5])
        search_text = (sid + " " + opts_text).lower()
        matched = False
        for key, cfg in known.items():
            for pat in cfg.get("patterns", []):
                if not re.search(pat, search_text, re.IGNORECASE): continue
                strategy = cfg.get("answer_strategy", "exact")
                if strategy == "longest":
                    last_opt = s["options"][-1]
                else:
                    last_opt = next((o for o in s["options"] if o["val"] == cfg.get("answer_value", "")), None)
                if last_opt:
                    v = last_opt["val"]
                    bb_eval(f"""(function(){{var s=document.getElementById('{sid}');if(s){{s.value='{v}';s.dispatchEvent(new Event('change',{{bubbles:true}}));}}}})())""")
                    matched = True
                break
            if matched: break
        if not matched:
            unknown.append(f"SELECT: {sid} opts={[o['text'] for o in s['options']]}")

    return unknown


def apply_job(job_link: str, job_title: str):
    print(f"🎯 {job_title[:60]}")

    # ── 检测外链 ──
    bb_open(job_link)
    bb_wait(3000)
    r = bb_eval("""(function(){
        var btns = document.querySelectorAll('a,button');
        var links = [];
        for(var i=0;i<btns.length;i++){
            var t = (btns[i].textContent||'').toLowerCase();
            if(t.indexOf('apply')>=0){
                var href = btns[i].getAttribute('href')||(btns[i].closest('a')?btns[i].closest('a').getAttribute('href'):'')||'';
                links.push(href);
            }
        }
        var ext = [];
        for(var j=0;j<links.length;j++){
            if(links[j] && links[j].indexOf('jobsdb.com')<0 && links[j].indexOf('http')===0) ext.push(links[j]);
        }
        return JSON.stringify({ext:ext});
    })()""")
    try:
        if json.loads(r).get("ext"):
            print("  ⚠️ 外链，需自行申请")
            # 标记 can_auto_apply=0 + last_apply_status（兼容旧表）
            conn = sqlite3.connect(str(DB_PATH))
            try: conn.execute("ALTER TABLE jobs ADD COLUMN can_auto_apply INTEGER DEFAULT 1")
            except sqlite3.OperationalError: pass
            try: conn.execute("ALTER TABLE jobs ADD COLUMN last_apply_status TEXT")
            except sqlite3.OperationalError: pass
            conn.execute("UPDATE jobs SET can_auto_apply=0, last_apply_status='external' WHERE job_link=?", (job_link,))
            conn.commit()
            conn.close()
            return "external"
    except: pass

    # ── 进入 Apply ──
    bb_open(f"{job_link.split('?')[0]}/apply")
    bb_wait(3000)

    # ── Step 1: 初始页（选简历 + 上传封面）→ Continue ──
    print("  ① 选简历...")
    bb_eval("""(function(){var s=document.querySelector('select');if(s){var o=[...s.options].find(o=>o.text.includes('Chi Zhang'));if(o){s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));}}return'OK';})()""")
    bb_wait(1000)

    print("  ② 上传 Cover Letter...")
    bb_eval("""(function(){var l=[...document.querySelectorAll('label')].find(l=>l.textContent.trim()==='Upload a cover letter');if(l)l.click();return l?'OK':'NO';})()""")
    bb_wait(1500)
    if COVER_PATH.exists():
        with open(COVER_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        bb_eval(f"""(function(){{var inp=document.getElementById('coverLetter-fileFile');if(!inp)return'NO';var d=atob('{b64}');var a=new Uint8Array(d.length);for(var i=0;i<d.length;i++)a[i]=d.charCodeAt(i);var b=new Blob([a],{{type:'application/pdf'}});var f=new File([b],'cover_letter.pdf',{{type:'application/pdf'}});var dt=new DataTransfer();dt.items.add(f);inp.files=dt.files;inp.dispatchEvent(new Event('change',{{bubbles:true}}));return'FILES:'+inp.files.length;}})()""")
        print("    ✅ 已上传")
    bb_wait(1000)

    # 点 Continue（从初始页到 QA 或 Profile）
    bb_eval("""(function(){var bs=document.querySelectorAll('button');for(var i=0;i<bs.length;i++){var t=(bs[i].textContent||'').trim().toLowerCase();if(t.startsWith('continue')&&bs[i].offsetParent){bs[i].focus();bs[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));bs[i].dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));bs[i].click();return'OK';}}return'NO';})()""")
    bb_wait(5000)

    # ── Step 2: 检查 URL，处理问答 ──
    cur_url = bb_eval("location.href")
    print(f"  ③ 当前: {cur_url.split('/apply')[1] if '/apply' in cur_url else cur_url}")
    if "role-requirements" in cur_url:
        print("  📝 回答雇主问题...")
        unknown = answer_questions()
        if unknown:
            print(f"  ⚠️ {len(unknown)} 个新问题无法自动回答")
            save_unknown(unknown)
            print("  ⛔ 暂停申请，需人工处理未知问题后重试")
            bb_close()
            return "unknown_questions"
        # 回答完点 Continue
        for attempt in range(4):
            bb_eval("""(function(){var bs=document.querySelectorAll('button');for(var i=0;i<bs.length;i++){var t=(bs[i].textContent||'').trim().toLowerCase();if(t.startsWith('continue')&&bs[i].offsetParent){bs[i].focus();bs[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));bs[i].dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));bs[i].click();return'OK';}}return'NO';})()""")
            bb_wait(4000)
            cur_url = bb_eval("location.href")
            if "role-requirements" not in cur_url:
                break
            print(f"    ⚠️ 还在问答页，重试 ({attempt+1}/4)")

    # ── Step 3: Profile 页 → Continue ──
    cur_url = bb_eval("location.href")
    print(f"  ④ 当前: {cur_url.split('/apply')[1] if '/apply' in cur_url else cur_url}")
    if "profile" in cur_url:
        print("    跳过 Profile...")
        bb_eval("""(function(){var bs=document.querySelectorAll('button');for(var i=0;i<bs.length;i++){var t=(bs[i].textContent||'').trim().toLowerCase();if(t.startsWith('continue')&&bs[i].offsetParent){bs[i].focus();bs[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));bs[i].dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));bs[i].click();return'OK';}}return'NO';})()""")
        bb_wait(4000)

    # ── Step 4: Review → Submit ──
    cur_url = bb_eval("location.href")
    print(f"  ⑤ Review: {cur_url.split('/apply')[1] if '/apply' in cur_url else cur_url}")
    
    # 确认在 review 页（/apply 或 /apply/review，但没有 role-requirements/profile）
    if "role-requirements" not in cur_url and "profile" not in cur_url:
        print("    提交...")
        result_click = bb_eval("""(function(){
            var btns = document.querySelectorAll('button');
            for(var i=0;i<btns.length;i++){
                var t = (btns[i].textContent||'').toLowerCase();
                if(btns[i].offsetParent && t.indexOf('submit application')>=0){
                    btns[i].focus();
                    btns[i].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
                    btns[i].dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
                    btns[i].click();
                    return 'CLICKED';
                }
            }
            return 'NO_BTN';
        })()""")
        print(f"    click: {result_click}")
        bb_wait(5000)
    else:
        print(f"    ⚠️ 未到 review 页，跳过提交")

    result = run_bb(f"{BB} get url")
    success = "success" in result.lower()
    print(f"  {'✅ 已提交' if success else '⚠️ ' + result.strip()}")
    bb_close()
    return success


def record_applied(conn, job_link):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE jobs SET applied=1, applied_at=?, progress='applied', last_apply_status='applied' WHERE job_link LIKE ?",
                 (now, f"%{job_link.split('/job/')[1].split('?')[0]}%"))
    conn.commit()


def set_last_status(conn, job_link, status: str):
    """记录最后一次申请状态，兼容旧表"""
    try: conn.execute("ALTER TABLE jobs ADD COLUMN last_apply_status TEXT")
    except sqlite3.OperationalError: pass
    conn.execute("UPDATE jobs SET last_apply_status=? WHERE job_link LIKE ?",
                 (status, f"%{job_link.split('/job/')[1].split('?')[0]}%"))
    conn.commit()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 apply_job.py <number>")
        print("      python3 apply_job.py --link <url>")
        print("      python3 apply_job.py --retry-unknowns  (重试所有待处理的未知问题)")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))

    # ── 批量重试未知问题 ──
    if sys.argv[1] == "--retry-unknowns":
        rows = conn.execute(
            "SELECT job_link, title FROM jobs WHERE is_active=1 AND last_apply_status='unknown_questions'"
        ).fetchall()
        if not rows:
            print("✅ 没有待重试的未知问题职位")
            conn.close()
            return
        print(f"🔁 重试 {len(rows)} 个待处理职位...\n")
        for idx, (link, title) in enumerate(rows, 1):
            print(f"[{idx}/{len(rows)}] ", end="")
            r = apply_job(link, title)
            if r is True:
                record_applied(conn, link)
                print(f"  ✅ applied")
            elif r == "unknown_questions":
                set_last_status(conn, link, "unknown_questions")
                print(f"  ⛔ 仍有未知问题")
            elif r == "external":
                print(f"  ⏭️ 外链")
            elif r is False:
                set_last_status(conn, link, "failed")
                print(f"  ❌ 提交失败")
            else:
                set_last_status(conn, link, "skipped")
                print(f"  ⏭️ 跳过")
        conn.close()
        return

    if sys.argv[1] == "--link":
        job_link = sys.argv[2]
        r = conn.execute("SELECT title FROM jobs WHERE job_link LIKE ?",
                         (f"%{job_link.split('/job/')[1].split('?')[0]}%",)).fetchone()
        job_title = r[0] if r else "Unknown"
        num_ref = ""
    else:
        num_ref = sys.argv[1]
        with open(MAP_FILE) as f: mapping = json.load(f)
        if num_ref not in mapping: print(f"❌ #{num_ref} 不存在"); sys.exit(1)
        job = mapping[num_ref]; job_link = job["link"]; job_title = job["title"]

    r = apply_job(job_link, job_title)
    if r is True:
        record_applied(conn, job_link)
        print(f"✅ #{num_ref} → applied")
    elif r == "unknown_questions":
        set_last_status(conn, job_link, "unknown_questions")
        print(f"⛔ #{num_ref} 暂停（有未知问题需人工处理）")
    elif r == "external":
        print(f"⏭️ #{num_ref} 外链，已标记")
    elif r is False:
        set_last_status(conn, job_link, "failed")
        print(f"❌ #{num_ref} 提交失败")
    else:
        set_last_status(conn, job_link, "skipped")
        print(f"⏭️ #{num_ref} 跳过")
    conn.close()


if __name__ == "__main__":
    main()
