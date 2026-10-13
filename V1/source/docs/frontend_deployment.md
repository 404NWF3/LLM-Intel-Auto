# SUFE-SAADS 前端部署文档

> 最后更新：2026-03-19
> 框架版本：Next.js 16.1.7 / React 19.2.3 / Node.js ≥ 20

---

## 1. 技术栈一览

### 运行时依赖

| 包名 | 版本 | 用途 | 引入阶段 |
|------|------|------|----------|
| `next` | 16.1.7 | App Router SSR/SSG 框架 | Phase 1 |
| `react` / `react-dom` | 19.2.3 | UI 运行时 | Phase 1 |
| `zod` | ^3.25.76 | API 响应 schema 验证 | Phase 1 |
| `swr` | ^2.4.1 | 数据获取 + 轮询（Dashboard hooks） | Phase 3 |
| `lucide-react` | ^0.511.0 | SVG 图标 | Phase 1 |
| `react-window` | ^2.2.7 | 虚拟列表（LogViewer 日志流） | Phase 3 |
| `@types/react-window` | ^1.8.8 | react-window TypeScript 类型 | Phase 3 |
| `unified` | ^11.0.5 | Markdown 处理管道（纯 ESM） | **Phase 4** |
| `remark-parse` | ^11.0.0 | Markdown → mdast | **Phase 4** |
| `remark-gfm` | ^4.0.1 | GFM 扩展（表格、删除线等） | **Phase 4** |
| `remark-rehype` | ^11.1.2 | mdast → hast | **Phase 4** |
| `rehype-slug` | ^6.0.0 | 为标题添加 `id` 属性 | **Phase 4** |
| `rehype-highlight` | ^7.0.2 | 代码块语法高亮（highlight.js） | **Phase 4** |
| `rehype-sanitize` | ^6.0.0 | HTML 净化（防 XSS） | **Phase 4** |
| `rehype-stringify` | ^10.0.1 | hast → HTML 字符串 | **Phase 4** |

### 开发依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| `typescript` | ^5 | 类型检查 |
| `eslint` / `eslint-config-next` | ^9 / 16.1.7 | 代码规范 |
| `prettier` | ^3.8.1 | 代码格式化 |
| `vitest` | ^3.2.4 | 单元测试 |
| `@testing-library/react` | ^16.3.2 | 组件测试 |
| `@vitejs/plugin-react` | ^4.7.0 | Vitest React 插件 |
| `@next/bundle-analyzer` | ^16.1.7 | 包体积分析 |

---

## 2. 路由结构

```
/                          ○ Static  首页（技术展示）
/story                     ○ Static  项目故事页
/docs                      ○ Static  文档清单（11 篇，3 分类）
/docs/[slug]               ● SSG     文档详情（每篇静态预构建）
  /docs/wp11-architecture
  /docs/wp11-langgraph-state
  /docs/wp11-agentic-patterns
  /docs/wp11-tool-skill-partition
  /docs/wp11-development-plan
  /docs/wp11-phase0-preparation
  /docs/wp11-phase-review
  /docs/wp11-phase4-review
  /docs/db-module-design
  /docs/db-module-usage
  /docs/frontend-design
/dashboard                 ○ Static  运维总览（4 个 WP 状态卡）
/dashboard/[wp]            ● SSG     WP 详情页
  /dashboard/wp11          带调试面板（DebugControlPanel）
  /dashboard/wp12~wp14     标准详情页
```

`○ Static` = 完全静态，无数据依赖
`● SSG` = `generateStaticParams` 预构建，构建时确定所有路径

---

## 3. 目录结构

