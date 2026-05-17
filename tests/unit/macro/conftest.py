import sys
from pathlib import Path

# examples/macro をパッケージ import できるよう examples/ を追加する
_examples_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "examples")
if _examples_dir not in sys.path:
    sys.path.insert(0, _examples_dir)
