# サンプルマクロ

`examples\macros`, `examples\resources`, `examples\tests` は、NyX でマクロを実装するときの参照用サンプルです。利用者の作業場所は `macros\` と `resources\` です。

| サンプル | 実装内容 | 資材 | テスト |
|----------|----------|------|--------|
| `examples\macros\sample_turbo_a_macro.py` | ボタン連打、ログ、キャプチャ保存、通知の最小例 | なし | 個別テストなし |
| `examples\macros\test_ocr_init.py` | PaddleOCR 初期化確認用のデバッグマクロ | なし | 個別テストなし |
| `examples\macros\nsmb_sort_or_splode` | 3DS touch、テンプレートマッチング、設定読み込み | `examples\resources\nsmb_sort_or_splode` | unit / perf |
| `examples\macros\frlg_wild_rng` | FRLG 野生乱数、共有 restart / opening helper | `examples\resources\frlg_wild_rng` | unit |
| `examples\macros\frlg_initial_seed` | 初期 Seed 特定、CSV 出力、OCR、認識ロジック分離 | `examples\resources\frlg_initial_seed` | unit |
| `examples\macros\frlg_id_rng` | TID 乱数、frame sweep、キーボード配列、soft reset helper | `examples\resources\frlg_id_rng` | unit |
| `examples\macros\frlg_gorgeous_resort` | FRLG おねだり、frame search、species data、OCR 認識 | `examples\resources\frlg_gorgeous_resort` | unit |
| `examples\macros\shared` | 公開サンプル間の共通部品 | なし | 各マクロの test から利用 |

`examples\macros\shared` は examples 内の共有部品です。ローカル `macros\` から直接インポートする前提にはしません。複数のローカルマクロで共有したい処理は、ローカル側の共有部品として切り出します。

