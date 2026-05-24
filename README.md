# Job Crawlers — 自动化求职流水线

> 多平台香港 AI 职位爬取 → 入库去重 → 邮件通知 → 一键自动申请

| 平台 | 目录 | 状态 |
|------|------|------|
| [JobsDB](https://hk.jobsdb.com) | `jobsdb/` | ✅ 生产 |
| [CTGoodJobs](https://www.ctgoodjobs.hk) | `ctgoodjobs/` | ✅ 生产 |
| LinkedIn | `linkedin/` | 🔜 未来 |

## 目录结构

```
~/Documents/job_crawlers/
├── README.md
├── jobsdb/
│   ├── crawl.py                  # 爬虫：bb-browser adapter + SQLite
│   ├── notify_email.py           # 邮件：HTML 表格 + Gmail SMTP
│   ├── apply_job.py              # 申请：选简历/封面/问答/提交
│   ├── question_answers.json     # 已知雇主答案
│   ├── unknown_questions.json    # 新问题记录
│   ├── email_config.json         # Gmail SMTP（两个平台共享）
│   ├── jobs.db                   # SQLite
│   └── crawl.log
├── ctgoodjobs/
│   ├── crawl.py                  # 爬虫：eval 提取 + SQLite
│   ├── notify_email.py           # 邮件：HTML 表格 + Gmail SMTP
│   ├── apply_job.py              # 申请：3 种模式自动适配
│   └── jobs.db
└── ...
```

```
~/.hermes/cron/output/
├── latest_jobs_map.json                    # JobsDB 当天映射
├── latest_jobs_map_20260521.json           # JobsDB 归档
├── ctgoodjobs_latest_jobs_map.json         # CTGoodJobs 当天映射
└── ctgoodjobs_latest_jobs_map_20260523.json
```

```
~/.hermes/scripts/
└── job_crawlers_daily.sh          # Cron 入口：依次跑两个平台
```

---

## 1. 爬取（crawl.py）

### JobsDB

通过 `bb-browser site jobsdb/search` 调用自定义 adapter 抓取。

```bash
cd ~/Documents/job_crawlers/jobsdb
python3 crawl.py --keyword "AI Agent,AI Developer" --salary 50000-120000 --count 100
python3 crawl.py --report
```

### CTGoodJobs

通过 `bb-browser eval` 直接从搜索结果页 DOM 提取（无需 adapter）。支持薪资过滤。

```
搜索 URL:   https://jobs.ctgoodjobs.hk/jobs/{keyword-slug}
薪资 URL:   ?salary_type=MON&salary_from=50000&salary_to=120000
选择器:     .job-card[data-job-id] → .jc-company / .jc-position / .jc-highlight / .jc-info
```

```bash
cd ~/Documents/job_crawlers/ctgoodjobs
python3 crawl.py --keyword "AI Agent,AI Developer" --salary 50000-120000 --count 100
python3 crawl.py --report
```

## 2. 入库与每日去重

| 平台 | 唯一键 | 新 job | 旧 job |
|------|--------|--------|--------|
| JobsDB | `job_link` (URL) | INSERT first_seen=now | UPDATE last_seen=now |
| CTGoodJobs | `job_id` (数字 ID) | INSERT first_seen=now | UPDATE last_seen=now |

```
first_seen 只在 INSERT 时写入，UPDATE 不碰 → 天然不可变
超过 30 天 last_seen 未更新 → is_active=0
```

### can_auto_apply 列

DB 新增 `can_auto_apply`（INTEGER DEFAULT 1）区分是否可自动申请：

| 值 | 含义 | 触发条件 |
|----|------|---------|
| `1` | 可自动申请 | 1-Click Apply 按钮存在 |
| `0` | 外链，需手动 | Apply Now → count_job_detail.asp（招聘方外部系统） |

## 3. 邮件通知（notify_email.py）

### 每日发送逻辑（两个平台一致）

```sql
WHERE keyword = ?
  AND is_active = 1
  AND posted_hours <= 120                  -- 5 天窗口
  AND date(first_seen) = date('now')       -- ← 今天第一次入库
ORDER BY posted_hours ASC
```

**效果**：同一个 job 永远不会在两天邮件里重复出现。

### 输出文件

| 文件 | 说明 |
|------|------|
| `{prefix}_latest_jobs_map.json` | 当天映射（覆盖） |
| `{prefix}_latest_jobs_map_YYYYMMDD.json` | 归档（永久） |

JobsDB prefix = 空，CTGoodJobs prefix = `ctgoodjobs_`

## 4. 自动申请（apply_job.py）

### JobsDB — 5 步流程

```bash
python3 jobsdb/apply_job.py 4              # 通过邮件编号
python3 jobsdb/apply_job.py 4 --force-new  # 强制重新申请
```

```
→ ① 选择简历（Chi Zhang Full-20260504.pdf）
→ ② 上传 Cover Letter（base64 写入隐藏 input）
→ ③ 检查 /apply/role-requirements 问答页
    ├─ right_to_work       → "I have a temporary visa (IANG)"
    ├─ expected_salary     → "$60K"
    └─ years_of_experience → 自动选最长选项
→ ④ 跳过 /apply/profile
→ ⑤ /apply/review → 点击 "Submit application"
```

### CTGoodJobs — 3 种模式自动适配

```bash
python3 ctgoodjobs/apply_job.py 1          # 通过邮件编号
python3 ctgoodjobs/apply_job.py --link "https://..."  # 直接 URL
```

| 模式 | 按钮 | 流程 | 成功标记 |
|------|------|------|---------|
| **A: 填表型** | 1-Click Apply | → `jobApply.asp` → Send To Employer | `apply_complete_member` in URL |
| **B: 直达型** | 1-Click Apply | → `?popup=Y` 页面直接完成 | 按钮变 `btn--success "Applied"` |
| **C: 外链型** | Apply Now | → `count_job_detail.asp` 计数页 | ❌ 跳过 + 标记 `can_auto_apply=0` |

模式 C 的职位需用户手动申请——这些雇主要求通过外部系统投递。

## 5. 定时任务

```
Job ID:   a6b7a8a4276b
脚本:     job_crawlers_daily.sh
调度:     每天 11:05 HKT
薪资:     50K-120K（两个平台统一）
```

```bash
#!/bin/bash
# ~/.hermes/scripts/job_crawlers_daily.sh

SALARY="50000-120000"
KEYWORDS="AI Agent,AI Developer,LLM Engineer,NLP,Generative AI"

# JobsDB
cd ~/Documents/job_crawlers/jobsdb
python3 crawl.py --keyword "$KEYWORDS" --count 100 --salary $SALARY
python3 notify_email.py

# CTGoodJobs
cd ~/Documents/job_crawlers/ctgoodjobs
python3 crawl.py --keyword "$KEYWORDS" --count 100 --salary $SALARY
python3 notify_email.py
```

## 6. 前置条件

| 依赖 | 说明 |
|------|------|
| bb-browser | 浏览器自动化，独立 Chrome profile（需登录两个平台） |
| Gmail App Password | `jobsdb/email_config.json`（两个平台共享） |
| Cover Letter | `~/Documents/CV_2026/cover_letter.pdf`（仅 JobsDB） |
| 简历 | 已上传至 JobsDB / CTGoodJobs 账户 |

## 7. 快速命令

```bash
# 手动跑全流程
bash ~/.hermes/scripts/job_crawlers_daily.sh

# 查看 DB 统计
cd ~/Documents/job_crawlers/jobsdb && python3 crawl.py --report
cd ~/Documents/job_crawlers/ctgoodjobs && python3 crawl.py --report

# 查看外链职位（需手动申请）
cd ~/Documents/job_crawlers/ctgoodjobs && python3 -c "
import sqlite3;c=sqlite3.connect('jobs.db')
for r in c.execute('SELECT job_id,title,company FROM jobs WHERE can_auto_apply=0'):
    print(f'{r[0]} | {r[1][:50]} | {r[2]}')
"

# 对比两日映射
diff ~/.hermes/cron/output/ctgoodjobs_latest_jobs_map_20260523.json \
     ~/.hermes/cron/output/ctgoodjobs_latest_jobs_map_20260524.json
```