```
frontend/
├── src/
│   ├── app/
│   │   ├── (marketing)/          ← SiteHeader + SiteFooter 布局组
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx          ← 首页
│   │   │   ├── story/
│   │   │   └── docs/
│   │   │       ├── page.tsx      ← 文档清单
│   │   │       └── [slug]/
│   │   │           └── page.tsx  ← 文档详情（SSG）
│   │   ├── dashboard/            ← 独立 Layout（无 Header/Footer）
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── [wp]/page.tsx
│   │   ├── layout.tsx            ← 根 Layout（html/body）
│   │   └── globals.css
│   ├── components/
│   │   ├── docs/
│   │   │   ├── DocCard/          ← 文档卡片（含文件映射）
│   │   │   ├── DocRenderer/      ← 净化 HTML 渲染（prose 排版）
│   │   │   └── DocToc/           ← 目录侧边栏（IntersectionObserver）
│   │   ├── dashboard/            ← 运维面板组件
│   │   ├── layout/               ← SiteHeader / SiteFooter
│   │   └── ui/                   ← 基础 UI 原语
│   ├── lib/
│   │   ├── docs/
│   │   │   ├── registry.ts       ← 文档元数据 + 文件映射注册表
│   │   │   └── processor.ts      ← unified 管道（含 rehype-sanitize）
│   │   ├── hooks/                ← SWR hooks（Dashboard）
│   │   ├── types/                ← Zod schema
│   │   ├── api/                  ← fetch client + mock 数据
│   │   └── wp-registry.ts        ← WP 元数据注册表
│   └── styles/
│       ├── base.css              ← 设计 token
│       ├── tokens.css            ← 扩展 token（状态色）
│       └── animations.css
├── package.json
├── next.config.ts
└── tsconfig.json
```

---

## 4. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEXT_PUBLIC_USE_MOCK_API` | `false` | 设为 `true` 时 Dashboard 全程使用 mock 数据，不发网络请求 |
| `NEXT_PUBLIC_API_BASE` | — | （预留）生产环境后端 API 根路径，如 `https://api.sufe-saads.internal` |

---

## 5. 本地开发

```bash
# 安装依赖
cd frontend
npm install

# 启动开发服务器（Mock 模式，无需后端）
NEXT_PUBLIC_USE_MOCK_API=true npm run dev
# → http://localhost:3000

# 连接真实后端
NEXT_PUBLIC_USE_MOCK_API=false npm run dev
# 需要后端运行在 http://localhost:8000
```

**脚本说明：**

```bash
npm run type-check   # tsc --noEmit，零错误为通过标准
npm run lint         # eslint
npm run format       # prettier
npm run test         # vitest run（单次）
npm run test:watch   # vitest 监听模式
ANALYZE=true npm run build  # 打包体积分析
```

---

## 6. 生产构建与部署

### 构建

```bash
npm run build
# 输出：.next/ 目录
# 全部页面静态/SSG，无动态运行时数据依赖
```

### 部署方式 A：Node.js 服务器（推荐）

```bash
npm run build
npm run start
# 默认监听 :3000
```

### 部署方式 B：Nginx + Node.js（生产）

