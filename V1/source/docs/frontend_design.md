# 前端设计与开发方案

本文档覆盖 SUFE-SAADS 前端系统的完整设计方案，包括技术选型、部署架构、目录结构、设计系统、各页面规格、组件架构、数据层、可扩展性设计与开发计划。

---

## 1. 系统定位与目标

前端系统是 SUFE-SAADS 项目的对外展示与运营门户，承担以下职责：

1. **项目展示**：向学术界、合作方、评审方清晰传递系统的社会价值与技术深度
2. **技术文档**：作为项目技术文档的可视化入口，替代纯 Markdown 静态文档
3. **运营监控**：实时展示各智能体（WP1-1 ～ WP1-4）的运行状态、产出指标与告警
4. **可扩展基座**：架构上预留多 WP 接入能力，未来不需要改动框架，只扩展数据层

**当前阶段**：先接入 WP1-1（情报采集智能体），其余 WP 按需追加。

---

## 2. 技术栈选型

### 2.1 框架：Next.js 15（App Router）

| 维度 | 选择 | 理由 |
|------|------|------|
| **框架** | Next.js 15 (App Router) | SSR + SSG 兼备；文件路由天然支持层次结构；TypeScript 一等公民 |
| **语言** | TypeScript | 强类型约束 WP 注册表、API 类型、组件 Props，减少运行时错误 |
| **样式** | CSS Modules + 全局设计 Token | 复用现有 `anthropic-inspired.css`；组件样式隔离；无构建时 JS overhead |
| **数据获取** | SWR | 轻量、支持 SSE/轮询 revalidation，适合 Dashboard 实时数据 |
| **数据可视化** | Recharts | React 原生、轻量、可定制主题 token |
| **图标** | Lucide React | 统一 SVG 图标集，单 icon tree-shaking，viewBox 统一 24×24 |

### 2.2 不引入的工具

- **不用 Tailwind CSS**：现有 `anthropic-inspired.css` 已是完整设计系统，引入 Tailwind 会造成样式体系混乱
- **不用 Redux / Zustand**：Dashboard 数据通过 SWR key 隔离，无需全局状态管理
- **不用 Framer Motion**：所有动画用纯 CSS `@keyframes` + `Intersection Observer` 实现，零 JS 运行时开销

---

## 3. 前端部署架构

```
用户浏览器（HTTPS）
        │
        ▼
┌─────────────────────────────────────────────┐
│               Nginx 反向代理                 │
│                                             │
│  /          →  Next.js  :3000  (SSR/SSG)    │
│  /api/*     →  FastAPI  :8000  (后端)       │
│  /assets/*  →  静态文件直出                  │
└─────────────────────────────────────────────┘
        │
        │  实时数据流
        │  SSE（Server-Sent Events）
        ▼
   FastAPI 后端
   ├── /api/wp11/status     — WP1-1 运行状态
   ├── /api/wp11/metrics    — WP1-1 指标时序数据
   ├── /api/wp11/logs/stream — SSE 实时日志流
   └── /api/wp11/alerts     — 告警列表
```

**Docker Compose 组织**：

```yaml
services:
  nginx:     # 统一入口，SSL termination
  frontend:  # Next.js，端口 3000
  backend:   # FastAPI，端口 8000（现有）
  db:        # PostgreSQL（现有）
```

**SSR 策略**：
- `app/page.tsx`（Index）：静态生成（SSG），构建时生成，CDN 友好
- `app/story/page.tsx`：静态生成
- `app/docs/[section]/page.tsx`：静态生成，`generateStaticParams` 枚举所有章节
- `app/dashboard/page.tsx`：客户端渲染（CSR），SWR 轮询实时数据

---

## 4. 目录结构

```
frontend/
├── src/
│   ├── app/                            # Next.js App Router
│   │   ├── layout.tsx                  # 全局布局（SiteHeader + SiteFooter）
│   │   ├── page.tsx                    # 首页 Index
│   │   ├── story/
│   │   │   └── page.tsx                # 项目故事（滚动叙事）
│   │   ├── docs/
│   │   │   ├── page.tsx                # 文档首页（重定向到第一章）
│   │   │   └── [section]/
│   │   │       └── page.tsx            # 文档章节（动态路由）
│   │   └── dashboard/
│   │       ├── page.tsx                # 控制面板总览
│   │       └── [wp]/
│   │           └── page.tsx            # 各 WP 详情页
│   │
│   ├── components/
│   │   ├── ui/                         # 原子组件（无业务逻辑）
│   │   │   ├── Badge/
│   │   │   │   ├── index.tsx
│   │   │   │   └── Badge.module.css
│   │   │   ├── CountUp/                # 数字计数动画
│   │   │   ├── ScrollReveal/           # 滚动揭示 wrapper
│   │   │   ├── StatusDot/              # 脉冲状态圆点
│   │   │   └── CodeWindow/             # 代码展示窗口
│   │   │
│   │   ├── layout/
│   │   │   ├── SiteHeader/
│   │   │   ├── SiteFooter/
│   │   │   └── SiteNav/
│   │   │
│   │   ├── sections/                   # 页面级 Section（有业务内容）
│   │   │   ├── Hero/
│   │   │   │   ├── index.tsx
│   │   │   │   ├── SystemStatusPanel.tsx   # Hero 右侧动态面板
│   │   │   │   └── Hero.module.css
│   │   │   ├── KpiStrip/
│   │   │   ├── ArchitectureFlow/           # 攻防闭环架构图
│   │   │   ├── CtaBand/
│   │   │   ├── StorySlide/                 # Story 页单屏叙事
│   │   │   └── DocsLayout/                 # Docs 双栏布局
│   │   │
│   │   └── dashboard/
│   │       ├── WpStatusCard/
│   │       ├── WpDetailPanel/
│   │       ├── ActivityFeed/
│   │       ├── MetricsChart/
│   │       └── AlertList/
│   │
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts               # 基础 fetch wrapper
│   │   │   ├── wp11.ts                 # WP1-1 API 函数
│   │   │   └── index.ts
│   │   ├── types/
│   │   │   ├── wp.ts                   # WP 状态/数据 TypeScript 类型
│   │   │   └── api.ts                  # API 响应类型
│   │   ├── hooks/
│   │   │   ├── useWpStatus.ts          # SWR hook，WP 运行状态
│   │   │   ├── useWpMetrics.ts         # SWR hook，指标时序
│   │   │   ├── useWpLogs.ts            # SSE hook，实时日志
│   │   │   └── useCountUp.ts           # 数字计数动画 hook
│   │   └── wp-registry.ts              # ★ WP 注册表（可扩展性核心）
│   │
│   └── styles/
│       ├── globals.css                 # 导入 anthropic-inspired.css + 新增扩展
│       └── tokens.css                  # 新增设计 token（状态色、动画）
│
├── public/
│   └── assets/
│       └── diagrams/                   # SVG 架构图（从根目录 assets/ 复制）
│
├── next.config.ts
├── tsconfig.json
└── package.json
```

---

## 5. 设计系统

### 5.1 基础设计语言

完全继承 `frontend/anthropic-inspired.css`，不做破坏性修改，只做扩展。

| 设计决策 | 值 | 说明 |
|----------|-----|------|
| 主背景色 | `#f7f3eb` | 暖米白，书卷质感 |
| 标题字体 | Iowan Old Style / Palatino（衬线） | 人文气质 |
| 正文字体 | Inter（无衬线） | 现代可读性 |
| 代码字体 | SFMono-Regular / Menlo | 技术精确感 |
| 强调色 | `#a06a43`（焦糖棕） | 克制、温暖 |
| 基础圆角 | `10px / 14px / 20px / 28px` | 现代不失稳重 |
| 过渡时长 | `180ms cubic-bezier(0.2, 0.8, 0.2, 1)` | 流畅不浮夸 |

### 5.2 新增 Token（追加到 `styles/tokens.css`）

```css
/* 运行状态色 */
--status-running: #2d6e4e;
--status-running-bg: rgba(45, 110, 78, 0.10);
--status-warning: #9a6a2f;
--status-warning-bg: rgba(154, 106, 47, 0.10);
--status-error: #8d3f35;
--status-error-bg: rgba(141, 63, 53, 0.10);
--status-idle: #8b8378;
--status-idle-bg: rgba(139, 131, 120, 0.10);

/* 层次色（WP 通用层 vs 用户层） */
--layer-generic: rgba(160, 106, 67, 0.07);
--layer-user: rgba(23, 21, 18, 0.04);

/* Dashboard 数据 surface */
--surface-data: #eee8dc;

/* 动画 */
--duration-reveal: 480ms;
--duration-count: 1600ms;
--ease-reveal: cubic-bezier(0.2, 0.8, 0.2, 1);
```

