# 多源网络检索 Agent

一个通过多源并行爬取，提供比单一网页搜索更全面、更真实信息收集能力的检索 Agent。

用户提问后，Agent 自动完成：**查询理解与拆解 → 数据源路由 → 多源并行采集 → 归并去重 → 带引用的答案生成**。

---

## 目录结构

```
agent项目网络检索/
├── backend/                     # Python 后端（LangChain + LangGraph + FastAPI）
│   ├── app/
│   │   ├── adapters/            # 各数据源爬虫适配器（可插拔）
│   │   │   ├── base.py          # SourceAdapter 抽象基类 + mock 降级
│   │   │   ├── registry.py      # 适配器注册表
│   │   │   ├── bing_cn.py       # Bing 中国版（官方 API / HTML 双路线）
│   │   │   ├── google_search.py # Google（Serper / SerpAPI 中转，规避验证码）
│   │   │   ├── github.py        # GitHub 仓库 / 代码 / Issue
│   │   │   ├── nexus.py         # Nexus 学术文献（默认 Crossref 端点）
│   │   │   ├── arxiv.py         # arXiv 预印本
│   │   │   ├── mediacrawler.py  # 微博/小红书/抖音/B站/知乎（MediaCrawler 桥接）
│   │   │   └── web_fetch.py     # 通用网页正文抽取
│   │   ├── graph/               # LangGraph 检索工作流
│   │   │   ├── state.py         # AgentState 定义
│   │   │   ├── nodes.py         # 5 个节点实现
│   │   │   ├── workflow.py      # 图装配
│   │   │   ├── agent.py         # 执行入口 + SSE 事件流
│   │   │   ├── llm.py           # DeepSeek 封装
│   │   │   └── rerank.py        # 去重 + BM25 相关性与多样性排序
│   │   ├── core/                # 配置、模型、HTTP 工具、日志
│   │   └── main.py              # FastAPI 应用
│   ├── tests/                   # 数据源自检 + 端到端测试
│   ├── scripts/apply_cookies.py # Cookie 配置助手（交互 / 批量导入 / 状态查询）
│   ├── cookies.txt.example      # Cookie 填写模板（真实 cookies.txt 已 gitignore）
│   ├── requirements.txt
│   └── .env.example
└── frontend/                    # React 19 + Vite + Tailwind v4
```

---

## 一、架构设计

### 工作流（LangGraph）

```
START
  │
  ▼
understand ──(need_search=false)──┐
  查询理解/拆解                     │
  │                                │
  ▼                                │
plan                               │
  路由选源                          │
  │                                │
  ▼                                │
fan_out                            │
  └─ 并行调度所有选中源 ────────────┤
  │                                │
  ▼                                │
aggregate                          │
  去重 + BM25 排序 + 多样性控制      │
  │                                │
  ▼                                ▼
synthesize（DeepSeek 生成带引用的答案）
  │
  ▼
 END
```

**为什么用 LangGraph 而不是普通链式编排**：检索任务需要在「理解」后做**条件分支**（是否需要联网）、在调度阶段做 **fan-out/fan-in 并行**、并把中间过程实时推给前端。LangGraph 的状态图 + `Annotated` reducer 天然支持这种并行写回与条件路由，比用 if/else 串起来的链更清晰、也更容易扩展节点。

### 大模型：DeepSeek

- 通过 `langchain-openai` 的 OpenAI 兼容接口接入，支持 `deepseek-chat` 与 `deepseek-reasoner`。
- 分三处使用：**查询拆解**（temperature=0，输出 JSON）、**路由规划**（temperature=0）、**答案合成**（temperature=0.3）。
- 所有 LLM 调用都有**确定性回退**：LLM 不可用时，查询拆解退化为原问题、路由退化为启发式规则、答案退化为抽取式摘要 —— **保证 Agent 永远有可交付产出**，不会因为模型故障而整体失败。

---

## 二、数据源矩阵

