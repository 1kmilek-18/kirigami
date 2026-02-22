"""
CLI（Req: 1.3, 6.1, 8.1–8.3）

コマンドライン引数・オプションの解析、単一/ディレクトリ一括実行、進捗・エラー表示。
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .config_loader import load_config
from .pipeline import collect_input_paths, run_batch, run_pdf, run_single

if TYPE_CHECKING:
    from .config_loader import AppConfig

LOG = logging.getLogger(__name__)


def _apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> None:
    """CLI オプションを config に反映する。"""
    if args.layers is not None:
        config.decompose.num_layers = max(3, min(10, args.layers))
    if args.backend is not None:
        config.decompose.backend = args.backend
    if args.ocr is not None:
        config.ocr.method = args.ocr
    if args.no_llm_correct:
        config.llm_correction.enabled = False
    if args.output is not None:
        config.paths.output_dir = str(args.output)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解析する。"""
    parser = argparse.ArgumentParser(
        description="Kirigami: 画像・PDF を編集可能な PPTX に変換する",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=None,
        help="入力ファイルまたはディレクトリ（省略時は config の input_dir を一括対象にする）",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="出力ディレクトリ（省略時は config の output_dir）",
    )
    parser.add_argument(
        "--layers",
        type=int,
        default=None,
        metavar="N",
        help="レイヤー数（3–10）",
    )
    parser.add_argument(
        "--backend",
        choices=("api", "cpu"),
        default=None,
        help="レイヤー分解バックエンド（api=fal.ai, cpu=ローカル推論）",
    )
    parser.add_argument(
        "--ocr",
        choices=("paddle", "vision"),
        default=None,
        help="OCR 方式（paddle=PaddleOCR, vision=Gemini Vision）",
    )
    parser.add_argument(
        "--no-llm-correct",
        action="store_true",
        help="LLM 補正を無効にする",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path("config.yaml"),
        help="設定ファイルのパス",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細ログを出力する",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="進捗メッセージを抑える（エラーのみ）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。戻り値は終了コード（0=成功）。"""
    args = parse_args(argv)

    # ログレベル
    if args.quiet:
        logging.basicConfig(level=logging.WARNING, format="%(message)s")
    elif args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    if not config_path.exists():
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"

    try:
        config = load_config(config_path)
    except Exception as e:
        LOG.error("設定の読込に失敗しました: %s", e)
        return 1

    _apply_cli_overrides(config, args)

    # 入力の決定
    if args.input is not None:
        input_path = args.input.resolve()
    else:
        # 省略時は config の input_dir を一括対象
        from .config_loader import ensure_directories_from_config
        in_dir, out_dir, _ = ensure_directories_from_config(config)
        input_path = in_dir

    if not input_path.exists():
        LOG.error("入力が見つかりません: %s", input_path)
        return 2

    output_dir = None
    if args.output is not None:
        output_dir = args.output.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if input_path.is_file():
            # 単一ファイル
            if not args.quiet:
                print(f"処理中: {input_path.name}", flush=True)
            if input_path.suffix.lower() == ".pdf":
                out = run_pdf(input_path, config, output_path=output_dir / f"{input_path.stem}.pptx" if output_dir else None)
            else:
                out = run_single(input_path, config, output_path=output_dir / f"{input_path.stem}.pptx" if output_dir else None)
            if not args.quiet:
                print(f"出力: {out}", flush=True)
            return 0

        # ディレクトリ一括
        paths = collect_input_paths(input_path)
        if not paths:
            LOG.warning("対象ファイルがありません: %s", input_path)
            return 0
        if not args.quiet:
            print(f"一括処理: %d 件" % len(paths), flush=True)
        results = run_batch([p for p in paths], config, output_dir=output_dir)
        for out in results:
            if not args.quiet:
                print(f"  出力: {out}", flush=True)
        if not args.quiet:
            print(f"完了: %d 件" % len(results), flush=True)
        return 0
    except FileNotFoundError as e:
        LOG.error("ファイルが見つかりません: %s", e)
        return 2
    except ValueError as e:
        LOG.error("引数エラー: %s", e)
        return 2
    except Exception as e:
        LOG.exception("処理に失敗しました: %s", e)
        return 1


def run() -> None:
    """パッケージから呼ぶ用（sys.exit 付き）。"""
    sys.exit(main())


if __name__ == "__main__":
    run()