### 5.3 新增 CSS 动画

```css
/* 状态脉冲（WP 节点运行中指示） */
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.45; transform: scale(0.8); }
}

/* SVG 数据流动线 */
@keyframes flow-dash {
  to { stroke-dashoffset: -24; }
}

/* 滚动揭示（页面进入动画） */
@keyframes fade-slide-up {
  from { opacity: 0; transform: translateY(28px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 通用 stagger 工具类 */
[data-reveal] { opacity: 0; }
[data-reveal].is-visible {
  animation: fade-slide-up var(--duration-reveal) var(--ease-reveal) forwards;
}
[data-reveal-delay="1"] { animation-delay: 80ms; }
[data-reveal-delay="2"] { animation-delay: 160ms; }
[data-reveal-delay="3"] { animation-delay: 240ms; }
[data-reveal-delay="4"] { animation-delay: 320ms; }
```

### 5.4 排版规范

| 层级 | 字号 | 字体 | 备注 |
|------|------|------|------|
| 页面大标题 | `clamp(3rem, 8vw, 6.25rem)` | serif | `.hero__title` |
| Section 标题 | `clamp(2rem, 4.3vw, 3.5rem)` | serif | `h2` |
| 卡片标题 | `clamp(1.35rem, 2vw, 1.8rem)` | serif | `h3` |
| Lead 段落 | `clamp(1.05rem, 1.35vw, 1.28rem)` | sans | 最大宽度 56ch |
| 正文 | `1rem / 1.6 lh` | sans | 移动端最小 16px |
| 辅助文字 | `0.9rem` | sans | `--text-soft` |
| Eyebrow 标签 | `0.75rem / 600 / 0.08em` | sans uppercase | 含前缀圆点 |

---

## 6. 页面设计规格

### 6.1 Index（首页）

**目标**：60 秒内让访客理解「这是什么、为什么重要、如何深入了解」。

#### Hero Section

```
┌─────────────────────────────────────────────────────────────┐
│  [eyebrow] SUFE · 2026 · AI 系统安全                        │
│                                                             │
│  AI 系统                                                    │  ┌────────────────────┐
│  态势感知与防御         [了解项目故事 →]  [进入控制面板]     │  │  系统状态面板       │
│                                                             │  │  ● WP1-1  运行中    │
│  [lead] 构建自我感知、学习、规划、执行的智能体群，            │  │  ● WP1-2  运行中    │
│  解决 AI 系统面临的网络安全与功能安全挑战。                  │  │  ● WP1-3  待接入    │
│                                                             │  │  ● WP1-4  待接入    │
│  ↓ 向下探索                                                 │  │  [流动 SVG 连接线]  │
└─────────────────────────────────────────────────────────────┘  └────────────────────┘
```

**Hero 右侧 SystemStatusPanel 技术实现**：

- 使用内联 SVG 绘制 4 个 WP 节点 + 连接线
- 节点：`<circle>` + 标签文字，运行中节点加 CSS `animation: pulse-dot 2s infinite`
- 连接线：`<line stroke-dasharray="4 3">` + `animation: flow-dash 1.2s linear infinite`
- 通用层（WP1-1、WP1-2）与用户层（WP1-3、WP1-4）之间有竖向虚线分隔
- 底部展示 2-3 条最近情报 mock 条目（极小字体，增加技术质感）
- `panel::after` 保留右下角 radial-gradient 暖光晕

**进入动画**：`IntersectionObserver` 触发 `data-reveal` + `data-reveal-delay` stagger，eyebrow → h1 → lead → actions 依次淡入上滑。

#### KPI Strip

4 列 grid，进入 viewport 时触发 `useCountUp` hook 数字动画：

| 指标 | 示例值 | 说明 |
|------|--------|------|
| 已入库攻击情报 | 2,400+ | attack_pool 条目数 |
| OWASP LLM 覆盖 | 100% | Top 10 类型覆盖率 |
| 测试脚本 | 380+ | WP1-2 生成脚本数 |
| 检测模型准确率 | 97.3% | WP1-4 基线模型 F1 |

数字使用 `--font-serif` + `clamp(2rem, 3vw, 2.8rem)`，复用现有 `.kpi` `.kpi__value` 类。

#### Architecture Flow（攻防闭环流水线）

不做普通 4 列等宽卡片，而是带连接线的可视化流水线：

```
  ┌──── 通用层（持续运行）────┐     ┌──── 用户层（接入后启动）────┐
  │                          │     │                              │
[WP1-1]──→──[WP1-2]──────────────→[WP1-3]──→──[WP1-4]
情报采集     红队测试              沙盒模拟     异常检测
  │                                                 │
  └────────────── 攻防闭环反馈 ←───────────────────┘
```

技术实现：
- 外层 `position: relative` 容器，卡片用 `display: flex` 横排
- 箭头连接线：绝对定位 SVG，`<path>` 绘制，带 `flow-dash` 动画
- 底部回环箭头：弧形 SVG path
- 通用层/用户层分隔：垂直虚线 + 标签
- 卡片悬停展开细节：`max-height: 0 → max-height: 200px` transition，展示「核心产出」列表
- 移动端：flex 改为垂直 stack，连接线改为垂直箭头

每张卡片内容：

```
[WP 编号标签]  [层次 badge]
[角色标题（衬线体）]
[一句话职责]
───────────────
▸ 核心产出 1     (hover 后展开)
▸ 核心产出 2
▸ 核心产出 3
```

#### CTA Band

复用现有 `.cta-band` 类，左侧衬线标题 + lead，右侧两个按钮：
- Primary: 「查看项目故事」→ `/story`
- Secondary ghost: 「进入控制面板」→ `/dashboard`

---

### 6.2 Story（项目故事，滚动叙事）

**目标**：像一本视觉书，用 7-8 屏讲清楚项目的社会价值线与技术线。

**交互模式**：`scroll-snap: y mandatory`，每屏 100vh，键盘方向键 / 滚轮切换，右侧显示章节进度点。

| 屏次 | 主题 | 核心内容 |
|------|------|---------|
| 0 | 开场 | 全屏引语：「每个 AI 系统，都是一个新的攻击面」+ 背景数据（CVE 增长曲线）|
| 1 | 社会价值 | AI 安全威胁格局图（SVG 可视化）+ 「为什么现在？」文字 |
| 2 | 设计思想 | 双轨对比：传统被动防御 vs SAADS 攻防一体闭环 |
| 3 | WP1-1 | 左：情报采集流程图，右：技术细节（数据来源表格）|
| 4 | WP1-2 | 左：红队测试示意，右：OWASP LLM Top 10 覆盖热力图 |
| 5 | WP1-3 | 左：沙盒架构图，右：数据采集维度列表 |
| 6 | WP1-4 | 左：模型选择流程，右：ADBench 评测结果示意 |
| 7 | 闭环 | 全幅架构图 + 「持续进化」演进路线时间轴 |

**双轨叙事布局**（偶数屏）：
- 左列（人文/社会价值）：serif 字体，大引语，留白充足
- 右列（技术）：代码窗口 / 数据图表 / 架构图

**组件**：`StorySlide` wrapper + `NarrativeTrack` 双栏 + `ChapterDot` 进度导航。

---

### 6.3 Docs（技术文档）

**目标**：将现有 `docs/` 目录的 Markdown 文档可视化呈现，替代 GitHub 文件浏览体验。

**布局**：

```
┌──────────────┬──────────────────────────────────────────┐
│  侧边栏      │  内容区                                   │
│  （固定）    │  （滚动）                                  │
│              │                                          │
│ — 项目概览   │  # 标题                                   │
│ — 技术栈     │  正文 Markdown 渲染                       │
│ — 系统架构   │  代码块（语法高亮）                        │
│ ▾ WP 详解    │  内联 SVG 图表                            │
│   — WP1-1   │                                          │
│   — WP1-2   │                                          │
│   — WP1-3   │  [上一章] ←          → [下一章]           │
│   — WP1-4   │                                          │
│ — API 参考  │                                          │
└──────────────┴──────────────────────────────────────────┘
```

技术选型：
- 使用 `next-mdx-remote` 渲染 Markdown（支持自定义组件）
- 代码高亮：`rehype-highlight`，主题色与 `anthropic-inspired.css` 协调
- 侧边栏：静态生成时从文件系统读取文档结构，`generateStaticParams` 枚举

文档章节映射（`lib/docs-manifest.ts`）：

