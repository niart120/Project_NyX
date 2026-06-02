---
name: pr-merge-cleanup
description: "作業ブランチを GitHub PR 経由で main にマージし、ローカル同期・ブランチ削除まで一括実行するワークフロースキル。USE WHEN: ユーザが「PRを出して」「マージして」「ブランチをまとめて」「mainに入れて」「PRクリーンアップ」など、作業ブランチの変更をリモートに反映したい意図を示したとき。push → PR作成 → squashマージ → ローカル同期 → ブランチ削除の全ステップを自動化する。"
---

# PR Merge Cleanup

作業ブランチの変更を GitHub PR 経由でデフォルトブランチにマージし、ローカルへの同期と不要ブランチの削除までを一括で実行するワークフロー。

## 前提条件

- GitHub リモートが設定済みであること
- 作業ブランチで全コミットが完了していること
- GitHub への push 権限を持つこと

## ワークフロー

ローカル同期は必須ステップとして扱う。PR マージ後は必ずデフォルトブランチへ移動し、`git pull --ff-only` の実行結果とローカル HEAD を確認してから作業ブランチを削除する。

### 1. ブランチ確認

```bash
git branch --show-current
```

- デフォルトブランチ (`main` / `master`) の場合は処理を中断し、ユーザに報告する
- デフォルトブランチ名は `git symbolic-ref refs/remotes/origin/HEAD` や `git remote show origin` から取得する。取得できない場合は `main` を仮定する

### 2. リモートへプッシュ

```bash
git push -u origin <ブランチ名>
```

プッシュ失敗時はエラー内容に応じて対処する:

- **pre-push hook エラー**: hook が出力したメッセージに従い修正 → 再コミット → 再プッシュ
  - lint / format エラー: プロジェクトの lint / format コマンドを実行して修正
  - 型チェックエラー: 型定義を修正
- **リモートとの競合**: `git pull --rebase origin <デフォルトブランチ>` で解消を試みる
- **その他**: エラーメッセージをユーザに報告

### 3. リポジトリ情報の取得

```bash
git remote get-url origin
```

出力から `owner/repo` を抽出する (`https://github.com/OWNER/REPO.git` または `git@github.com:OWNER/REPO.git` のいずれにも対応)。

`mcp_github_get_me` で認証ユーザを確認する。

### 4. PR 作成

`mcp_github_create_pull_request` で PR を作成する。

- **ベースブランチ**: ステップ 1 で特定したデフォルトブランチ
- **タイトル**: ブランチ名から推測するか、直近のコミットメッセージを使用
- **本文の組み立て**:
  1. `.github/PULL_REQUEST_TEMPLATE.md` が存在すれば読み込み、そのセクション構成に従って本文を生成する
  2. テンプレートがなければ以下の最低限の構成で生成する:
     - **Summary**: 変更内容の要約 (コミットメッセージから生成)
     - **Commit Log**: `git log --oneline <デフォルトブランチ>..HEAD` の出力
     - **Testing**: 実行した検証コマンドとその結果 (なければ「手動確認」と記載)

### 5. PR マージ

`mcp_github_merge_pull_request` で squash マージを実行する。

- マージ方法: `squash` (全コミットを 1 つに集約)
- マージ失敗時はコンフリクトや CI 失敗をユーザに報告する
- マージ成功後、PR の `mergeCommit` SHA またはデフォルトブランチの最新 SHA を取得し、ステップ 6 の照合に使う

### 6. ローカル同期

```bash
git fetch --prune origin
git switch <デフォルトブランチ>
git pull --ff-only origin <デフォルトブランチ>
git status --short --branch
git log -1 --oneline
```

このステップは省略しない。`Already up to date.` の場合も、pull を実行した結果として扱い、最終報告に含める。

同期確認:

- `git status --short --branch` がデフォルトブランチ上で clean であることを確認する
- `git log -1 --oneline` の SHA が、PR の `mergeCommit` または `origin/<デフォルトブランチ>` の最新 SHA と一致することを確認する
- ローカルのデフォルトブランチに未コミット変更がある、または `pull --ff-only` が失敗した場合は、ブランチ削除を中断してユーザへ報告する

### 7. ブランチ削除

```bash
git branch -d <作業ブランチ名>
```

リモートブランチが残っている場合:

```bash
git push origin --delete <作業ブランチ名>
```

削除失敗時は残存ブランチ名をユーザに報告する。

## 実行結果の報告

全ステップ完了後、以下を簡潔に報告する:

- PR 番号と URL
- マージコミット SHA
- デフォルトブランチで実行した pull 結果と同期後の HEAD
- 削除したブランチ名 (ローカル・リモート)
