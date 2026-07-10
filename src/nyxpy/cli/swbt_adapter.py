"""CLI の swbt adapter 選択 helper。"""

from dataclasses import replace

from nyxpy.framework.core.hardware.swbt.config import SwbtControllerConfig
from nyxpy.framework.core.hardware.swbt.discovery import (
    SwbtAdapterDiscoveryService,
    resolve_adapter,
)


def canonicalize_swbt_adapter(
    config: SwbtControllerConfig,
    *,
    discovery_service: SwbtAdapterDiscoveryService | None = None,
) -> SwbtControllerConfig:
    """選択 adapter を discovery 結果の代表名へ正規化する。"""
    adapters = ()
    if config.adapter:
        service = discovery_service or SwbtAdapterDiscoveryService()
        adapters = service.list_adapters()
    selected = resolve_adapter(config.adapter, adapters)
    return replace(config, adapter=selected.name)