```typescript
export const DOCS_MANIFEST = [
  { slug: "overview",       title: "项目概览",   file: "README.md" },
  { slug: "architecture",   title: "系统架构",   file: "docs/wp11_architecture.md" },
  { slug: "wp11",           title: "WP1-1 情报采集", file: "docs/wp11_agentic_design_pattern_summary.md" },
  // ...
]
```

---

### 6.4 Dashboard（控制面板）

**目标**：运营人员实时监控各 WP 运行健康状况，发现异常并快速定位。

#### 总览页 `/dashboard`

```
┌─ 系统状态 ────────────────────────────────────────────────┐
│  整体：● 正常运行  最后更新：2026-03-18 14:32:18  [刷新]   │
└───────────────────────────────────────────────────────────┘

┌─ WP1-1 情报采集 ──┐  ┌─ WP1-2 红队测试 ──┐  ┌─ WP1-3 ┐  ┌─ WP1-4 ┐
│ ● 运行中           │  │ ○ 未接入           │  │ ○ 未接入│  │ ○ 未接入│
│ 攻击情报: 2,412    │  │                   │  │        │  │        │
│ 今日新增: +47      │  │ 接入后自动启用      │  │        │  │        │
│ 覆盖率: 91.3%      │  │                   │  │        │  │        │
│ [查看详情 →]       │  │                   │  │        │  │        │
└───────────────────┘  └───────────────────┘  └────────┘  └────────┘

┌─ 实时日志流 ─────────────────────────────────────────────────────────┐
│ [14:32:15] [WP1-1] [INFO]  Intel Supervisor: coverage gap analysis... │
│ [14:32:14] [WP1-1] [INFO]  Web Crawler: fetched 12 CVE entries       │
│ [14:32:11] [WP1-1] [WARN]  Dark Web Agent: Tor circuit timeout, retry │
└──────────────────────────────────────────────────────────────────────┘

┌─ 告警列表 ──────────────────────────────────────────────────┐
│ ● [HIGH] 新发现 Prompt Injection 变体，CVSS 8.1  12分钟前    │
└─────────────────────────────────────────────────────────────┘
```

**数据刷新策略**：
- WP 状态卡：`SWR` 每 30s revalidate
- 实时日志流：SSE（`EventSource` hook），后端推送
- 告警列表：`SWR` 每 60s revalidate
- 指标图表：`SWR` 每 5min revalidate

#### WP 详情页 `/dashboard/[wp]`

```
┌─ WP1-1 情报采集智能体 ──────────────────────────────────────┐
│  ● 运行中  │ 已运行 3d 14h 22m  │ 版本 v0.9.2               │
└────────────────────────────────────────────────────────────┘

┌─ 指标趋势（48h）──────────────────────────────────────────────┐
│  [折线图: 新增情报 / 覆盖率 / 查询成功率]  Recharts            │
└────────────────────────────────────────────────────────────────┘

┌─ 当前任务 ──────────────────────────┐  ┌─ 最近告警 ──────────┐
│ Intel Supervisor → analyzing gaps   │  │ ● HIGH  8.1  12m前  │
│ Web Crawler      → fetching NVD     │  │ ○ MED   5.3  2h前   │
│ Standardizer     → normalizing x12  │  └─────────────────────┘
└─────────────────────────────────────┘
```

---

## 7. 可扩展性设计：WP 注册表

**核心原则**：新增 WP 只修改一个文件，不改动任何页面组件。

```typescript
// src/lib/wp-registry.ts

export type WpStatus = "running" | "idle" | "warning" | "error" | "pending"

export interface WpMetricDef {
  key: string           // API 字段名
  label: string         // 显示标签
  unit?: string         // 单位（%、+、条等）
  format?: "number" | "percent" | "duration"
}

export interface WpMeta {
  id: string            // "wp11" | "wp12" | "wp13" | "wp14"
  label: string         // "情报采集智能体"
  code: string          // "WP1-1"
  layer: "generic" | "user"
  apiBase: string       // "/api/wp11"
  metrics: WpMetricDef[]
  statusKey: string     // API 响应中 status 字段路径
  logStream: string     // SSE 端点路径
  order: number         // 在 Dashboard 中的排列顺序
}

export const WP_REGISTRY: WpMeta[] = [
  {
    id: "wp11",
    label: "情报采集智能体",
    code: "WP1-1",
    layer: "generic",
    apiBase: "/api/wp11",
    metrics: [
      { key: "attack_pool_size", label: "已入库情报",  unit: "条" },
      { key: "coverage_rate",    label: "OWASP 覆盖率", unit: "%", format: "percent" },
      { key: "new_intel_24h",    label: "今日新增",     unit: "条", format: "number"  },
    ],
    statusKey: "status",
    logStream: "/api/wp11/logs/stream",
    order: 1,
  },
  // WP1-2, WP1-3, WP1-4 追加于此
]
```

Dashboard 所有 WP 状态卡、详情页路由、图表均从注册表动态渲染，`WP_REGISTRY.map(...)` 驱动。

---

## 8. 数据层设计

### 8.1 API 类型定义（`src/lib/types/wp.ts`）

```typescript
export interface WpStatusResponse {
  wp_id: string
  status: WpStatus
  uptime_seconds: number
  version: string
  metrics: Record<string, number | string>
  last_updated: string   // ISO 8601
}

export interface WpMetricPoint {
  timestamp: string      // ISO 8601
  value: number
}

export interface WpMetricSeries {
  key: string
  points: WpMetricPoint[]
}

export interface WpAlert {
  id: string
  severity: "HIGH" | "MEDIUM" | "LOW"
  title: string
  cvss?: number
  created_at: string
}

export interface WpLogEntry {
  timestamp: string
  level: "INFO" | "WARN" | "ERROR" | "DEBUG"
  source: string         // e.g. "Intel Supervisor"
  message: string
}
```

### 8.2 SWR Hook 模式（`src/lib/hooks/useWpStatus.ts`）

```typescript
import useSWR from "swr"
import type { WpStatusResponse } from "../types/wp"

const fetcher = (url: string) => fetch(url).then(r => r.json())

export function useWpStatus(wpId: string) {
  const { data, error, isLoading } = useSWR<WpStatusResponse>(
    `/api/${wpId}/status`,
    fetcher,
    { refreshInterval: 30_000 }
  )
  return { status: data, error, isLoading }
}
```

### 8.3 SSE 日志流 Hook（`src/lib/hooks/useWpLogs.ts`）

```typescript
import { useEffect, useRef, useState } from "react"
import type { WpLogEntry } from "../types/wp"

export function useWpLogs(streamUrl: string, maxLines = 200) {
  const [logs, setLogs] = useState<WpLogEntry[]>([])
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource(streamUrl)
    esRef.current = es
    es.onmessage = (e) => {
      const entry: WpLogEntry = JSON.parse(e.data)
      setLogs(prev => [entry, ...prev].slice(0, maxLines))
    }
    return () => es.close()
  }, [streamUrl])

  return logs
}
```

---

## 9. 组件开发规范

与后端 `AGENTS.md` 保持一致的命名风格：

| 类型 | 命名规范 | 示例 |
|------|----------|------|
| 页面组件 | `PascalCase` | `DashboardPage` |
| Section 组件 | `PascalCase + Section` 后缀 | `HeroSection` |
| UI 原子组件 | `PascalCase` | `StatusDot`, `CountUp` |
| Hook | `use` 前缀 | `useWpStatus` |
| 类型 | `PascalCase + DTO/Response/Meta` | `WpStatusResponse` |
| CSS Module class | `camelCase` | `styles.statusDot` |

**组件文件结构**：
```
ComponentName/
├── index.tsx           # 主组件（导出入口）
├── ComponentName.module.css
└── types.ts            # 仅当 Props 复杂时单独提取
```

**禁止项**：
- 不在组件内写内联 `style={{}}` 对象（除非动态值无法用 CSS 变量表达）
- 不用 emoji 作为图标（统一用 Lucide React SVG）
- 所有可点击元素必须带 `cursor: pointer`（已在全局 CSS 中处理 `button`，其余手动补充）
- 不跳过 `aria-label`（icon-only 按钮必须有描述）

---

## 10. 前端开发计划

### 10.1 开发总目标

构建一个视觉上令人惊艳、技术上健壮可维护的前端系统，在以下维度全部达标：

- **展示层**：60 秒内让陌生访客理解项目的社会价值与技术深度
- **叙事层**：Story 页能作为答辩 / 汇报的独立演示材料
- **运营层**：Dashboard 可无人值守实时监控 WP1-1，异常时 5 分钟内发现
- **工程层**：新增 WP 不改框架，Lighthouse Performance ≥ 90、Accessibility ≥ 95

### 10.2 开发原则

