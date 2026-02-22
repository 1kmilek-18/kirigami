# Requirements Document

## Introduction

本ドキュメントは、画像を編集可能な PowerPoint（.pptx）に変換するローカルツール「Kirigami 型アプリ」の要件を定義する。AI 生成スライド画像をレイヤー分解・OCR・LLM 補正を経て .pptx に再構成し、Kirigami.app と同等の機能をローカル環境で実現する。対象は個人利用・ローカル動作（Ubuntu + Cursor）とする。

---

## Project Description (Input)

# Kirigami型アプリ — 要件定義・技術仕様書（最終版）

> **画像 → 編集可能PowerPoint 自動変換ツール**
>
> ローカル動作・個人利用 ｜ MINISFORUM X1 Pro 370 + Ubuntu + Cursor

（目的）AI 生成スライド画像を編集可能な .pptx に変換する。（背景）画像の要素分解＋PPTX 再構築により、1 文字修正のためだけの再生成を不要にする。（参考）Kirigami.app と同等機能をローカルで実現。

**環境前提**: Ubuntu、Python 3.10〜3.12、NVIDIA GPU 非搭載（CUDA 前提にしない）。レイヤー分解は API または CPU 推論。認証・課金・デプロイ不要。CLI（メイン）＋ Gradio Web UI（オプション）。

**コア機能**: 入力（PNG/JPEG/WebP/PDF、ファイル・ディレクトリ・バッチ）、レイヤー分解（RGBA 3〜10 層、fal.ai API 優先・CPU 推論代替）、テキスト抽出・補正（OCR＋LLM 補正、日英、Gemini Vision 代替ルート）、出力（.pptx、テキスト/画像/図形の個別オブジェクト、レイアウト・Z-order 再現、output/ 出力）。

---

## Requirements

### 1. 入力と前処理

**Objective:** As a 利用者, I want 画像または PDF を指定してツールに渡せる, so that スライド画像を編集可能 PPTX に変換できる。

#### Acceptance Criteria

1. When 利用者が画像ファイル（PNG, JPEG, WebP）のパスを指定したとき, the Kirigami ツール shall その画像を入力として受け付け、パイプラインに渡す。
2. When 利用者が PDF ファイルを指定したとき, the Kirigami ツール shall 複数ページをページ単位に分割し、各ページを個別の画像として処理する。
3. Where CLI が利用される, the Kirigami ツール shall ファイルパス指定およびディレクトリ一括指定のいずれかで入力を受け付ける。
4. Where Web UI が利用される, the Kirigami ツール shall ドラッグ&ドロップでファイルを受け付ける。
5. When 利用者がディレクトリを指定しバッチ処理を要求したとき, the Kirigami ツール shall フォルダ内の対象画像および PDF を一括で変換する。
6. The Kirigami ツール shall 入力画像の読み込み・リサイズ・正規化などの前処理を実施し、後段のレイヤー分解および OCR に渡せる形式にする。

---

### 2. レイヤー分解

**Objective:** As a 利用者, I want 画像を背景・グラフィック・テキスト領域・装飾などに自動分解される, so that 編集可能な要素として PPTX に再構成できる。

#### Acceptance Criteria

1. When 入力画像が前処理を完了したとき, the Kirigami ツール shall 画像を複数の RGBA レイヤー（3〜10 層）に自動分解する。
2. The Kirigami ツール shall 背景・グラフィック要素・テキスト領域・装飾を分離対象として扱う。
3. Where 画像要素が重なっている, the Kirigami ツール shall 重なった要素をインテリジェントに分離する。
4. When 利用者がレイヤー数を指定したとき（例: --layers N）, the Kirigami ツール shall 指定された層数で分解を実行する。
5. The Kirigami ツール shall レイヤー分解の実行方式として、優先的に外部 API（例: fal.ai）を用い、利用不可時は CPU 推論で代替できるようにする。
6. The Kirigami ツール shall レイヤー分解の実装が NVIDIA GPU（CUDA）に依存しない設計とする。

---

### 3. テキスト抽出と座標・属性

**Objective:** As a 利用者, I want 画像内のテキストが認識され座標と属性付きで取得される, so that PPTX 上で編集可能なテキストボックスとして再現できる。

#### Acceptance Criteria

1. When 入力画像または分解済みレイヤーが与えられたとき, the Kirigami ツール shall 画像内テキストを認識し、テキスト内容と座標を抽出する。
2. The Kirigami ツール shall 日本語および英語のテキスト抽出に対応する。
3. The Kirigami ツール shall 各テキストについて、レイアウト再現に必要な座標（境界ボックス等）を保持する。
4. Where テキストの視覚的属性が利用可能である, the Kirigami ツール shall フォントサイズ・色・太さなどを推定し、出力 PPTX に反映する。
5. Where 代替ルートとして Vision API が利用される, the Kirigami ツール shall 画像を直接入力としてテキスト抽出と属性推定を一括で取得できるようにする。

