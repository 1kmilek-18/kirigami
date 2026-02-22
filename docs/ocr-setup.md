# OCR 環境の用意

画像・PDF からテキストを抽出するために、**どちらか一方**の環境を用意してください。

---

## 方法 A: Vision API（Gemini）— おすすめ

**やること**: API キーが読まれるようにするだけ。追加の pip インストールは不要です。

1. **キーがすでにある場合**  
   `presentation-maker/.env` に `GEMINI_API_KEY` が入っていれば、Kirigami が自動で参照します（`GOOGLE_API_KEY` として利用）。

2. **config.yaml で Vision を指定**  
   ```yaml
   ocr:
     method: vision   # paddle → vision に変更
   ```

3. **実行**  
   ```bash
   python -m kirigami_image_to_pptx input/sample.png
   ```

**補足**: 通信が発生するためオフラインでは使えません。キーは .env のみ（config.yaml には書かない）で運用してください。

---

## 方法 B: PaddleOCR（ローカル）

**やること**: パッケージを入れて、初回実行時にモデルをダウンロードします。オフラインで使えます。

1. **インストール**  
   ```bash
   pip install paddlepaddle paddleocr
   ```

2. **config.yaml で Paddle を指定**（既定のままなら不要）  
   ```yaml
   ocr:
     method: paddle
   ```

3. **初回実行**  
   初回だけモデルがダウンロードされます。2 回目以降はそのまま使えます。

**補足**: ディスク容量とメモリをいくらか使います。API キーは不要です。

---

## どちらを選ぶか

| 項目           | Vision API（Gemini） | PaddleOCR      |
|----------------|----------------------|----------------|
| 準備           | キーを .env に用意   | pip でインストール |
| オフライン     | 不可                 | 可             |
| 追加コスト     | API 利用料           | なし           |
| 推奨           | すでに GEMINI キーがある場合 | オフライン・キーを増やしたくない場合 |

**まとめ**: すでに `presentation-maker/.env` で Gemini を使っているなら、**config の `ocr.method` を `vision` にするだけ**で OCR 環境は整います。