#### 10.2.1 骨架优先，数据后接

所有页面先用静态 mock 数据完成完整视觉与交互，验收通过后再接入真实 API。原因：后端接口往往比预期晚就绪，视觉评审不应被数据层阻塞。

绝不允许把接口未就绪作为页面未完成的理由。

#### 10.2.2 组件边界一次设计到位

以下内容从第一天开始就必须按完整系统设计：

- `WP_REGISTRY` 结构（新增 WP 时只追加条目，不改组件）
- Zod schema（`WpStatusResponse`、`WpLogEntry` 等 API 契约）
- CSS token 命名空间（`--status-*`、`--layer-*`，不得后期随意追加）
- Server / Client 组件边界（一旦确定，不轻易翻转）

以下内容允许先弱实现，再逐步增强：

- 页面内容（KPI 数字、Story 文案可先用占位符）
- 图表复杂度（先画折线图，再加热力图、散点图）
- 动画精细度（先有 fade-in，再加 stagger、SVG 流动线）
- 错误处理（先 throw，再加 retry / fallback UI）

#### 10.2.3 并行但不交叉

前端 Phase 0-2（脚手架、首页、Story）与后端 WP1-1 开发**并行推进**，完全不依赖后端。Phase 3（Dashboard 实时数据）才需要后端接口，届时两侧同步联调。

不允许在 Phase 0-2 阶段为了等后端接口而停滞前端工作。

#### 10.2.4 每个 Phase 独立可演示

每个 Phase 完成后，产出必须是可以在浏览器中独立运行和演示的状态，不存在「半成品」合并到 main 的情况。

---

### 10.3 阶段划分总览

| Phase | 名称 | 核心产出 | 后端依赖 | 预计工作量 |
|-------|------|---------|---------|-----------|
| 0 | 脚手架与设计系统 | 可运行的 Next.js 项目 + 原子组件库 | 无 | 1-2 天 |
| 1 | Index 首页 | 完整首页（含动画、架构流水线） | 无（mock 数据） | 2-3 天 |
| 2 | Story 滚动叙事 | 8 屏叙事页面 | 无（静态内容） | 2-3 天 |
| 3 | Dashboard 控制面板 | WP1-1 实时监控 | **需要 FastAPI 接口** | 3-4 天 |
| 4 | Docs 文档页 | Markdown 可视化文档 | 无（读本地文件） | 1-2 天 |
| 5 | 生产部署 | Docker + Nginx + 可访问 URL | 需要服务器 | 1 天 |

---

### 10.4 Phase 0：脚手架与设计系统

**目标**：搭建可运行骨架，设计 token 体系落地，原子组件库可复用。

**一次设计到位的内容**：在此阶段确定后不得更改。

#### 任务清单

**项目初始化**
- [ ] `npx create-next-app@latest frontend --typescript --app --src-dir --no-tailwind`
- [ ] 配置 `next.config.ts`：Bundle Analyzer、CSP 响应头、图片域名白名单
- [ ] 配置 `tsconfig.json`：启用 `strict`、`noUncheckedIndexedAccess`、`exactOptionalPropertyTypes`
- [ ] 配置 `.eslintrc.json`：继承 `next/core-web-vitals`，追加 `react/no-danger`、`consistent-type-imports`
- [ ] 配置 Husky + lint-staged（pre-commit 自动 lint + format）
- [ ] 配置 Vitest（单元测试运行器）
- [ ] 目录结构创建（`components/ui/`、`components/layout/`、`components/sections/`、`components/dashboard/`、`lib/`、`styles/`）

**设计系统**
- [ ] 将 `frontend/anthropic-inspired.css` 迁移到 `src/styles/globals.css`（不修改，只迁移）
- [ ] 创建 `src/styles/tokens.css`，追加状态色（`--status-*`）、层次色（`--layer-*`）、动画 token、骨架屏 shimmer
- [ ] 创建 `src/styles/animations.css`，定义 `@keyframes`：`pulse-dot`、`flow-dash`、`fade-slide-up`、`shimmer`
- [ ] `app/layout.tsx`：接入 `next/font`（Inter），注入 `--font-inter` CSS 变量，配置全局 metadata

**原子组件**（全部无业务逻辑，纯展示）
- [ ] `StatusDot`：props `status: WpStatus`，渲染对应颜色圆点，`running` 状态加 `pulse-dot` 动画
- [ ] `Badge`：props `variant: "running" | "warning" | "error" | "idle" | "pending" | "generic" | "user"`，复用 `--status-*` token
- [ ] `ScrollReveal`：`IntersectionObserver` wrapper，子元素进入视口时添加 `is-visible` class，支持 `delay` prop（数字型，映射到 `data-reveal-delay`）；`prefers-reduced-motion` 时跳过动画直接显示
- [ ] `CountUp`：接收 `to: number`、`duration?: number`、`formatter?: (n: number) => string`；在 `ScrollReveal` 触发时开始计数；`prefers-reduced-motion` 时直接显示最终值
- [ ] `CodeWindow`：展示代码片段的装饰性窗口（三个圆点 + 代码内容），用于 Story 页技术轨道
- [ ] `SkeletonLine`：骨架屏单行，props `width?: string`，shimmer 动画

**布局组件**
- [ ] `SiteHeader`（`"use client"`）：Logo + 导航链接（`usePathname` 高亮当前页）+ 「进入控制面板」按钮；移动端汉堡菜单
- [ ] `SiteFooter`：项目信息 + 导航链接 + 版权
- [ ] `app/layout.tsx`：组装 Header + Footer，设置全局 `<html lang="zh-CN">`

**WP 注册表**
- [ ] 创建 `src/lib/wp-registry.ts`，定义 `WpMeta`、`WpMetricDef` 接口，填入 WP1-1 条目（mock 数据）
- [ ] 创建 `src/lib/types/wp.ts`，定义 Zod schema（`WpStatusSchema`、`WpLogEntrySchema` 等）及推导类型
- [ ] 创建 `src/lib/api/client.ts`，实现 `fetchValidated<T>(url, schema)` 泛型 fetch wrapper

#### 验收标准

- `npm run dev` 启动无报错，`localhost:3000` 可访问
- 浏览器 DevTools 中能看到所有 CSS token 变量（`--status-running`、`--font-inter` 等）
- `npm run type-check` 零错误
- `npm run lint` 零错误
- 提交时 Husky pre-commit 正常拦截并修复格式问题

---

### 10.5 Phase 1：Index 首页

**目标**：完成首页完整视觉与交互，使用静态 mock 数据，达到可对外演示的水准。

**关键设计决策**：本阶段确定 Hero、KPI、ArchitectureFlow 的 DOM 结构和 CSS Module 类名；后续不得因为样式微调破坏已确定的 HTML 语义结构。

#### 任务清单

**Hero Section**
- [ ] 左侧内容区：eyebrow → `h1`（serif，`clamp(3rem, 8vw, 6.25rem)`）→ lead → actions 两个按钮
- [ ] `ScrollReveal` + `data-reveal-delay` 实现 stagger 进入动画（eyebrow delay=0、h1 delay=1、lead delay=2、actions delay=3）
- [ ] 右侧 `SystemStatusPanel`（`"use client"`）：内联 SVG，4 个 WP 节点圆圈 + 连接线（`stroke-dasharray` + `flow-dash` 动画）+ 通用层/用户层虚线分隔 + 底部 mock 情报条目列表；节点颜色从 `WP_REGISTRY` 读取（`running` 节点加 `pulse-dot`）
- [ ] 响应式：`≤ 768px` 时 `SystemStatusPanel` 折叠到文字下方，缩小展示

**KPI Strip**
- [ ] 4 列 grid，数据从 `KPI_DATA` 静态常量读取（mock）
- [ ] 每列：数字（`CountUp` + `ScrollReveal`）+ 单位标签 + 说明文字
- [ ] `≤ 640px` 变为 2×2 grid

**Architecture Flow（可视化流水线）**
- [ ] 外层容器 `position: relative`，4 张卡片 `display: flex` 横排
- [ ] SVG 层绝对定位，绘制 WP1-1→WP1-2→WP1-3→WP1-4 水平箭头 + 底部回环弧形箭头，均带 `flow-dash` 动画
- [ ] 通用层/用户层之间竖向虚线分隔 + 标签
- [ ] 卡片 hover 展开核心产出列表（`max-height` transition，不用 `height`）
- [ ] `≤ 768px`：改为垂直 stack，连接线改为垂直向下箭头，禁用 hover 展开（改为默认展开）

**CTA Band**
- [ ] 复用 `.cta-band` 样式，左文右按钮布局
- [ ] Primary：「了解项目故事」→ `/story`；Ghost：「进入控制面板」→ `/dashboard`

