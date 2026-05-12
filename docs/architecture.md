# GuiYi 技术架构文档

> 本地优先的个人知识收集与检索系统

---

## 系统架构概览

```mermaid
graph TB
    subgraph Frontend["前端 (Swift)"]
        UI[SwiftUI 界面]
        Hotkey[全局快捷键 Cmd+J]
        Tray[状态栏集成]
        API[URLSession API 客户端]
    end

    subgraph Backend["后端 (Python)"]
        FastAPI[FastAPI 服务]
        Sync[同步引擎]
        AI[AI 服务]
        Index[向量索引]
        Scheduler[定时调度器]
    end

    subgraph Storage["存储层"]
        MySQL[(MySQL)]
        FAISS[(FAISS)]
        Files[文件系统]
        Keychain[macOS Keychain]
    end

    subgraph External["外部服务"]
        Feishu[飞书 API]
        Yinxiang[印象笔记 API]
        OpenAI[OpenAI 兼容 API]
    end

    UI --> API
    API --> FastAPI
    FastAPI --> Sync
    FastAPI --> AI
    FastAPI --> Index
    FastAPI --> Scheduler
    Sync --> MySQL
    Sync --> Files
    Index --> FAISS
    AI --> OpenAI
    Sync --> Feishu
    Sync --> Yinxiang
    Sync --> Keychain
```

---

## 技术栈

### 前端技术栈

| 组件 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| 语言 | Swift | 5.9+ | 原生开发 |
| UI 框架 | SwiftUI | - | 声明式界面 |
| 快捷键 | HotKey | - | 全局快捷键监听 (Cmd+J) |
| 网络请求 | URLSession | - | API 通信 |
| 数据存储 | @AppStorage | - | 用户偏好存储 |

### 后端技术栈

| 组件 | 技术 | 版本 | 用途 |
|-----|------|------|------|
| 语言 | Python | 3.11+ | 后端开发 |
| Web 框架 | FastAPI | - | REST API |
| 服务器 | Uvicorn | - | ASGI 服务器 |
| 向量引擎 | txtai | - | 语义索引 |
| 向量存储 | FAISS | 1.13.2 | 向量数据库 |
| 嵌入模型 | BAAI/bge-m3 | - | 多语言向量模型 |
| 网页抓取 | trafilatura | - | 内容提取 |
| 定时任务 | APScheduler | - | 同步调度 |
| 文件监听 | watchdog | - | 文件变更检测 |
| 凭证管理 | keyring | - | macOS Keychain |
| 飞书 SDK | lark-oapi | - | 飞书 API |
| PDF 解析 | PyPDF2 | - | PDF 内容提取 |
| Word 解析 | python-docx | - | Word 文档解析 |
| Excel 解析 | openpyxl | - | Excel 文档解析 |
| PPT 解析 | python-pptx | - | PPT 文档解析 |
| HTTP 客户端 | httpx | - | AI API 调用 |
| 数据库连接 | pymysql | - | MySQL 数据库连接 |

---

## 核心模块设计

### 1. 数据源适配器 (Adapters)

```mermaid
classDiagram
    class BaseAdapter {
        <<abstract>>
        +fetch_all_for_index(account) List[Dict]
        +get_document_content(doc_id, file_path) str
    }

    class FeishuAdapter {
        -accounts: Dict
        +fetch_all_for_index(account) List[Dict]
        +get_document_content(doc_id) str
        +add_account()
        +refresh_user_token()
    }

    class YinxiangAdapter {
        -accounts: Dict
        -_note_stores: Dict
        -_sync_state_cache: Dict
        +fetch_all_for_index(account) List[Dict]
        +get_note_content(account, guid) str
        +list_notes_incremental(account, usn) List[Dict]
        +get_sync_chunk(account, usn) SyncChunk
    }

    class LocalFileAdapter {
        -store: LocalDirectoryStore
        +fetch_all_for_index(account) List[Dict]
        +get_document_content(doc_id, file_path) str
        +count_files(dir_id) int
    }

    BaseAdapter <|-- FeishuAdapter
    BaseAdapter <|-- YinxiangAdapter
    BaseAdapter <|-- LocalFileAdapter
```

**适配器职责**：
- 统一不同数据源的接口
- 获取文档列表用于索引
- 提取文档内容
- 支持增量同步

### 2. 印象笔记适配器 (YinxiangAdapter)

