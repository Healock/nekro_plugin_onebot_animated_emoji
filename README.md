# NekroAgent OneBot 动画表情上下文

识别 NapCat/OneBot V11 原始事件中的动画表情标记，并在消息上下文中说明其通常是情绪或语气表达，避免 Agent 默认逐张解读和点评画面。

## 安装

将整个 `nekro_plugin_onebot_animated_emoji` 目录放入 NekroAgent 数据目录的插件工作区：

```text
DATA_DIR/plugins/workdir/nekro_plugin_onebot_animated_emoji/
```

插件仅支持 OneBot V11，不需要额外依赖或配置。

## 行为

- 只识别原始图片段 `summary` 精确等于 `[动画表情]` 的消息。
- 为避免误标，消息里只要混有普通图片，就不添加动画表情标注。
- 通过消息 ID、发送者和频道关联原始事件与 Nekro 消息；缓存最多保留 4096 条，120 秒后过期。
- 使用插件提示词接口提供带消息 ID、发送者和图片文件名的标签，不修改用户消息、历史内容、触发标记或纯媒体判断。
- 标签仅在内存保留一小时，最多 4096 条；每次提示只列当前频道最近 4 条。频道 reset、插件卸载和进程重启会清空标签，不补标旧历史。
- 提示 Agent 将动画表情优先理解为情绪/语气线索；用户明确询问画面内容时仍可回应。
- 其他适配器、普通图片、群聊和私聊的原有消息处理均不变。

本插件不改动 NekroAgent 核心。静态测试不能替代真实 NekroAgent、OneBot 和多模态模型环境验证。

## 生命周期与热重载

`0.1.1` 修复热重载后显示加载成功但原始事件监听已失效的问题。matcher 在插件初始化时注册，清理时销毁并清空缓存；再次初始化会重新注册，不依赖 Python 子模块重新导入。重复初始化不会重复注册，重复清理可以安全执行。

热重载会清空已有表情标签，不补标此前收到的图片；重载后新收到的表情包重新识别。不修改 NekroAgent 核心、用户消息或 Agent 触发规则。

## 开发验证

```powershell
python -B -m unittest discover -s tests -v
poe lint
git diff --check
```

生命周期回归测试使用轻量替身模拟 NoneBot 注册表及 Nekro 模块缓存，未做真实 Nekro 运行验证。