**页面组装**
- [ ] `app/page.tsx`（Server Component）：按序组装 Hero → KPI Strip → Architecture Flow → CTA Band
- [ ] `app/page.tsx` 设置 `metadata`（title、description、OG 图）

#### 验收标准

- 1440px 桌面宽度下，Hero 高度填满视口（`100dvh`），视觉无裁剪
- 375px 移动端宽度下，无横向滚动，`SystemStatusPanel` 正常折叠展示
- 滚动至 KPI 区域，数字动画自动触发一次
- `ArchitectureFlow` SVG 箭头流动动画平滑，WP 卡片 hover 展开无抖动
- 关闭动画（`prefers-reduced-motion: reduce`）时，所有动画跳过，内容直接显示
- Lighthouse：Performance ≥ 90，Accessibility ≥ 95，Best Practices ≥ 95

---

### 10.6 Phase 2：Story 滚动叙事页

**目标**：完成 8 屏滚动叙事页面，可独立用于项目汇报演示。

**关键设计决策**：`scroll-snap` 容器高度固定 `100dvh`，不支持内容超长的屏（内容必须适配屏幕高度，而非滚动）；移动端降级为普通滚动（不用 scroll-snap），保证内容完整可读。

#### 任务清单

**框架组件**
- [ ] `StoryContainer`（`"use client"`）：外层 `overflow-y: scroll; scroll-snap-type: y mandatory`，高度 `100dvh`；监听 `keydown`（ArrowUp/ArrowDown）滚动到上/下一屏；`≤ 768px` 关闭 scroll-snap，改为普通流布局
- [ ] `ChapterNav`：右侧固定竖向点导航，当前章节高亮；点击跳转到对应章节；`≤ 768px` 隐藏
- [ ] `StorySlide`：单屏 wrapper，`scroll-snap-align: start; height: 100dvh`；接收 `layout: "full" | "split"` prop（全幅 / 双轨）
- [ ] `NarrativeTrack`：`layout: "split"` 时的左右双栏，左（人文轨，serif 字体，留白充足）+ 右（技术轨，代码窗口 / 图表）

**8 个章节内容**（内容与组件分离，内容写在 `src/data/story-slides.tsx`）

| 章节 | 布局 | 左轨 | 右轨 |
|------|------|------|------|
| 0 开场 | full | 全幅引语 + 副标题 | — |
| 1 社会价值 | split | 「为什么现在」文字 + 3 个威胁统计数字（`CountUp`）| AI CVE 增长折线图（SVG 静态）|
| 2 设计思想 | split | 「攻防一体闭环」设计哲学引语 | 传统防御 vs SAADS 对比图（两列卡片）|
| 3 WP1-1 | split | 「威胁发现者」角色定位 + 核心产出列表 | 数据来源表格 + 情报标准化流程图（SVG）|
| 4 WP1-2 | split | 「方案生成者」角色定位 | OWASP LLM Top 10 热力方块（10 个色块，数字覆盖率）|
| 5 WP1-3 | split | 「测试执行者」角色定位 | 沙盒层次示意图（SVG：用户系统 → 虚拟化克隆 → 沙盒）|
| 6 WP1-4 | split | 「防御建设者」角色定位 | 模型评估雷达图（SVG 静态，F1/Precision/Recall/AUC 四轴）|
| 7 闭环 | full | 全幅攻防闭环架构图（SVG，与 Index 的 ArchitectureFlow 同源，但全幅版本）+ 演进路线时间轴 | — |

- [ ] 章节 0-7 内容全部填充，文案从 README.md 提炼
- [ ] 所有章节内的 SVG 图表手工编写内联 SVG（不依赖图表库，保证静态渲染性能）
- [ ] 章节切换时标题和内容有轻微 fade 进入动画（CSS `@keyframes`，`prefers-reduced-motion` 时关闭）

#### 验收标准

- 1440px 下，8 屏均无内容溢出（无滚动条出现在单屏内）
- 键盘 ArrowDown / ArrowUp 可完整导航 8 屏
- 右侧进度点实时高亮当前章节
- 375px 移动端：scroll-snap 关闭，8 个章节连续展示，全部内容可读（无裁剪）
- 可直接截图 / 录屏作为汇报演示材料使用

---

### 10.7 Phase 3：Dashboard 控制面板

**目标**：WP1-1 运行状态、指标、实时日志、告警全部可观测；与后端 FastAPI 联调。

**前提条件（进入本阶段前需确认）**：
- 后端已实现 `/api/wp11/status`（GET，返回 `WpStatusResponse`）
- 后端已实现 `/api/wp11/metrics?series=attack_pool_size,coverage_rate&hours=48`（GET）
- 后端已实现 `/api/wp11/logs/stream`（SSE，每条推送 `WpLogEntry` JSON）
- 后端已实现 `/api/wp11/alerts`（GET，返回 `WpAlert[]`）
- Nginx 配置 `/api/*` 反向代理已就绪

#### 任务清单

**数据 Hook 层**
- [ ] `useWpStatus(wpId)` — SWR，30s revalidate，Zod 校验响应
- [ ] `useWpMetrics(wpId, series, hours)` — SWR，5min revalidate
- [ ] `useWpLogs(streamUrl)` — SSE + 指数退避重连（完整实现见第 17 节），返回 `{ logs, connected }`
- [ ] `useWpAlerts(wpId)` — SWR，60s revalidate
- [ ] 为 Phase 3 之前的 mock 阶段：创建 `src/lib/api/mock.ts`，导出 mock fetcher，可通过 env 变量切换真实/mock 模式（`NEXT_PUBLIC_USE_MOCK_API=true`）

**Dashboard 总览页** `app/dashboard/page.tsx`（Server Component）
- [ ] 顶部状态条：「整体：● 正常运行」（聚合所有 WP 状态的最差值）+ 最后更新时间 + 手动刷新按钮
- [ ] WP 卡片网格：`WP_REGISTRY.map(wp => <WpStatusCard wp={wp} />)`，注册表驱动
- [ ] 日志流：`<ActivityFeed />` 展示所有 WP 的合并日志（按时间倒序）
- [ ] 告警列表：`<AlertList />` 展示最近 10 条告警，HIGH 级别用红色

**WpStatusCard**（`"use client"`）
- [ ] 读取 `useWpStatus(wp.id)`，加载中时展示 `WpStatusCardSkeleton`
- [ ] 展示：WP 编号 + 名称 + `StatusDot` + 状态文字 + 3 个核心指标（从注册表 `metrics` 定义动态渲染）+ 「查看详情 →」链接
- [ ] 未接入（`status: "pending"`）时展示灰色降级 UI + 「接入后自动启用」文案
- [ ] 错误时展示 `error.tsx` 降级 UI（「数据暂时不可用，重试」）

**ActivityFeed**（`"use client"`）
- [ ] `useWpLogs` 订阅日志流，右上角连接状态指示（绿/黄/灰）
- [ ] `react-window` `FixedSizeList` 虚拟化（单条行高 28px，容器高度 320px）
- [ ] 日志格式：`[时间] [WP编号] [级别] 消息`；级别颜色：`INFO` 默认、`WARN` 警告棕、`ERROR` 错误红
- [ ] 「暂停滚动」toggle：开启时停止自动滚到底部（用于用户查看历史）

**MetricsChart**（`"use client"`，`dynamic` + `ssr: false`）
- [ ] Recharts `LineChart`，支持多条折线（每条对应一个 metric key）
- [ ] X 轴：时间（48h），Y 轴：数值，tooltip 显示具体数值 + 时间
- [ ] 颜色从设计 token 读取（`--status-running`、`--accent` 等），不硬编码

**WP 详情页** `app/dashboard/[wp]/page.tsx`（Server Component + Client 子组件）
- [ ] 面包屑：Dashboard → WP1-1 情报采集智能体
- [ ] 顶部状态栏：状态 + 已运行时长（`useWpStatus` 的 `uptime_seconds` 格式化为 `Xd Xh Xm`）+ 版本号
- [ ] 48h 指标趋势图（`MetricsChart`，动态 import）
- [ ] 当前任务列表（来自 `status.current_tasks`，若后端支持）
- [ ] 最近告警（`AlertList`，小尺寸变体）
- [ ] 全量日志流（`ActivityFeed`，高度 480px）

**联调**
- [ ] 配置 Nginx 将 `/api/*` 代理到 FastAPI `localhost:8000`
- [ ] 验证 SSE 通过 Nginx 正常穿透（需要在 Nginx 配置中关闭 `proxy_buffering`）
- [ ] 端到端测试：页面展示数据与后端数据库记录一致

