# SUFE-SAADS 前端维护文档

> 面向接手团队的工程维护参考手册
> 最后更新：2026-03-19

---

## 1. 技术栈概览

| 层次 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | Next.js | 16.1.7 | App Router，全量 SSG/SSR |
| UI 运行时 | React | 19.2.3 | Server/Client Components |
| 语言 | TypeScript | ^5 | 严格模式 |
| 数据获取 | SWR | ^2.4.1 | Dashboard 轮询 |
| Schema 验证 | Zod | ^3.25.76 | API 响应运行时校验 |
| 图标 | lucide-react | ^0.511.0 | SVG 图标集 |
| 虚拟列表 | react-window | ^2.2.7 | 日志流渲染 |
| Markdown | unified + rehype | v11 系列 | 文档页渲染管道 |

**运行环境要求：**
- Node.js ≥ 20（推荐 LTS 版本）
- npm ≥ 10

---

## 2. 项目目录结构

```
frontend/
├── src/
│   ├── app/                         ← Next.js App Router 路由
│   │   ├── layout.tsx               ← 根 layout（html/body/globals.css）
│   │   ├── globals.css
│   │   ├── (marketing)/             ← 营销页路由组（含 SiteHeader/Footer）
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx             ← 首页 /
│   │   │   ├── story/               ← /story
│   │   │   └── docs/                ← /docs 及 /docs/[slug]
│   │   └── dashboard/               ← 运维面板（独立 layout，无 Header/Footer）
│   │       ├── layout.tsx
│   │       ├── page.tsx             ← /dashboard 总览
│   │       └── [wp]/page.tsx        ← /dashboard/wp11 等详情页
│   ├── components/
│   │   ├── ui/                      ← 基础 UI 原语（Badge、StatusDot 等）
│   │   ├── layout/                  ← SiteHeader、SiteFooter
│   │   ├── sections/                ← 首页各 section
│   │   ├── dashboard/               ← 运维面板组件
│   │   └── docs/                    ← 文档页组件
│   ├── lib/
│   │   ├── wp-registry.ts           ← 4 个 WP 的元数据注册表（必读）
│   │   ├── api/
│   │   │   ├── client.ts            ← 带 Zod 校验的 fetch 包装
│   │   │   └── mock.ts              ← 全量 mock 数据
│   │   ├── hooks/                   ← SWR/SSE hooks
│   │   ├── types/
│   │   │   ├── wp.ts                ← WP 状态、告警、日志 Zod schema
│   │   │   └── dashboard.ts         ← 运行控制、节点、GraphState schema
│   │   └── docs/
│   │       ├── registry.ts          ← 11 篇文档元数据注册表
│   │       └── processor.ts         ← unified Markdown 处理管道
│   └── styles/
│       ├── base.css                 ← CSS 变量设计 token
│       ├── tokens.css               ← 扩展 token（状态色）
│       └── animations.css
├── package.json
├── next.config.ts                   ← 安全响应头、bundle 分析开关
└── tsconfig.json
```

---

## 3. 关键模块说明

### 3.1 WP 注册表（`lib/wp-registry.ts`）

系统的核心配置文件。定义了 4 个智能体工作包（WP）的元数据，包括：

```typescript
{
  id: "wp11",
  name: "WP1-1 情报采集智能体",
  apiBase: "/api/wp11",      // 后端 API 前缀
  logStream: "/api/wp11/logs/stream",  // SSE 端点
  metricsKeys: ["attack_pool_size", "coverage_rate", "new_intel_24h"],
  // ...
}
```

**维护须知：** 若后端 API 路径变更，只需修改此文件中的 `apiBase`，所有 hooks 自动感知。

### 3.2 API 客户端（`lib/api/client.ts`）

```typescript
// 所有数据请求都经过此函数，会用 Zod schema 校验响应
fetchValidated(url, schema, options?)
```

**Mock 模式开关：**
```typescript
const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === "true"
```
设为 `true` 时，所有 hook 返回 `mock.ts` 中的假数据，不发送任何网络请求。

### 3.3 数据 Hooks（`lib/hooks/`）

| Hook 文件 | 用途 | 轮询间隔 |
|-----------|------|---------|
| `useWpStatus.ts` | WP 运行状态 + 指标 | 5 秒 |
| `useWpMetrics.ts` | 历史指标时序（48h） | 30 秒 |
| `useWpAlerts.ts` | 告警列表 | 10 秒 |
| `useSSELog.ts` | 实时日志流（SSE） | 持久连接 |
| `useWpRun.ts` | 启动/取消运行 | 2 秒（运行期间） |
| `useWp11Nodes.ts` | WP1-1 图节点列表 + 触发 | 按需 |
| `useWp11State.ts` | WP1-1 GraphState 快照 | 5 秒 |

**useSSELog 重连策略：** 退避序列 1s→2s→4s→8s→16s→30s，超 10 次停止自动重连；Tab 切回时立即重连；环形缓冲最多保留 500 条日志。

### 3.4 文档注册表（`lib/docs/registry.ts`）

管理 `/docs` 页面下 11 篇技术文档的元数据。每条记录包含 `slug`（URL 路径段）、`filename`（对应 `docs/` 目录下的 `.md` 文件名）、`sourceFiles`（相关源码路径）等。

