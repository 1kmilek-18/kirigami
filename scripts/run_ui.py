#!/usr/bin/env python3
"""Gradio Web UI をローカルで起動する。認証・課金・リモートデプロイは不要。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kirigami_image_to_pptx.app import launch_local

if __name__ == "__main__":
    launch_local(server_name="127.0.0.1", server_port=7860)