#### 验收标准

- WP1-1 运行时，Dashboard 总览页 30 秒内自动刷新状态卡
- 实时日志流：新日志条目在 1 秒内出现在 ActivityFeed（SSE 延迟）
- 模拟后端重启：SSE 断线后 1 秒内开始重连，重连成功后日志流恢复，状态指示变回绿色
- 500 条日志下，ActivityFeed 滚动流畅（虚拟列表有效）
- Zod 校验：后端返回格式错误的响应时，组件展示错误边界 UI，控制台有 Zod 错误详情

---

### 10.8 Phase 4：Docs 文档页

**目标**：将现有 `docs/` 目录的 Markdown 文档可视化，替代 GitHub 文件浏览体验。

#### 任务清单

**文档清单**
- [ ] 创建 `src/lib/docs-manifest.ts`，将现有 `docs/` 文档映射到 slug：

```typescript
export const DOCS_MANIFEST = [
  { slug: "overview",      title: "项目概览",        file: "README.md" },
  { slug: "architecture",  title: "系统架构",        file: "docs/wp11_architecture.md" },
  { slug: "wp11-design",   title: "WP1-1 设计模式",  file: "docs/wp11_agentic_design_pattern_summary.md" },
  { slug: "wp11-dev",      title: "WP1-1 开发计划",  file: "docs/wp11_development_plan.md" },
  { slug: "wp11-state",    title: "WP1-1 状态设计",  file: "docs/wp11_langgraph_state.md" },
  { slug: "db-design",     title: "数据库设计",      file: "docs/db_module_design.md" },
  { slug: "frontend",      title: "前端设计",        file: "docs/frontend_design.md" },
]
```

**Markdown 渲染**
- [ ] 安装 `next-mdx-remote`、`rehype-highlight`、`rehype-sanitize`、`remark-gfm`
- [ ] `app/docs/[section]/page.tsx`（Server Component）：从文件系统读取 Markdown，`compileMDX` 渲染
- [ ] `generateStaticParams`：枚举 `DOCS_MANIFEST` 所有 slug，构建时静态预渲染
- [ ] `generateMetadata`：每章节设置独立 title

**DocsLayout 组件**
- [ ] 左侧固定导航栏（宽 240px）：章节列表，`usePathname` 高亮当前章节，支持分组折叠（「WP 详解」分组）
- [ ] 右侧内容区：Markdown 渲染，`prose` 排版（自定义，与设计 token 对齐，不用 Tailwind prose）
- [ ] 内容区底部：「上一章 /  下一章」翻页导航
- [ ] `≤ 768px`：侧边栏折叠为顶部下拉选择器

**代码高亮主题**
- [ ] 基于 `rehype-highlight` 的 GitHub Light 主题，覆盖颜色使其与 `--bg: #f7f3eb` 背景协调
- [ ] 代码块加 `CodeWindow` 装饰（三个圆点 header），与 Story 页保持一致

**首页重定向**
- [ ] `app/docs/page.tsx`：`redirect("/docs/overview")`

#### 验收标准

- `npm run build` 时所有文档章节静态预渲染成功，无文件读取报错
- 所有 Markdown 中的代码块有语法高亮，颜色与背景协调
- 左侧导航当前章节高亮正确
- 上一章 / 下一章翻页链接正确（不越界）
- `rehype-sanitize` 生效：Markdown 中的 `<script>` 标签被过滤

---

### 10.9 Phase 5：生产部署

**目标**：前端可通过公网 HTTPS URL 访问，与后端 FastAPI 联通，性能达标。

#### 任务清单

**Docker 化**
- [ ] 创建 `frontend/Dockerfile`（多阶段构建：`node:20-alpine` builder + `node:20-alpine` runner）
- [ ] 在根目录 `docker-compose.yml` 中追加 `frontend` 服务

**Nginx 配置**
- [ ] `nginx.conf` 追加规则：
  - `/api/*` → FastAPI `backend:8000`（关闭 `proxy_buffering`，支持 SSE）
  - `/` → Next.js `frontend:3000`
  - SSE 端点额外配置：`proxy_read_timeout 3600s`、`X-Accel-Buffering: no`
- [ ] SSL 证书配置（Let's Encrypt 或自签）

**生产验证**
- [ ] `docker compose build && docker compose up -d` 无报错
- [ ] `npm run build` 无 TypeScript 错误，无 ESLint 错误
- [ ] 访问生产 URL，确认 CSP 响应头正确
- [ ] SSE 日志流通过 Nginx 正常穿透（测试：关闭后端再启动，观察重连）

**性能基线**
- [ ] Lighthouse 生产环境跑分：
  - Performance ≥ 90
  - Accessibility ≥ 95
  - Best Practices ≥ 95
  - SEO ≥ 90
- [ ] Core Web Vitals：LCP < 2.5s，CLS < 0.1，INP < 200ms

---

### 10.10 技术债务管理

开发过程中，以下债务允许存在，但必须有明确的 TODO 注释和后续 Phase 的清偿计划：

| 债务 | 允许存在于 | 必须在 Phase 清偿 |
|------|-----------|-----------------|
| mock API 数据（`NEXT_PUBLIC_USE_MOCK_API=true`）| Phase 0-2 | Phase 3 |
| Story 页 SVG 图表使用占位灰色方块 | Phase 1-2 | Phase 2（Phase 2 内完成）|
| `WpStatusCard` error 状态展示纯文字 | Phase 3 初期 | Phase 3 完成前 |
| Dashboard 日志流无「暂停滚动」功能 | Phase 3 初期 | Phase 3 完成前 |
| Docs 代码高亮主题未精细调整 | Phase 4 初期 | Phase 4 完成前 |

不允许以「后续再说」的方式引入以下问题：

- `console.log` 残留在生产代码中
- TypeScript `any` 类型（除非有明确注释说明原因）
- 内联 `style={{}}` 对象（动态 CSS 变量除外）
- 未处理的 Promise rejection

---

### 10.11 与后端协作边界

前端与后端的唯一正式接口是 `/api/*` 路径，通过 Nginx 路由到 FastAPI。

**前端不依赖后端的内容**（Phase 0-2 可完全独立）：
- 所有 SSG 页面（Index、Story、Docs）
- 设计系统、原子组件库
- WP 注册表（纯前端静态数据）

**前端需要后端配合的内容**（Phase 3 联调阶段协商）：

| 接口 | 请求 | 响应 schema | 备注 |
|------|------|------------|------|
| `GET /api/wp11/status` | — | `WpStatusResponse`（见第 8 节）| 30s 轮询 |
| `GET /api/wp11/metrics` | `?series=k1,k2&hours=48` | `WpMetricSeries[]` | 5min 轮询 |
| `GET /api/wp11/logs/stream` | — | SSE，每条 `WpLogEntry` JSON | 长连接 |
| `GET /api/wp11/alerts` | `?limit=20` | `WpAlert[]` | 60s 轮询 |
| `POST /api/vitals` | `NextWebVitalsMetric` | `{ ok: true }` | 可选，性能监控 |

**接口协商原则**：
- 接口字段命名以 Zod schema（`src/lib/types/wp.ts`）为准，后端适配前端 schema，而非反之（前端已先确定 schema 结构）
- 后端接口变更必须先更新 Zod schema，前端重新校验后再联调
- SSE 格式：每条消息为单行 JSON，字段与 `WpLogEntrySchema` 一致

---

## 11. 验证检查清单

每个 Phase 完成后，执行以下检查：

### 视觉质量
- [ ] 无 emoji 作图标（使用 Lucide SVG）
- [ ] 所有 icon 尺寸统一（`width: 20` / `width: 24`）
- [ ] hover 状态无布局偏移（只改颜色/阴影/透明度）
- [ ] 光标：所有可点击元素有 `cursor-pointer`

### 无障碍访问
- [ ] 图片均有 `alt` 文字
- [ ] icon-only 按钮有 `aria-label`
- [ ] 颜色对比度 ≥ 4.5:1（正文）
- [ ] 焦点环可见（已在全局 CSS 中定义 `:focus-visible`）
- [ ] `prefers-reduced-motion` 下动画关闭

### 响应式
- [ ] 375px（iPhone SE）
- [ ] 768px（iPad）
- [ ] 1024px（小笔记本）
- [ ] 1440px（桌面）
- [ ] 无横向滚动条

### 性能
- [ ] 无 console 错误
- [ ] 无 layout shift（CLS ≈ 0，预留 async 内容空间）
- [ ] 图片使用 `next/image`（WebP + lazy load）
- [ ] 动画使用 `transform` / `opacity`，不使用 `width` / `height`

