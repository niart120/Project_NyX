## Summary

<!-- 変更内容を1-3行で要約する。背景や動機の詳細は Related セクションのリンク先に委ねる -->

## Related

<!-- 関連する Issue・spec・プロンプト等へのリンク。エージェントの場合は指示元を必ず記載する -->

- closes #

## Changes

<!-- 論理的な変更単位でリスト化する。diff を見れば分かるファイル名の羅列ではなく「何をどう変えたか」を書く -->

-

## Commit Log

<!-- squash マージで個別コミットが消えるため、ここにコミット履歴を残す。
     `git log --oneline main..HEAD` の出力を貼り付ける。
     各コミットメッセージが変更の "Why" を記録する役割を持つ -->

```
<git log --oneline main..HEAD の出力>
```

## Testing

<!-- 実行した検証コマンドとその結果を記載する -->

```
pnpm lint
pnpm test:run
pnpm exec tsc -b --noEmit
```

## Checklist

- [ ] lint / format チェック通過
- [ ] 既存テスト通過
- [ ] コミット prefix (feat/fix 等) が変更の動機と一致している
- [ ] 新規・変更コードに対するテスト追加（該当する場合）
- [ ] 型チェック通過

## Review Notes

<!-- レビュアーに判断を委ねたい箇所、既知のリスク、検討した代替案などを記載する。特になければセクションごと削除して良い -->

<!-- 任意セクション: 必要に応じて以下を追加する
### Screenshots
### Migration / Breaking Changes
-->
