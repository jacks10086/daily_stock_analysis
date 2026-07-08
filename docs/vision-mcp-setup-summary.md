# Vision MCP 配置踩坑记录

## 背景

Claude Code 使用的 DeepSeek 等模型不具备多模态（看图）能力，需要借助 Vision MCP Server 转发图片到视觉 API 来识别图片。

选择方案：[vision_mcp](https://github.com/rongtianjie/vision_mcp) — 一个 Python MCP 服务器，通过 OpenAI 兼容 API 将图片转发给视觉模型。

## 配置信息

- **API**: `https://integrate.api.nvidia.com/v1`
- **模型**: `meta/llama-3.2-11b-vision-instruct`（踩坑：最初配的 `stepfun-ai/step-3.5-flash` 不是视觉模型，报了 400 错误）
- **Key**: NVIDIA API Key

---

## 踩坑过程

### 1. 安装 vision_mcp

```bash
gh repo clone rongtianjie/vision_mcp ~/vision_mcp
pip install -e ~/vision_mcp
```

验证安装：`vision-mcp --help` 应正常输出。

### 2. 配置 .env 文件

放在 `~/vision_mcp/.env`，内容：

```
VISION_API_BASE=https://integrate.api.nvidia.com/v1
VISION_API_KEY=nvapi-xxxx
VISION_MODEL=meta/llama-3.2-11b-vision-instruct
VISION_MAX_TOKENS=2000
```

> 注意：vision_mcp 启动时通过 `Path(__file__).parent.parent / ".env"` 加载此文件，因此必须放在项目根目录。

### 3. 注册 MCP 服务器

在 `C:\Users\WU\.claude\.mcp.json` 中添加：

```json
{
  "mcpServers": {
    "vision": {
      "command": "vision-mcp",
      "args": [],
      "env": {
        "VISION_API_BASE": "https://integrate.api.nvidia.com/v1",
        "VISION_API_KEY": "nvapi-xxxx",
        "VISION_MODEL": "meta/llama-3.2-11b-vision-instruct",
        "VISION_MAX_TOKENS": "2000"
      }
    }
  }
}
```

### 4. 模型选型踩坑

最初配置 `stepfun-ai/step-3.5-flash`，调用时报 400 错误。经排查 NVIDIA API 模型列表发现该模型不是视觉模型。

**NVIDIA API 支持的视觉模型：**
- `meta/llama-3.2-11b-vision-instruct`
- `meta/llama-3.2-90b-vision-instruct`
- `microsoft/phi-3-vision-128k-instruct`
- `microsoft/phi-4-multimodal-instruct`
- `nvidia/vila`

最终选用 `meta/llama-3.2-11b-vision-instruct`。

---

## cc-switch 托管踩坑

### 问题：cc-switch 没有自动发现 vision MCP

cc-switch 的"导入已有"功能**只扫描插件市场目录**（`~/.claude/plugins/marketplaces/`），不会读取 `~/.claude/.mcp.json`。

### 原因：Claude Code 配置体系

Claude Code 的 MCP 配置分散在多个文件中：

| 文件 | 用途 | 说明 |
|------|------|------|
| `~/.claude/.mcp.json` | MCP 服务器定义（新版） | 手动配置的手动管理的 MCP |
| `~/.claude.json` | Claude Code 全局设置 | 包含 mcpServers、启动统计等（55KB+） |
| `~/.claude/plugins/marketplaces/` | 插件市场安装的 MCP | 每个插件有自己的 `.mcp.json` |

cc-switch 从 `~/.claude.json` 的 `mcpServers` 读取和同步配置，不会扫描 `.mcp.json`。

### 错误尝试：直接操作 cc-switch 数据库

尝试直接用 `sqlite3` 插入 cc-switch 的 SQLite 数据库（`~/.cc-switch/cc-switch.db` 的 `mcp_servers` 表），但写入后 cc-switch 异常，只能删记录回滚。

### 正确方法

在 cc-switch 界面中点击右上角 **"+"** → 选择 **自定义** → 填入：

- 服务器 ID: `vision`
- 命令: `vision-mcp`
- 环境变量: 填入 VISION_API_BASE / VISION_API_KEY / VISION_MODEL

---

## 最终验证

```bash
claude mcp list
```

输出应为：
```
vision: vision-mcp - ✔ Connected
```

---

## 注意事项

1. **重启生效**：修改 `.mcp.json` 后需运行 `/mcp` 重连；修改 `.env` 后需重启 Claude Code
2. **模型选型**：确保选的模型支持多模态（vision）能力
3. **PATH 路径**：`vision-mcp` 命令需在 PATH 中（pip 安装后一般自动在 `venv/Scripts/` 下）
4. **会话工具刷新**：mid-session 切换模型可能导致 MCP 工具的注册中断，需要重启会话