```nginx
server {
    listen 80;
    server_name saads.example.com;

    # 静态资源
    location /_next/static/ {
        alias /var/www/saads/frontend/.next/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Next.js 服务
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # SSE 日志流（Dashboard LogViewer）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_buffering off;                    # ← SSE 必须关闭缓冲
        proxy_set_header X-Accel-Buffering no;  # ← 通知 Nginx 层不缓冲
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

> **注意**：`/api/*` 反向代理至后端 FastAPI（`:8000`）。CORS 在同源代理下自动解决，无需后端额外配置。
> 开发阶段前端 `:3000` 与后端 `:8000` 跨域时，后端需设置：
> ```python
> allow_origins=["http://localhost:3000"]
> ```

### 部署方式 C：静态导出（仅文档/营销页，不含 Dashboard）

```bash
# next.config.ts 添加：output: 'export'
# 仅在 Dashboard 不需要时使用，因为 Dashboard 依赖 SWR 客户端请求
npm run build
# 输出：out/ 目录，可直接上传 CDN/对象存储
```

---

## 7. 文档页（Phase 4）说明

文档数据来源是 `docs/` 目录下的 Markdown 文件（相对项目根，非 `frontend/`）。

- 构建时 `process.cwd()` = `frontend/`，文件读取路径为 `path.join(process.cwd(), '..', 'docs', filename)`
- 所有文档在构建时静态化，**无运行时文件读取**
- Markdown 处理管道：`remark-parse` → `remark-gfm` → `remark-rehype` → `rehype-slug` → `rehype-highlight` → **`rehype-sanitize`** → `rehype-stringify`
- `rehype-sanitize` 使用 `defaultSchema` 扩展版本，额外允许：
  - 所有元素的 `id` 属性（defaultSchema `"*"` 已全局允许）
  - `<code>` / `<pre>` 的 `language-*` 和 `hljs*` className（语法高亮）
  - `<span>` 的 `hljs*` className（内联 token 着色）

---

## 8. 安全配置

`next.config.ts` 已配置以下安全响应头（全路由）：

| 响应头 | 值 | 用途 |
|--------|----|------|
| `X-Frame-Options` | `DENY` | 禁止 iframe 嵌入 |
| `X-Content-Type-Options` | `nosniff` | 禁止 MIME 嗅探 |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | 限制 Referrer 泄漏 |
| `Content-Security-Policy` | 见下 | 限制资源加载来源 |

CSP 策略：
```
default-src 'self'
script-src 'self' 'unsafe-eval' 'unsafe-inline'
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com
font-src 'self' https://fonts.gstatic.com
img-src 'self' data: blob:
connect-src 'self' ws:
frame-ancestors 'none'
```

> 生产部署建议将 `script-src 'unsafe-eval'` 替换为 nonce 方案。

---

## 9. Dashboard 后端联调前提（Phase 4 待完成）

以下后端端点尚未实现，Dashboard 当前通过 `NEXT_PUBLIC_USE_MOCK_API=true` 绕过：

| 端点 | 方法 | 用途 | 优先级 |
|------|------|------|--------|
| `/api/wp11/status` | GET | WP1-1 状态 + 指标 | P0 |
| `/api/wp11/logs/stream` | GET (SSE) | 实时日志流 | P0 |
| `/api/wp11/alerts` | GET | WP1-1 告警 | P1 |
| `/api/wp11/metrics` | GET | 历史指标时序 | P1 |
| `/api/wp11/runs` | POST / DELETE | 启动/取消运行 | P1 |
| `/api/wp11/runs/active` | GET | 活跃运行状态 | P1 |
| `/api/wp11/nodes` | GET | 21 个图节点信息 | P2 |
| `/api/wp11/nodes/{name}/run` | POST | 触发单节点 | P2 |
| `/api/wp11/state/latest` | GET | GraphState 快照 | P2 |
| `/api/alerts` | GET | 全局告警 | P2 |
| `/api/wp12~wp14/status` | GET | WP1-2~4 状态 stub | P3 |

告警 severity 规范：后端必须输出大写 `HIGH` / `MEDIUM` / `LOW`（`critical` 映射为 `HIGH`）。

---

## 10. 验收标准

### Phase 4：文档页

- [ ] `/docs` 渲染 11 张文档卡，按 3 分类分组
- [ ] 每张卡片展示：标题、描述、类别 badge、文件映射 chips、标签
- [ ] 点击卡片跳转至 `/docs/[slug]`
- [ ] `/docs/[slug]` 正确渲染 Markdown：标题层级、列表、代码块、表格、粗体/斜体、引用
- [ ] 代码块有语法高亮（深色背景 + token 着色）
- [ ] H2/H3 有 `id` 属性（rehype-slug）
- [ ] TOC 侧边栏列出 H2/H3，点击滚动至对应位置（`scroll-margin-top: 5rem`）
- [ ] 滚动时 TOC 高亮当前可见标题（IntersectionObserver）
- [ ] 桌面端 TOC 右侧 sticky；≤900px 时 TOC 移至文章上方
- [ ] `/docs/不存在的slug` 返回 404
- [ ] `<script>`、`on*` 属性、`javascript:` href 被 rehype-sanitize 剥除
- [ ] `npm run type-check` 零错误
- [ ] `npm run build` 通过，22 个页面全部静态生成

### 通用

- [ ] 所有交互元素有 `:focus-visible` 轮廓
- [ ] `prefers-reduced-motion` 时过渡动画禁用
- [ ] `NEXT_PUBLIC_USE_MOCK_API=true` 时 Dashboard 全程无网络请求
