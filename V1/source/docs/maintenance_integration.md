# SUFE-SAADS 前后端联调文档

> 面向接手团队的前后端接口集成参考手册
> 最后更新：2026-03-19

---

## 1. 架构概览

```
┌────────────────────────────────────┐
│   浏览器                           │
│   Next.js 前端 (:3000)             │
│   ┌──────────────────────────────┐ │
│   │ Dashboard（Client Component）│ │
│   │  SWR hooks → fetchValidated()│ │
│   │  useSSELog → EventSource     │ │
│   └──────────────────────────────┘ │
└────────────┬───────────────────────┘
             │ HTTP / SSE
             ▼ /api/*（同源代理）
┌────────────────────────────────────┐
│   Nginx 反向代理                   │
│   / → :3000（Next.js）            │
│   /api/ → :8000（FastAPI）        │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│   FastAPI 后端 (:8000)             │
│   LangGraph 智能体引擎             │
│   PostgreSQL + Qdrant              │
└────────────────────────────────────┘
```

**关键设计原则：**
- 前端通过 `/api/*` 访问后端，在 Nginx 同源代理下**无 CORS 问题**
- 开发阶段（无 Nginx）前端 `:3000` → 后端 `:8000`，需后端配置 CORS
- 前端所有数据请求都经过 `lib/api/client.ts` 的 `fetchValidated()`，用 Zod 校验响应

---

## 2. 开发环境联调步骤

### 第 1 步：确认前端 Mock 模式关闭

```bash
# frontend/.env.local
NEXT_PUBLIC_USE_MOCK_API=false
```

### 第 2 步：启动后端

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 第 3 步：后端配置 CORS

开发阶段前端跑在 `:3000`，后端需允许跨域：

```python
# main.py（FastAPI 入口）
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

### 第 4 步：启动前端

```bash
cd frontend
NEXT_PUBLIC_USE_MOCK_API=false npm run dev
# → http://localhost:3000
```

### 第 5 步：验证联通性

访问 `http://localhost:3000/dashboard`，若 WP1-1 状态卡显示真实数据（而非 mock 的固定值），则联调成功。

---

## 3. 完整 API 契约

### 3.1 通用端点（4 个 WP 均需实现）

**路径规则：** 将 `{wp}` 替换为 `wp11` / `wp12` / `wp13` / `wp14`

---

#### `GET /api/{wp}/status`

WP 运行状态与关键指标。前端 5 秒轮询。

**响应格式（Zod schema: `WpStatusResponseSchema`）：**

```json
{
  "wp_id": "wp11",
  "status": "running",
  "uptime_seconds": 86400,
  "version": "0.4.1",
  "current_task": "semantic_dedup_and_merge",
  "metrics": [
    { "key": "attack_pool_size", "label": "攻击池规模", "value": 14230, "unit": "条", "delta_24h": 87 },
    { "key": "coverage_rate",    "label": "覆盖率",    "value": 0.847, "unit": "%", "delta_24h": 0.023 },
    { "key": "new_intel_24h",    "label": "24h新情报", "value": 87,   "unit": "条", "delta_24h": null }
  ]
}
```

**status 枚举：** `"running"` / `"idle"` / `"error"` / `"pending"` / `"stopped"`

**metrics.key 对应关系：**

| WP | metricsKeys |
|----|------------|
| WP1-1 | `attack_pool_size`, `coverage_rate`, `new_intel_24h` |
| WP1-2 | `script_count`, `owasp_coverage`, `scripts_24h` |
| WP1-3 | `sessions`, `datasets`, `vuln_confirmed` |
| WP1-4 | `models_trained`, `best_f1`, `iterations` |

---

#### `GET /api/{wp}/metrics?keys=k1,k2&window=48h`

历史指标时序。前端 30 秒轮询。

**响应格式（`WpMetricSeriesSchema[]`）：**

```json
[
  {
    "key": "attack_pool_size",
    "label": "攻击池规模",
    "unit": "条",
    "data": [
      { "ts": "2026-03-18T00:00:00Z", "value": 14100 },
      { "ts": "2026-03-18T01:00:00Z", "value": 14120 }
    ]
  }
]
```

**参数说明：**
- `keys`：逗号分隔的指标键名（从 `metricsKeys` 中取）
- `window`：时间窗口，前端默认传 `48h`，按小时粒度返回（约 48 个数据点）

---

#### `GET /api/{wp}/alerts?limit=20`

WP 级别告警列表。前端 10 秒轮询。

**响应格式（`WpAlertSchema[]`）：**

```json
[
  {
    "id": "alert-001",
    "severity": "HIGH",
    "title": "高危漏洞：CVE-2026-12345",
    "message": "检测到 GPT 系列模型存在提示注入漏洞，CVSS 9.1",
    "timestamp": "2026-03-19T10:23:00Z",
    "wp_id": "wp11",
    "acknowledged": false
  }
]
```

**severity 枚举：严格使用大写三值 `"HIGH"` / `"MEDIUM"` / `"LOW"`**

> 后端内部若使用 `"critical"`，序列化时必须映射为 `"HIGH"`。

---

#### `GET /api/{wp}/logs/stream`

