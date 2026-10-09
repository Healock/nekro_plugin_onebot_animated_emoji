from __future__ import annotations

import time

from nonebot import on_message
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher

from nekro_agent.api.schemas import AgentCtx
from nekro_agent.schemas.chat_message import ChatMessage

from . import plugin
from .event_cache import animation_file_names
from .event_registry import (
    AnimationEventCache,
    AnimationHintCache,
    CapturedAnimationEvent,
    animation_image_count,
    onebot_chat_key,
)

animation_event_cache = AnimationEventCache()
animation_hint_cache = AnimationHintCache()
animation_event_matcher = on_message(priority=99998, block=False)


@animation_event_matcher.handle()
async def capture_animation_event(_: Matcher, event: MessageEvent) -> None:
    if not plugin.is_enabled:
        return
    image_count = animation_image_count(event.get_message())
    if image_count == 0:
        return

    chat_key = onebot_chat_key(
        message_type=event.message_type,
        user_id=event.user_id,
        group_id=getattr(event, "group_id", None),
    )
    if chat_key is None:
        return

    animation_event_cache.record(
        CapturedAnimationEvent(
            chat_key=chat_key,
            message_id=str(event.message_id),
            sender_id=str(event.sender.user_id),
            image_count=image_count,
            captured_at=time.monotonic(),
        ),
    )


@plugin.mount_on_user_message()
async def annotate_animated_emoji(_ctx: AgentCtx, message: ChatMessage) -> None:
    if message.adapter_key != "onebot_v11":
        return

    captured = animation_event_cache.consume(
        chat_key=message.chat_key,
        message_id=message.message_id,
        sender_id=message.sender_id,
    )
    if captured is None:
        return

    file_names = animation_file_names(message, captured.image_count)
    if file_names:
        animation_hint_cache.record(captured, file_names)
        plugin.logger.debug(
            f"已标注 OneBot 动画表情: chat={message.chat_key} "
            f"message_id={message.message_id} images={captured.image_count}",
        )


@plugin.mount_prompt_inject_method("动画表情上下文")
async def inject_animation_hint(_ctx: AgentCtx) -> str:
    return animation_hint_cache.prompt(_ctx.chat_key)


@plugin.mount_on_channel_reset()
async def reset_animation_hint(_ctx: AgentCtx) -> None:
    animation_hint_cache.clear(_ctx.chat_key)
