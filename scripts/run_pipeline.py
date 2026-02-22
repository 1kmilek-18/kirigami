#!/usr/bin/env python3
"""
パイプラインを実行するスクリプト（CLI のラッパー）。

使い方:
  python scripts/run_pipeline.py [入力パス]
  python scripts/run_pipeline.py input/
  python scripts/run_pipeline.py --help

  環境変数で入力既定値を上書き:
  KIRIGAMI_TEST_PDF=/path/to/file.pdf python scripts/run_pipeline.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from kirigami_image_to_pptx.cli import main as cli_main


def main() -> None:
    argv = list(sys.argv[1:])
    if not argv and os.environ.get("KIRIGAMI_TEST_PDF"):
        argv = [os.environ["KIRIGAMI_TEST_PDF"]]
    elif not argv:
        default = ROOT / "input" / "jooto_proposal_20260203232912.pdf"
        if default.exists():
            argv = [str(default)]
    exit_code = cli_main(argv)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
