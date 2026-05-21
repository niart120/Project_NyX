"""GUI 表示用の macro catalog model。"""

from nyxpy.framework.core.macro.registry import MacroDefinition, MacroRegistry


class MacroCatalog:
    """GUI 表示用に macro definition を registry から読み込む catalog。"""

    def __init__(self, registry: MacroRegistry) -> None:
        """Macro registry を保持し、初回 reload で表示用 index を構築します。"""
        self.registry = registry
        self.definitions_by_id: dict[str, MacroDefinition] = {}
        self.reload_macros()

    def reload_macros(self) -> None:
        self.registry.reload()
        self.definitions_by_id = {
            definition.id: definition for definition in self.registry.list(include_failed=False)
        }

    def list(self) -> list[MacroDefinition]:
        return sorted(
            self.definitions_by_id.values(),
            key=lambda definition: (definition.display_name, definition.id),
        )

    def get(self, macro_id: str) -> MacroDefinition:
        return self.definitions_by_id[macro_id]
