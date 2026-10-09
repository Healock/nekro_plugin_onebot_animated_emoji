from __future__ import annotations

from nekro_agent.api.plugin import NekroPlugin

from . import matcher


async def initialize() -> None:
    matcher.register_matcher()


async def cleanup() -> None:
    matcher.unregister_matcher()
    matcher.animation_event_cache.clear()
    matcher.animation_hint_cache.clear()


def bind_plugin(instance: NekroPlugin) -> None:
    instance.mount_init_method()(initialize)
    instance.mount_cleanup_method()(cleanup)
