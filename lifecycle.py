from __future__ import annotations

from . import plugin
from .matcher import animation_event_cache, animation_event_matcher, animation_hint_cache
from .matcher_cleanup import destroy_matcher


@plugin.mount_cleanup_method()
async def cleanup() -> None:
    animation_event_cache.clear()
    animation_hint_cache.clear()
    destroy_matcher(animation_event_matcher)
