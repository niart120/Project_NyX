# 抽象レイヤーの自己検証

この文書は、swbt 対応で不要な抽象や中間レイヤーを増やしていないかを確認するための設計チェックである。

## 現行実装で既にある境界

Project_NyX には controller 出力の境界として `ControllerOutputPort` がある。GUI の仮想コントローラーは `VirtualControllerModel` が `ControllerOutputPort | None` を保持し、button / D-pad / stick 操作を `press()` / `release()` へ流す構造になっている。

runtime 側には `MacroRuntimeBuilder` があり、macro 実行用の controller factory と GUI lifetime 用の `manual_controller_factory` を受け取れる。GUI manual input 用 controller は `controller_output_for_manual_input()` で遅延生成される。

serial backend では `SerialControllerOutputPort` が `ControllerOutputPort` を実装し、`SerialProtocolInterface` と `SerialComm` に委譲している。

したがって、swbt backend はこの既存構造に差し込むだけでよい。

## 採用する境界

| 境界 | 採用理由 |
|---|---|
| `ControllerOutputPort` | 既に macro と GUI manual input の共通境界であるため |
| `SwbtControllerOutputPort` | `ControllerOutputPort` の swbt 実装として必要 |
| `SwbtControllerSession` | `swbt-python` の async controller、event loop、pair/reconnect、apply/neutral/close を同期 port から扱うために必要 |
| `SwbtControllerOutputPortFactory` | runtime builder が controller port を作る既存方式に合わせるために必要 |
| `NyxSwbtInputMapper` | NyX の `Button` / `Hat` / `Stick` / `IMUFrame` と swbt input model の変換を port から分離するために必要 |

`SwbtControllerSession` は上位 domain service ではなく backend resource adapter として扱う。serial backend における `SerialComm` と `SerialProtocolInterface` の役割を、swbt の async resource 向けにまとめたものと位置づける。

## 採用しない境界

| 採用しないもの | 理由 |
|---|---|
| `SwbtManualInputSession` | GUI manual input は既存の `VirtualControllerModel -> ControllerOutputPort` で足りる |
| `SwbtManualInputModel` | GUI model を backend-aware にすると既存抽象を壊す |
| `SwbtVirtualControllerAdapter` | `ControllerOutputPort` がすでに adapter 役を担っている |
| `ControllerBackendRouter` | runtime builder の factory 選択で十分 |
| `SwbtGamepadService` と `SwbtControllerSession` の併存 | service / session の二重化になるため、`SwbtControllerSession` に統一する |
| GUI/CLI clipboard bridge | GUI と CLI の運用導線を結合し、今回の目的に不要 |
| IMU gesture / pose / raw editor | GUI manual input の scope を超える |
| diagnostics editor | developer option で十分 |
| controller color editor | 接続・入力反映の目的に不要 |

## 入力反映経路の検証

### macro 実行

```text
Command.press / hold / release / imu
  -> ExecutionContext.controller
  -> ControllerOutputPort
  -> SwbtControllerOutputPort
  -> SwbtControllerSession
  -> swbt-python
```

`Command` から swbt 固有 class は見えない。

### GUI manual input

```text
VirtualControllerPane
  -> VirtualControllerModel
  -> ControllerOutputPort
  -> SwbtControllerOutputPort
  -> SwbtControllerSession
  -> swbt-python
```

GUI model から swbt 固有 class は見えない。

### adapter refresh / pair / reconnect

```text
GUI / CLI operation
  -> app service / command handler
  -> SwbtControllerOutputPortFactory or hardware.swbt discovery/session lifecycle
```

これは入力反映経路とは別である。button を押すたびに lifecycle layer を経由しない。

## 最小実装チェックリスト

```text
[ ] `manual.py` を追加していない
[ ] `SwbtManualInputSession` を追加していない
[ ] GUI model に swbt import がない
[ ] GUI model に backend 分岐がない
[ ] runtime builder が `ControllerOutputPort` factory を受け取る構造を維持している
[ ] macro 実行と GUI manual input の両方が `ControllerOutputPort` で合流している
[ ] pair/reconnect は lifecycle 操作であり、input command path に混ぜていない
[ ] `SwbtGamepadService` と `SwbtControllerSession` を二重に作っていない
[ ] swbt の async loop は GUI thread に漏れていない
[ ] IMU は command / port surface にだけ追加し、GUI manual input UI へ出していない
```

## 判断

`SwbtManualInputSession` は採用しない。現行 GUI が `ControllerOutputPort` を受け取る設計になっているため、manual input 専用 session を作ると、同じ責務を `VirtualControllerModel` と二重に持つことになる。

修正後の設計では、追加する中心部品は `SwbtControllerOutputPort`、`SwbtControllerSession`、`SwbtControllerOutputPortFactory`、`NyxSwbtInputMapper` に絞る。これは backend を差し替えるために必要な最小限の層であり、GUI 上位層へ新しい manual input abstraction は追加しない。
