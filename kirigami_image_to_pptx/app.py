"""
Web UI（Gradio）（Req: 1.4, 6.2–6.4）

ファイルアップロード・オプション設定・処理進捗表示・PPTX ダウンロード。
ローカル起動のみ想定（認証・課金・リモートデプロイ不要）。
"""
from __future__ import annotations

import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import gradio as gr
from dotenv import load_dotenv

from .config_loader import load_config
from .debug_log import log as debug_log
from .errors import (
    MSG_FAL_KEY_MISSING,
    PROGRESS_DECOMPOSE,
    PROGRESS_DONE,
    PROGRESS_OCR,
    PROGRESS_PPTX,
    PROGRESS_PREPROCESS,
)
from .pipeline import run_pdf, run_single


def _find_config_path() -> Path:
    p = Path(__file__).resolve().parent.parent / "config.yaml"
    if p.exists():
        return p
    return Path("config.yaml")


def run_pipeline_ui(
    file_in: str | list[str] | None,
    layers: int,
    backend: str,
    ocr_method: str,
    llm_correct: bool,
    progress: gr.Progress = gr.Progress(),
):
    """
    アップロードされたファイルを 1 件だけ受け取り、パイプラインを実行して
    生成 .pptx のパスとメッセージを返す。PDF の場合は進捗を逐次 yield して状態欄を更新する。
    """
    # 実行時に .env を再読込（Gradio ワーカー等で未読込になる場合の対策）
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

    if file_in is None:
        yield None, "ファイルをアップロードしてください。"
        return
    path_str = file_in if isinstance(file_in, str) else (file_in[0] if file_in else None)
    if not path_str:
        yield None, "ファイルをアップロードしてください。"
        return
    path = Path(path_str)
    if not path.exists():
        yield None, f"ファイルが見つかりません: {path}"
        return

    config_path = _find_config_path()
    try:
        config = load_config(config_path)
    except Exception as e:
        yield None, f"設定の読込に失敗しました: {e}"
        return

    config.decompose.num_layers = max(3, min(10, layers))
    config.decompose.backend = "api" if backend == "API (fal.ai)" else "cpu"
    config.ocr.method = "vision" if "Vision" in ocr_method else "paddle"
    config.llm_correction.enabled = llm_correct

    out_dir = Path(tempfile.mkdtemp(prefix="kirigami_ui_"))
    out_path = out_dir / f"{path.stem}.pptx"

    if path.suffix.lower() == ".pdf":
        # PDF: 別スレッドで実行し、進捗をキューで受け取って「状態」に逐次表示
        progress_queue: queue.Queue = queue.Queue()
        result_holder: list[Any] = []
        exc_holder: list[BaseException] = []

        def run_in_thread() -> None:
            try:
                def report(ratio: float, msg: str) -> None:
                    debug_log(f"report ratio={ratio:.2f} msg={msg[:50]}")
                    progress_queue.put(("progress", ratio, msg))

                debug_log("worker: start")
                if progress is not None:
                    progress(0.05, desc=PROGRESS_PREPROCESS)
                progress_queue.put(("progress", 0.05, PROGRESS_PREPROCESS))
                result = run_pdf(
                    path,
                    config,
                    output_path=out_path,
                    progress_callback=report,
                )
                debug_log("worker: run_pdf done")
                progress_queue.put(("done", result))
            except Exception as e:
                debug_log(f"worker: exception {type(e).__name__}: {e}")
                exc_holder.append(e)
                progress_queue.put(("error", None))

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        start_time = time.monotonic()

        debug_log("main: first yield")
        yield None, "PDF を読み込んでいます…"

        last_ratio, last_msg = 0.05, PROGRESS_PREPROCESS  # 最初の Empty でもハートビート出す（Gradio は yield 間隔 10s 以内が必要）
        last_progress_time = time.monotonic()  # 最終進捗受信時刻（内部処理が進んでいるか点検用）
        while True:
            try:
                item = progress_queue.get(timeout=1.0)
                debug_log(f"main: got item {item[0]}")
            except queue.Empty:
                debug_log("main: queue empty (heartbeat)")
                elapsed = int(time.monotonic() - start_time)
                since_last = int(time.monotonic() - last_progress_time)
                pct = int(last_ratio * 100)
                yield None, (
                    f"[{pct}%] {last_msg}\n"
                    f"（経過 {elapsed} 秒・処理続行中）\n"
                    f"最終進捗: {since_last} 秒前 — レイヤー分解・OCR・LLM 中は数十秒〜数分更新されません"
                )
                continue
            if item[0] == "progress":
                _, ratio, msg = item
                last_ratio, last_msg = ratio, msg
                last_progress_time = time.monotonic()
                if progress is not None:
                    progress(ratio, desc=msg)
                elapsed = int(time.monotonic() - start_time)
                pct = int(ratio * 100)
                yield None, f"[{pct}%] {msg}\n（経過 {elapsed} 秒）"
            elif item[0] == "done":
                if progress is not None:
                    progress(1.0, desc=PROGRESS_DONE)
                yield item[1], f"変換しました: {Path(item[1]).name}"
                break
            elif item[0] == "error":
                e = exc_holder[0] if exc_holder else Exception("Unknown error")
                msg = str(e)
                if isinstance(e, ValueError) and "FAL_KEY" in msg:
                    yield None, f"エラー: {MSG_FAL_KEY_MISSING}（Web UI では「レイヤー分解」を「CPU (ローカル)」に変更しても利用できます。）"
                elif "Exhausted balance" in msg or "User is locked" in msg or "fal.ai" in msg.lower():
                    yield None, f"エラー: {msg}\n\nfal.ai の残高が不足しています。「レイヤー分解」を「CPU (ローカル)」に変更するか、fal.ai/dashboard/billing でチャージしてください。"
                elif "paddleocr" in msg or "No module named" in msg and "paddle" in msg.lower():
                    yield None, f"エラー: {msg}\n\nPaddleOCR が未インストールです。「OCR方式」を「Vision (Gemini)」に変更するか、.venv で pip install paddlepaddle paddleocr を実行してください。"
                else:
                    yield None, f"エラー: {e}"
                break
        thread.join(timeout=0.1)
    else:
        # 画像 1 枚: 従来どおり一括実行
        def update_progress(step: float, msg: str) -> None:
            if progress is not None:
                progress(step, desc=msg)

        try:
            update_progress(0.05, PROGRESS_PREPROCESS)
            yield None, PROGRESS_PREPROCESS
            update_progress(0.2, PROGRESS_DECOMPOSE)
            result = run_single(path, config, output_path=out_path)
            update_progress(1.0, PROGRESS_DONE)
            yield result, f"変換しました: {Path(result).name}"
        except ValueError as e:
            msg = str(e)
            if "FAL_KEY" in msg:
                yield None, f"エラー: {MSG_FAL_KEY_MISSING}（Web UI では「レイヤー分解」を「CPU (ローカル)」に変更しても利用できます。）"
            else:
                yield None, f"エラー: {e}"
        except Exception as e:
            msg = str(e)
            if "Exhausted balance" in msg or "User is locked" in msg or "fal.ai" in msg.lower():
                yield None, f"エラー: {msg}\n\nfal.ai の残高が不足しています。「レイヤー分解」を「CPU (ローカル)」に変更するか、fal.ai/dashboard/billing でチャージしてください。"
            elif "paddleocr" in msg or ("No module named" in msg and "paddle" in msg.lower()):
                yield None, f"エラー: {msg}\n\nPaddleOCR が未インストールです。「OCR方式」を「Vision (Gemini)」に変更するか、.venv で pip install paddlepaddle paddleocr を実行してください。"
            else:
                yield None, f"エラー: {e}"


