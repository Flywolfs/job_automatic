#!/usr/bin/env python3
"""CTGoodJobs 邮件通知 — 继承 BaseNotifier"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.base_notifier import BaseNotifier

# 共享 email config
SHARED_CONFIG = Path(__file__).parent.parent / "email_config.json"
CONFIG_PATH = SHARED_CONFIG if SHARED_CONFIG.exists() else (Path(__file__).parent.parent / "jobsdb" / "email_config.json")


class CTGoodJobsNotifier(BaseNotifier):
    PLATFORM = "CTGoodJobs"
    EMOJI = "🔶"
    THEME_COLOR = "#e65100"
    THEME_BG = "#fff3e0"


if __name__ == "__main__":
    CTGoodJobsNotifier(Path(__file__).parent, CONFIG_PATH).build_and_send()
