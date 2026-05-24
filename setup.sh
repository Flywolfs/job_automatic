#!/bin/bash
# Job Crawlers 环境搭建脚本
# 用法: bash setup.sh

set -e

echo "============================================"
echo "  Job Crawlers 环境检查与搭建"
echo "============================================"

# ── 1. Python ────────────────────────────
echo ""
echo "[1/5] 检查 Python..."
python3 --version 2>/dev/null || { echo "❌ 需要 Python 3.10+"; exit 1; }
echo "  ✅ $(python3 --version)"

# ── 2. Node.js ───────────────────────────
echo ""
echo "[2/5] 检查 Node.js..."
NODE_VERSION=$(node --version 2>/dev/null || echo "")
if [ -z "$NODE_VERSION" ]; then
    echo "  ⚠️ Node.js 未安装，尝试通过 nvm 安装..."
    if [ -f "$HOME/.nvm/nvm.sh" ]; then
        source "$HOME/.nvm/nvm.sh"
        nvm install 22
        nvm use 22
        echo "  ✅ node $(node --version)"
    else
        echo "  ❌ 请先安装 nvm: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
        exit 1
    fi
else
    echo "  ✅ node $NODE_VERSION"
fi

# ── 3. bb-browser ────────────────────────
echo ""
echo "[3/5] 检查 bb-browser..."
if command -v bb-browser &>/dev/null; then
    echo "  ✅ $(which bb-browser)"
else
    echo "  ❌ bb-browser 未安装"
    echo "  请参考 bb-browser 安装文档进行安装"
    echo "  安装后需在独立 Chrome profile 中登录 JobsDB 和 CTGoodJobs"
fi

# ── 4. Chrome ────────────────────────────
echo ""
echo "[4/5] 检查 Chrome..."
if command -v google-chrome &>/dev/null || command -v chromium-browser &>/dev/null; then
    echo "  ✅ Chrome/Chromium 已安装"
else
    echo "  ⚠️ Chrome 未找到，bb-browser 需要 Chrome 浏览器"
fi

# ── 5. 配置文件 ──────────────────────────
echo ""
echo "[5/5] 检查配置文件..."
CONFIG_FILE="$(dirname "$0")/email_config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "  创建 email_config.json 模板..."
    cat > "$CONFIG_FILE" << 'EOF'
{
    "sender_name": "Jobs Bot",
    "sender_email": "your-email@gmail.com",
    "recipient": "your-email@gmail.com",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "app_password": "YOUR_GMAIL_APP_PASSWORD"
}
EOF
    chmod 600 "$CONFIG_FILE"
    echo "  ⚠️ 请编辑 $CONFIG_FILE 填入真实的 Gmail 信息"
else
    echo "  ✅ email_config.json 已存在"
fi

# ── 登录提示 ────────────────────────────
echo ""
echo "============================================"
echo "  后续步骤"
echo "============================================"
echo ""
echo "1. 编辑 email_config.json:"
echo "   vim $(dirname "$0")/email_config.json"
echo ""
echo "2. 在 bb-browser 的 Chrome 中登录各平台:"
echo "   bb-browser open https://hk.jobsdb.com"
echo "   → 登录你的 JobsDB 账户"
echo "   bb-browser open https://www.ctgoodjobs.hk"
echo "   → 登录你的 CTGoodJobs 账户"
echo ""
echo "3. 上传 Cover Letter (仅 JobsDB 需要):"
echo "   确保 ~/Documents/CV_2026/cover_letter.pdf 存在"
echo ""
echo "4. 测试运行:"
echo "   cd $(dirname "$0")/jobsdb && python3 crawl.py --report"
echo "   cd $(dirname "$0")/ctgoodjobs && python3 crawl.py --report"
echo ""
echo "5. 手动跑一次全流程:"
echo "   bash ~/.hermes/scripts/job_crawlers_daily.sh"
echo ""
echo "6. 查看 Cron 状态:"
echo "   hermes cron list"
echo ""
echo "✅ 环境检查完成"
