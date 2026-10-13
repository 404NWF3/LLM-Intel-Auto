from pathlib import Path
# Reuse the distilled template and verified feature descriptions; do not rebuild source DOCX.
source=Path('.docx-work/build_documents.py').read_text().split('# Core implementation order')[0]
exec(compile(source,'template_builder','exec'))
original=manual[:]
manual=[]
page('本地部署与安装',[
 ('部署准备',[
 '本地部署适合首次使用和单机采集，默认使用 JSON 文件，不需要安装 MongoDB。准备完整项目目录，保留 backend、pyproject.toml、uv.lock 与 .env.example；所有命令均在项目根目录执行。',
 '运行环境为 Python 3.10 至 3.13，建议使用 Python 3.12；需要 uv 包管理工具及可访问软件依赖仓库、公开情报源的网络。智能采集还需能够访问所配置的模型接口。浏览器使用现代 Chrome、Edge 或 Safari。']),
 ('第一步 安装依赖',[
 '在终端进入解压后的 LLM-Intel-Auto 目录。先执行 python --version 和 uv --version 检查工具；macOS 或 Linux 中 Python 命令也可能为 python3。若未安装 uv，可在已有 Python 环境执行 python -m pip install uv，安装后重新打开终端。',
 '执行以下命令，按项目锁文件安装依赖并创建虚拟环境：',
 'uv sync --locked --group dev',
 '该命令包含运行依赖与测试依赖。安装结束且未报错后继续配置；不需要手工激活虚拟环境，后续统一通过 uv run 启动。']),
 ('第二步 创建配置文件',[
 '首次部署将根目录 .env.example 复制为 .env。macOS 或 Linux 执行 cp .env.example .env；Windows PowerShell 执行 Copy-Item .env.example .env。若 .env 已存在，直接编辑现有文件，避免覆盖密钥和存储设置。',
 '先体验规则采集时，可保持模型密钥为空。需要模型自主检索时，按下一章填写供应商和密钥。默认本地配置为 GRADIO_SERVER_NAME=127.0.0.1、GRADIO_SERVER_PORT=8000；默认不配置 INTEL_MONGO_URI。'])])
page('首次启动与部署验证',[
 ('第三步 启动控制台',[
 '在项目根目录执行：',
 'uv run web',
 '保持终端运行，在浏览器打开 http://127.0.0.1:8000/。若已修改 GRADIO_SERVER_PORT，以启动终端实际显示地址为准。打开后应看到 Collect、情报态势、Trace replay、Database 和 Memory 五个页签。',
 '首页还显示采集配置、主模型和快速模型。规则采集可以访问真实公开数据源；SDK 智能采集表示本地模型配置检查通过，实际是否使用模型仍需查看任务追踪。界面不需要注册或登录。']),
 ('第四步 执行首次验证',[
 '进入 Collect，Mode 选 full，Max rounds 填 1，Max API calls 填 4，保留 Verbose 勾选，然后点击 Run collection。等待 Run summary 和 Collected items 更新，记录 run_id。',
 '查看 Agent verbose trace 是否出现工具调用、来源错误或 [fallback]。出现 [fallback] 表示模型会话降级为规则采集；任务完成不等同于所有来源均成功，也不保证本次一定获得新条目。',
 '点击 Load latest run，确认刚完成的记录可以再次加载。再进入 Database，点击 Refresh store status；默认应使用 JSON 存储。也可执行 uv run intel-agent latest 核对最近持久化结果。']),
 ('停止 重启与配置生效',[
 '停止本地服务时，在启动终端按 Ctrl+C；再次执行 uv run web 可重启。修改 .env 后应停止并重新启动服务。尽量等待采集完成后再停止，以便任务正常保存。',
 '端口占用时，将 .env 中 GRADIO_SERVER_PORT 改为其他可用端口，例如 8001，再重启并访问对应地址。服务默认仅允许本机访问；当前界面没有账户认证，不应直接作为公共互联网服务开放。'])])