---

## 12. Server vs Client Components 边界（App Router 核心）

Next.js 15 App Router 默认所有组件为 **Server Component（RSC）**，错误地加 `"use client"` 会把大量代码推到客户端 bundle，降低性能。

### 边界划分原则

| 组件类型 | 是否加 `"use client"` | 理由 |
|----------|----------------------|------|
| 页面布局（`layout.tsx`）| 否 | 只做结构，无交互 |
| `app/page.tsx`（Index）| 否 | 静态内容，SSG |
| `app/story/page.tsx` | 否 | 内容静态 |
| `app/docs/[section]/page.tsx` | 否 | Markdown 静态渲染 |
| `app/dashboard/page.tsx` | **否** | 页面本身为 RSC，把 CSR 下沉到子组件 |
| `WpStatusCard` | **是** | 调用 `useWpStatus` SWR hook |
| `ActivityFeed` | **是** | 调用 `useWpLogs` SSE hook |
| `MetricsChart` | **是** | Recharts 依赖 DOM API |
| `CountUp` | **是** | 依赖 `IntersectionObserver` |
| `ScrollReveal` | **是** | 依赖 `IntersectionObserver` |
| `SystemStatusPanel` | **是** | 读取 WP 状态，CSS 动画触发 |
| `SiteHeader` | **是** | 导航高亮需要 `usePathname()` |

### 关键模式：把 CSR 叶子节点下沉

```tsx
// app/dashboard/page.tsx — Server Component（不加 "use client"）
import { WP_REGISTRY } from "@/lib/wp-registry"
import { WpStatusCard } from "@/components/dashboard/WpStatusCard" // "use client"

export default function DashboardPage() {
  // 从注册表静态生成卡片骨架，数据由子组件 SWR 填充
  return (
    <main>
      <div className={styles.grid}>
        {WP_REGISTRY.map(wp => (
          <WpStatusCard key={wp.id} wp={wp} />  {/* Client 边界在这里 */}
        ))}
      </div>
    </main>
  )
}
```

---

## 13. 错误边界与 Suspense 策略

### 13.1 错误边界（Error Boundaries）

Next.js App Router 通过 `error.tsx` 文件约定自动创建错误边界：

```
app/
├── error.tsx              # 全局错误边界（捕获 layout 以下所有错误）
├── dashboard/
│   ├── error.tsx          # Dashboard 错误边界（Dashboard 崩溃不影响其他页面）
│   └── [wp]/
│       └── error.tsx      # WP 详情页独立错误边界
└── not-found.tsx          # 404 页面
```

`dashboard/error.tsx` 核心设计：显示「WP 数据暂时不可用」降级 UI，而非白屏。提供「重试」按钮调用 `reset()`。

### 13.2 Suspense 边界（Loading 骨架屏）

```
app/
├── loading.tsx            # 全局 loading（路由切换时自动显示）
└── dashboard/
    └── loading.tsx        # Dashboard 专属骨架屏
```

**骨架屏策略**：Dashboard 卡片区域预占位，避免内容跳动（CLS 来源之一）：

```tsx
// components/dashboard/WpStatusCard/Skeleton.tsx
export function WpStatusCardSkeleton() {
  return (
    <div className={styles.card} aria-busy="true">
      <div className={`${styles.skeletonLine} ${styles.wide}`} />
      <div className={`${styles.skeletonLine} ${styles.narrow}`} />
    </div>
  )
}
```

CSS 骨架屏动画：
```css
@keyframes shimmer {
  from { background-position: -200% 0; }
  to   { background-position:  200% 0; }
}
.skeletonLine {
  background: linear-gradient(90deg,
    var(--surface-2) 25%,
    var(--surface) 50%,
    var(--surface-2) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
  border-radius: var(--radius-xs);
  height: 0.85em;
}
```

---

## 14. Bundle 分割与动态 Import

**问题**：Recharts 库体积约 350KB（gzip 后 ~100KB），所有页面都会加载它——即使用户只访问 Index 页。

**方案**：对重型依赖使用 `next/dynamic`：

```tsx
// components/dashboard/MetricsChart/index.tsx
import dynamic from "next/dynamic"

const RechartsLineChart = dynamic(
  () => import("./RechartsLineChart"),
  {
    loading: () => <MetricsChartSkeleton />,
    ssr: false,   // Recharts 不支持 SSR，关闭服务端渲染
  }
)
```

**Bundle 分割策略**：

| 模块 | 策略 | 原因 |
|------|------|------|
| Recharts | `dynamic` + `ssr: false` | DOM 依赖，体积大 |
| `StorySlide` 内容（图表/SVG） | `dynamic` | 每屏内容独立 chunk |
| Docs Markdown 渲染 | Server Component（无需 dynamic）| 服务端处理 |
| Lucide React 图标 | 按需 named import，自动 tree-shaking | `import { Shield } from "lucide-react"` |

**Bundle 分析**（开发时定期检查）：
```bash
ANALYZE=true npm run build
# 依赖 @next/bundle-analyzer，在 next.config.ts 中配置
```

---

## 15. 字体加载策略

**问题**：`anthropic-inspired.css` 使用 `Iowan Old Style`（系统字体）+ `Inter`（需要加载），如果处理不当会触发 FOUT（无样式文字闪烁）。

**方案**：使用 `next/font` 实现零 FOUT：

```tsx
// app/layout.tsx
import { Inter } from "next/font/google"

const inter = Inter({
  subsets: ["latin"],
  display: "swap",          // 先用系统字体，Inter 加载后替换
  preload: true,
  variable: "--font-inter", // 注入 CSS 变量
})

// 衬线字体来自系统栈（Iowan Old Style / Palatino），无需加载
// 因此 --font-serif 直接在 CSS 中声明，不经过 next/font
```

**注意**：不要把 `--font-sans` 硬编码为 `"Inter"`，而应用 `var(--font-inter)` + fallback，确保字体未加载时有合适的 fallback 字体防止布局偏移。

---

## 16. 运行时类型安全（Zod 校验）

API 响应在运行时不受 TypeScript 控制。后端接口变更或返回异常数据时，若缺少运行时校验，错误会在深层组件中以难以追踪的方式爆发。

**方案**：在 API 客户端层用 Zod 校验所有外部数据：

```typescript
// src/lib/api/client.ts
import { z } from "zod"

export async function fetchValidated<T>(
  url: string,
  schema: z.ZodType<T>
): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API ${res.status}: ${url}`)
  const raw = await res.json()
  return schema.parse(raw)  // 解析失败时抛出详细错误，而非静默失败
}

// src/lib/types/wp.ts — Zod schema 是 source of truth，TypeScript 类型从中推导
export const WpStatusSchema = z.object({
  wp_id: z.string(),
  status: z.enum(["running", "idle", "warning", "error", "pending"]),
  uptime_seconds: z.number(),
  version: z.string(),
  metrics: z.record(z.union([z.number(), z.string()])),
  last_updated: z.string().datetime(),
})

export type WpStatusResponse = z.infer<typeof WpStatusSchema>
```

---

## 17. SSE 实时数据健壮性

SSE 连接在网络切换、后端重启、浏览器后台限流时会断开，必须有重连机制。

### 17.1 健壮的 SSE Hook

```typescript
// src/lib/hooks/useWpLogs.ts
import { useEffect, useRef, useState, useCallback } from "react"
import type { WpLogEntry } from "../types/wp"

const RECONNECT_BASE_MS = 1_000
const RECONNECT_MAX_MS  = 30_000
const MAX_LINES         = 500