Server-Sent Events 实时日志流。

**响应头（必须）：**

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

**事件格式：**

```
data: {"timestamp":"2026-03-19T12:00:00Z","level":"INFO","source":"supervisor_plan","message":"规划完成，分发 5 个采集任务"}

data: {"timestamp":"2026-03-19T12:00:01Z","level":"WARN","source":"collect_code_sources","message":"GitHub API 限流，等待 60s"}

```

**注意事项：**
- 每条 `data:` 后必须跟一个**空行**（SSE 协议要求）
- 后端每次 yield 后必须立即 flush，**不能批量缓冲**
- `level` 枚举：`"DEBUG"` / `"INFO"` / `"WARN"` / `"ERROR"`
- `source` 字段填节点名称（如 `supervisor_plan`、`semantic_dedup_and_merge`）

**FastAPI 实现示例：**

```python
from fastapi.responses import StreamingResponse
import asyncio
import json

@router.get("/api/wp11/logs/stream")
async def log_stream():
    async def generate():
        async for log_entry in runtime.log_queue():
            data = json.dumps({
                "timestamp": log_entry.timestamp.isoformat(),
                "level": log_entry.level,
                "source": log_entry.source,
                "message": log_entry.message,
            })
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
```

---

#### `POST /api/{wp}/runs`

启动新运行。

**请求体（`WpRunRequestSchema`）：**

```json
{
  "run_mode": "incremental",
  "target_sources": ["nvd", "github"],
  "runtime_context_overrides": {}
}
```

- `run_mode`：`"bootstrap"` / `"incremental"` / `"gap_fill"` / `"mixed"`
- `target_sources`：可选，限定数据源范围；为空数组时采集全部源
- `runtime_context_overrides`：高级调试用，覆盖初始状态字段

**响应体（`WpRunStatusSchema`）：**

```json
{
  "run_id": "run-20260319-001",
  "status": "running",
  "run_mode": "incremental",
  "started_at": "2026-03-19T12:00:00Z",
  "progress": {
    "current_node": "supervisor_plan",
    "completed_nodes": ["load_runtime_context"],
    "percent": 5
  },
  "errors": []
}
```

---

#### `DELETE /api/{wp}/runs/{run_id}`

取消运行。

**响应：** `204 No Content`（成功）或 `404`（运行不存在/已结束）

---

#### `GET /api/{wp}/runs/active`

查询当前活跃运行状态。前端在有活跃运行时 2 秒轮询。

**响应：** 同 `WpRunStatusSchema`，若无活跃运行返回 `null`（或 `204`）

---

### 3.2 WP1-1 专属端点

---

#### `GET /api/wp11/nodes`

获取 20 个图节点信息。

**响应（`WpNodeInfoSchema[]`）：**

```json
[
  {
    "node_name": "load_runtime_context",
    "display_name": "加载运行时上下文",
    "description": "初始化运行环境和上下文配置",
    "last_status": "succeeded",
    "is_triggerable": false
  },
  {
    "node_name": "supervisor_plan",
    "display_name": "主管规划",
    "description": "LLM 分析当前状态，制定采集策略",
    "last_status": "succeeded",
    "is_triggerable": true
  }
]
```

**重要约定：**
- `node_name` 必须与 `orchestrator/runtime.py` 中 `node_order` 的值**完全一致**（前端用它构造 POST URL）
- `load_runtime_context` 必须设 `is_triggerable: false`
- `last_status`：`"pending"` / `"running"` / `"succeeded"` / `"failed"` / `"skipped"`

---

#### `POST /api/wp11/nodes/{node_name}/run`

触发指定节点执行（调试用）。

**节点名称**来自 `GET /api/wp11/nodes` 返回的 `node_name` 字段。

**响应：** 同 `WpRunStatusSchema`

---

#### `GET /api/wp11/state/latest`

获取最新 GraphState 摘要（轻量，不含大数组）。

**响应（`WP11StateSnapshotSchema`）：**

```json
{
  "run_id": "run-20260319-001",
  "run_status": "running",
  "completed_nodes": ["load_runtime_context", "supervisor_plan", "dispatch_collection"],
  "processed_count": 1423,
  "new_attack_count": 87,
  "dedup_merged_count": 156,
  "alert_count": 12,
  "error_count": 0,
  "_full_state": null
}
```

**参数：** `?include_full=true` 时在 `_full_state` 字段中返回完整 70 字段（约 50KB，仅调试用）

---

#### `GET /api/wp11/runs/{run_id}/state`

获取指定运行的 GraphState 摘要（同上格式）。

---

### 3.3 全局端点

#### `GET /api/alerts`

全局告警（跨 WP 汇总）。格式同 `/api/{wp}/alerts`，但 `wp_id` 字段可为任意 WP 值。

---

## 4. 前端数据类型参考

前端 Zod schema 定义位于：
- `frontend/src/lib/types/wp.ts` — WP 状态、告警、日志、指标
- `frontend/src/lib/types/dashboard.ts` — 运行控制、节点、GraphState

接口实现时可直接参照这两个文件中的字段定义。

---

## 5. Mock 模式 → 真实模式迁移

