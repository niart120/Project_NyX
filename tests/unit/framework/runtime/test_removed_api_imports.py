import ast
from pathlib import Path

SRC_ROOT = Path(__file__).parents[4] / "src" / "nyxpy"
REMOVED_IMPORTS = (
    "nyxpy.framework.core.logger.log_manager",
    "nyxpy.framework.core.singletons",
)
REMOVED_NAMES = {
    "CaptureManager",
    "LogManager",
    "NotificationHandlerPort",
    "SerialManager",
    "capture_manager",
    "create_legacy_runtime_builder",
    "load_macro_settings",
    "log_manager",
    "serial_manager",
}


def test_application_code_does_not_import_removed_apis() -> None:
    violations: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if (
                        alias.name in REMOVED_IMPORTS
                        or alias.name.rsplit(".", 1)[-1] in REMOVED_NAMES
                    ):
                        violations.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported_names = {alias.name for alias in node.names}
                if module in REMOVED_IMPORTS or imported_names & REMOVED_NAMES:
                    violations.append(f"{path}: from {module} import {sorted(imported_names)}")

    assert violations == []
