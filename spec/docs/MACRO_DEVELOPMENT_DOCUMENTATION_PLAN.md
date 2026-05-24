# マクロ開発者向け仕様提供 作業計画仕様書

> **文書種別**: 作業計画仕様。NyX のマクロ実装者へ公開 API、配置規約、テスト方法、AI agent へ渡す実装情報を提供するための方針と作業単位を定義する。
> **対象領域**: `README.md`, `docs\macro-development\`, `src\nyxpy\framework\`, `examples\`, `.github\skills\`, `spec\framework\rearchitecture\`, `spec\macro\`
> **目的**: Python 知識を持つ実装者と AI agent が、リポジトリを clone しない環境でもマクロを実装できる情報面を整える。
> **関連ドキュメント**: `README.md`, `spec/framework/rearchitecture/MACRO_MIGRATION_GUIDE.md`, `spec/framework/rearchitecture/RUNTIME_AND_IO_PORTS.md`, `spec/framework/rearchitecture/RESOURCE_FILE_IO.md`, `spec/framework/rearchitecture/CONFIGURATION_AND_RESOURCES.md`, `spec/macro/**/spec.md`

## 1. 概要

### 1.1 対象読者

一定の Python 知識を持ち、NyX の公開 API を使ってマクロを書く実装者を対象にする。読者は `class`、型ヒント、例外、pytest、TOML、PowerShell の基本を理解している前提でよい。

実装作業は人間が直接書く場合だけでなく、AI agent に依頼する場合を主対象に含める。人間向けには判断材料と確認手順を提供し、AI agent 向けには実装制約、入出力形式、禁止事項、参照すべき API を機械的に拾いやすい形で提供する。

### 1.2 背景

現状の README には最小マクロ例と主要コマンドがあるが、実装者が必要とする情報は `spec\framework\rearchitecture\` の内部設計仕様、`examples\macros`、個別マクロ仕様、テストに分散している。`spec\framework\rearchitecture\` は再設計時の判断材料としては有用だが、現行 API とのずれが出始めているため、マクロ開発者向けの正本にはしない。

この作業では、公開 API の仕様正本を `docs\macro-development\` と公開 API の docstring / 型ヒントへ移す。`spec\framework\rearchitecture\` は参照元・移行元として扱い、最新仕様の根拠にはしない。

正式公開後は、実装者がこのリポジトリを clone せず、別プロジェクトや専用 workspace で利用する可能性が高い。

```powershell
# マクロ実装プロジェクトから framework API を import する場合
uv add nyxfw

