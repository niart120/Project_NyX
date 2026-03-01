import sys
from pathlib import Path

# macros/ ディレクトリをインポートパスに追加し、
# frlg_id_rng パッケージおよびマクロモジュールを参照可能にする
_macros_dir = str(Path(__file__).resolve().parent.parent.parent / "macros")
if _macros_dir not in sys.path:
    sys.path.insert(0, _macros_dir)
