from nekro_agent.api.plugin import NekroPlugin

plugin = NekroPlugin(
    name="OneBot 动画表情上下文",
    module_name="nekro_plugin_onebot_animated_emoji",
    description="识别 NapCat/OneBot 动画表情并提示 Agent 将其作为情绪表达低关注处理。",
    version="0.1.1",
    author="Healock",
    url="https://github.com/Healock/nekro_plugin_onebot_animated_emoji",
    support_adapter=["onebot_v11"],
    allow_sleep=False,
)

from . import lifecycle, matcher  # noqa: E402,F401

# Submodules can remain cached across Nekro plugin reloads.
matcher.bind_plugin(plugin)
lifecycle.bind_plugin(plugin)

__all__ = ["plugin"]