# CLI/GUI ツールとして使う場合
uv tool install nyxfw
```

`uv add` はマクロ実装側が `nyxpy.framework.*` を import するライブラリ依存として自然であり、`uv tool install` は `nyx-cli` / `nyx-gui` をツールとして使う導入に向く。PyPI 配布名は `nyxfw`、import 名は `nyxpy` とする。`nyxfw` は NyX Framework の短縮名であり、既存 PyPI の `nyxpy` との衝突を避けつつ導入コマンドを短く保つために採用する。

いずれの場合も、リポジトリ内の `spec\` や `examples\` に依存した案内だけでは不足する。パッケージとして取得した環境、エディタの補完、型検査、AI agent のコード読解のどこからでも、最低限の実装情報へ到達できる必要がある。

導入方式で最も違うのは、マクロを import する Python 環境である。

| 導入方式 | `nyx-cli` / `nyx-gui` の環境 | マクロから見える依存関係 | 向く用途 |
|----------|------------------------------|--------------------------|----------|
| `uv tool install nyxfw` | uv tool の隔離環境 | NyX と NyX の依存関係。マクロ固有の追加依存は別途 tool 環境へ入れる必要がある | 既存マクロを実行する利用者 |
| `uv add nyxfw` | マクロ実装プロジェクトの仮想環境 | そのプロジェクトの依存関係すべて | マクロを開発し、追加ライブラリやテストを同じ環境で扱う実装者 |

現行のマクロ探索は、workspace の `macros\` を一時的に import path へ追加して `MacroBase` 派生クラスを import する。そのため `uv tool install` でも、標準ライブラリと NyX 依存だけで書かれたマクロは動く。一方で、マクロが NyX には含まれない外部ライブラリを import する場合、tool の隔離環境にその依存が無いと import 失敗する。この点は利用者向け手順とマクロ実装者向け手順の両方で明記する。

## 2. 情報提供面の設計

### 2.1 提供面の分類

| 提供面 | 主な読者 | 役割 | 配布形態 |
|--------|----------|------|----------|
| `docs\macro-development\` | 人間、AI agent | 実装手順、公開 API の使い方、配置規約、テスト手順 | リポジトリ、将来のドキュメントサイト |
| `src\nyxpy\framework\...` の docstring | 人間、AI agent、エディタ | API の直近説明、引数、戻り値、例外、使用上の注意 | wheel / sdist に同梱 |
| 型ヒントと `py.typed` | エディタ、型検査、AI agent | 呼び出し可能な API と値の形を補完可能にする | wheel に同梱 |
| 最小テンプレート | 人間、AI agent | 新規マクロ作成時の正しい初期形 | パッケージ内データまたは CLI 生成 |
| サンプルマクロ | 人間、AI agent | 実装パターン、テスト、resources の読み方を示す | リポジトリ、将来は別配布も検討 |
| マクロ生成 skill | AI agent | 新規マクロ作成時の調査、雛形生成、テスト追加を手順化 | `.github\skills\` |
| AI agent 向け短縮仕様 | AI agent | 守るべき制約と参照 API を短く列挙 | skill、docs、GitHub Pages |

### 2.2 PyPI 配布後の到達性

PyPI 配布後に clone なしで使う実装者向けには、次の到達経路を用意する。

| 到達経路 | 期待する使い方 | 必要な整備 |
|----------|----------------|------------|
| エディタ補完 | `MacroBase` や `Command` の docstring を見る | 公開 API の docstring と型ヒントを整備する |
| `python -m pydoc` | インストール済みパッケージから API 説明を見る | module / class / method docstring を公開 API に書く |
| CLI | ツール導入後にテンプレートや docs の場所を表示する | `uv tool install nyxfw` で使える `nyx-cli` から scaffold / docs URL を出す |
| パッケージ内テンプレート | ライブラリ依存またはツール導入後に新規マクロ雛形を生成する | template ファイルを package data として同梱する |
| 公開 docs | 詳細手順やサンプルを見る | `docs\macro-development\` をサイト化できる構成にする |

この計画では、公開 API に関わる Markdown と docstring / 型ヒントを同じ作業単位で整備し、その後にテンプレート、CLI 導線、GitHub Pages 生成を実装対象へ落とす。

### 2.3 API 仕様の生成方針

API 仕様は Markdown へ手で再掲し続けない。公開 API の docstring と型ヒントを正本に近づけ、サイト生成時に API リファレンスへ取り込む。概念説明と作例は `docs\macro-development\`、関数・クラス・引数・例外の近接仕様は docstring / 型ヒントを正本にする。

| 候補 | 特徴 | NyX での判断 |
|------|------|--------------|
| Sphinx + autodoc | Python module を import して docstring から API docs を生成できる。napoleon で Google / NumPy style docstring も扱える | API リファレンスの精度は高いが、Markdown 中心の手順書とは分離しやすい |
| MkDocs + mkdocstrings | Markdown ベースの docs に Python API リファレンスを差し込める | `docs\` を Markdown で育てる方針と相性がよく、第一候補 |
| pydoc | インストール済み環境で docstring を直接読む標準手段 | 公開 docs の代替ではなく、clone なし利用時の最低限の到達経路として扱う |

Sphinx も MkDocs も docstring 対応はできる。NyX では、手順書を Markdown で整備し、API だけ docstring から挿入したいので、まずは MkDocs + mkdocstrings を候補にする。API リファレンスの厳密性や外部 API との相互参照が主課題になった場合は Sphinx へ寄せる。

公開ドキュメントは GitHub Pages に統一する。GitHub Wiki も git repository として扱えるため CI から生成済み Markdown を push する運用は可能だが、通常の pull request review、branch protection、docs build 検証、package data 同梱の流れから外れやすい。SSOT を保つには、ソースを本リポジトリの `docs\` と docstring に置き、GitHub Pages へ生成物を配信する方が単純である。

### 2.4 AI agent 向け情報形式

AI agent は長い設計書より、明確な制約、正しい import、最小例、テストコマンド、禁止事項を拾いやすい。新規マクロ作成は Markdown のチェックリストを人間に読ませるより、専用 skill と雛形生成で誘導する。

| 文書 | 目的 | 記述内容 |
|------|------|----------|
| `.github\skills\macro-development\SKILL.md` | agent に新規マクロ作成・更新の手順を実行させる | 調査順、配置、雛形、テスト、禁止事項、完了条件 |
| `docs\macro-development\agent-brief.md` | skill を使えない agent や人間へ渡す短縮仕様 | 依存方向、標準配置、import、settings、resources、テストコマンド、禁止事項 |
| `docs\macro-development\macro-template.md` | 新規マクロ作成時の雛形説明 | ディレクトリ構造、最小コード、settings、テストの形 |
| 公開 API docstring | エディタ内で参照する仕様 | メソッドの意味、単位、例外、戻り値、実行時制約 |

`agent-brief.md` は、内部設計の詳細ではなく実装者が守る契約だけを書く。AI agent へ投入しやすいように、短い見出し、箇条書き、コード例、明示的な禁止事項を優先する。独立した `checklist.md` は必須成果物にしない。チェックリスト相当の内容は skill の完了条件と `macro-template.md` の末尾へ集約する。

clone しないマクロ開発者には、このリポジトリの `.github\skills\macro-development\SKILL.md` を取得して各自の agent 環境へ導入する手順を案内する。skill はこのリポジトリで保守し、GitHub Pages 上の `agent-brief.md` から取得先へ誘導する。現時点では skill を package data として同梱しない。

### 2.5 AI 向けドキュメンテーションの周辺事情

現時点で、uv に AI 向けドキュメントを自動提供する専用機能は見当たらない。uv で使えるのは、tool の隔離環境、`uv add` による依存追加、`uv tool install --with` による追加依存注入など、実行環境の管理である。

Python packaging 側の標準としては、型情報配布のための `py.typed` がある。これは PEP 561 に基づく仕組みで、型検査器やエディタがインストール済み package の inline type hints を使えるようにする。AI agent にも補完・静的解析経由で効くため、公開 API は型ヒントと `py.typed` を整える。

AI agent 向けのコミュニティ慣習としては、次の候補がある。

| 形式 | 位置づけ | NyX での扱い |
|------|----------|--------------|
| `AGENTS.md` | coding agent 向けのリポジトリ内指示ファイル。build/test、規約、注意点を書く | repository 作業者向けに有効。マクロ利用者へ配る docs とは分ける |
| `llms.txt` | Web サイト上で LLM 向けに重要 Markdown へのリンクを示す提案 | docs をサイト化する場合の公開入口候補 |
| GitHub Copilot / CLI skills | 特定作業を agent に実行させる手順化 | NyX のマクロ生成では最も直接的。`macro-development` skill を候補にする |

### 2.6 公開 API の範囲と安定性

マクロ開発者向け docs が扱う公開 API は、マクロから直接 import または呼び出しされる面に限定する。内部 Runtime / Port / Adapter の構成は、公開 API を説明するために必要な最小限だけを扱う。

| 区分 | 公開対象 | 安定性 |
|------|----------|--------|
| Macro lifecycle | `MacroBase`, `initialize(cmd, args)`, `run(cmd)`, `finalize(cmd)` | マクロ実装者向け契約として維持する |
| Command API | `Command`, `DefaultCommand` の import path、`press`, `hold`, `release`, `wait`, `capture`, `load_img`, `save_img`, `notify`, `log`, `touch`, `disable_sleep` など | docs と docstring を同じ変更で更新する |
| constants | `Button`, `Hat`, `LStick`, `RStick`, `ThreeDSButton`, `TouchState` | 値の意味と利用例を公開する |
| exceptions | `MacroStopException` とマクロ実装者が扱う設定・画像処理例外 | 例外の捕捉方針を公開する |
| image processing | `ImageProcessor`, `OCRProcessor`, `find_template`, `contains_template`, `ImagePreprocessor` | NyX が提供する範囲だけを公開する |
| settings / resources | `settings_path`, `resource:` / `project:` source、`resources\<macro_id>`、run outputs | 配置規約として維持する |

公開 API の追加・変更では、該当 docstring、型ヒント、`docs\macro-development\` の対応ページ、サンプルまたはテストを同じ変更単位で更新する。破壊的変更を行う場合は、NyX がアルファ版である前提に従い、旧 API の互換 shim よりも公開 docs と実装の同期を優先する。

## 3. 目標構成

### 3.1 名称

`macro-authoring` は文書執筆寄りの語感があるため使わない。NyX では実装・テスト・設定・配布まで含むので、ディレクトリ名は `docs\macro-development\` とする。日本語では「マクロ開発者向け」と呼ぶ。

### 3.2 `docs\macro-development\`

| 文書 | 内容 | 主な移設元 |
|------|------|------------|
| `docs\macro-development\README.md` | マクロ開発者向け目次、最短作成手順、関連仕様へのリンク | `README.md` 4章 |
| `docs\macro-development\agent-brief.md` | AI agent へ渡す短縮仕様、制約、禁止事項、テストコマンド | 本計画で新規 |
| `docs\macro-development\macro-layout.md` | `macros\`, `resources\`, `examples\macros`, `examples\resources` の使い分け | `README.md`, `MACRO_MIGRATION_GUIDE.md` |
| `docs\macro-development\macro-lifecycle.md` | `MacroBase.initialize/run/finalize`、実行引数、終了処理 | `README.md`, `RUNTIME_AND_IO_PORTS.md` |
| `docs\macro-development\command-api.md` | `Command` の操作 API、待機、キャプチャ、画像入出力、通知、ログ | `README.md`, `RUNTIME_AND_IO_PORTS.md` |
| `docs\macro-development\settings-and-resources.md` | `settings_path = "resource:settings.toml"`、`resources\<macro_id>`、assets、run outputs | `README.md`, `MACRO_MIGRATION_GUIDE.md` |
| `docs\macro-development\manifest.md` | `macro.toml` が必要な条件、entrypoint、metadata | `MACRO_MIGRATION_GUIDE.md` |
| `docs\macro-development\testing.md` | 単体テスト、実機テスト、`@pytest.mark.realdevice`、公開例のテスト配置 | `pyproject.toml`, `tests\`, `examples\tests` |
| `docs\macro-development\image-processing.md` | `ImageProcessor`、OCR、テンプレートマッチング、前処理の使い方と所掌範囲 | `src\nyxpy\framework\core\imgproc\` |
| `docs\macro-development\nintendo-3ds.md` | 3DS 向け定数、touch、sleep control、座標系、補助関数の使い方 | `src\nyxpy\framework\core\constants\controller.py`, `Command` |
| `docs\macro-development\sample-macros.md` | `examples\macros` / `examples\resources` / `examples\tests` の読み方 | 既存 examples 配置 |

### 3.3 公開ドキュメントの扱い

公開ドキュメントは GitHub Pages に統一する。GitHub Wiki は使わない。API 仕様、マクロ配置規約、利用手順のソースは本リポジトリの `docs\` と docstring に置き、CI で生成・検証した成果物だけを GitHub Pages へ公開する。

FAQ、既知の実機構成、動画付き手順なども、まずは `docs\user-guide\` または `docs\macro-development\` に置く。コードと同期しない補足情報が増えた場合も、公開面は GitHub Pages の中で分ける。

### 3.4 パッケージ同梱候補

clone なし利用を考えると、Markdown をリポジトリに置くだけでは足りない。次のいずれかを package data として同梱する案を検討する。

| 候補 | 目的 | 判断 |
|------|------|------|
| `nyxpy\templates\macro\` | macro 個別生成サービスの雛形 | 優先度高 |
| `nyxpy\docs\macro-development\agent-brief.md` | agent に渡す短縮仕様をインストール済み環境から取得 | 現時点では採用しない。GitHub Pages と skill 導入案内を優先 |
| `examples\` 全体 | サンプルマクロをパッケージから参照 | wheel 肥大化と保守のため慎重に扱う |

package data を入れる場合は、`pyproject.toml` の hatchling 設定で同梱対象を明示する。どのファイルを wheel に含めるかは、配布サイズと更新頻度を見て決める。

## 4. 正本ルール

| 情報 | 正本 | 参照側の扱い |
|------|------|--------------|
| マクロ開発者向け公開契約 | `docs\macro-development\` | README には最小例だけを置く |
| `MacroBase` / `Command` の引数・戻り値・例外 | 対象 API の docstring と型ヒント | docs は使い方と例を説明する |
| Runtime / Resource I/O / settings の内部設計 | `spec\framework\rearchitecture\` | 移行元・参考資料として扱い、正本にはしない |
| 個別マクロ仕様 | `spec\macro\<macro_id>\spec.md` | サンプルや examples から必要に応じてリンクする |
| サンプル実装 | `examples\macros\`, `examples\resources\`, `examples\tests\` | 読み物として参照する。実装者の配置先にはしない |
| 履歴資料 | `spec\framework\archive\` | 現行仕様の根拠としては扱わない |

## 5. docstring 整備方針

docstring は進めるべきだが、Markdown docs の代替にはしない。役割は「インストール済み環境で、API のすぐ近くにある短い仕様」とする。

### 5.1 対象 API

優先して docstring を整備する対象は次の範囲に限定する。

| 対象 | 書く内容 |
|------|----------|
| `MacroBase` | lifecycle、各 method の呼び出し順、`args` の扱い、状態保持の注意 |
| `Command` | 各操作の単位、待機・キャンセル、画像入出力、通知、例外 |
| constants (`Button`, `Hat`, `LStick`, `RStick`) | 利用例、値の意味 |
| 3DS constants (`ThreeDSButton`, `TouchState`) | 3DS 固有ボタン、touch 入力、座標系、対応プロトコルの注意 |
| `MacroStopException` | 中断を表す例外としての扱い |
| `ImageProcessor` / `OCRProcessor` / template matcher | OCR、テンプレートマッチング、前処理、例外、初回ロードコスト |
| settings resolver の公開面 | `resource:` / `project:` などの settings path の意味 |

### 5.2 書かない内容

- GUI/CLI の使い方は docstring に書かない。
- 内部 Port / Adapter の設計理由は docstring に書かない。
- 長いチュートリアルは docs に置き、docstring にはリンクまたは短い例だけを書く。

### 5.3 形式

docstring は、要約、引数、戻り値、送出例外、短い例を持つ。型ヒントと重複する型名の羅列は避け、実装者が誤用しやすい制約を優先する。

```python
def wait(self, sec: float) -> None:
    """指定秒数だけ待機する。

    待機中も中断要求を確認する。長い処理では `time.sleep()` を直接呼ばず、
    このメソッドを使う。

    Raises:
        MacroStopException: 実行中断が要求された場合。
    """