| 源 | 平台 | 类别 | 凭证 | 状态 |
|---|---|---|---|---|
| `bing_cn` | Bing 中国版 | 国内通用 | 可选（官方 API） | ✅ 开箱可用（HTML 路线） |
| `google_web` | Google | 国外通用 | 需 Serper/SerpAPI | ✅ 已接入（Serper） |
| `github` | GitHub | 开源代码 | 可选（提高配额） | ✅ 已接入 |
| `nexus` | Nexus / Crossref | 学术文献 | 可选 | ✅ 开箱可用 |
| `arxiv` | arXiv | 学术预印本 | 无 | ✅ 开箱可用 |
| `web_fetch` | 网页正文 | 网页 | 无 | ✅ 开箱可用 |
| `xiaoheihe` | 小黑盒 | 国内社媒 | 扫码登录一次 | ✅ 内置签名算法（browser 模式） |
| `boss_zhipin` | BOSS直聘 | 招聘信息 | 扫码登录一次 | ✅ 内部 API + 明文薪资（browser 模式） |
| `mediacrawler_xhs` | 小红书 | 国内社媒 | 需部署 + Cookie | ⚠️ 需 Cookie |
| `mediacrawler_dy` | 抖音 | 国内社媒 | 需部署 + Cookie | ⚠️ 需 Cookie |
| `mediacrawler_ks` | 快手 | 国内社媒 | 需部署 + Cookie | ⚠️ 需 Cookie |
| `mediacrawler_bili` | B站 | 国内社媒 | 需部署 + Cookie | ⚠️ 需 Cookie |
| `mediacrawler_wb` | 微博 | 国内社媒 | 需部署 + Cookie | ⚠️ 需 Cookie |
| `mediacrawler_tieba` | 贴吧 | 国内社媒 | 需部署 + Cookie | ⚠️ 需 Cookie |
| `mediacrawler_zhihu` | 知乎 | 国内社媒 | 需部署 + Cookie | ⚠️ 需 Cookie |

> 平台代码沿用 MediaCrawler 的 `PlatformEnum`：`xhs` / `dy` / `ks` / `bili` / `wb` / `tieba` / `zhihu`。
> 配置里写英文全称（`weibo`、`bilibili` 等）也会被自动归一化。

> **降级机制**：未配置凭证的源不会让流程失败。默认 `ENABLE_MOCK_FALLBACK=true` 时会返回带 `mock: true` 标记的占位结果，前端明确标注「部分降级」。设为 `false` 则该源直接跳过。

---

## 三、快速开始

### 1. 后端

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# 配置环境变量
cp .env.example .env      # Windows: copy .env.example .env
# 编辑 .env，至少确认 DEEPSEEK_API_KEY 已填写
```

启动服务：

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问 http://127.0.0.1:8000/docs 可看到自动生成的 API 文档。

### 2. 前端

```bash
cd frontend
npm install

cp .env.example .env      # 可选，默认已指向 127.0.0.1:8000
npm run dev
```

打开 http://localhost:3000

---

## 四、接口约定

前端 `src/api/client.ts` 与后端 `app/main.py` 已对齐：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 + 模型与源状态 |
| GET | `/api/sources` | 所有数据源可用性（前端数据源面板） |
| POST | `/api/chat` | 非流式检索（脚本测试用） |
| POST | `/api/chat/stream` | **SSE 流式检索**（前端主用） |

### SSE 事件格式

```
data: {"type":"start","task":"用户问题"}

data: {"type":"tool","name":"查询拆解","ok":true,"result":"意图=compare，生成 4 条子查询","arguments":{...}}

data: {"type":"tool","name":"bing_cn","ok":true,"result":"命中 8 条（2069ms）","arguments":{"platform":"Bing (中国版)"}}

data: {"type":"final","content":"答案正文…","citations":[...],"stats":{...},"sub_queries":[...],"plan":[...],"degraded":false,"notes":[]}

