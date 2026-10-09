from __future__ import annotations

import json
import time
from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

ANIMATED_EMOJI_SUMMARY = "[动画表情]"
_EVENT_TTL_SECONDS = 120.0
_MAX_EVENTS = 4096


@dataclass(frozen=True)
class CapturedAnimationEvent:
    chat_key: str
    message_id: str
    sender_id: str
    image_count: int
    captured_at: float


class AnimationEventCache:
    def __init__(self, ttl_seconds: float = _EVENT_TTL_SECONDS, max_events: int = _MAX_EVENTS) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_events = max_events
        self._events: OrderedDict[tuple[str, str], CapturedAnimationEvent] = OrderedDict()

    def record(self, event: CapturedAnimationEvent) -> None:
        self._prune(event.captured_at)
        key = (event.chat_key, event.message_id)
        self._events[key] = event
        self._events.move_to_end(key)
        while len(self._events) > self._max_events:
            self._events.popitem(last=False)

    def consume(self, chat_key: str, message_id: str, sender_id: str, now: float | None = None) -> CapturedAnimationEvent | None:
        current_time = time.monotonic() if now is None else now
        self._prune(current_time)
        key = (chat_key, message_id)
        event = self._events.get(key)
        if event is None or event.sender_id != sender_id:
            return None
        return self._events.pop(key)

    def clear(self) -> None:
        self._events.clear()

    def _prune(self, now: float) -> None:
        expired_keys = [
            key
            for key, event in self._events.items()
            if now - event.captured_at > self._ttl_seconds
        ]
        for key in expired_keys:
            self._events.pop(key, None)


def animation_image_count(raw_segments: Iterable[Any]) -> int:
    """仅当消息中的每个图片段都具有精确动画表情标记时返回图片数量。"""
    image_count = 0
    for segment in raw_segments:
        if getattr(segment, "type", None) != "image":
            continue
        data = getattr(segment, "data", None)
        if not isinstance(data, Mapping) or data.get("summary") != ANIMATED_EMOJI_SUMMARY:
            return 0
        image_count += 1
    return image_count


def onebot_chat_key(message_type: str, user_id: int, group_id: int | None = None) -> str | None:
    if message_type in {"private", "friend"}:
        return f"onebot_v11-private_{user_id}"
    if message_type == "group" and group_id is not None:
        return f"onebot_v11-group_{group_id}"
    return None


class AnimationHintCache:
    """Bounded, channel-scoped metadata; never mutates a user message."""

    def __init__(self, ttl_seconds: float = 3600, max_records: int = 4096) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_records = max_records
        self._records: OrderedDict[tuple[str, str, str], tuple[float, tuple[str, ...]]] = OrderedDict()

    def record(self, event: CapturedAnimationEvent, file_names: tuple[str, ...], now: float | None = None) -> None:
        current_time = time.monotonic() if now is None else now
        self._prune(current_time)
        key = (event.chat_key, event.message_id, event.sender_id)
        self._records[key] = (current_time, file_names[:4])
        self._records.move_to_end(key)
        while len(self._records) > self._max_records:
            self._records.popitem(last=False)

    def prompt(self, chat_key: str, now: float | None = None) -> str:
        self._prune(time.monotonic() if now is None else now)
        refs = [
            {"message_id": key[1], "sender_id": key[2], "images": value[1]}
            for key, value in self._records.items()
            if key[0] == chat_key
        ][-4:]
        if not refs:
            return ""
        return (
            "以下文件名对应本频道历史中的 QQ 动画表情（平台标记，不是用户原话）：\n"
            + json.dumps(refs, ensure_ascii=False)
            + "\n仅对历史中匹配的图片适用：通常是情绪或语气表达，低关注；不要逐图点评，"
            "不要推断用户情绪或必须回应。明确询问图片内容时可正常分析，其他普通图片不受影响。"
        )

    def clear(self, chat_key: str | None = None) -> None:
        if chat_key is None:
            self._records.clear()
        else:
            for key in list(self._records):
                if key[0] == chat_key:
                    self._records.pop(key)

    def _prune(self, now: float) -> None:
        for key, (created_at, _) in list(self._records.items()):
            if now - created_at > self._ttl_seconds:
                self._records.pop(key)