```

## 6. 執筆ルール

- Python 知識を持つ読者を前提にし、基礎文法の説明はしない。
- 最小コード例、推奨配置、テスト例をセットで示す。
- `macros\` と `examples\macros` の使い分けを明記する。
- 実装者のマクロ本体は `macros\<macro_id>`、設定・画像資材は `resources\<macro_id>` に置く。`examples\` はサンプルの参照先であり、利用者に配置させる場所ではない。
- `resources\<macro_id>\settings.toml` と `settings_path = "resource:settings.toml"` を標準例にする。
- `macro.toml` や settings に保存する portable path は `/` を使う。
- PowerShell コマンド例を使う。
- AI agent 向け文書では、禁止事項を曖昧に書かない。
- 画像処理は NyX が提供する OCR / template matcher / 前処理を中心に扱う。OpenCV の一般的な解説は、NyX API と組み合わせる短い recipe に限定する。

## 7. 作業計画

### Phase 0: 現状棚卸し

Phase 0 では、以後の docs に影響する前提を確定する。特に PyPI 配布名と import 名は、利用手順、skill、テンプレート、API リファレンスの全例に影響するため、Phase 1 着手前のゲートにする。

**ステータス**: 完了（2026-05-19）

| 作業 | 成果物 |
|------|--------|
| PyPI 配布名と import 名を決める | 配布名 `nyxfw` / import 名 `nyxpy` |
| 公開 API の範囲を確定する | 公開 API 一覧 |
| README のマクロ開発節を移設対象として分解する | README 移設対応表 |
| `spec\framework\rearchitecture\` から実装者向け公開契約だけを抽出する | macro-development 文書一覧の確定 |
| `examples\macros` / `examples\resources` / `examples\tests` の現行構成を確認する | examples の読み方一覧 |
| `MacroBase` / `Command` / constants の docstring と型ヒントの現状を確認する | docstring 整備対象一覧 |
| 3DS 向け定数・補助 API・座標系を確認する | 3DS 補足資料の対象一覧 |
| OCR / template matcher / 前処理 API を確認する | 画像処理資料の対象一覧 |

`spec\framework\rearchitecture\` 由来の記述は、現行 `src\nyxpy\framework\` またはテストで確認してから採用する。新しい docs では rearchitecture 仕様を根拠として引用せず、確認済みのコード、テスト、docstring を根拠にする。

#### Phase 0 棚卸し結果

##### 配布名・import 名

現行コードでは、配布名は `pyproject.toml` の `project.name = "nyxfw"`、import 名は `src\nyxpy\` の `nyxpy` である。`nyxpy` は PyPI 上で既存プロジェクトが使用しているため配布名には使わない。`project-nyx` は未登録で旧設定との整合はあったが、公開パッケージ名としてはリポジトリ内向きに見えるため採用しない。`nyx-automation`、`nyx-switch`、`nyx-framework`、`nyx-fw`、`nyxframework` も未登録だったが、導入コマンドを短く保てる `nyxfw` を採用する。

##### 公開 API 一覧

マクロ開発者向け docs の対象にする公開面は、現行コードまたは import 契約テストで確認できる次の範囲とする。

| 区分 | 公開対象 | 確認元 |
|------|----------|--------|
| lifecycle | `MacroBase.description`, `tags`, `args_schema`, `initialize(cmd, args)`, `run(cmd)`, `finalize(cmd)` | `src\nyxpy\framework\core\macro\base.py`, `tests\unit\framework\macro\test_import_contract.py` |
| command | `Command`, `DefaultCommand`, `press`, `hold`, `release`, `wait`, `stop`, `log`, `capture`, `save_img`, `load_img`, `keyboard`, `type`, `notify`, `artifacts`, `touch`, `touch_down`, `touch_up`, `disable_sleep` | `src\nyxpy\framework\core\macro\command.py`, `tests\unit\framework\macro\test_import_contract.py` |
| constants | `Button`, `Hat`, `LStick`, `RStick`, `KeyType`, `KeyboardOp`, `KeyCode`, `SpecialKeyCode` | `src\nyxpy\framework\core\constants\__init__.py`, `tests\unit\framework\macro\test_import_contract.py` |
| 3DS | `ThreeDSButton`, `TouchState`, `ScreenSize`, `ScreenPoint`, `ScreenRect`, `TouchPoint`, `ScaleRounding`, `THREEDS_*`, 座標変換 helper | `src\nyxpy\framework\core\constants\controller.py`, `src\nyxpy\framework\core\constants\screen.py`, `tests\unit\framework\constants\test_3ds_screen.py` |
| macro discovery | `MacroRegistry`, `MacroSearchRoot`, convention discovery, `macro.toml` manifest, `MacroDefinition` の公開説明に必要な範囲 | `src\nyxpy\framework\core\macro\registry.py`, `src\nyxpy\framework\core\macro\entrypoint_loader.py`, `tests\unit\framework\macro\test_registry.py` |
| settings | `settings_path`, `resource:`, `project:`, manifest `settings` | `src\nyxpy\framework\core\macro\settings_resolver.py`, `tests\unit\framework\macro\test_registry.py` |
| resources / outputs | `cmd.load_img`, `cmd.save_img`, `cmd.artifacts`, `MacroResourceScope`, `LocalResourceStore`, `LocalRunArtifactStore`, `OverwritePolicy` | `src\nyxpy\framework\core\io\resources.py`, `tests\unit\framework\io\test_resource_file_io.py` |
| exceptions | `MacroStopException`, `MacroCancelled`, `ResourceError`, `ConfigurationError`, 画像処理例外 | `src\nyxpy\framework\core\macro\exceptions.py`, `src\nyxpy\framework\core\imgproc\exceptions.py` |
| image processing | `ImageProcessor`, `OCRProcessor`, `OCRResult`, `ImagePreprocessor`, `find_template`, `contains_template`, `MatchResult` | `src\nyxpy\framework\core\imgproc\__init__.py`, `src\nyxpy\framework\core\imgproc\*.py` |

内部 Runtime / Port / Adapter / GUI / CLI の詳細は、公開 API の動作説明に必要な範囲だけ扱う。マクロ開発者向け docs で内部構造を再定義しない。

##### README 移設対応表

`README.md` の「4. マクロ開発」は、Phase 1 で短い入口に縮約する。移設先は次の対応にする。

| README の現行内容 | 移設先 |
|-------------------|--------|
| `macros\` / `resources\` はローカル作業用、`examples\macros` / `examples\resources` はサンプル | `docs\macro-development\macro-layout.md` |
| 最小 `MacroBase` 派生クラス例 | `docs\macro-development\README.md`, `docs\macro-development\macro-template.md` |
| `macros\<macro_id>.py` / `macros\<macro_id>\macro.py` の自動検出 | `docs\macro-development\macro-layout.md`, `docs\macro-development\manifest.md` |
| `macro.toml` の `id`, `entrypoint`, `settings` 例 | `docs\macro-development\manifest.md` |
| `cmd.press`, `cmd.wait`, `cmd.capture`, `cmd.keyboard`, `cmd.notify`, `cmd.log` など | `docs\macro-development\command-api.md` |
| `Button`, `Hat`, `LStick`, `RStick` の例 | `docs\macro-development\command-api.md` |
| `settings = "resource:settings.toml"` と `resources\<macro_id>` | `docs\macro-development\settings-and-resources.md` |
| `cmd.load_img`, `cmd.save_img`, `cmd.artifacts.open_output()` | `docs\macro-development\settings-and-resources.md` |
| `static\<macro_name>` は標準探索しない | `docs\macro-development\settings-and-resources.md` |
| rearchitecture 仕様への直接リンク | README からは削除し、必要な公開契約だけ docs へ移す |

##### rearchitecture 仕様から抽出する公開契約

`spec\framework\rearchitecture\` は正本にしない。Phase 1 以降で参照してよいのは、現行コード・テストで確認済みの次の契約だけとする。

| 契約 | docs で扱う粒度 |
|------|-----------------|
| マクロ配置 | 実装者は `macros\<macro_id>` と `resources\<macro_id>` を使う。`examples\` はサンプル参照先であり配置先ではない。 |
| import 方向 | マクロは `nyxpy.framework.*` と共有部品だけへ依存し、他マクロへ直接依存しない。 |
| lifecycle | `initialize` は設定読み込み後の初期化、`run` は本処理、`finalize` は終了処理として説明する。 |
| command | コントローラー操作、待機、capture、画像入出力、通知、ログ、3DS touch / sleep control を公開 API として説明する。 |
| settings | `resource:settings.toml` を標準例にし、portable path は `/` を使う。 |
| resources | `cmd.load_img()` は `resources\<macro_id>\assets` を優先し、マクロ package 内 `assets` を代替探索先とする。 |
| outputs | `cmd.save_img()` と `cmd.artifacts.open_output()` は run ごとの `runs\<run_id>\outputs` へ保存する。 |
| manifest | 複数 entrypoint、単一ファイル manifest、metadata 明示が必要な場合だけ `macro.toml` を使う。 |
| testing | `pytest` は `tests`, `macros`, `examples\tests` を収集し、実機テストは `@pytest.mark.realdevice` で分離する。 |

##### examples の読み方一覧

`examples\macros` は公開サンプル、`examples\resources` は公開サンプル用設定・画像資材、`examples\tests` は公開サンプルのテストとして説明する。

| サンプル | 役割 | 資源 | テスト |
|----------|------|------|--------|
| `sample_turbo_a_macro.py` | 最小に近いボタン連打・capture 保存例 | なし | 個別テストなし |
| `test_ocr_init.py` | PaddleOCR 初期化確認用のデバッグ・テスト用マクロ | なし | 個別テストなし |
| `nsmb_sort_or_splode` | 3DS touch、テンプレートマッチング、設定読み込みの例 | `settings.toml`, `assets\templates\*.png` | unit / perf |
| `frlg_wild_rng` | FRLG 野生乱数、共有 restart / opening helper 利用例 | `settings.toml` | unit |
| `frlg_initial_seed` | 初期 Seed 特定、CSV 出力、OCR / 認識ロジック分離例 | `settings.toml` | unit |
| `frlg_id_rng` | TID 乱数、frame sweep、keyboard layout、soft reset helper 例 | `settings.toml` | unit |
| `frlg_gorgeous_resort` | FRLG おねだり、frame search、species data、OCR 認識例 | `settings.toml` | unit |
| `shared` | 公開サンプル間の共通部品 | なし | 各マクロ test から利用 |

`examples\macros\shared` は examples 内の共有部品として説明する。利用者のローカル `macros\` から直接 import する前提にはしない。

##### docstring / 型ヒント整備対象

現状は最低限の docstring はあるが、公開 docs の正本にするには不足がある。Phase 2 では Markdown docs と同じ変更単位で次を整備する。

| 対象 | 現状 | Phase 2 の対応 |
|------|------|----------------|
| `MacroBase` | lifecycle method の短い説明のみ。`args_schema`, `description`, `tags` の説明がない。 | 呼び出し順、`args`、状態保持、metadata、例外方針を追加する。 |
| `Command` | 主要 method に説明あり。`artifacts`, `touch`, `touch_down`, `touch_up`, `disable_sleep` は interface 側に説明がない。 | 単位、待機、中断、非対応 protocol の `NotImplementedError`、3DS API を明記する。 |
| `Command.capture` | docstring は HD 1280x720 と 3DS crop を説明するが、型ヒントは `MatLike` のみで no frame 時の `None` と合っていない。 | 戻り値と失敗時挙動を型ヒントまたは実装と同期する。 |
| constants | 値の意味は短い。3DS 座標 helper は docstring が少ない。 | ボタン種別、stick の単位、3DS 座標系と変換 helper の用途を追加する。 |
| `MacroSettingsResolver` | class / method docstring がない。 | `resource:` / `project:` / manifest 相対 path、portable path 制約、例外を説明する。 |
| resources | 抽象 class と concrete store の docstring が薄い。 | `resources\<macro_id>\assets`、package `assets` への代替探索、outputs、path guard を説明する。 |
| imgproc | 主要 class / function に説明あり。例外、初回 OCR load cost、`contains_template` の失敗時 `False` が不足。 | OCR / template / preprocess の責務と例外を追加する。 |
| `py.typed` | `src\nyxpy\py.typed` は未配置。 | Phase 3 で PEP 561 対応方針を決める。 |

##### 3DS 補足資料の対象

`docs\macro-development\nintendo-3ds.md` では、次を公開対象にする。

| 対象 | 内容 |
|------|------|
| 3DS 固有入力 | `ThreeDSButton.POWER`, `TouchState.down(x, y)`, `TouchState.up()`, `Command.touch*`, `Command.disable_sleep()` |
| 正規化座標 | `THREEDS_CAPTURE_SIZE = 400x480`, top / bottom / full screen の `ScreenRect` |
| HD capture 座標 | `THREEDS_HD_CAPTURE_SIZE = 1280x720`, content / top / bottom / pillarbox 領域 |
| touch 座標 | `THREEDS_TOUCH_SIZE = 320x240`, `validate_3ds_touch_point()` |
| 座標変換 | normalized / HD / cropped / preview / scaled source から touch への変換 helper |
| 例外方針 | 範囲外は `ValueError`、`try_*` helper は `None` を返す |

##### 画像処理資料の対象

`docs\macro-development\image-processing.md` では、NyX が提供する範囲だけを扱う。

| 対象 | 内容 |
|------|------|
| `ImageProcessor` | 画像を保持して template matching / OCR / 前処理込み処理を呼ぶ入口 |
| `find_template` / `contains_template` | `MatchResult`, confidence, `threshold`, `cv2.TM_*`, threshold 未達時の扱い |
| `OCRProcessor` | `get_instance(language)`, `recognize_text`, `get_best_text`, `extract_digits`, PaddleOCR 初期化コスト |
| `ImagePreprocessor` | contrast, denoise, sharpen, binarize, template / OCR 向け前処理 |
| 例外 | `InvalidImageError`, `ThresholdNotMetError`, `TemplateMatchingError`, `OCREngineNotFoundError`, `OCRProcessingError` |
| 非対象 | OpenCV / PaddleOCR の一般解説、モデル学習、NyX API を通らない画像処理手引き |

### Phase 1: agent に渡せる入口を作る

| 作業 | 成果物 |
|------|--------|
| `docs\macro-development\README.md` を作る | 実装者向け目次 |
| `docs\macro-development\agent-brief.md` を作る | AI agent 向け短縮仕様 |
| `.github\skills\macro-development\SKILL.md` を作る | AI agent によるマクロ生成・更新手順 |
| `docs\macro-development\macro-template.md` を作る | 雛形説明と完了前確認 |
| README のマクロ開発節を短くし、詳細文書へリンクする | README 改訂 |

### Phase 2: マクロ実装手順を分ける

| 作業 | 成果物 |
|------|--------|
| 配置規約を整理する | `macro-layout.md` |
| lifecycle と `MacroBase` docstring を同時に整理する | `macro-lifecycle.md`, `MacroBase` docstring |
| `Command` API と `Command` docstring を同時に整理する | `command-api.md`, `Command` docstring |
| settings / resources / outputs と resolver docstring を同時に整理する | `settings-and-resources.md`, settings resolver docstring |
| manifest とテスト手順を整理する | `manifest.md`, `testing.md` |
| 3DS 向け補足と constants / touch docstring を同時に整理する | `nintendo-3ds.md`, 3DS constants / touch docstring |
| OCR と画像処理 API の使い方と imgproc docstring を同時に整理する | `image-processing.md`, imgproc docstring |
| examples の読み方をまとめる | `sample-macros.md` |

### Phase 3: パッケージから到達できる情報を増やす

詳細仕様は `spec\docs\MACRO_DEVELOPMENT_PHASE3_SPEC.md` に分離する。
実装順は、PEP 561 対応、`ty` 型検査厳格化、API reference 生成、GitHub Pages 配信、scaffold template、`nyx-cli` 導線、利用者向け docs 更新、package-publish の順を推奨する。`package-publish` は最終公開準備として最後に回す。

| 作業 | 成果物 |
|------|--------|
| `py.typed` の有無と型ヒント公開方針を確認する | PEP 561 対応方針 |
| PyPI 公開に必要な package metadata / publish 手順を整備する | `nyxfw` 配布準備と publish 手順 |
| マクロ雛形を package data として持つか決める | workspace 初期化と macro 個別生成を分けた scaffold 方針 |
| `nyxpy` から docs URL / scaffold 生成へ到達する導線を検討する | `nyxpy ...` 主導線と `nyx-cli` / `nyx-gui` alias 方針 |
| MkDocs + mkdocstrings による API リファレンス生成を検証する | docs 生成方式の判断 |
| GitHub Pages へ生成 docs を配信できるか確認する | 公開面の判断 |

GitHub Pages の公開面はマクロ開発者向け docs と API reference だけに限定しない。通常利用者向け手順は `docs\user-guide\` に整備し、同じ MkDocs site から公開する。初期公開 URL は repository root、`/macro-development/`、`/api/framework/` を起点にし、`docs\user-guide\` 整備後に `/user-guide/` を nav に追加する。

### Phase 4: 重複削減と検証

| 作業 | 成果物 |
|------|--------|
| docs から内部仕様の再定義を削る | docs と spec の責務分離 |
| docstring と Markdown docs の矛盾を確認する | API 説明の整合 |
| 主要リンク、パス表記、PowerShell コマンド例を確認する | リンク・表記の修正差分 |

## 8. 受け入れ条件

- Python 知識を持つ実装者が、`docs\macro-development\README.md` から必要な文書へ移動できる。
- AI agent に `agent-brief.md` と対象マクロ仕様を渡せば、標準配置・公開 API・禁止事項を外しにくい。
- `MacroBase` / `Command` / constants の公開 API は、docstring と型ヒントから最低限の使い方が分かる。
- clone なし利用でも、エディタ補完、`pydoc`、CLI、公開 docs のいずれかから実装情報へ到達できる設計になっている。
- マクロ開発者向け docs は内部 Runtime 仕様を再定義せず、公開契約だけを説明している。
- `macros\` / `resources\` が実装者の配置先であり、`examples\macros` / `examples\resources` はサンプル参照先であることが明記されている。
- 3DS 向けマクロで使う定数、touch、座標系、補助 API へ到達できる。
- OCR と画像処理 API の所掌範囲が明記され、OpenCV の一般解説へ広げすぎていない。

## 9. 未決事項

| 論点 | 判断候補 | ドラフト上の仮置き |
|------|----------|--------------------|
| API リファレンス生成手段 | MkDocs + mkdocstrings / Sphinx + autodoc | Markdown 手順書と相性がよい MkDocs + mkdocstrings を第一候補 |
| agent brief を wheel に同梱するか | 同梱する / docs のみ | 同梱候補として検討 |
| scaffold の公開入口 | `nyxpy create` / `nyx-cli scaffold` / なし | `new` は多義的なため避け、`nyxpy create` を主導線にする |
| examples 全体を package data に含めるか | 含める / 含めない / 別配布 | wheel 肥大化を避けるため慎重に扱う |
| GitHub Pages の構成 | MkDocs の直接 publish / GitHub Actions 生成 / 手動生成 | GitHub Actions で生成し Pages へ公開 |
| `spec\framework\rearchitecture\` の扱い | 正本 / 参考資料 / archive 化 | 正本にはしない。macro-development docs 作成時の参考資料 |