data: [DONE]
```

---

## 五、各数据源接入指引

### 5.1 Bing 中国版

**当前默认走 HTML 抓取**（`cn.bing.com`），已内置 1.2s 进程内限速。若出现验证页，程序会抛出明确错误并提示配置官方 API。

**申请官方 API（推荐用于生产）**：
1. 访问 https://portal.azure.com ，注册/登录 Azure 账号
2. 搜索「Bing Search v7」→ 创建资源（选 F1 免费层，1000 次/月）
3. 在资源的「密钥和终结点」页面复制 Key
4. 写入 `.env`：`BING_SEARCH_API_KEY=<你的key>`

配置后适配器会**自动优先使用官方 API**，失败时才回退 HTML。

### 5.2 Google 搜索（人机验证问题的解法）

**直接抓取 google.com 会立即触发 reCAPTCHA**，且随频率与 IP 归属迅速恶化，无法稳定工程化。因此本项目的方案是**走搜索 API 中转**，由服务商承担 IP 池与验证码绕过：

**方案 A：Serper（推荐，便宜快速）**
1. 访问 https://serper.dev 注册
2. 控制台获取 API Key（免费 2500 次）
3. `.env` 写入：
   ```
   SERPER_API_KEY=<你的key>
   GOOGLE_SEARCH_PROVIDER=serper
   ```

**方案 B：SerpAPI（老牌，稳定性好）**
1. 访问 https://serpapi.com 注册
2. 获取 API Key（免费 100 次/月）
3. `.env` 写入：
   ```
   SERPAPI_API_KEY=<你的key>
   GOOGLE_SEARCH_PROVIDER=serpapi
   ```

> 若你有自建代理池 + 打码服务，可自行实现一个 `SourceAdapter` 子类并在 `registry.py` 注册，接口完全一致。

### 5.3 GitHub

**匿名即可用**，但配额低（search 10 次/分钟）。

**申请 Token（推荐）**：
1. 访问 https://github.com/settings/tokens
2. 「Generate new token (classic)」→ 勾选 `public_repo`（只读足够）
3. `.env` 写入：`GITHUB_TOKEN=<你的token>`

### 5.4 Nexus（学术文献）

默认对接 **Crossref 公共 API**（无需 Key）：
- 建议填写 `NEXUS_MAILTO` 进入 polite pool，速率与稳定性更好：
  ```
  NEXUS_MAILTO=your_email@example.com
  ```

**若你采购了商业版 / 自建 Nexus 端点**：只需改 `.env` 中的 `NEXUS_API_URL` 与 `NEXUS_API_KEY`，适配器会自动带上 Bearer 认证，并兼容 `items` / `results` / `data` / `hits` 等多种响应结构，**无需改代码**。

### 5.5 MediaCrawler（国内社媒）

MediaCrawler 是独立项目，不是 pip 库。本项目通过**子进程调用 + 结果文件解析**桥接，另提供 remote 模式对接服务化封装。

支持 7 个平台：小红书 `xhs`、抖音 `dy`、快手 `ks`、B站 `bili`、微博 `wb`、贴吧 `tieba`、知乎 `zhihu`。

**部署步骤**（本项目已部署到 `D:/MediaCrawler`）：

```bash
# 1. 克隆项目
git clone --depth 1 https://github.com/NanmiCoder/MediaCrawler.git D:/MediaCrawler
cd D:/MediaCrawler

# 2. 安装依赖（该项目使用 uv；若清华源 TLS 报错，强制走官方源）
UV_DEFAULT_INDEX=https://pypi.org/simple uv sync --index-strategy first-index

# 3. 安装浏览器驱动
.venv/Scripts/python.exe -m playwright install chromium

