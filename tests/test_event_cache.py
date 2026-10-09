from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from event_registry import (  # noqa: E402
    ANIMATED_EMOJI_SUMMARY,
    AnimationEventCache,
    AnimationHintCache,
    CapturedAnimationEvent,
    animation_image_count,
    onebot_chat_key,
)
from event_cache import animation_file_names  # noqa: E402
from types import SimpleNamespace


@dataclass
class RawSegment:
    type: str
    data: dict[str, object]


class AnimationRecognitionTests(unittest.TestCase):
    def test_exact_animation_summary_is_recognized(self) -> None:
        segments = [RawSegment("text", {"text": "hi"}), RawSegment("image", {"summary": ANIMATED_EMOJI_SUMMARY})]
        self.assertEqual(animation_image_count(segments), 1)

    def test_ordinary_or_mixed_images_are_not_recognized(self) -> None:
        ordinary = [RawSegment("image", {"summary": "[图片]"})]
        mixed = [
            RawSegment("image", {"summary": ANIMATED_EMOJI_SUMMARY}),
            RawSegment("image", {"summary": "[图片]"}),
        ]
        self.assertEqual(animation_image_count(ordinary), 0)
        self.assertEqual(animation_image_count(mixed), 0)

    def test_private_and_group_channel_keys(self) -> None:
        self.assertEqual(onebot_chat_key("private", 123), "onebot_v11-private_123")
        self.assertEqual(onebot_chat_key("group", 123, 456), "onebot_v11-group_456")
        self.assertIsNone(onebot_chat_key("unknown", 123))


class AnimationEventCacheTests(unittest.TestCase):
    def test_cache_consumes_only_matching_sender_and_message(self) -> None:
        cache = AnimationEventCache()
        event = CapturedAnimationEvent("chat", "message", "sender", 1, 10.0)
        cache.record(event)

        self.assertIsNone(cache.consume("chat", "message", "other", now=11.0))
        self.assertEqual(cache.consume("chat", "message", "sender", now=11.0), event)
        self.assertIsNone(cache.consume("chat", "message", "sender", now=11.0))

    def test_expired_event_is_not_consumed(self) -> None:
        cache = AnimationEventCache(ttl_seconds=5)
        cache.record(CapturedAnimationEvent("chat", "message", "sender", 1, 10.0))
        self.assertIsNone(cache.consume("chat", "message", "sender", now=16.0))

    def test_capacity_evicts_oldest_event(self) -> None:
        cache = AnimationEventCache(max_events=1)
        cache.record(CapturedAnimationEvent("chat", "first", "sender", 1, 10.0))
        cache.record(CapturedAnimationEvent("chat", "second", "sender", 1, 11.0))
        self.assertIsNone(cache.consume("chat", "first", "sender", now=11.0))
        self.assertIsNotNone(cache.consume("chat", "second", "sender", now=11.0))

    def test_annotation_preserves_image_and_original_text(self) -> None:
        image = SimpleNamespace(type="image", text="original image", file_name="emoji.png")
        message = SimpleNamespace(content_data=[image], content_text="original", is_tome=0)
        self.assertEqual(animation_file_names(message, 1), ("emoji.png",))
        self.assertEqual(message.content_data, [image])
        self.assertEqual(message.content_text, "original")
        self.assertEqual(message.is_tome, 0)

    def test_annotation_requires_exact_image_count(self) -> None:
        image = SimpleNamespace(type="image", file_name="emoji.png")
        message = SimpleNamespace(content_data=[image])
        self.assertEqual(animation_file_names(message, 2), ())

    def test_hint_cache_channel_isolation_expiration_and_reset(self) -> None:
        cache = AnimationHintCache(ttl_seconds=5)
        event = CapturedAnimationEvent("chat", "message", "sender", 1, 10)
        cache.record(event, ("emoji.png",), now=10)
        self.assertIn("emoji.png", cache.prompt("chat", now=11))
        self.assertEqual(cache.prompt("other", now=11), "")
        self.assertEqual(cache.prompt("chat", now=16), "")
        cache.record(event, ("emoji.png",), now=20)
        cache.clear("chat")
        self.assertEqual(cache.prompt("chat", now=21), "")

    def test_hint_cache_capacity_and_prompt_limit(self) -> None:
        cache = AnimationHintCache(max_records=5)
        for index in range(8):
            event = CapturedAnimationEvent("chat", str(index), "sender", 1, 10)
            cache.record(event, (f"image-{index}.png",), now=10)
        prompt = cache.prompt("chat", now=11)
        self.assertNotIn("image-3.png", prompt)
        self.assertIn("image-4.png", prompt)
        self.assertIn("image-7.png", prompt)


if __name__ == "__main__":
    unittest.main()
