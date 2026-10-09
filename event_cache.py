from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nekro_agent.schemas.chat_message import ChatMessage


def animation_file_names(message: ChatMessage, image_count: int) -> tuple[str, ...]:
    images = [segment for segment in message.content_data if segment.type == "image"]
    if image_count <= 0 or len(images) != image_count:
        return ()
    # Only generated image names are used, never raw summary text or remote URLs.
    names = tuple(str(getattr(segment, "file_name", "")) for segment in images)
    return names if all(names) else ()