# 4. 首次登录，生成 Cookie（每个平台执行一次）
.venv/Scripts/python.exe main.py --platform xhs --lt qrcode --type search
# 扫码登录后 Ctrl+C 退出，登录态会保存到 browser_data/
```

**.env 配置**：
```
MEDIACRAWLER_ENABLED=true
MEDIACRAWLER_MODE=local
MEDIACRAWLER_HOME=D:/MediaCrawler
MEDIACRAWLER_PYTHON=D:/MediaCrawler/.venv/Scripts/python.exe
MEDIACRAWLER_PLATFORMS=xhs,dy,ks,bili,wb,tieba,zhihu
MEDIACRAWLER_TIMEOUT=200
```

**Cookie 配置**（三种方式任选）：

方式一 —— **批量导入（推荐，Cookie 过期后重刷也用它）**：
```bash
cd backend
cp cookies.txt.example cookies.txt   # 首次：从模板创建
# 编辑 cookies.txt，按平台填入 Cookie
.venv/Scripts/python.exe scripts/apply_cookies.py --from-file cookies.txt
```
`cookies.txt` 格式宽松，键可用平台代码或中文名，分隔符 `=` 或 `:` 均可：
```
zhihu=SESSDATA=xxx; _zap=yyy
bili: buvid3=aaa; SESSDATA=bbb
小红书=web_session=ccc
```
重复运行会**原地覆盖**同名变量，不会产生重复行。

方式二 —— **交互式逐个粘贴**：
```bash
cd backend && .venv/Scripts/python.exe scripts/apply_cookies.py
```

方式三 —— **直接编辑 `.env`**：
```
# 统一变量，多平台用分号分隔
MEDIACRAWLER_COOKIES=xhs=<cookie>;wb=<cookie>;bili=<cookie>
# 或独立变量
MEDIACRAWLER_COOKIE_XHS=<cookie>
```

随时查看各平台配置状态：
```bash
.venv/Scripts/python.exe scripts/apply_cookies.py --status
```

> ⚠️ `cookies.txt` 与 `.env` 均含登录凭证，已在 `.gitignore` 中排除（模板 `cookies.txt.example` 例外），切勿提交。

> **CLI 参数已对齐 MediaCrawler v0.1.0**：平台代码取 `PlatformEnum` 值（`wb` 而非 `weibo`），
> 关键词统一用 `--keywords`（多词逗号分隔），Cookie 用 `--cookies`，输出为
> `data/{platform}/json/search_contents_{date}.json`。适配器会比对执行前后的文件时间戳，
> 只读取本次新写入的结果。若你换用别的版本，只需调整 `mediacrawler.py` 的 `_build_argv()`。

**remote 模式**（若你自己把 MediaCrawler 封装成了 HTTP 服务）：
```
MEDIACRAWLER_MODE=remote
MEDIACRAWLER_SERVICE_URL=http://127.0.0.1:9000
```

### 5.6 小黑盒（xiaoheihe.cn）

小黑盒接口 `api.xiaoheihe.cn` 有**双重门槛**，本适配器已全部解决：

1. **签名参数**：必须携带 `hkey` / `_time` / `nonce`。
   本仓库在 `backend/app/core/xhh_signing.py` 中完整实现了该算法
   （混淆 MD5 + GF(2⁸) 列混合 + 自定义字符表映射），
   并已与网页端参考实现做固定输入比对，**输出逐位一致**。
2. **登录态**：服务端对匿名请求返回「非法请求」，需有效会话 Cookie。

**两种模式**（`XIAOHEIHE_MODE`）：

| 模式 | 原理 | 是否需要手工配 Cookie |
|---|---|---|
| `browser`（默认） | Playwright 打开小黑盒页面，在页面上下文内 `fetch()` 接口，自动携带 Cookie 与真实浏览器环境 | 否，扫码登录一次即可 |
| `api` | httpx 直连 + 内置签名 | 是，需粘贴网页版 Cookie |

```bash
# 首次运行 browser 模式：把 HEADLESS 设为 false 以便扫码
XIAOHEIHE_MODE=browser
XIAOHEIHE_HEADLESS=false      # 登录成功后改回 true
XIAOHEIHE_USER_DATA_DIR=D:/agent项目网络检索/backend/.cache/xiaoheihe-profile
```

登录态持久化在上述 profile 目录，后续无需重复登录。

期望服务端提供 `POST /search`，接收 `{platform, keyword, limit}`，返回 `{"items": [...]}`。

### 5.7 BOSS直聘（zhipin.com）

BOSS直聘的职位检索走内部 API：

```
GET https://www.zhipin.com/wapi/zpgeek/search/joblist.json
```

**为什么不去解析页面 DOM？** 该站对薪资数字做了**字体反爬**——前端用每次访问都不同的
自定义 woff 字体渲染，抓 DOM 或解析字体文件都极其脆弱。但接口返回的 `salaryDesc`
字段本身**就是明文**（如 `30-60K·15薪`），字体混淆只存在于前端渲染层。
因此正确做法是直接调接口，绕开整个字体问题。

**门槛与解法**：接口有 Cookie 校验 + `__zp_stoken__` 风控参数，必须**在已登录的
浏览器页面上下文里**发起请求才通得过。这与小黑盒同构，因此复用同一套「浏览器桥接」方案。

**两种模式**（`BOSS_MODE`）：

| 模式 | 原理 | 是否需要手工配 Cookie |
|---|---|---|
| `browser`（默认） | Playwright 打开职位搜索页，在页面内 `fetch()` 接口，自动携带 Cookie / stoken / 真实 UA 与 TLS 指纹 | 否，扫码登录一次即可 |
| `api` | httpx 直连，需粘贴含 `__zp_stoken__` 的完整 Cookie | 是 |

**查询解析**：适配器会自动从问题里识别城市并剔除招聘噪声词，例如

| 输入 | 关键词 | 城市代码 |
|---|---|---|
| `上海 AI Agent 工程师 招聘` | `AI Agent 工程师` | `101020100` |
| `北京 Python 后端招聘` | `Python 后端` | `101010100` |
| `Java 开发` | `Java 开发` | 空（全国） |

内置 27 个常用城市代码（北京/上海/广州/深圳/杭州/成都/武汉/南京/西安/苏州/长沙/
郑州/重庆/天津/青岛/合肥/厦门/福州/济南/大连/沈阳/宁波/东莞/佛山/无锡/香港…）。
也可用 `BOSS_CITY` 强制指定城市。

```bash
BOSS_MODE=browser
BOSS_HEADLESS=false           # 首次扫码登录后改回 true
BOSS_CITY=                    # 留空则由查询自动推断
BOSS_TIMEOUT=60
BOSS_USER_DATA_DIR=D:/agent项目网络检索/backend/.cache/boss-profile
```

**产出字段**：岗位名、公司、**明文薪资**、城市/区域/商圈、经验与学历要求、
技能标签、职位标签、福利、行业、公司规模、融资阶段、招聘者，以及可点击的职位详情链接。
所有字段同时保留在 `Doc.extras` 中（`kind: "job"`），便于前端结构化展示。

> 若未取到职位（未登录 / 风控 / 网络不可达），适配器**不会静默失败**，而是返回一条
> 带降级说明的可点击搜索入口（`kind: "search_entry"`），由模型在答案中如实标注证据缺口。

---

## 六、测试

### 数据源连通性自检

```bash
cd backend
python -m tests.test_sources              # 检查全部源
python -m tests.test_sources bing_cn github   # 检查指定源
```

输出示例：
```
bing_cn                 Bing (中国版)      OK 3 条（2251ms）示例：如何评价字节发布的豆包Seed 2.1 Pro
github                  GitHub          OK 3 条（679ms）示例：AgentTeam-TaichuAI/ScienceClaw
mediacrawler_zhihu      知乎              MOCK 2 条（1ms）
```

`MOCK` 表示该源缺少凭证，已在 `.env` 补齐后即可返回真实数据。

### Agent 端到端测试

```bash
python -m tests.test_e2e tech     # 技术对比类问题
python -m tests.test_e2e code     # 开源代码类问题
python -m tests.test_e2e cn       # 中文社媒类问题
```

### 实测结果（本机验证）

| 用例 | 调度源数 | 采集 | 去重后 | 耗时 | 结果 |
|---|---|---|---|---|---|
| LangGraph vs AutoGen 架构区别 | 5 | 32 | 32 | 11.3s | ✅ |
| 开源 MediaCrawler 替代方案 | 5 | 22 | 22 | 12.5s | ✅ |
| MCP 协议架构原理 | 5 | 33 | 33 | 17.4s | ✅ |

---

## 七、技术栈说明与替代建议

**当前栈**：LangChain + LangGraph + DeepSeek + FastAPI + React 19

这一套在**可观测性、条件路由、并行 fan-out** 上表现良好，实测端到端 11-17 秒返回带引用答案，我建议保留。如果后续遇到瓶颈，可按以下方向替换：

| 场景 | 替代方案 | 理由 |
|---|---|---|
| 图编排过重、想更轻量 | 直接用 `asyncio.gather` + 状态机 | 本项目 `fan_out` 节点本质就是 `gather`，若不需要 checkpointer/人工介入，可省掉 LangGraph 依赖 |
| 需要更复杂的多 Agent 协作（如规划者-执行者-审查者分离） | AutoGen / CrewAI | 原生支持多角色对话式协作 |
| 需要断点续跑、人工审批 | LangGraph + `SqliteSaver` checkpointer | 当前已支持，只需在 `workflow.py` 的 `compile()` 传入 checkpointer |
| 检索质量要求更高 | 在 `aggregate` 后加 Cross-Encoder 重排（如 `bge-reranker`） | 当前用 BM25 近似，语义重排精度更高但更慢 |
| 需要向量召回 | 引入 Milvus / pgvector，对 `doc.content` 建索引 | 适合大规模语料与增量更新 |

**关于爬虫的边界**：社媒平台的稳定采集依赖账号与代理资源，这是**运营成本问题而非技术问题**。本项目已把每个源做成独立适配器，任何一个源失效都不会影响整体 —— 这也是为什么要做降级机制。

---

## 八、常见问题

**Q: 前端显示「调用后端失败」？**
A: 确认后端已启动且端口为 8000；检查 `frontend/.env` 的 `VITE_API_BASE`。

**Q: 检索结果里出现「模拟数据」标记？**
A: 对应源缺少凭证。查看前端右上角「数据源状态」面板，会列出每个源的具体缺失原因。

**Q: Bing 返回人机验证错误？**
A: 已触发 cn.bing.com 限速。降低检索频率，或按 5.1 申请官方 API。

**Q: MediaCrawler 报参数错误？**
A: 你使用的 MediaCrawler 版本 CLI 参数与默认不同，修改 `app/adapters/mediacrawler.py` 的 `_build_argv()` 方法。

**Q: 想关掉某个源？**
A: 在 `.env` 中设置 `ENABLE_MOCK_FALLBACK=false` 并让该源不可用（如 `MEDIACRAWLER_ENABLED=false`），它会直接从调度计划中消失。
