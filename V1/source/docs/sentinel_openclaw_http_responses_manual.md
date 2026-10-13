# Sentinel 通过 OpenClaw HTTP Responses 的改动清单与新机复现手册

本文档面向两类场景：

1. 你要知道为了让前端 Sentinel 能通过 OpenClaw HTTP Responses 工作，仓库里到底改了哪些文件。
2. 你要在一台全新的 Windows 机器上，把 `llm-security-intel` workspace 和 SAADS 一次性装起来，并让前端真正走 `GET /v1/models` + `POST /v1/responses`。

相关官方文档：

- [OpenResponses API](https://docs.openclaw.ai/zh-CN/gateway/openresponses-http-api)
- [OpenAI-compatible HTTP API](https://docs.openclaw.ai/gateway/openai-http-api)
- [Configuration Reference](https://docs.openclaw.ai/gateway/configuration-reference)
- [Onboarding (CLI)](https://docs.openclaw.ai/start/wizard)

## 1. 这套链路现在是怎么工作的

当前 Sentinel 面板不再走旧的 Gateway WebSocket/RPC 控制面，而是分成两步：

1. 后端先调用 `GET /v1/models` 检查 OpenClaw HTTP Responses 面是否就绪。
2. 就绪后，后端调用 `POST /v1/responses`，并通过 `x-openclaw-agent-id: llm-security-intel` 把请求路由到目标 agent。

前端本身不直接拿 Gateway token。浏览器只请求 SAADS 后端：

- `GET /api/sentinel/connection`
- `POST /api/sentinel/runs`
- `GET /api/sentinel/runs/{id}`
- `GET /api/sentinel/logs/stream`

也就是说，前端看到的是 SAADS 的接口，真正去访问 OpenClaw HTTP Responses 的只有 SAADS 后端。

当前后端为了稳定性，使用的是“非流式 `POST /v1/responses` 完成态 JSON”模式，而不是 SSE 增量流。这仍然属于官方 HTTP Responses 面，只是没有使用 `stream=true`。

## 2. 为了支持 HTTP Responses，具体改了哪些文件

### 2.1 后端

核心文件：`backend/api/routers/sentinel.py`

这一个文件承担了绝大部分 OpenClaw 集成工作。

#### A. 解析 OpenClaw 配置与运行环境

关键位置：

- `OpenClawSettings`
- `_load_openclaw_settings()`

新增和调整的能力：

- 从 `~/.openclaw/openclaw.json` 读取：
  - `agents.list[].workspace`
  - `gateway.port`
  - `gateway.bind`
  - `gateway.auth.token`
- 支持这些环境变量覆盖：
  - `OPENCLAW_CONFIG_PATH`
  - `OPENCLAW_AGENT_ID`
  - `SENTINEL_WORKSPACE_ROOT`
  - `OPENCLAW_GATEWAY_URL`
  - `OPENCLAW_GATEWAY_TOKEN`
- `gateway token` 的来源优先级改成：
  1. `OPENCLAW_GATEWAY_TOKEN`
  2. `openclaw.json -> gateway.auth.token`
- 明确取消了对 `OPENCLAW_HOOKS_TOKEN` 的运行时回退。

这一步的目的，是让后端能自动发现：

- 目标 agent 是否存在
- workspace 路径是否正确
- OpenClaw Gateway 的 HTTP 地址是什么
- 是否具备合法的 Gateway token

#### B. 新增 HTTP Responses 客户端

关键位置：

- `OpenClawResponsesClient`

新增能力：

- 用 `httpx.AsyncClient` 调 `GET /v1/models`
- 用 `httpx.AsyncClient` 调 `POST /v1/responses`
- Bearer 认证统一走 Gateway token
- 通过 `x-openclaw-agent-id` 路由到 `llm-security-intel`

这一步替代了旧的自定义 WS Gateway 控制逻辑，是这次重构的核心。

#### C. 连接诊断改成 HTTP readiness

关键位置：

- `_build_connection_snapshot()`

现在 `/api/sentinel/connection` 不再以 WS 是否能连上为准，而是改成下面这套判定：

- `GET /v1/models` 必须返回 JSON
- `gateway.models_ready == true`
- 模型列表里必须包含：
  - `openclaw`
  - `openclaw/default`
  - `openclaw/llm-security-intel`
- workspace 路径必须存在
- `llm-security-intel` agent 必须存在
- agent 里的 workspace 必须和 Sentinel 目标 workspace 匹配

同时返回给前端的新字段包括：

- `gateway.responses_url`
- `gateway.surface`
- `gateway.models_ready`

兼容保留：

- `gateway.http_url`
- `gateway.ws_url`
- `gateway.protocol`

但前端不再拿 WS readiness 决定能不能点 OpenClaw。

#### D. OpenClaw 运行逻辑改成 `/v1/responses`

关键位置：

- `_run_openclaw_collector()`

现在 `transport="openclaw"` 时，后端会：

1. 先检查 `_build_connection_snapshot()`
2. 如果 `preferred_transport != "openclaw"`，直接返回 503 或失败状态
3. 调 `OpenClawResponsesClient.complete_response(...)`
4. 请求头里带：
   - `Authorization: Bearer <gateway_token>`
   - `x-openclaw-agent-id: llm-security-intel`
5. 请求体里带：
   - `model: "openclaw"`
   - `input: <prompt>`

取消行为也变了：

- 不再调用旧的 WS `chat.abort`
- 现在是取消本地等待任务，把 SAADS run 标为 `cancelled`
- 属于 best-effort 停止

#### E. OpenClaw prompt 改成自然任务描述

关键位置：

- `_build_openclaw_message()`

旧逻辑会强制 OpenClaw 执行固定命令：

- 不允许先探索 workspace
- 固定让它跑 `daily_run.py`

现在改成自然中文任务，例如：

- `sentinel，为我收集最近7天与大模型攻击相关的情报`

同时明确允许：

- 使用 `skills`
- 使用原生搜索工具
- 使用 workspace 已有脚本
- 自主决定研究路径

只保留一条前端所需的约束：

- 最终回复第一行必须输出 `[STATUS] ...`

### 2.2 前端

#### A. 运行控制状态机

核心文件：`frontend/src/lib/hooks/useSentinelRunController.ts`

主要改动：

- `ConnectionSnapshot.gateway` 增加：
  - `responses_url`
  - `surface`
  - `models_ready`
- `openClawReady` 变成：

```ts
connection?.preferred_transport === "openclaw" &&
connection?.gateway.models_ready === true
```

- 前端首次加载时会自动请求 `/api/sentinel/connection`
- 如果后端判断 OpenClaw 没准备好，前端默认会切回 `subprocess`
- 启动 OpenClaw run 前，会先阻止不满足 readiness 的请求

#### B. 控制面板 UI

核心文件：`frontend/src/components/dashboard/SentinelControlPanel/index.tsx`

主要改动：

- 原来的 `OpenClaw Gateway` 选项改名为 `OpenClaw HTTP Responses`
- 面板显示：
  - `responses_url`
  - `Workspace` 是否存在
  - `Agent` 是否存在
  - `HTTP` 是否 reachable
  - `Responses API` 是否已启用
  - `HTTP Surface` 当前是 `responses` 还是 `subprocess-fallback`
- 当 `models_ready=false` 时：
  - `OpenClaw HTTP Responses` 单选按钮不可用
  - “发起采集”按钮也不可用
- `subprocess` 保留为兜底模式

### 2.3 测试

#### 后端测试

文件：`tests/test_sentinel_gateway.py`

覆盖内容：

- `OPENCLAW_HOOKS_TOKEN` 不再回退为 Gateway token
- `/v1/models` 返回 HTML 时连接状态必须是 `degraded`
- `responses_url` 和 `models_ready` 字段必须存在
- Responses 事件翻译后，`assistant_markdown` / `[STATUS]` 能进入运行历史
- OpenClaw prompt 现在是自然语言任务，不再包含固定 `exec` 命令
- 取消行为会取消挂起的 HTTP 请求

#### 前端测试

文件：`frontend/src/components/dashboard/SentinelControlPanel/SentinelControlPanel.test.tsx`

覆盖内容：

- `models_ready=false` 时 OpenClaw 选项必须禁用
- `subprocess` 仍然可切换

### 2.4 环境变量说明

文件：`.env.example`

新增或强化说明：

- `SENTINEL_WORKSPACE_ROOT`
- `OPENCLAW_GATEWAY_URL`
- `OPENCLAW_GATEWAY_TOKEN`
- `OPENCLAW_WAIT_TIMEOUT_MS`
- `OPENCLAW_WAIT_TIMEOUT_S`

并明确写明：

- 需要在 `~/.openclaw/openclaw.json` 中启用 `gateway.http.endpoints.responses.enabled=true`
- Sentinel 只认 `OPENCLAW_GATEWAY_TOKEN` 或 `gateway.auth.token`
- 不再回退 `OPENCLAW_HOOKS_TOKEN`

### 2.5 外部 workspace 修复

文件：`%USERPROFILE%\\.openclaw\\workspace-llm-security-intel\\src\\other\\daily_run.py`

改动：

- 把 workspace 根目录定位修成：

```python
WORKSPACE = Path(__file__).resolve().parents[2]
```

原因：

- `daily_run.py` 位于 `src/other/`
- 如果根路径算错，subprocess 兜底模式会找不到 `.venv`、`config`、`src`

## 3. 当前运行时配置要求

这部分不在仓库里，但必须满足。

### 3.1 OpenClaw agent 配置要求

文件：`%USERPROFILE%\\.openclaw\\openclaw.json`

必须有一个 `llm-security-intel` agent，至少满足：

- `id = "llm-security-intel"`
- `workspace = "%USERPROFILE%\\.openclaw\\workspace-llm-security-intel"`
- 工具允许列表包含：
  - `read`
  - `write`
  - `edit`
  - `apply_patch`
  - `exec`
  - `process`
  - `web_search`
  - `web_fetch`
  - `memory_search`
  - `memory_get`
  - `subagents`
  - `sessions_spawn`
  - `browser`
  - `canvas`
  - `cron`
  - `gateway`
  - `nodes`
  - `agents_list`

参考片段：

```json
{
  "id": "llm-security-intel",
  "name": "llm-security-intel",
  "workspace": "C:\\Users\\YourUser\\.openclaw\\workspace-llm-security-intel",
  "model": "zai/glm-5",
  "tools": {
    "alsoAllow": [
      "read",
      "write",
      "edit",
      "apply_patch",
      "exec",
      "process",
      "web_search",
      "web_fetch",
      "memory_search",
      "memory_get",
      "subagents",
      "sessions_spawn",
      "browser",
      "canvas",
      "cron",
      "gateway",
      "nodes",
      "agents_list"
    ],
    "deny": ["image"]
  }
}
```

### 3.2 Gateway HTTP Responses 配置要求

文件：`%USERPROFILE%\\.openclaw\\openclaw.json`

必须包含：

```json
{
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "your-gateway-token"
    },
    "http": {
      "endpoints": {
        "responses": {
          "enabled": true
        }
      }
    }
  }
}
```

说明：

- `gateway.http.endpoints.responses.enabled` 默认不是开着的
- 改完以后必须重启 Gateway
- `Authorization: Bearer <token>` 走的是 Gateway auth

### 3.3 hooks token 不能和 gateway token 复用

文件：`%USERPROFILE%\\.openclaw\\openclaw.json`

如果你启用 hooks：

- `hooks.token`
- `gateway.auth.token`

必须是两套不同值。

官方配置文档明确说明：

- `hooks.token must be distinct from gateway.auth.token`

Sentinel 侧也已经按这个原则实现：

- 不再回退 `OPENCLAW_HOOKS_TOKEN`
- 只使用 `OPENCLAW_GATEWAY_TOKEN` 或 `gateway.auth.token`

## 4. 新机上到底要复制什么

### 4.1 推荐复制两套内容

推荐复制：

1. 整个 SAADS 仓库
2. 整个 `workspace-llm-security-intel` 源码目录

推荐目录结构：

```text
C:\saads
C:\Users\YourUser\.openclaw\workspace-llm-security-intel
```

### 4.2 如果只想复制 workspace 的必要文件

至少复制这些：

- `src/`
- `skills/`
- `config/`
- `requirements.txt`
- `pyproject.toml`
- `.env.example`
- `README.md`
- `AGENTS.md`
- `TOOLS.md`

可选但推荐：

- `USER.md`
- `MEMORY.md`
- `SKILLS_GUIDE.md`
- `IDENTITY.md`
- `SOUL.md`

### 4.3 不建议直接复制的运行时产物

不要直接复制：

- `.venv/`
- `.openclaw/`
- `.clawhub/`
- `__pycache__/`
- `data/`
- `kb/`
- `memory/`
- `reports/`

说明：

- `.venv/` 建议新机重建
- `.openclaw/`、`.clawhub/` 带有运行态信息，不适合直接迁移
- `data/`、`kb/`、`memory/`、`reports/` 只有在你要保留旧历史结果时才复制
- 它们不是“前端能用 HTTP Responses”这条链路的必需条件

## 5. 新机必须修改的文件

新机落地时，通常要动 4 类文件。

### 5.1 `%USERPROFILE%\\.openclaw\\openclaw.json`

这是最关键的文件，必须做 3 件事：

1. 有 `llm-security-intel` agent
2. agent 的 `workspace` 指向正确目录
3. `gateway.http.endpoints.responses.enabled=true`

推荐做法：

- 先 `openclaw onboard`
- 让 OpenClaw 自己生成一版新的 `openclaw.json`
- 然后把上面的 agent 块和 gateway 块手动合进去

不建议整份照抄旧机的 `openclaw.json`，因为：

- token
- 默认模型
- 本地插件
- onboarding 生成的安全默认项

都可能和新机环境不同。

### 5.2 `%USERPROFILE%\\.openclaw\\workspace-llm-security-intel\\.env`

从 `.env.example` 复制生成 `.env`，至少填写：

```env
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_API_KEY=your-minimax-key
MINIMAX_MODEL=MiniMax-M2.7
MINIMAX_FAST_MODEL=MiniMax-M2.7-highspeed
MINIMAX_CHEAP_FAST_MODEL=MiniMax-M2.5-highspeed
NVD_API_KEY=your-nvd-key
GITHUB_TOKEN=your-github-pat
HF_TOKEN=your-hf-token
```

如果你不想用 MiniMax，需要同步检查并修改：

- `config/config.json`

因为当前 workspace 默认 provider/model 就是按这套写的。

### 5.3 `SUFE-SAADS-Qwen\\.env`

从仓库根目录 `.env.example` 复制为 `.env`，至少填写：

```env
SENTINEL_WORKSPACE_ROOT=C:\Users\YourUser\.openclaw\workspace-llm-security-intel
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_GATEWAY_TOKEN=your-gateway-token
OPENCLAW_WAIT_TIMEOUT_MS=3900000
```

说明：

- `OPENCLAW_GATEWAY_TOKEN` 理论上可以省略，只要 `openclaw.json` 里已经有 `gateway.auth.token`
- 但新机建议显式写上，排障时更直接

### 5.4 `SUFE-SAADS-Qwen\\frontend\\.env.local`

必须确保前端不是 mock 模式：

```env
NEXT_PUBLIC_USE_MOCK_API=false
```

如果不写这个，开发时有可能页面能打开，但根本没打到真实后端。

## 6. 新机一步步操作

下面按 Windows 原生路径写。

### 步骤 1：安装基础环境

安装：

- OpenClaw
- Python 3.12
- Node.js 20
- Git
- `uv`（推荐）

首次安装 OpenClaw 后运行：

```powershell
openclaw onboard
```

官方 onboarding 文档：

- [Onboarding (CLI)](https://docs.openclaw.ai/start/wizard)

### 步骤 2：获取 SAADS 仓库

推荐：

```powershell
git clone <your-repo-url> C:\saads
cd C:\saads
```

如果不是 `git clone`，也可以直接从旧机复制整个 `SUFE-SAADS-Qwen` 目录到 `C:\saads`。

### 步骤 3：获取 workspace 源码

在新机创建：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.openclaw\workspace-llm-security-intel"
```

然后把旧机 workspace 的源码复制到这里。

如果你是从移动硬盘迁移，可以参考：

```powershell
robocopy D:\transfer\workspace-llm-security-intel `
  "$env:USERPROFILE\.openclaw\workspace-llm-security-intel" `
  /E `
  /XD .venv .openclaw .clawhub __pycache__ data kb memory reports
```

### 步骤 4：重建 workspace 的虚拟环境

不要直接拷旧 `.venv`。

在 workspace 根目录执行：

```powershell
cd "$env:USERPROFILE\.openclaw\workspace-llm-security-intel"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 步骤 5：生成 workspace `.env`

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，补齐：

- `MINIMAX_*`
- `NVD_API_KEY`
- `GITHUB_TOKEN`
- `HF_TOKEN`

### 步骤 6：配置 OpenClaw agent 与 Gateway

运行一次：

```powershell
openclaw onboard
```

然后编辑：

```text
%USERPROFILE%\.openclaw\openclaw.json
```

必须确认：

- 有 `llm-security-intel` agent
- 该 agent 的 `workspace` 正确
- `gateway.auth.mode = token`
- `gateway.auth.token` 已设置
- `gateway.http.endpoints.responses.enabled = true`

### 步骤 7：配置 SAADS 后端 `.env`

在 `C:\saads` 下：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，补齐：

- `SENTINEL_WORKSPACE_ROOT`
- `OPENCLAW_GATEWAY_URL`
- `OPENCLAW_GATEWAY_TOKEN`
- 其他你项目本身需要的 API key / DB 配置

### 步骤 8：配置前端不是 mock 模式

在 `C:\saads\frontend` 下创建：

```text
.env.local
```

内容：

```env
NEXT_PUBLIC_USE_MOCK_API=false
```

### 步骤 9：安装并启动 SAADS 后端

```powershell
cd C:\saads
uv sync
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 步骤 10：安装并启动 SAADS 前端

```powershell
cd C:\saads\frontend
npm install
$env:NEXT_PUBLIC_USE_MOCK_API="false"
npm run dev
```

### 步骤 11：启动或重启 OpenClaw Gateway

如果你是前台手动运行：

```powershell
openclaw gateway
```

如果 onboarding 已经帮你装成后台服务，也至少要确保：

- 改完 `openclaw.json` 后已经重启过 Gateway

## 7. 如何验收

建议按下面顺序验收，不要一上来就只看前端。

### 7.1 先验收 `/v1/models`

```powershell
Invoke-RestMethod http://127.0.0.1:18789/v1/models `
  -Headers @{ Authorization = "Bearer your-gateway-token" }
```

正常结果：

- 返回 JSON
- `data[].id` 里至少包含：
  - `openclaw`
  - `openclaw/default`
  - `openclaw/llm-security-intel`

### 7.2 再验收 `/v1/responses`

```powershell
$body = @{
  model = "openclaw"
  input = "请只回复一行：OPENCLAW_HTTP_OK"
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:18789/v1/responses `
  -Method Post `
  -Headers @{
    Authorization = "Bearer your-gateway-token"
    "x-openclaw-agent-id" = "llm-security-intel"
  } `
  -ContentType "application/json" `
  -Body $body
```

### 7.3 再验收 SAADS 后端诊断接口

打开：

```text
http://127.0.0.1:8000/api/sentinel/connection
```

期望返回里至少看到：

- `status = "ready"`
- `preferred_transport = "openclaw"`
- `gateway.surface = "responses"`
- `gateway.models_ready = true`

### 7.4 最后验收前端

在 Sentinel 面板里，你应该看到：

- `OpenClaw HTTP Responses`
- `responses_url=http://127.0.0.1:18789/v1/responses`
- `Responses API=已启用`
- `HTTP Surface=responses`

并且：

- `OpenClaw HTTP Responses` 选项可点
- “发起采集”按钮可点
- 触发后 “OpenClaw 智能体回复” 面板能看到返回内容

## 8. 常见问题

### 8.1 `/v1/models` 返回 HTML

通常原因：

- `gateway.http.endpoints.responses.enabled` 没开
- 或者开了但 Gateway 没重启

### 8.2 `/v1/models` 返回 401

通常原因：

- `OPENCLAW_GATEWAY_TOKEN` 不对
- 或者 `openclaw.json -> gateway.auth.token` 不对

### 8.3 前端仍然自动回退到 `subprocess`

通常原因：

- `llm-security-intel` agent 不存在
- agent 的 `workspace` 和 Sentinel 目标 workspace 不一致
- `models_ready=false`
- `/v1/models` 模型列表缺少 `openclaw/llm-security-intel`

### 8.4 OpenClaw 能回，但不用搜索或 skills

检查：

- `openclaw.json` 里 `llm-security-intel.tools.alsoAllow` 是否包含：
  - `web_search`
  - `web_fetch`
  - `read`
  - `exec`

同时确认你当前发给 OpenClaw 的 prompt 是新的自然语言任务，而不是旧的强制 `exec` 版本。

## 9. 辅助自检脚本

仓库内提供一个辅助脚本：

- `scripts/openclaw_responses_smoke.py`

用途：

- 读取 `~/.openclaw/openclaw.json`
- 读取 Gateway token
- 调用 `/v1/models`
- 调用 `/v1/responses`
- 打印最终回复文本

示例：

```powershell
cd C:\saads
uv run python scripts/openclaw_responses_smoke.py `
  --agent-id llm-security-intel `
  --prompt "请只回复一行：OPENCLAW_HTTP_OK"
```

这个脚本只是自检工具，不是前端真实链路。前端真实链路仍以后端 `backend/api/routers/sentinel.py` 为准。

## 10. 最小复现清单

如果你只关心“新机上最少需要改什么”，最小集合如下：

1. 把 SAADS 仓库放到 `C:\saads`
2. 把 workspace 源码放到 `%USERPROFILE%\.openclaw\workspace-llm-security-intel`
3. 重建 workspace `.venv`
4. 填 `workspace/.env`
5. 在 `openclaw.json` 加上：
   - `llm-security-intel` agent
   - `gateway.auth.token`
   - `gateway.http.endpoints.responses.enabled=true`
6. 在 `C:\saads\.env` 填：
   - `SENTINEL_WORKSPACE_ROOT`
   - `OPENCLAW_GATEWAY_URL`
   - `OPENCLAW_GATEWAY_TOKEN`
7. 在 `C:\saads\frontend\.env.local` 填：
   - `NEXT_PUBLIC_USE_MOCK_API=false`
8. 启动 OpenClaw Gateway、SAADS 后端、SAADS 前端
9. 先测 `/v1/models`，再测 `/api/sentinel/connection`，最后再点前端
