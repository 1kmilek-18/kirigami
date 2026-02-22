# Research & Design Decisions Template

---
**Purpose**: 画像→PPTX 変換ツールの技術設計に必要な調査結果と決定根拠を記録する。
---

## Summary

- **Feature**: kirigami-image-to-pptx
- **Discovery Scope**: New Feature（グリーンフィールド・複数外部API統合）
- **Key Findings**:
  - fal.ai Qwen Image Layered API は image_url / num_layers / output が明確。Python では fal-client で subscribe または queue 利用。約 $0.05/画像、15–30 秒。
  - Qwen-Image-Layered のローカル CPU 推論は公式に最適化されておらず、16GB×4 GPU でも負荷報告あり。fal.ai API をデフォルトとし、CPU はオフライン代替として位置づける。
  - PaddleOCR は lang='japan' で日本語対応、PaddlePaddle CPU 版で GPU 不要。python-pptx は add_picture / add_textbox でスライド構築に十分。
  - パイプライン型（入力→前処理→分解→OCR→補正→PPTX）で境界を分離し、各ステップを差し替え可能にする設計が適切。

## Research Log

### fal.ai Qwen Image Layered API

- **Context**: 要件 2（レイヤー分解）の一次手段として API 契約を確認。
- **Sources Consulted**: [fal.ai Qwen Image Layered API](https://fal.ai/models/fal-ai/qwen-image-layered/api)、検索結果（フォーマット・料金・制限）。
- **Findings**:
  - 入力: `image_url`（必須）、`num_layers`（デフォルト 4、1–10）、`num_inference_steps`、`output_format`（png/webp）等。
  - 出力: `images` 配列（各要素に `url`）。Data URI / ファイルアップロードも利用可。
  - 認証: 環境変数 `FAL_KEY`。Python は `fal-client` または REST。
  - 制限: 重なり多いオブジェクトの融合、透明・低コントラストは苦手。
- **Implications**: decompose コンポーネントは「画像パス → ローカル/URL 化 → API 呼び出し → 返却 URL からレイヤー画像ダウンロード」のインターフェースで隠蔽する。

### Qwen-Image-Layered ローカル（CPU / diffusers）

- **Context**: オフライン代替（要件 2.5, 8.1）の実現性確認。
- **Sources Consulted**: Hugging Face Qwen/Qwen-Image-Layered、ディスカッション（GPU メモリ）、検索結果。
- **Findings**:
  - diffusers の `QwenImageLayeredPipeline`、`transformers>=4.51.3`。通常は CUDA + bfloat16。
  - CPU 推論の公式例は少なく、計算負荷大。96GB RAM 環境では実用可能性はあるが速度は遅い（分単位）。
- **Implications**: レイヤー分解は「API アダプタ」と「ローカル推論アダプタ」の二実装にし、設定で切替。CPU はオプションとしてドキュメント化する。

### PaddleOCR 日本語・CPU

- **Context**: 要件 3（テキスト抽出）の一次ルート。
- **Sources Consulted**: PaddleOCR 公式ドキュメント、Quick Start。
- **Findings**:
  - `PaddleOCR(lang='japan', use_angle_cls=True)` で日本語。CPU 用は `paddlepaddle`（GPU 用は別パッケージ）。
  - モデルは初回自動ダウンロード（`~/.paddleocr` 等）。`ocr.ocr(image_path, cls=True)` で bbox + テキスト + 信頼度。
- **Implications**: ocr コンポーネントは「画像パス → List[（bbox, text, confidence）]」の型で契約。後段で座標正規化・属性推定と結合する。

### python-pptx スライド構築

- **Context**: 要件 5（出力）の実装手段。
- **Sources Consulted**: python-pptx ドキュメント（Shapes, Quick Start）。
- **Findings**:
  - `slide.shapes.add_picture(path, left, top, width, height)`、`add_textbox(left, top, width, height)`。寸法は Emu または Inches/Pt。
  - テキストは `text_frame.paragraphs[0].text`、`font.size`、`font.bold`、`font.color.rgb` で設定。
- **Implications**: pptx_builder は「レイヤー画像パス列 + テキスト要素リスト + スライド寸法」を入力とし、Z-order 順に add_picture / add_textbox で配置するインターフェースとする。

### Gradio 進捗・ファイル入力

- **Context**: 要件 6.2（進捗表示・アップロード）。
- **Sources Consulted**: Gradio Docs（Progress）、検索結果。
- **Findings**:
  - 処理進捗は `gr.Progress()` を関数引数に取り、`progress(0, desc="...")` や `progress.tqdm(iterable)` で更新。
  - ファイルは `gr.File` または `gr.Image`。アップロード進捗の不具合は過去に修正済み。
- **Implications**: app コンポーネントはパイプラインをラップし、Progress でステップ表示。入力は File で受け、一時保存後に main パイプラインに渡す。

### PyMuPDF PDF→画像

- **Context**: 要件 1.2（PDF 複数ページ分割）。
- **Sources Consulted**: PyMuPDF Recipes (Images)、検索結果。
- **Findings**:
  - `pymupdf.open(path)` → `for page in doc: page.get_pixmap(dpi=...)` → `pix.save(...)`。PNG 等出力可能。
- **Implications**: pdf_utils は「PDF パス → List[画像パス]」を返すインターフェース。解像度は config で指定可能とする。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| Pipeline / Layered | 入力→前処理→分解→OCR→補正→PPTX の順でコンポーネントを直列に実行 | 境界明確、ステップ差し替え・テスト容易、要件の 1–5 と対応 | 並列化はステップ内（例: バッチ）で検討 | 採用 |
| Monolith single module | 全処理を一ファイルに集約 | 実装が単純 | テスト・差し替え・並列実装が困難 | 不採用 |
| Microservices | 各ステップを別プロセス/サービスに分割 | スケール可能 | ローカル単体ツールには過剰、認証・デプロイ不要の前提に反する | 不採用 |

## Design Decisions

### Decision: パイプライン＋アダプタによるレイヤー分解の二重化

- **Context**: 要件 2.5（API 優先・CPU 代替）、2.6（CUDA 非依存）。
- **Alternatives Considered**:
  1. API のみ — 実装が簡単だがオフライン不可。
  2. CPU のみ — オフライン可だが速度・メモリ負荷が大きい。
- **Selected Approach**: decompose モジュールで「レイヤー分解プロトコル」（入力画像 → レイヤー画像リスト）を定義し、fal.ai 用アダプタとローカル推論用アダプタの二実装を config/CLI で切替。
- **Rationale**: ユーザーがネット・コストを考慮して選択できる。CUDA に依存しない。
- **Trade-offs**: アダプタ層の追加でコード量は増えるが、テストと保守が容易。
- **Follow-up**: CPU 推論時の解像度・ステップ数でメモリ使用量を実機で計測する。

### Decision: OCR と LLM 補正の分離

- **Context**: 要件 3（テキスト抽出）、4（LLM 補正）。Gemini Vision は一括ルートとして別オプション。
- **Alternatives Considered**:
  1. OCR と補正を常に一体 — シンプルだが、補正 OFF や Vision 一括ルートとの切り替えが難しい。
  2. OCR → 補正をパイプラインの二ステップに分離し、補正はオプション。Vision は別コンポーネントで「画像 → テキスト+属性」を返す。
- **Selected Approach**: ocr（PaddleOCR）と llm_correct を別コンポーネントにし、vision_ocr を代替ルートとして用意。pipeline が ocr_method に応じて PaddleOCR+llm_correct または vision_ocr を選択。
- **Rationale**: 要件 3.5、4.1–4.3 を満たしつつ、テストとフォールバックが明確になる。
- **Trade-offs**: データ型（テキスト+bbox+属性）を共通化する必要がある。
- **Follow-up**: テキスト要素の共通 DTO（dataclass または TypedDict）を設計で定義する。

### Decision: 設定の一元化（config.yaml + .env）

- **Context**: 要件 7（設定と環境）。
- **Selected Approach**: レイヤー数・バックエンド・OCR 方式・LLM プロバイダ・出力先等は config.yaml。API キーは .env と環境変数のみ。
- **Rationale**: 機密情報をリポジトリに含めず、設定のバージョン管理と分離が可能。
- **Follow-up**: 起動時に config と必須 env の存在チェックを行う。

## Risks & Mitigations

- **fal.ai API 障害・廃止** — レイヤー分解を CPU アダプタに切替可能にし、ドキュメントに手順を記載。
- **Qwen-Image-Layered CPU 推論の遅さ・メモリ** — デフォルトを API にし、CPU は「オフライン時のみ」と明記。解像度・ステップ数を設定で下げられるようにする。
- **PaddleOCR 日本語の精度** — LLM 補正と Gemini Vision 代替ルートで補完。品質目標（CER 等）はテストでモニタリング。
- **python-pptx の座標・Emu 変換ミス** — 座標正規化（0–1 またはピクセル→インチ/Emu）を image_utils または pptx_builder の単一レイヤーに集約し、単体テストで検証。

## References

- [fal.ai Qwen Image Layered API](https://fal.ai/models/fal-ai/qwen-image-layered/api) — 入力/出力スキーマ、認証、ファイル扱い
- [Qwen/Qwen-Image-Layered (Hugging Face)](https://huggingface.co/Qwen/Qwen-Image-Layered) — ローカル推論
- [PaddleOCR Documentation](https://www.paddleocr.ai/) — 日本語・CPU
- [python-pptx — python-pptx documentation](https://python-pptx.readthedocs.io/) — スライド・図形・テキスト
- [PyMuPDF Recipes: Images](https://pymupdf.readthedocs.io/en/latest/recipes-images.html) — PDF→画像
- [Gradio Progress](https://www.gradio.app/guides/progress-bars) — 進捗表示
