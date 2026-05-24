"""公共工具函数"""
import os, re, subprocess

NVM_BIN = os.path.expanduser("~/.nvm/versions/node/v22.22.1/bin")
BB = "bb-browser"


def ensure_env():
    """Cron 环境下修复 PATH 和 DISPLAY"""
    os.environ["PATH"] = f"/usr/bin:/usr/local/bin:{NVM_BIN}:{os.environ.get('PATH','')}"
    os.environ.setdefault("DISPLAY", ":1")


def run_bb(cmd: str, timeout: int = 30) -> tuple:
    """运行 bb-browser 命令，返回 (stdout, stderr, returncode)"""
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, env=env)
    return r.stdout, r.stderr, r.returncode


def bb_eval(js: str, timeout: int = 15) -> str:
    """在浏览器中执行 JS 并返回结果"""
    stdout, _, _ = run_bb(f'{BB} eval "{js}"', timeout)
    return stdout.strip()


def bb_wait(ms: int = 2000):
    run_bb(f"{BB} wait {ms}")


def bb_open(url: str):
    run_bb(f'{BB} open "{url}"')


def bb_close():
    run_bb(f"{BB} close")


def parse_posted_hours(text: str) -> int | None:
    """'2h ago' → 2, '1d ago' → 24, 'Listed two days ago' → 48, '30d+ ago' → 720"""
    if not text:
        return None
    text = text.lower().replace("posted on ", "").replace("posted ", "").replace("listed ", "").strip()

    # 数字形式: "2h ago", "3d ago", "30d+ ago"
    m = re.match(r"(\d+)\s*h\w*\s*ago", text)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d+)\s*d\w*\+\s*ago", text)
    if m:
        return int(m.group(1)) * 24
    m = re.match(r"(\d+)\s*d\w*\s*ago", text)
    if m:
        return int(m.group(1)) * 24

    # 文字形式: "two hours ago", "ten hours ago", "one day ago"
    _WORD = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
             "eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,
             "seventeen":17,"eighteen":18,"nineteen":19,"twenty":20,"twenty one":21,"twenty two":22,
             "twenty three":23,"twenty four":24,"twenty five":25,"twenty six":26,"twenty seven":27,
             "twenty eight":28,"twenty nine":29,"thirty":30}
    m = re.match(r"([a-z ]+)\s+hours?\s+ago", text)
    if m:
        return _WORD.get(m.group(1).strip())
    m = re.match(r"([a-z ]+)\s+days?\s+ago", text)
    if m:
        val = _WORD.get(m.group(1).strip())
        if val:
            return val * 24

    return None


def parse_salary_range(salary_str: str) -> tuple:
    """'50000-120000' → (50000, 120000), '50000-' → (50000, 999999)"""
    if not salary_str:
        return (0, 999999)
    parts = salary_str.replace(",", "").split("-")
    lo = int(parts[0]) if parts[0] else 0
    hi = int(parts[1]) if len(parts) > 1 and parts[1] else 999999
    return (lo, hi)


def fmt_time(h: int | None) -> str:
    if h is None:
        return ""
    if h < 24:
        return f"{h}h前"
    return f"{h//24}天前"
