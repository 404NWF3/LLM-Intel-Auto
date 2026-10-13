# 部署方案：SUFE-SAADS-Qwen 全栈服务器部署

## Context

用户需要在一台 Windows Server 上部署整个项目（前端 Next.js + 后端 FastAPI），使其他电脑通过域名/IP 可访问。目前无域名，先了解整体流程。项目服务：
- **后端 FastAPI**：运行在 `:8000`
- **前端 Next.js**：运行在 `:3000`
- **反向代理 Nginx**：统一对外暴露 `:80`（后续可加 HTTPS 443）
- **数据库**：PostgreSQL 已在阿里云 RDS（不需在服务器部署），Qdrant 可本地嵌入模式运行

---

## 架构图

```
外部浏览器
    │
    ▼ HTTP :80 (域名/IP)
┌─────────────────────────┐
│       Nginx (Windows)   │
│  / → localhost:3000     │  ← Next.js 前端
│  /api/ → localhost:8000 │  ← FastAPI 后端（SSE 需 buffering off）
└─────────────────────────┘
    │                  │
    ▼                  ▼
 Next.js :3000    FastAPI :8000
                      │
                      ▼
              阿里云 PostgreSQL RDS
              Qdrant (本地嵌入模式)
```

---

## 需要修改的代码（1处）

**文件：`backend/api/server.py`（第 44-53 行）**

问题：CORS `allow_origins` 硬编码了 `localhost:3000`，生产环境浏览器发送的 `Origin` 是服务器的 IP/域名，会被拒绝。

修改方案：从环境变量读取 `CORS_ORIGINS`，格式为逗号分隔的字符串。

```python
# 修改前
allow_origins=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
],

# 修改后
import os
_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allow_origins=[o.strip() for o in _raw.split(",") if o.strip()],
```

`.env` 中新增（部署时填入实际 IP/域名）：
```
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://YOUR_SERVER_IP
```

---

## 分步部署流程（Windows Server）

### 第一步：安装运行时依赖

在服务器上安装：

1. **Python 3.11+**：https://python.org/downloads → 安装时勾选"Add to PATH"
2. **Node.js 20 LTS**：https://nodejs.org/en/download → LTS 版本
3. **Git**：https://git-scm.com/download/win
4. **Nginx for Windows**：https://nginx.org/en/docs/windows.html → 下载 nginx/Windows 版解压到 `C:\nginx`

可选（推荐）：
- **NSSM**（Non-Sucking Service Manager）：https://nssm.cc — 将 Python/Node 进程注册为 Windows 服务，开机自启

### 第二步：部署项目代码

```powershell
# 克隆项目（或直接复制文件夹）
git clone <repo-url> C:\saads
cd C:\saads

# 安装 Python 依赖
pip install -r requirements.txt
# 或使用 uv：uv sync

# 安装前端依赖并构建
cd frontend
npm install
npm run build   # 输出到 frontend/.next/
```

### 第三步：配置环境变量

复制 `.env.example` 为 `.env`，填入生产配置：
```
# 现有配置保持不变...

# 新增：允许访问的来源（填服务器 IP 或域名）
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://<服务器IP>
```

### 第四步：配置 Nginx

编辑 `C:\nginx\conf\nginx.conf`：

```nginx
worker_processes 1;

events { worker_connections 1024; }

http {
    include       mime.types;
    default_type  application/octet-stream;

    server {
        listen 80;
        server_name <服务器IP或域名>;   # 填实际值

        # 静态资源缓存
        location /_next/static/ {
            alias C:/saads/frontend/.next/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # FastAPI 后端（SSE 必须关闭缓冲！）
        location /api/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_buffering off;
            proxy_set_header X-Accel-Buffering no;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # Next.js 前端
        location / {
            proxy_pass http://127.0.0.1:3000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
        }
    }
}
```

启动 Nginx：
```powershell
C:\nginx\nginx.exe
# 重载配置：
C:\nginx\nginx.exe -s reload
```

### 第五步：启动服务

**方式 A（临时测试，开命令行窗口）**：
```powershell
# 窗口1：启动后端
cd C:\saads
python serve.py --host 127.0.0.1 --port 8000 --no-reload

# 窗口2：启动前端
cd C:\saads\frontend
npm run start
```

**方式 B（推荐：用 NSSM 注册为 Windows 服务）**：
```powershell
# 安装后端服务
nssm install saads-backend "python" "C:\saads\serve.py --host 127.0.0.1 --port 8000 --no-reload"
nssm set saads-backend AppDirectory "C:\saads"
nssm start saads-backend

# 安装前端服务
nssm install saads-frontend "node_modules\.bin\next" "start"
nssm set saads-frontend AppDirectory "C:\saads\frontend"
nssm start saads-frontend
```

### 第六步：域名配置（有域名后）

1. 在域名注册商的 DNS 管理面板添加：
   - **A 记录**：`@`（或 `www`）→ 服务器公网 IP
   - TTL：300（5分钟，便于调试）
2. 将 nginx.conf 的 `server_name` 改为你的域名
3. 执行 `C:\nginx\nginx.exe -s reload`

### 第七步：HTTPS（可选，有域名后）

推荐用 **win-acme**（Windows 上的 Let's Encrypt 客户端）：
```powershell
# 下载 win-acme: https://www.win-acme.com
# 运行后选择 Nginx，自动申请证书并更新配置
wacs.exe
```

---

## 防火墙设置

确保 Windows 防火墙放行端口 80（HTTP）和 443（HTTPS）：
```powershell
netsh advfirewall firewall add rule name="HTTP" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="HTTPS" dir=in action=allow protocol=TCP localport=443
```

注意：端口 3000 和 8000 **不需要**对外开放，因为它们只被 Nginx 内部访问。

---

## 修改文件清单

| 文件 | 变更内容 |
|------|---------|
| `backend/api/server.py` | CORS origins 改为从 `CORS_ORIGINS` 环境变量读取 |
| `.env` | 新增 `CORS_ORIGINS` 变量（填服务器 IP/域名） |

**不需要修改** `frontend/next.config.ts`：生产环境中 Nginx 会在 Next.js 之前拦截 `/api/*`，Next.js 的 rewrite 规则不会被执行，且其指向 `localhost:8000` 在同机部署时仍然正确。

---

## 验证方法

1. 从另一台电脑浏览器访问 `http://<服务器IP>/`：前端首页正常显示
2. 访问 `http://<服务器IP>/dashboard/wp11`：Dashboard 加载，无跨域报错
3. 访问 `http://<服务器IP>/api/health`：返回 `{"status":"ok"}`
4. 触发一次 WP1-1 运行，观察 LogViewer SSE 日志是否正常流式输出（验证 `proxy_buffering off` 生效）
5. 访问 `http://<服务器IP>/docs`：文档页正常渲染