export function useWpLogs(streamUrl: string) {
  const [logs, setLogs]         = useState<WpLogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const esRef     = useRef<EventSource | null>(null)
  const timerRef  = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (esRef.current) esRef.current.close()

    const es = new EventSource(streamUrl)
    esRef.current = es

    es.onopen = () => {
      setConnected(true)
      setRetryCount(0)
    }

    es.onmessage = (e) => {
      try {
        const entry: WpLogEntry = JSON.parse(e.data)
        setLogs(prev => [entry, ...prev].slice(0, MAX_LINES))
      } catch { /* 忽略解析错误，避免单条坏数据中断日志流 */ }
    }

    es.onerror = () => {
      setConnected(false)
      es.close()
      // 指数退避重连
      const delay = Math.min(RECONNECT_BASE_MS * 2 ** retryCount, RECONNECT_MAX_MS)
      timerRef.current = setTimeout(() => {
        setRetryCount(c => c + 1)
        connect()
      }, delay)
    }
  }, [streamUrl, retryCount])

  useEffect(() => {
    connect()
    return () => {
      esRef.current?.close()
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [streamUrl])    // streamUrl 变化时重建连接

  return { logs, connected }
}
```

### 17.2 连接状态展示

`ActivityFeed` 组件右上角显示连接状态：
- 绿点 + "实时" — SSE 已连接
- 黄点 + "重连中..." — 断线重连
- 灰点 + "已断开" — 多次重连失败

---

## 18. 安全

### 18.1 Content Security Policy（CSP）

在 `next.config.ts` 中通过 HTTP 响应头配置：

```typescript
// next.config.ts
const cspHeader = `
  default-src 'self';
  script-src  'self' 'nonce-{NONCE}';
  style-src   'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src    'self' https://fonts.gstatic.com;
  img-src     'self' data: blob:;
  connect-src 'self' /api/;
  frame-ancestors 'none';
`.replace(/\n/g, " ").trim()
```

**注意**：Next.js 15 App Router 的 Server Actions 需要 `'unsafe-inline'` 或 nonce 方案处理。

### 18.2 环境变量管理

| 变量 | 前缀 | 位置 | 说明 |
|------|------|------|------|
| `NEXT_PUBLIC_API_BASE` | `NEXT_PUBLIC_` | `.env.local` | 客户端可见，后端 API 基础 URL |
| `NEXT_PUBLIC_APP_VERSION` | `NEXT_PUBLIC_` | `.env.local` | 版本号展示 |
| 内部密钥（如后端 service token）| 无前缀 | `.env.local` | **仅服务端**，不暴露到浏览器 |

在 `next.config.ts` 中用 Zod 校验必要的环境变量，确保构建时尽早报错：

```typescript
import { z } from "zod"
const envSchema = z.object({
  NEXT_PUBLIC_API_BASE: z.string().url(),
})
envSchema.parse(process.env)  // 构建时失败比运行时失败更好
```

### 18.3 XSS 防范

- `next-mdx-remote` 渲染 Markdown 时，配置 `rehype-sanitize`，过滤 `<script>`、`onerror` 等危险属性
- 所有从 API 获取的文本内容通过 React 正常渲染（JSX 自动转义），不用 `dangerouslySetInnerHTML`
- 实时日志条目的 `message` 字段只以文本节点渲染，绝不插入 HTML

---

## 19. 测试策略

### 19.1 层次划分

| 测试层 | 工具 | 覆盖范围 |
|--------|------|---------|
| **单元测试** | Vitest | 工具函数、hook 逻辑、Zod schema |
| **组件测试** | React Testing Library | 原子组件渲染、交互行为 |
| **集成测试** | Playwright | 关键用户路径端到端（Index → Story → Dashboard）|

### 19.2 必须覆盖的测试用例

**Hook 测试（Vitest + `@testing-library/react-hooks`）**：
- `useWpLogs`：SSE 断线后触发重连
- `useWpLogs`：日志超过 MAX_LINES 时自动截断
- `useCountUp`：数字从 0 动画到目标值，尊重 `prefers-reduced-motion`

**组件测试（React Testing Library）**：
- `WpStatusCard`：加载中状态 → 渲染骨架屏
- `WpStatusCard`：`status: "error"` 时渲染错误状态色和文案
- `ActivityFeed`：新日志条目出现在列表顶部

**端到端（Playwright）**：
- 首页 KPI 数字滚动动画触发
- Dashboard 页面加载后 WP 卡片出现（mock API）
- 键盘导航可以遍历所有交互元素

### 19.3 测试文件约定

```
src/
├── components/
│   └── dashboard/
│       └── WpStatusCard/
│           ├── index.tsx
│           └── WpStatusCard.test.tsx   # 就近放置
├── lib/
│   └── hooks/
│       ├── useWpLogs.ts
│       └── useWpLogs.test.ts
```

---

## 20. 工程化配置

### 20.1 ESLint

基于 `eslint-config-next`，追加以下规则：

```jsonc
// .eslintrc.json
{
  "extends": ["next/core-web-vitals"],
  "rules": {
    "no-console": ["warn", { "allow": ["error", "warn"] }],
    "react/no-danger": "error",                 // 禁止 dangerouslySetInnerHTML
    "@typescript-eslint/no-explicit-any": "warn",
    "@typescript-eslint/consistent-type-imports": "error"
  }
}
```

### 20.2 Pre-commit Hook（Husky + lint-staged）

```json
// package.json
"lint-staged": {
  "src/**/*.{ts,tsx}": ["eslint --fix", "prettier --write"],
  "src/**/*.css": ["prettier --write"]
}
```

提交前自动修复格式问题，防止风格差异进入 git history。

### 20.3 TypeScript 严格模式

```jsonc
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,   // arr[i] 返回 T | undefined，强制处理边界
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true
  }
}
```

`noUncheckedIndexedAccess` 在处理 API 数组响应时尤其重要，防止 `undefined` 静默传播到渲染层。

### 20.4 CI/CD 流水线建议

```yaml
# .github/workflows/frontend.yml（示意）
jobs:
  quality:
    steps:
      - run: npm ci
      - run: npm run type-check      # tsc --noEmit
      - run: npm run lint
      - run: npm run test            # Vitest unit + component

  build:
    needs: quality
    steps:
      - run: npm run build           # 生产构建，确认无 TS 错误
      - run: ANALYZE=true npm run build  # bundle 大小检查（可选）
```

---

## 21. 性能工程

### 21.1 Core Web Vitals 目标

| 指标 | 目标 | 主要来源 |
|------|------|---------|
| **LCP**（最大内容绘制）| < 2.5s | Hero 图片/文字 |
| **CLS**（累积布局偏移）| < 0.1 | 字体加载、图片占位 |
| **INP**（交互响应）| < 200ms | 动画、SSE 更新 |

### 21.2 CLS 防范清单

```css
/* 1. 图片预留尺寸（next/image 自动处理） */
/* 2. 字体加载：font-display: swap + size-adjust 防止字形切换偏移 */
@font-face {
  font-family: "Inter";
  font-display: swap;
  size-adjust: 100.06%;   /* 与系统字体等宽，切换时不引起偏移 */
}

/* 3. Dashboard 卡片预留高度，不等数据加载完再撑开 */
.wpCard { min-height: 160px; }

/* 4. KPI 数字区域预留宽度 */
.kpiValue { min-width: 4ch; }
```

### 21.3 `will-change` 使用规范

```css
/* 只在动画开始前加，动画结束后移除（避免常驻 GPU 层内存浪费） */
.revealElement.is-entering {
  will-change: transform, opacity;
}
.revealElement.is-visible {
  will-change: auto;   /* 动画完成后恢复 */
}
```

### 21.4 大列表优化（日志流）

`ActivityFeed` 实时日志最多 500 条，DOM 节点过多时（尤其移动端）会导致滚动卡顿：

```tsx
// 使用 react-window 虚拟化列表（仅渲染可视区域内的条目）
import { FixedSizeList } from "react-window"

<FixedSizeList
  height={320}
  itemCount={logs.length}
  itemSize={28}          // 单条日志行高
  width="100%"
>
  {({ index, style }) => (
    <LogEntry style={style} entry={logs[index]} />
  )}
</FixedSizeList>
```

---

## 22. 监控与可观测性

### 22.1 Web Vitals 上报

Next.js 内置 `useReportWebVitals`，在 `app/layout.tsx` 中接入：

```tsx
// app/layout.tsx
export function reportWebVitals(metric: NextWebVitalsMetric) {
  if (process.env.NODE_ENV === "production") {
    // 上报到后端监控端点或第三方服务
    fetch("/api/vitals", {
      method: "POST",
      body: JSON.stringify(metric),
      keepalive: true,
    })
  }
}
```

### 22.2 前端错误监控

推荐接入 **Sentry**（开源可私有部署）：

```typescript
// instrumentation.ts（Next.js 15 instrumentation hook）
import * as Sentry from "@sentry/nextjs"
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0.1,    // 10% 性能追踪
  environment: process.env.NODE_ENV,
})
```

关键配置：
- 过滤已知的 SSE 断线错误（避免告警噪声）
- 为 Dashboard 页面设置较高采样率（核心路径）
- 上报用户操作面包屑（帮助复现 Dashboard 问题）

### 22.3 Dashboard 自身的健康指标

前端 Dashboard 本身也应被监控——如果 SSE 连接成功率 < 90%，说明后端或网络有问题：

```typescript
// 在 useWpLogs 中记录连接事件
const reportSSEHealth = (event: "connect" | "disconnect" | "error") => {
  fetch("/api/metrics/sse", { method: "POST", body: JSON.stringify({ event, wp: streamUrl }) })
}
```
