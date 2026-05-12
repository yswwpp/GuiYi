# GuiYi Backend API 文档

## 概述

GuiYi Backend 提供基于 FastAPI 的 REST API 服务，支持网页保存、语义搜索、AI 增强搜索和多数据源同步。

**基础 URL**: `http://127.0.0.1:8765`

**API 文档**: `http://127.0.0.1:8765/docs` (Swagger UI)

---

## 核心 API

### 1. 获取服务状态

**GET** `/api/status`

获取服务运行状态和统计信息。

**响应示例**:

```json
{
  "status": "running",
  "uptime": 3600.5,
  "sources": ["web", "feishu", "local", "yinxiang"],
  "storage": {
    "total_files": 10,
    "total_size_mb": 2.5,
    "vault_path": "data/obsidian_vault",
    "inbox_path": "data/obsidian_vault/inbox"
  },
  "sync": {
    "total_documents": 2314,
    "last_sync_time": 1776917130.83
  },
  "scheduled_jobs": 4,
  "index": {
    "total_documents": 2314,
    "index_path": "data/index",
    "model": "BAAI/bge-m3"
  }
}
```

### 2. 保存网页链接

**POST** `/api/save`

抓取网页内容，保存到 Obsidian，并建立语义索引。

**请求体**:

```json
{
  "url": "https://example.com/article"
}
```

**响应示例**:

```json
{
  "status": "success",
  "url": "https://example.com/article",
  "title": "文章标题",
  "file_path": "data/obsidian_vault/inbox/文章标题.md",
  "doc_id": "abc123def456"
}
```

### 3. 语义搜索

**POST** `/api/search`

执行语义搜索，支持自然语言查询。

**请求体**:

