# 通知設定

NyX はマクロから `cmd.notify(...)` が呼ばれたときに外部サービスへ通知できます。秘密情報は workspace の `.nyxpy\secrets.toml` に保存します。

## Discord

Discord の webhook URL を設定します。

```toml
[notification.discord]
enabled = true
webhook_url = "https://discord.com/api/webhooks/..."
```

## Bluesky

Bluesky の identifier と password を設定します。

```toml
[notification.bluesky]
enabled = true
identifier = "example.bsky.social"
password = "app-password"
```

## 秘密情報の扱い

- `.nyxpy\secrets.toml` を Git に含めない。
- webhook URL、password、token を Issue やログへ貼らない。
- 通知が不要な場合は `enabled = false` のままにする。

`.nyxpy\secrets.toml` は `nyxpy init` や初回起動時に既定値で作成されます。手動編集した後に TOML の構文エラーが出る場合は、引用符とテーブル名を確認してください。
