#!/usr/bin/env python3
"""JobsDB 邮件通知 — 继承 BaseNotifier"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.base_notifier import BaseNotifier

SHARED_CONFIG = Path(__file__).parent.parent.parent / "email_config.json"
CONFIG_PATH = SHARED_CONFIG if SHARED_CONFIG.exists() else (Path(__file__).parent / "email_config.json")


class JobsDBNotifier(BaseNotifier):
    PLATFORM = "JobsDB"
    EMOJI = "🤖"
    THEME_COLOR = "#1a73e8"
    THEME_BG = "#f0f7ff"


if __name__ == "__main__":
    JobsDBNotifier(Path(__file__).parent, CONFIG_PATH).build_and_send()