```json
{
  "query": "Python 性能优化",
  "source": null,
  "account": null,
  "limit": 10
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索查询（支持自然语言） |
| source | string | 否 | 数据源过滤（web, feishu, local, yinxiang） |
| account | string | 否 | 账号过滤 |
| limit | integer | 否 | 返回结果数量，默认 10 |

**响应示例**:

```json
[
  {
    "id": "abc123def456",
    "title": "Python 性能优化指南",
    "url": "https://example.com/python-optimization",
    "source": "web",
    "account": null,
    "score": 0.95,
    "text": "这是一篇关于 Python 性能优化的文章..."
  }
]
```

### 4. AI 增强搜索

**POST** `/api/ai-search`

执行 AI 增强的语义搜索，支持关键词提取和智能重排。

**请求体**:

```json
{
  "query": "Python 性能优化",
  "enable_keyword_extraction": true,
  "enable_rerank": true,
  "limit": 10
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索查询 |
| enable_keyword_extraction | boolean | 否 | 启用 AI 关键词提取 |
| enable_rerank | boolean | 否 | 启用 AI 智能重排 |
| limit | integer | 否 | 返回结果数量 |

**响应示例**:

```json
{
  "results": [
    {
      "id": "abc123def456",
      "title": "Python 性能优化指南",
      "url": "https://example.com/python-optimization",
      "source": "web",
      "account": null,
      "score": 0.85,
      "rerank_score": 0.92,
      "final_score": 0.89,
      "text": "这是一篇关于 Python 性能优化的文章...",
      "ai_keywords": ["Python", "性能", "优化"]
    }
  ],
  "ai_enhanced": true,
  "keywords_extracted": ["Python", "性能优化", "代码"],
  "rerank_used": true,
  "processing_time_ms": 523.5
}
```

---

## 印象笔记 API

### 1. 列出印象笔记账号

**GET** `/api/yinxiang/accounts`

**响应示例**:

```json
{
  "accounts": [
    {
      "name": "main",
      "note_store_url": "https://app.yinxiang.com/shard/s1/notestore",
      "is_china": true,
      "sync_notebooks": []
    }
  ]
}
```

### 2. 添加印象笔记账号

**POST** `/api/yinxiang/accounts`

**请求体**:

```json
{
  "name": "main",
  "token": "S=s1:U=124701:E=...",
  "note_store_url": "https://app.yinxiang.com/shard/s1/notestore",
  "is_china": true,
  "sync_notebooks": []
}
```

### 3. 触发后台同步

**POST** `/api/yinxiang/accounts/{name}/background-sync`

启动后台持续同步，自动处理 API 限流直到完成。

**响应示例**:

```json
{
  "status": "started",
  "message": "账号 main 后台同步已启动，将自动处理限流直到完成"
}
```

### 4. 重置同步状态

**POST** `/api/yinxiang/accounts/{name}/reset-sync`

重置同步状态，下次同步将全量获取。

### 5. 获取笔记本列表

**GET** `/api/yinxiang/accounts/{name}/notebooks`

### 6. 测试连接

**POST** `/api/yinxiang/test`

测试印象笔记连接是否正常。

---

## 飞书 API

### 1. 列出飞书账号

**GET** `/api/feishu/accounts`

### 2. 添加飞书账号

**POST** `/api/feishu/accounts`

**请求体**:

```json
{
  "name": "wiki_user",
  "app_id": "cli_xxx",
  "app_secret": "xxx",
  "wiki_space_id": "123456"
}
```

### 3. 获取 OAuth 授权 URL

**GET** `/api/feishu/oauth/url`

### 4. OAuth 回调

**GET** `/api/feishu/oauth/callback?code=xxx&state=xxx`

---

## 本地文件 API

### 1. 列出本地目录

**GET** `/api/local-directories`

### 2. 添加本地目录

**POST** `/api/local-directories`

**请求体**:

```json
{
  "name": "文档目录",
  "path": "/Users/xxx/Documents",
  "file_types": ["pdf", "docx", "md", "txt"],
  "enabled": true
}
```

### 3. 更新本地目录

**PATCH** `/api/local-directories/{dir_id}`

### 4. 删除本地目录

**DELETE** `/api/local-directories/{dir_id}`

---

## 同步 API

### 1. 触发同步

**POST** `/api/sync`

**请求体**:

```json
{
  "source": "local",
  "account": null
}
```

### 2. 获取同步状态

**GET** `/api/sync/status`

### 3. 获取同步日志

**GET** `/api/sync/logs?limit=100`

### 4. 获取定时任务列表

**GET** `/api/scheduled-jobs`

**响应示例**:

```json
{
  "total": 4,
  "jobs": [
    {
      "id": "sync_feishu_default",
      "name": "feishu (default) 同步",
      "next_run_time": "2026-04-23T12:00:00+08:00",
      "trigger": "cron[hour='12', minute='0']"
    }
  ]
}
```

---

## AI 配置 API

### 1. 获取 AI 配置

**GET** `/api/ai/config`

### 2. 更新 AI 配置

**PUT** `/api/ai/config`

**请求体**:

```json
{
  "provider": "openai",
  "api_key": "sk-xxx",
  "api_base": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "max_tokens": 1000
}
```

### 3. 测试 AI 配置

**POST** `/api/ai/test`

### 4. 获取搜索配置

**GET** `/api/ai/search-config`

### 5. 更新搜索配置

**PUT** `/api/ai/search-config`

**请求体**:

```json
{
  "rerank_enabled": false,
  "keyword_extraction_enabled": false,
  "rerank_model": "BAAI/bge-reranker-v2-m3",
  "keyword_model": "gpt-4o-mini"
}
```

---

## 数据模型

### SearchResult

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 文档唯一标识 |
| title | string | 文档标题 |
| url | string | 原始 URL |
| source | string | 数据来源 |
| account | string? | 账号信息 |
| score | float | 相关性得分 |
| text | string | 文档摘要 |

### AISearchResult

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 文档唯一标识 |
| title | string | 文档标题 |
| url | string | 原始 URL |
| source | string | 数据来源 |
| account | string? | 账号信息 |
| score | float | 原始向量分数 |
| rerank_score | float? | Rerank 分数 |
| final_score | float | 最终综合分数 |
| text | string | 文档摘要 |
| ai_keywords | string[]? | AI 提取的关键词 |

### AISearchResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| results | AISearchResult[] | 搜索结果列表 |
| ai_enhanced | boolean | 是否使用 AI 增强 |
| keywords_extracted | string[] | AI 提取的关键词 |
| rerank_used | boolean | 是否使用 Rerank |
| processing_time_ms | float | 处理耗时 |

---

## 错误处理

API 使用标准 HTTP 状态码：

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

错误响应格式：

```json
{
  "detail": "错误描述信息"
}
```

---

## 使用示例

### cURL

```bash
# 保存网页
curl -X POST http://localhost:8765/api/save \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'

# 普通搜索
curl -X POST http://localhost:8765/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python 教程", "limit": 5}'

# AI 增强搜索
curl -X POST http://localhost:8765/api/ai-search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python 教程", "enable_keyword_extraction": true, "enable_rerank": true}'

# 触发印象笔记后台同步
curl -X POST http://localhost:8765/api/yinxiang/accounts/main/background-sync

# 查看状态
curl http://localhost:8765/api/status
```

### Python

```python
import httpx

# 保存网页
response = httpx.post(
    "http://localhost:8765/api/save",
    json={"url": "https://example.com/article"}
)
print(response.json())

# AI 搜索
response = httpx.post(
    "http://localhost:8765/api/ai-search",
    json={
        "query": "Python 教程",
        "enable_keyword_extraction": True,
        "enable_rerank": True,
        "limit": 5
    }
)
print(response.json())
```

---

## 配置

API 服务配置可通过环境变量或 `.env` 文件设置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| API_HOST | 127.0.0.1 | 监听地址 |
| API_PORT | 8765 | 监听端口 |
| API_DEBUG | true | 调试模式 |
| OBSIDIAN_VAULT_PATH | data/obsidian_vault | Obsidian 库路径 |
| INDEX_PATH | data/index | 索引存储路径 |
