# 入力ファイル

テスト用 PDF を使う場合:

1. **jooto_proposal_20260203232912.pdf** をこのフォルダにコピーする  
   または
2. 環境変数でパスを指定する:
   ```bash
   export KIRIGAMI_TEST_PDF="/path/to/jooto_proposal_20260203232912.pdf"
   python scripts/run_pipeline.py
   ```

Windows の Cursor ワークスペースに PDF がある場合の WSL での例:
```bash
export KIRIGAMI_TEST_PDF="/mnt/c/Users/1kmilek/AppData/Roaming/Cursor/User/workspaceStorage/1ae7e87fcef5cf5e8a0a569fcb041c03/pdfs/3c63d71a-201a-49e8-91bc-7167d173bf49/jooto_proposal_20260203232912.pdf"
python scripts/run_pipeline.py
```

**OCR について**: config.yaml の `ocr.method` が `vision` のときは `GOOGLE_API_KEY` を .env に設定してください。`paddle` のときは `pip install paddlepaddle paddleocr` が必要です。FAL_KEY が無い場合はレイヤー分解は自動で CPU にフォールバックします。