前端所有 hooks 都有 mock/real 双分支。迁移步骤：

```
1. 设置 NEXT_PUBLIC_USE_MOCK_API=false
2. 逐个实现后端端点（从 P0 开始）
3. 每实现一个端点，在 /dashboard 页面验证对应组件显示真实数据
4. 若某端点尚未实现，临时在后端返回符合格式的 stub 数据（不要返回 500）
```

**推荐实现顺序：**

```
P0: GET /api/wp11/status
    GET /api/wp11/logs/stream

P1: GET /api/wp11/alerts
    GET /api/wp11/metrics
    POST /api/wp11/runs
    DELETE /api/wp11/runs/{run_id}
    GET /api/wp11/runs/active

P2: GET /api/wp11/nodes
    POST /api/wp11/nodes/{name}/run
    GET /api/wp11/state/latest
    GET /api/alerts

P3: GET /api/wp12/status  (stub: {"wp_id":"wp12","status":"pending","metrics":[]})
    GET /api/wp13/status  (stub)
    GET /api/wp14/status  (stub)
```

---

## 6. Nginx 生产配置

```nginx
server {
    listen 80;
    server_name saads.example.com;

    # 前端静态资源（长期缓存）
    location /_next/static/ {
        alias /var/www/saads/frontend/.next/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Next.js 服务（前端）
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # FastAPI 后端（含 SSE 日志流）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_buffering off;                    # ← SSE 必须关闭缓冲
        proxy_set_header X-Accel-Buffering no;  # ← 通知 Nginx 层不缓冲
        proxy_read_timeout 3600s;               # ← SSE 长连接超时
        proxy_send_timeout 3600s;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**关键点：**
- `proxy_buffering off` 是 SSE 流正常工作的前提，缺少此配置时日志流会缓冲后批量推送
- 生产环境下前后端同源，**后端无需配置 CORS**

---

## 7. 故障排查：联调常见问题

### 7.1 前端显示 "connecting…" 但日志流不到达

**排查步骤：**
1. 浏览器 DevTools → Network → 找到 `/api/wp11/logs/stream` 请求
2. 确认响应头有 `Content-Type: text/event-stream`
3. 确认后端每次 yield 后调用了 flush
4. 若经过 Nginx：确认 `proxy_buffering off` 已配置

### 7.2 前端收到数据但 Zod 校验报错

在浏览器 Console 查找类似 `ZodError` 的报错，定位是哪个字段类型不匹配。常见问题：
- `severity` 字段返回了小写 `"high"` 而不是 `"HIGH"`
- `status` 字段返回了后端内部枚举值（如 `"in_progress"`）而不是前端约定值（`"running"`）
- 数值字段返回了 `null` 但前端 schema 要求 `number`

### 7.3 Dashboard 卡片显示正确但 WP 详情页数据为空

WP 详情页（`/dashboard/wp11`）同时请求 status、metrics、alerts、logs/stream 四个端点。逐个检查 Network 面板中这四个请求的响应状态。

### 7.4 CORS 报错（开发环境）

```
Access to fetch at 'http://localhost:8000/api/wp11/status'
from origin 'http://localhost:3000' has been blocked by CORS policy
```

在后端 `main.py` 添加 CORS middleware（见第 2 节第 3 步）。

### 7.5 运行启动后进度不更新

`useWpRun` 在有活跃运行时每 2 秒轮询 `GET /api/wp11/runs/active`。确认该端点实现正确，返回的 `progress.percent` 是动态递增的。

---

## 8. 端到端验收测试清单

联调完成后，按此清单逐项验证：

### 基础连通性
- [ ] `NEXT_PUBLIC_USE_MOCK_API=false`，刷新 `/dashboard`，WP1-1 卡片显示真实运行状态
- [ ] WP1-1 卡片的三个指标数值与后端数据库一致

### 日志流
- [ ] `/dashboard/wp11` 日志区域实时更新（不需要手动刷新）
- [ ] 后端触发 ERROR 级别日志，前端对应行显示红色
- [ ] 断开后端连接，前端状态变为 "reconnecting" 并显示重试次数
- [ ] 重新启动后端，前端自动重连并恢复日志流

### 运行控制
- [ ] 点击"启动运行"，POST 请求发送正确，进度条开始递增
- [ ] 进度条中 `current_node` 文字随节点执行更新
- [ ] 点击"取消运行"，DELETE 请求成功，进度条消失

### 节点调试
- [ ] 20 个节点卡片全部渲染，`load_runtime_context` 按钮为 disabled
- [ ] 触发某个节点，后端执行对应逻辑，节点状态更新为 "succeeded" 或 "failed"

### 告警
- [ ] `/dashboard` 总览页显示全局告警，severity 颜色正确（HIGH=红，MEDIUM=橙，LOW=黄）
- [ ] `/dashboard/wp11` 详情页告警与 `GET /api/wp11/alerts` 返回数据一致

### 错误处理
- [ ] 关闭后端，前端 Dashboard 不崩溃，显示"加载失败"状态
- [ ] 后端返回非法格式（如缺少字段），前端 Console 显示 ZodError，页面不白屏
