# フレームワーク再設計ドキュメント 残レビューコメント

> **対象**: `spec\framework\rearchitecture\*.md`  
> **観点**: `framework-spec-writing` の必須構成、公開 API の一貫性、依存方向、後方互換性、スレッド安全性、テストゲート、移行可能性

## 1. 総評

再設計ドキュメント群に対する機械的な整合修正は反映済みである。本ファイルには、公開 API の意味論や実装方針の選択を伴うためユーザー判断が必要なコメントだけを残す。

## 2. 判断待ち

### J-01 概要の未決事項が残っている

- **対象**: `FW_REARCHITECTURE_OVERVIEW.md:293-296`
- **問題**: `MacroDefinition` の class 参照保持と singleton の runtime 登録方針が未決である。
- **影響**: reload 時の古い class 参照混入や、テスト間状態汚染の扱いを実装者が判断できない。
- **判断事項**: `MacroDefinition` が import 後の class object を保持するか、module/class 名だけを保持して factory で再解決するかを決める。`singletons.py` に既定 runtime を置くか、factory 関数に留めるかを決める。