印象笔记适配器使用 Thrift 协议直接连接 NoteStore API，支持：

**特性**：
- 支持 Developer Token 认证
- 支持国际版 Evernote 和中国版印象笔记
- 增量同步（基于 USN）
- API 限流自动处理

**URL 生成**：
```
https://app.yinxiang.com/shard/{shardId}/nl/{userId}/{noteGuid}
```

从 Token 解析参数：
- `S=s1` → shard_id
- `U=124701` → user_id

**限流处理策略**：

| 策略 | 说明 |
|------|------|
| API 调用间隔 | 1.5 秒 |
| 限流等待 | 等待 rateLimitDuration 后重试 |
| 重试次数 | 最多 3 次 |
| 待处理队列 | 限流失败的笔记保存到 pending 列表 |

### 3. 同步引擎 (Sync Engine)

```mermaid
flowchart TD
    A[触发同步] --> B[获取文档列表]
    B --> C{文档存在?}

    C -->|否| D[新增文档]
    C -->|是| E{快速检测}

    E -->|size/mtime 变化| F[读取内容]
    E -->|未变化| G[跳过]

    D --> F
    F --> H{内容哈希变化?}

    H -->|是| I[更新索引]
    H -->|否| J[更新元数据]

    I --> K[保存到 FAISS]
    J --> L[更新 MySQL]
    G --> L
```

**增量同步策略**：

| 检测层级 | 检测方式 | 性能 |
|---------|---------|------|
| 第一层 | file_size + file_mtime | 极快，不读文件 |
| 第二层 | content_hash (MD5) | 需读文件，中等 |
| 第三层 | 向量索引更新 | 最慢 |

### 4. 向量索引 (Vector Index)

```mermaid
flowchart LR
    A[文档内容] --> B[文本预处理]
    B --> C[BAAI/bge-m3]
    C --> D[向量 1024维]
    D --> E[FAISS 索引]

    F[搜索查询] --> G[向量编码]
    G --> H[FAISS 检索]
    H --> I[相似度排序]
    I --> J[返回结果]
```

**索引配置**：

```python
embeddings = Embeddings({
    "path": "BAAI/bge-m3",    # 多语言模型
    "content": False,          # 禁用 SQLite 内容存储
    "objects": True            # 启用对象存储
})
```

### 5. AI 搜索增强

```mermaid
flowchart TD
    A[用户查询] --> B{AI 增强开启?}

    B -->|否| C[直接向量搜索]
    B -->|是| D{关键词提取开启?}

    D -->|是| E[AI 提取关键词]
    E --> F[关键词 + 原查询搜索]
    D -->|否| F

    F --> G{Rerank 开启?}
    C --> G

    G -->|是| H[AI Rerank 重排序]
    G -->|否| I[返回结果]

    H --> I
```

**AI 搜索功能**：

| 功能 | 说明 | 开关 |
|------|------|------|
| 关键词提取 | 从查询中提取关键搜索词 | keyword_extraction_enabled |
| 智能重排 | 使用 Rerank 模型重新排序结果 | rerank_enabled |

---

## 存储架构

### 文件结构

```
data/
├── index/                      # 向量索引
│   ├── documents/
│   │   ├── embeddings          # FAISS 向量
│   │   ├── ids                 # 文档 ID 映射
│   │   └── config.json         # 索引配置
│   └── metadata.json           # 文档元数据
│
├── db_config.json              # 数据库配置 (MySQL)
│
├── ai_config.json              # AI 配置
│
├── search_config.json          # AI 搜索配置
│
├── scheduler_jobs.json         # 定时任务配置
│
├── yinxiang_sync_state.json    # 印象笔记同步状态
│
├── local_directories.json      # 本地目录配置
│
└── obsidian_vault/             # 网页存储
    └── inbox/
        └── *.md                # Markdown 文件
```

### 数据库设计

> 系统使用 MySQL 存储同步元数据，支持更大规模数据。

#### sync_metadata 表

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | VARCHAR(255) | 文档唯一标识 |
| `source` | VARCHAR(50) | 数据源 (feishu/local/yinxiang) |
| `account` | VARCHAR(255) | 账号/目录标识 |
| `url` | TEXT | 原文链接/文件路径 |
| `title` | TEXT | 文档标题 |
| `content_hash` | VARCHAR(64) | 内容 MD5 哈希 |
| `file_size` | BIGINT | 文件大小 (字节) |
| `file_mtime` | DOUBLE | 文件修改时间戳 |
| `last_modified` | DOUBLE | 最后修改时间 |
| `last_synced` | DOUBLE | 最后同步时间 |
| `sync_status` | VARCHAR(20) | 状态 (synced/deleted) |
| `ai_summary` | TEXT | AI 生成的摘要 |
| `ai_tags` | TEXT | AI 生成的标签 (JSON) |

