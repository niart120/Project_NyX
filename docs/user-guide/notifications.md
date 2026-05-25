# 通知設定

NyX はマクロから `cmd.notify(...)` が呼ばれたときに外部サービスへ通知できます。秘密情報は workspace の `.nyxpy/secrets.toml` に保存します。

通知は任意です。通知を使わない場合は既定値のまま `enabled = false` にしておきます。

## GUI で設定する

GUI の `設定` から通知設定タブを開き、Discord または Bluesky を有効化します。入力欄は秘密情報を扱うため、画面共有やスクリーンショットに含めないでください。

## Discord

Discord の webhook URL を設定します。

```toml
[notification.discord]
enabled = true
webhook_url = "https://discord.com/api/webhooks/..."
```

`webhook_url` は Discord 側で発行した webhook URL を指定します。URL を知っている人は通知先へ投稿できるため、公開リポジトリ、Issue、ログに貼らないでください。

## Bluesky

Bluesky の identifier と password を設定します。

```toml
[notification.bluesky]
enabled = true
identifier = "example.bsky.social"
password = "app-password"
```

`password` には通常のログインパスワードではなく、Bluesky の app password を使います。

## 秘密情報の扱い

- `.nyxpy/secrets.toml` を Git に含めない。
- webhook URL、password、token を Issue やログへ貼らない。
- 通知が不要な場合は `enabled = false` のままにする。
- スクリーンショットを共有する場合は、通知設定画面や `secrets.toml` の内容が写っていないか確認する。

`.nyxpy/secrets.toml` は `nyxpy init` や初回起動時に既定値で作成されます。手動編集した後に TOML の構文エラーが出る場合は、引用符とテーブル名を確認してください。

## ログ設定

通知設定画面ではログ出力の設定も変更できます。

| 項目 | 内容 |
|------|------|
| ログファイルレベル | `logs/` と `runs/` に保存するログの詳細度 |
| コマンド詳細ログ | ボタン入力や待機などの細かい操作ログを出す |

通常は既定値のままで使います。問題調査で詳細ログが必要な場合だけ、ログレベルを下げるかコマンド詳細ログを有効にしてください。