**新增文档步骤：**
1. 将 Markdown 文件放入项目根目录 `docs/` 文件夹
2. 在 `registry.ts` 的 `DOC_REGISTRY` 数组中追加一条记录
3. 运行 `npm run build` 验证 SSG 路径生成正确

---

## 4. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEXT_PUBLIC_USE_MOCK_API` | `false` | `true` 时 Dashboard 全程使用 mock 数据 |
| `NEXT_PUBLIC_API_BASE` | （空） | 预留，生产环境后端根路径 |

**本地开发推荐：**
```bash
# .env.local（不提交 Git）
NEXT_PUBLIC_USE_MOCK_API=true
```

---

## 5. 常用命令

```bash
# 安装依赖
cd frontend && npm install

# 启动开发服务器（Mock 模式）
NEXT_PUBLIC_USE_MOCK_API=true npm run dev
# → http://localhost:3000

# 类型检查（零错误为通过标准）
npm run type-check

# 代码规范检查
npm run lint

# 代码格式化
npm run format

# 单元测试
npm run test
npm run test:watch    # 监听模式

# 生产构建（输出 .next/）
npm run build

# 本地启动生产构建
npm run start

# 打包体积分析
ANALYZE=true npm run build
```

---

## 6. 生产部署

### 方式 A：Node.js 服务器（推荐）

```bash
npm run build && npm run start
# 默认监听 :3000
```

### 方式 B：Nginx 反向代理（生产）

参见 `docs/frontend_deployment.md` 第 6 节的完整 Nginx 配置。重点：
- 静态资源（`/_next/static/`）设置长缓存 1 年
- SSE 端点（`/api/`）**必须**设置 `proxy_buffering off`，否则日志流无法实时推送

### 方式 C：纯静态导出

仅适用于不含 Dashboard 的纯文档/营销页场景（Dashboard 依赖 SWR 客户端请求，不兼容静态导出）。在 `next.config.ts` 添加 `output: 'export'` 后执行 `npm run build`。

---

## 7. 安全配置（`next.config.ts`）

已配置以下响应头，无需额外设置：

| 响应头 | 值 | 作用 |
|--------|----|------|
| `X-Frame-Options` | `DENY` | 禁止 iframe 嵌入 |
| `X-Content-Type-Options` | `nosniff` | 禁止 MIME 嗅探 |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | 限制 Referrer 泄漏 |
| `Content-Security-Policy` | 见配置文件 | 限制资源加载来源 |

**生产建议：** 将 CSP 中的 `script-src 'unsafe-eval'` 替换为 nonce 方案。

---

## 8. 常见维护任务

### 8.1 修改某个 WP 的显示名称或图标

编辑 `frontend/src/lib/wp-registry.ts`，修改对应 WP 的 `name`、`shortName`、`description` 字段。

### 8.2 新增文档页

1. 将 `.md` 文件放入 `docs/`（项目根目录，非 frontend/）
2. 在 `frontend/src/lib/docs/registry.ts` 添加条目
3. `npm run build` 验证

### 8.3 调整 Dashboard 轮询频率

在对应 hook 文件中修改 SWR 的 `refreshInterval`：
- `useWpStatus.ts` → 改 `5000`（毫秒）
- `useWpMetrics.ts` → 改 `30000`
- `useWpAlerts.ts` → 改 `10000`

### 8.4 新增 WP 状态卡

1. 在 `wp-registry.ts` 新增 WP 条目
2. 在 `lib/api/mock.ts` 添加对应的 mock 数据
3. `generateStaticParams` 在 `app/dashboard/[wp]/page.tsx` 会自动读取注册表生成路由

### 8.5 更新依赖

```bash
# 检查过时的包
npm outdated

# 更新 patch/minor（安全）
npm update

# 更新 major（注意 breaking changes）
npm install package@latest
npm run type-check  # 必须通过
npm run build       # 必须通过
```

---

## 9. 故障排查

### 9.1 构建失败

```bash
npm run type-check   # 先确认 TS 零错误
npm run lint         # 再确认 ESLint 通过
npm run build        # 最后构建
```

常见原因：
- `lib/docs/registry.ts` 中的 `filename` 与 `docs/` 实际文件名不匹配 → 构建时文件读取失败
- 新增的 Zod schema 字段与 mock 数据不一致 → 运行时报错

### 9.2 Dashboard 页面一直 loading

检查 `NEXT_PUBLIC_USE_MOCK_API` 环境变量：
```bash
# 确认 mock 模式已启用（后端未就绪时）
NEXT_PUBLIC_USE_MOCK_API=true npm run dev
```

### 9.3 日志流不更新

- Mock 模式：正常，每 2 秒推入一条 mock 日志
- 真实模式：检查后端 SSE 端点是否已实现，Nginx 是否设置了 `proxy_buffering off`

### 9.4 文档页代码块没有语法高亮

检查 `lib/docs/processor.ts` 中的 `safeSchema` 是否包含了 `hljs` className 的放行规则；检查 `DocRenderer.module.css` 中的 hljs token 选择器是否使用了 `:global()` 包裹。

---

## 10. 测试

单元测试使用 Vitest + @testing-library/react，测试文件位于 `src/__tests__/` 或与组件并列的 `.test.tsx` 文件中。

```bash
npm run test          # 单次运行
npm run test:watch    # 监听模式
```

目前测试覆盖：Zod schema 验证逻辑、工具函数、部分 UI 组件行为。