---

## API 设计

### RESTful API 端点

```mermaid
graph LR
    subgraph Core["核心 API"]
        A1[POST /api/save]
        A2[POST /api/search]
        A2b[POST /api/ai-search]
        A3[GET /api/status]
    end

    subgraph Sync["同步 API"]
        B1[POST /api/sync]
        B2[GET /api/sync/status]
        B3[GET /api/sync/logs]
        B4[GET /api/scheduled-jobs]
    end

    subgraph Local["本地文件 API"]
        C1[GET /api/local-directories]
        C2[POST /api/local-directories]
        C3[PATCH /api/local-directories/:id]
        C4[DELETE /api/local-directories/:id]
    end

    subgraph Feishu["飞书 API"]
        E1[GET /api/feishu/accounts]
        E2[POST /api/feishu/accounts]
        E3[DELETE /api/feishu/accounts/:name]
    end

    subgraph Yinxiang["印象笔记 API"]
        F1[GET /api/yinxiang/accounts]
        F2[POST /api/yinxiang/accounts]
        F3[POST /api/yinxiang/accounts/:name/background-sync]
        F4[POST /api/yinxiang/accounts/:name/reset-sync]
    end

    subgraph AI["AI 配置 API"]
        D1[GET /api/ai/config]
        D2[PUT /api/ai/config]
        D3[POST /api/ai/test]
        D4[GET /api/ai/search-config]
        D5[PUT /api/ai/search-config]
    end
```

---

## 前端架构

### SwiftUI 视图层次

```mermaid
graph TB
    GuiYiApp[GuiYiApp 入口]

    GuiYiApp --> ContentView[ContentView 悬浮窗]
    GuiYiApp --> SettingsView[SettingsView 设置]

    ContentView --> SearchView[SearchView 搜索界面]
    SearchView --> SearchBar[搜索框]
    SearchView --> AIEnhanceToggle[AI 增强开关]
    SearchView --> ResultsList[结果列表]

    SettingsView --> GeneralSettingsView[通用设置]
    SettingsView --> SyncSettingsView[同步设置]
    SettingsView --> AISettingsView[AI 设置]
```

### 全局快捷键

- **Cmd+J**: 唤起搜索窗口
- 使用 NSEvent.addGlobalMonitorForEvents 实现

### 数据源图标

| 数据源 | 图标 | 颜色 |
|-------|------|------|
| 飞书 | 纸飞机 Shape | 蓝色 (#3370FF) |
| 本地文件 | 文件夹 SF Symbol | 橙色 (#F97316) |
| 网页 | 地球 SF Symbol | 绿色 (#22C55E) |
| 印象笔记 | 大象 Shape | 绿色 (#009933) |
| 夸克网盘 | 云 SF Symbol | 蓝色 (#3399FF) |

---

## 定时任务

### 调度器配置

定时任务使用 APScheduler 实现，配置持久化到 `data/scheduler_jobs.json`。

**默认任务**：

| 任务 | 执行时间 | 说明 |
|------|---------|------|
| feishu 同步 | 每天 12:00 | 同步飞书文档 |
| yinxiang 同步 | 每天 12:00 | 同步印象笔记 |
| local 同步 | 每天 12:00 | 同步本地文件 |
| quark 同步 | 每周一 08:00 | 同步夸克网盘 |

---

## 安全设计

### 凭证管理

```mermaid
flowchart LR
    A[用户输入凭证] --> B[前端 SecureField]
    B --> C[HTTPS API 调用]
    C --> D[后端接收]
    D --> E[keyring 库]
    E --> F[macOS Keychain]
```

**存储的凭证类型**：
- 飞书 App ID / App Secret
- 飞书 User Access Token / Refresh Token
- AI API Key
- 印象笔记 Developer Token

---

## 相关文档

- [需求与技术方案](./归一GuiYi-需求与技术方案.md)
- [飞书文档索引规则](./feishu-index-rules.md)
- [本地文件索引规则](./local-file-index-rules.md)
- [API 参考](./api-reference.md)
