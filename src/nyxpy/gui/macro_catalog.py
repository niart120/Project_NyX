from nyxpy.framework.core.macro.registry import MacroRegistry


class MacroCatalog:
    def __init__(self, registry: MacroRegistry) -> None:
        self.registry = registry
        self.macros = {}
        self.reload_macros()

    def reload_macros(self) -> None:
        self.registry.reload()
        self.macros = {
            definition.class_name: definition
            for definition in self.registry.list(include_failed=False)
        }
