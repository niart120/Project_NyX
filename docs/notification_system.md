# 通知システム設計詳細

このドキュメントでは、Project NyX における外部通知システムの設計と実装について説明します。

**実装状況: ✅ 通知システムは実装済み (`src/nyxpy/framework/core/api/`)**

---

## 1. 概要

通知システムは、マクロの実行完了や重要なイベントを外部のプラットフォームに自動送信する機能です。

### 主な特徴
- マクロ実行完了時の自動通知
- スクリーンショット付き通知
- 複数プラットフォームへの同時送信
- 拡張可能なアーキテクチャ

---

## 2. サポート対象プラットフォーム

### 2.1 Discord ✅ **実装済み**
- **方式**: Webhook を使用
- **送信内容**: テキストメッセージ + 画像添付
- **設定項目**:
  - `discord.webhook_url`: Discord Webhook URL
  - `discord.enabled`: 通知の有効/無効

### 2.2 Bluesky ✅ **実装済み**  
- **方式**: AT Protocol を使用
- **送信内容**: テキスト投稿 + 画像添付
- **設定項目**:
  - `bluesky.handle`: ユーザーハンドル
  - `bluesky.password`: アプリパスワード
  - `bluesky.enabled`: 通知の有効/無効

---

## 3. アーキテクチャ

### 3.1 コンポーネント構成

```
NotificationHandler
├── NotificationInterface (抽象クラス)
├── DiscordNotification (実装クラス)
└── BlueskyNotification (実装クラス)
```

### 3.2 責務分離

- **NotificationInterface**: 通知の抽象インターフェース
- **NotificationHandler**: 複数通知サービスの統合管理
- **各実装クラス**: プラットフォーム固有の通知ロジック

---

## 4. 設定方法

### 4.1 設定ファイルの場所
通知の認証情報は `.nyxpy/secrets.toml` に保存されます。

### 4.2 設定例

```toml
[discord]
enabled = true
webhook_url = "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"

[bluesky]
enabled = true
handle = "your-handle.bsky.social"
password = "your-app-password"
```

### 4.3 セキュリティ
- 認証情報は `secrets.toml` で分離管理
- Git に含まれないよう `.gitignore` に追加推奨
- パスワードはBlueskyアプリパスワードを使用

---

## 5. 使用方法

### 5.1 プログラムからの呼び出し

```python
from nyxpy.framework.core.api.notification_handler import create_notification_handler_from_settings
from nyxpy.framework.core.settings.secrets_settings import SecretsSettings

# 設定から通知ハンドラーを作成
secrets = SecretsSettings()
handler = create_notification_handler_from_settings(secrets)

# テキストのみ通知
handler.publish("マクロが完了しました")

# スクリーンショット付き通知
import cv2
image = cv2.imread("screenshot.png")
handler.publish("マクロが完了しました", image)
```

### 5.2 CLI での利用
CLI でマクロを実行する際、設定が有効であれば自動的に通知が送信されます。

---

## 6. 拡張方法

### 6.1 新しいプラットフォームの追加

1. `NotificationInterface` を継承したクラスを作成
2. `notify(text: str, img: Optional[cv2.typing.MatLike])` メソッドを実装
3. `create_notification_handler_from_settings` 関数に追加ロジックを実装

### 6.2 実装例

```python
from .notification_interface import NotificationInterface
import cv2
from typing import Optional

class NewPlatformNotification(NotificationInterface):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def notify(self, text: str, img: Optional[cv2.typing.MatLike] = None) -> None:
        # プラットフォーム固有の通知実装
        pass
```

---

## 7. トラブルシューティング

### 7.1 Discord 通知が送信されない
- Webhook URL が正しく設定されているか確認
- Discord サーバーの権限設定を確認
- ネットワーク接続を確認

### 7.2 Bluesky 通知が送信されない
- ハンドル名が正しく設定されているか確認 (例: user.bsky.social)
- アプリパスワードが正しく設定されているか確認
- AT Protocol サーバーへの接続を確認

### 7.3 通知機能を無効にしたい
各プラットフォームの `enabled` を `false` に設定するか、`secrets.toml` を削除してください。

---

## 8. 将来の拡張予定

- **Slack**: Webhook 経由での通知
- **LINE**: LINE Notify API の利用
- **Email**: SMTP 経由でのメール通知
- **Webhook**: カスタム Webhook エンドポイントへの送信

---

このシステムにより、マクロの実行状況を柔軟に外部へ通知できるようになり、ユーザーの利便性が大幅に向上します。