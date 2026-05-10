import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[3]
FRAMEWORK_ROOT = PROJECT_ROOT / "src" / "nyxpy" / "framework"
MACROS_ROOT = PROJECT_ROOT / "macros"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_framework_does_not_depend_on_upper_layers() -> None:
    violations: list[str] = []
    for path in FRAMEWORK_ROOT.rglob("*.py"):
        for module in _imported_modules(path):
            if module == "macros" or module.startswith(("macros.", "nyxpy.gui", "nyxpy.cli")):
                violations.append(f"{path}: {module}")

    assert violations == []


def test_macros_do_not_import_other_macro_packages() -> None:
    violations: list[str] = []
    macro_names = {
        path.name
        for path in MACROS_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name != "shared"
    }
    for macro_name in macro_names:
        for path in (MACROS_ROOT / macro_name).rglob("*.py"):
            for module in _imported_modules(path):
                if not module.startswith("macros."):
                    continue
                imported_macro = module.split(".", 2)[1]
                if imported_macro != "shared" and imported_macro != macro_name:
                    violations.append(f"{path}: {module}")

    assert violations == []