---

### 4. テキスト補正（LLM）

**Objective:** As a 利用者, I want OCR の誤認識が文脈に基づいて補正される, so that 潰れ文字や曖昧な文字の編集可能性が高まる。

#### Acceptance Criteria

1. When テキスト抽出結果が得られたとき, the Kirigami ツール shall オプションで LLM による文脈ベースの誤認識補正を実行できる。
2. Where LLM 補正が有効である, the Kirigami ツール shall 利用可能な API（例: Claude, Gemini）またはローカル LLM（例: Ollama）のいずれかで補正を実行する。
3. When 利用者が LLM 補正を無効にしたとき, the Kirigami ツール shall 補正を行わず、OCR 結果をそのまま後段に渡す。
4. The Kirigami ツール shall 補正後もテキストと座標の対応を維持し、PPTX 上の正しい位置にテキストを配置する。

---

### 5. 出力（PPTX 生成）

**Objective:** As a 利用者, I want 変換結果が編集可能な .pptx として得られる, so that PowerPoint 等で文字・図形を個別に編集できる。

#### Acceptance Criteria

1. When レイヤー分解結果とテキスト（および属性）が揃ったとき, the Kirigami ツール shall 編集可能な .pptx 形式で出力する。
2. The Kirigami ツール shall 出力をテキストボックス・画像・図形の個別オブジェクトとして配置する。
3. The Kirigami ツール shall 元画像のレイアウトおよび Z-order（前面/背面）を再現する。
4. When 出力先が指定されていないとき, the Kirigami ツール shall 既定の出力ディレクトリ（例: output/）に .pptx を保存する。
5. When 利用者が出力先を指定したとき, the Kirigami ツール shall 指定されたディレクトリに .pptx を保存する。
6. The Kirigami ツール shall スライドのアスペクト比（例: 16:9）を設定可能とし、座標をそれに合わせて変換する。

---

### 6. CLI と Web UI

**Objective:** As a 利用者, I want CLI または Web UI のどちらかで操作できる, so that 作業スタイルに合わせて利用できる。

#### Acceptance Criteria

1. Where CLI が利用される, the Kirigami ツール shall コマンドライン引数で入力パス・レイヤー数・バックエンド（API/CPU）・OCR 方式・LLM 補正の有無・出力先などを指定可能とする。
2. Where Web UI が利用される, the Kirigami ツール shall ファイルアップロード・オプション設定・処理進捗表示・結果のプレビューおよび PPTX ダウンロードを提供する。
3. When Web UI を起動したとき, the Kirigami ツール shall ローカルでサーバー（例: Gradio）を起動し、ブラウザからアクセス可能な URL を提供する。
4. The Kirigami ツール shall 認証・課金・リモートデプロイを必要とせず、ローカル起動のみで利用できる。

---

### 7. 設定と環境

**Objective:** As a 利用者, I want 設定ファイルと環境変数で動作を切り替えられる, so that API キー・バックエンド・言語などを柔軟に設定できる。

#### Acceptance Criteria

1. The Kirigami ツール shall 設定をファイル（例: config.yaml）で管理し、レイヤー数・分解バックエンド・OCR 方式・LLM プロバイダ・出力ディレクトリ等を指定可能とする。
2. The Kirigami ツール shall API キー等の機密情報を環境変数（例: .env）から読み込み、リポジトリにコミットしない運用を可能とする。
3. When 複数の LLM または API プロバイダが設定されている, the Kirigami ツール shall 優先順位またはフォールバックに従って利用する。
4. The Kirigami ツール shall 中間ファイル（例: レイヤー PNG）を一時ディレクトリに出力し、オプションで処理後の削除を可能とする。

---

### 8. 非機能・制約

**Objective:** As a 開発者/利用者, I want 環境制約と品質目標が満たされる, so that 指定環境で安定して利用できる。

#### Acceptance Criteria

1. The Kirigami ツール shall NVIDIA GPU（CUDA）を前提としない。レイヤー分解は API または CPU 推論で実行する。
2. The Kirigami ツール shall Python 3.10〜3.12 で動作する。
3. When ネットワークが利用できない場合, the Kirigami ツール shall 設定に応じて API に依存しないルート（CPU 推論・ローカル OCR・ローカル LLM）で処理を継続できる。
4. If 入力ファイルが対応フォーマットでない、または破損している, the Kirigami ツール shall 明確なエラーを報告し、可能であれば処理をスキップする。
5. The Kirigami ツール shall 処理の進捗またはエラーを利用者が把握できるようにする（CLI のログまたは Web UI の表示）。
