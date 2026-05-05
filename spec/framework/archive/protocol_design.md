# 通信プロトコル抽象化設計詳細

このドキュメントでは、シリアル通信におけるプロトコル変換部分の設計について説明します。旧 `docs` から移設したアーカイブであり、現行コードでは `src/nyxpy/framework/core/hardware/protocol.py` と `protocol_factory.py` が正本です。

## 1. 目的と背景

- **目的:**  
  高レベル操作（例：press, release, keyboard）のパラメータを、シリアル通信で送信可能なバイナリデータに変換する。
  
- **背景:**  
  自動操作層（Command, DefaultCommand）は、具体的な通信プロトコルの詳細を意識することなく操作を記述できるようにするため、 プロトコル変換処理を独立させる必要があります。

## 2. 設計方針

- **抽象化:**  
  `SerialProtocolInterface` を定義し、プロトコル変換の共通インターフェースを提供します。  
- **具体的実装:**  
  `CH552SerialProtocol`、`PokeConSerialProtocol`、`ThreeDSSerialProtocol` を提供します。CH552 の詳細は [ch552_protocol_spec.md](./protocol/ch552_protocol_spec.md)、PokeCon の詳細は [pokecon_protocol_spec.md](./protocol/pokecon_protocol_spec.md)、3DS 対応の設計経緯は [Nintendo 3DS シリアル通信プロトコル対応 仕様書](../../agent/wip/local_1/NINTENDO_3DS_SERIAL_PROTOCOL.md) を参照してください。
- **プロトコル選択:**  
  `ProtocolFactory` がプロトコル名、別名、既定ボーレート、対応ボーレートを管理します。
- **責務分離:**  
  - **Command (DefaultCommand):**  
    ユーザー操作から発生するパラメータを、プロトコル変換のために `SerialProtocolInterface` の実装を呼び出す。  
  - **SerialManager:**  
    生成されたコマンドデータを、実際のシリアル通信で送信する。

## 3. 連携フロー

1. **操作発行:**  
   自動操作層（DefaultCommand）が、例えば `press()` を呼び出すと、  
   渡されたキー情報を元に、注入されたプロトコル実装（例：`CH552SerialProtocol`）で送信用データを生成します。

2. **送信:**  
   生成されたコマンドデータは `SerialCommInterface` の実装に渡され、アクティブなシリアルデバイスに送信されます。

## 4. 将来的な拡張

- **複数プロトコル対応:**  
  `SerialProtocolInterface` の実装を追加し、`ProtocolFactory` に登録することで他のデバイス向けのプロトコル実装へ切り替え可能です。  
- **手動入力との統合:**  
  将来的に手動入力層でも同様のプロトコル変換が必要な場合、共通のインターフェースを利用することで再利用性が高まります。

---

このドキュメントでは、プロトコル変換処理の抽象化と、現行実装で登録済みのプロトコル概要を説明しています。  
詳細な CH552SerialProtocol の仕様については、[ch552_protocol_spec.md](./protocol/ch552_protocol_spec.md) を参照してください。