def build_ui() -> gr.Blocks:
    """Gradio インターフェースを組み立てる。"""
    with gr.Blocks(title="Kirigami 画像→PPTX") as demo:
        gr.Markdown("# Kirigami — 画像・PDF を編集可能な PPTX に変換")

        with gr.Row():
            with gr.Column(scale=1):
                file_in = gr.File(
                    label="画像または PDF をアップロード",
                    file_count="single",
                    type="filepath",
                )
                layers = gr.Slider(
                    minimum=3,
                    maximum=10,
                    value=4,
                    step=1,
                    label="レイヤー数",
                )
                backend = gr.Radio(
                    choices=["API (fal.ai)", "CPU (ローカル)"],
                    value="API (fal.ai)",
                    label="レイヤー分解",
                )
                ocr_method = gr.Radio(
                    choices=["PaddleOCR", "Vision (Gemini)"],
                    value="Vision (Gemini)",
                    label="OCR 方式",
                )
                llm_correct = gr.Checkbox(
                    value=True,
                    label="LLM でテキスト補正を行う",
                )
                run_btn = gr.Button("変換する", variant="primary")

            with gr.Column(scale=1):
                status = gr.Textbox(
                    label="状態",
                    interactive=False,
                    lines=4,
                    placeholder="変換するを押すと、ここに進捗（例: PDF 2/10 ページ変換中…）が表示されます。",
                )
                file_out = gr.File(label="PPTX をダウンロード", interactive=False)

        run_btn.click(
            fn=run_pipeline_ui,
            inputs=[file_in, layers, backend, ocr_method, llm_correct],
            outputs=[file_out, status],
        )

        gr.Markdown(
            "---\n"
            "ローカルで動作します。認証・課金・リモートデプロイは不要です。\n\n"
            "**進捗が長時間更新されない場合**: レイヤー分解（fal.ai）・OCR（Gemini）は1ステップに数分かかることがあります。"
            "内部処理の進行確認は `.env` に `KIRIGAMI_DEBUG=1` を追加して再起動し、`temp/kirigami_debug.log` を参照してください。"
        )
    return demo


def launch_local(
    server_name: str = "127.0.0.1",
    server_port: int = 7860,
    share: bool = False,
    **kwargs: Any,
) -> None:
    """ローカルで Gradio を起動する。"""
    demo = build_ui()
    demo.launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        **kwargs,
    )


if __name__ == "__main__":
    launch_local()