page('Docker 与 MongoDB 部署',[
 ('完整容器部署',[
 '此方式适合已安装并启动 Docker Engine 或 Docker Desktop、且可使用 docker compose 的环境。先在项目根目录准备 .env 并按需填写模型配置，再执行：',
 'docker compose up -d --build web',
 'Compose 会构建控制台镜像，同时启动并等待 MongoDB 健康检查通过。执行 docker compose ps 检查 web 与 mongo 状态，执行 docker compose logs --tail=100 web 查看启动日志，随后打开 http://127.0.0.1:8000/。',
 'Compose 固定将宿主机 8000 映射到容器 8000，并覆盖容器内监听地址和端口。需要更换外部端口时，编辑 docker-compose.yml 的 web.ports，例如改为 8001:8000；仅修改 .env 中端口不会改变该映射。']),
 ('仅使用容器数据库',[
 '若控制台仍在本地运行，只执行 docker compose up -d mongo，然后在本地 .env 设置 INTEL_MONGO_URI=mongodb://localhost:27018，重新执行 uv run web。数据库名可通过 INTEL_MONGO_DB 指定，默认 intel_agent。',
 '完整容器部署在容器内部使用 mongodb://mongo:27017；本地程序通过宿主机发布端口连接。若修改 INTEL_MONGO_HOST_PORT，本地连接地址也应同步修改。切换存储后看到的是所选存储中的记录，已有 JSON 数据不会自动迁移到 MongoDB。']),
 ('运行维护与数据位置',[
 '修改容器使用的 .env 后，执行 docker compose up -d --force-recreate web 重新创建服务。停止容器可执行 docker compose stop；重新启动执行 docker compose up -d web。',
 '批量采集可执行 docker compose run --rm --build intel-agent full --max-rounds 1 --max-api-calls 4 --verbose。运行记录存入 MongoDB；技巧库、缓存及追踪通过 ./data 挂载保留。MongoDB 数据使用 mongo_data 命名卷，备份时需单独备份数据库，不要使用带 -v 的删除命令清除数据卷。'])])
deployment=manual[:]
manual=[original[0]]+deployment+original[2:]
# Correct exact live UI labels from app.py.
for rows in manual:
 for p in rows:
  for t in p.findall('.//w:t',NS):
   if t.text:t.text=t.text.replace('点击 Load cache 查看缓存摘要','点击 Load relevance cache 查看缓存摘要')
# Give users a copyable minimal model configuration as its own short page.
manual_before=manual[:];manual=[]
page('智能采集配置示例',[
 ('使用 DeepSeek 采集',[
 '在根目录 .env 中填写以下配置；密钥值替换为自己的实际密钥，其他行可直接按示例填写。模型名称采用当前项目代码默认值，若所用接口不再支持该名称，应填写该接口实际可用的模型标识。',
 'INTEL_SDK_PROVIDER=deepseek',
 'DEEPSEEK_API_KEY=在此填写自己的密钥',
 'INTEL_SDK_MODEL=deepseek-flash',
 'INTEL_SDK_FAST_MODEL=deepseek-flash',
 'GRADIO_SERVER_NAME=127.0.0.1',
 'GRADIO_SERVER_PORT=8000',
 '主模型负责采集会话；快速模型用于代码中选择快速模型的辅助决策。它们分别由 INTEL_SDK_MODEL 和 INTEL_SDK_FAST_MODEL 指定，也可以设置为同一模型。']),
 ('确认配置已生效',[
 '保存 .env 后按部署方式重启服务，再检查首页显示的供应商相关状态及两个模型名称。运行一次小预算采集，查看 Agent verbose trace；只有实际调用过程才能确认远程接口是否成功。',
 '若首页仍显示旧配置，检查启动进程的环境变量是否覆盖 .env，并确认终端位于本项目根目录。若配置了 ANTHROPIC_BASE_URL 和 ANTHROPIC_AUTH_TOKEN，它们会覆盖供应商端点与密钥；直接使用供应商接口时应清除无意保留的自定义覆盖。']),
 ('规则采集与可选增强',[
 '模型密钥为空时，可用规则方式体验数据源采集。只配置 DeepSeek 即可启用模型采集，不必同时填写 GLM；GLM_API_KEY 对应的语义过滤与 embedding 属于可选增强。',
 '密钥只写入配置文件，不写进采集主题或导出材料。NVD_API_KEY 为可选数据源配置；不填写时仍可请求数据，但可能受到更严格的限流。'])])
config_example=manual[0];manual=manual_before[:4]+[config_example]+manual_before[4:]
print(build('manual',manual));print('Manual body pages:',len(manual))
