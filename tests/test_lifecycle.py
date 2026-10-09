from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE = "animated_emoji_lifecycle_test"


class FakePlugin:
    def __init__(self, **metadata: object) -> None:
        self.is_enabled = True
        self.logger = Mock()
        self.metadata = metadata
        self.init_method = None
        self.cleanup_method = None
        self.on_user_message_method = None
        self.prompt_inject_method = None
        self.on_reset_method = None

    def _mount(self, attribute: str):
        def decorator(function):
            setattr(self, attribute, function)
            return function

        return decorator

    def mount_init_method(self):
        return self._mount("init_method")

    def mount_cleanup_method(self):
        return self._mount("cleanup_method")

    def mount_on_user_message(self):
        return self._mount("on_user_message_method")

    def mount_prompt_inject_method(self, name: str):
        return self._mount("prompt_inject_method")

    def mount_on_channel_reset(self):
        return self._mount("on_reset_method")


class ReloadLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.active: list[type] = []
        self.created: list[type] = []

        def on_message(*, priority: int, block: bool):
            self.assertEqual(priority, 99998)
            self.assertFalse(block)
            active = self.active

            class FakeMatcher:
                handler = None

                @classmethod
                def handle(cls):
                    def decorator(function):
                        cls.handler = function
                        return function

                    return decorator

                @classmethod
                def destroy(cls):
                    active.remove(cls)

            self.active.append(FakeMatcher)
            self.created.append(FakeMatcher)
            return FakeMatcher

        modules = {name: ModuleType(name) for name in (
            "nonebot", "nonebot.adapters", "nonebot.adapters.onebot",
            "nonebot.adapters.onebot.v11", "nonebot.matcher", "nekro_agent",
            "nekro_agent.api", "nekro_agent.api.plugin", "nekro_agent.api.schemas",
            "nekro_agent.schemas", "nekro_agent.schemas.chat_message",
        )}
        modules["nonebot"].on_message = on_message
        modules["nonebot.matcher"].Matcher = type("Matcher", (), {})
        modules["nonebot.adapters.onebot.v11"].MessageEvent = type("MessageEvent", (), {})
        modules["nekro_agent.api.plugin"].NekroPlugin = FakePlugin
        modules["nekro_agent.api.schemas"].AgentCtx = type("AgentCtx", (), {})
        modules["nekro_agent.schemas.chat_message"].ChatMessage = type("ChatMessage", (), {})
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        spec = importlib.util.spec_from_file_location(
            PACKAGE, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)],
        )
        self.package = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = self.package
        spec.loader.exec_module(self.package)

    async def _capture_and_get_hint(self, plugin: FakePlugin) -> str:
        event = SimpleNamespace(
            message_type="private", user_id=942273839, sender=SimpleNamespace(user_id=942273839),
            message_id=234196408,
            get_message=lambda: [SimpleNamespace(type="image", data={"summary": "[动画表情]"})],
        )
        await self.active[0].handler(None, event)
        message = SimpleNamespace(
            adapter_key="onebot_v11", chat_key="onebot_v11-private_942273839",
            message_id="234196408", sender_id="942273839", content_text="original", is_tome=0,
            content_data=[SimpleNamespace(type="image", file_name="emoji.png")],
        )
        ctx = SimpleNamespace(chat_key=message.chat_key)
        await plugin.on_user_message_method(ctx, message)
        self.assertEqual(message.content_text, "original")
        self.assertEqual(message.is_tome, 0)
        self.assertEqual(len(message.content_data), 1)
        return await plugin.prompt_inject_method(ctx)

    async def test_import_has_no_matcher_and_init_is_idempotent(self) -> None:
        self.assertEqual(self.active, [])
        await self.package.plugin.init_method()
        await self.package.plugin.init_method()
        self.assertEqual(len(self.active), 1)
        self.assertEqual(len(self.created), 1)
        self.assertIn("emoji.png", await self._capture_and_get_hint(self.package.plugin))

    async def test_cached_package_cleanup_then_init_restores_capture(self) -> None:
        plugin = self.package.plugin
        await plugin.init_method()
        self.assertIn("emoji.png", await self._capture_and_get_hint(plugin))
        await plugin.cleanup_method()
        await plugin.cleanup_method()
        self.assertEqual(self.active, [])
        self.assertEqual(await plugin.prompt_inject_method(SimpleNamespace(chat_key="onebot_v11-private_942273839")), "")
        await plugin.init_method()
        self.assertEqual(len(self.active), 1)
        self.assertIn("emoji.png", await self._capture_and_get_hint(plugin))

    async def test_reimport_root_with_cached_submodules_rebinds_new_plugin(self) -> None:
        old_plugin = self.package.plugin
        await old_plugin.init_method()
        await old_plugin.cleanup_method()
        old_matcher_module = self.package.matcher
        spec = self.package.__spec__
        new_package = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = new_package
        spec.loader.exec_module(new_package)
        self.assertIs(new_package.matcher, old_matcher_module)
        self.assertIsNot(new_package.plugin, old_plugin)
        self.assertIs(new_package.matcher.plugin, new_package.plugin)
        await new_package.plugin.init_method()
        self.assertEqual(len(self.active), 1)
        old_plugin.is_enabled = False
        self.assertIn("emoji.png", await self._capture_and_get_hint(new_package.plugin))

    async def test_cleanup_after_external_removal_is_safe(self) -> None:
        await self.package.plugin.init_method()
        self.active[0].destroy()
        await self.package.plugin.cleanup_method()
        await self.package.plugin.init_method()
        self.assertEqual(len(self.active), 1)

    async def test_disabled_plugin_does_not_capture(self) -> None:
        await self.package.plugin.init_method()
        self.package.plugin.is_enabled = False
        self.assertEqual(await self._capture_and_get_hint(self.package.plugin), "")

    async def test_registration_failure_removes_partial_matcher(self) -> None:
        matcher = self.package.matcher
        with patch.object(matcher, "on_message") as factory:
            partial = Mock()
            partial.handle.side_effect = RuntimeError("handler registration failed")
            factory.return_value = partial
            with self.assertRaises(RuntimeError):
                await self.package.plugin.init_method()
            partial.destroy.assert_called_once_with()
        self.assertIsNone(matcher.animation_event_matcher)
        await self.package.plugin.init_method()
        self.assertEqual(len(self.active), 1)


if __name__ == "__main__":
    unittest.main()
