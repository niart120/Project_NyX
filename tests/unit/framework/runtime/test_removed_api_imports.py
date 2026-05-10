import ast
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).parents[4] / "src" / "nyxpy" / "framework" / "core"
SCANNED_PACKAGES = ("runtime", "io", "macro")
REMOVED_IMPORTS = (
    "nyxpy.framework.core.logger.log_manager",
    "nyxpy.framework.core.singletons",
)
REMOVED_NAMES = {"LogManager", "log_manager", "serial_manager", "capture_manager"}


def test_framework_runtime_path_does_not_import_removed_apis() -> None:
    violations: list[str] = []
    for package in SCANNED_PACKAGES:
        for path in (FRAMEWORK_ROOT / package).rglob("*.py"):
            if path.name == "executor.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in REMOVED_IMPORTS or alias.name.rsplit(".", 1)[-1] in REMOVED_NAMES:
                            violations.append(f"{path}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    imported_names = {alias.name for alias in node.names}
                    if module in REMOVED_IMPORTS or imported_names & REMOVED_NAMES:
                        violations.append(f"{path}: from {module} import {sorted(imported_names)}")

    assert violations == []
