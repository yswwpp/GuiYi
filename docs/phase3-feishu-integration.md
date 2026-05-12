# GuiYi Phase 3: Feishu Multi-Account Integration

## 🎯 功能概述

第三阶段实现了以下核心功能：

### 1. 飞书多账号支持
- ✅ 多账号管理（公司账号 + 个人账号）
- ✅ 凭证安全存储（macOS Keychain）
- ✅ 文档列表获取
- ✅ 文档摘要提取（用于索引）
- ✅ 仅索引模式（不存储原文）

### 2. 增量同步引擎
- ✅ SQLite 同步元数据管理
- ✅ 变更检测（内容哈希 + 修改时间）
- ✅ 增量更新索引
- ✅ 删除文档清理
- ✅ 同步日志记录

### 3. 定时任务调度
- ✅ APScheduler 后台调度
- ✅ Cron 表达式支持
- ✅ 手动触发同步
- ✅ 任务管理 API

## 🚀 快速开始

### 1. 安装依赖

```bash
cd guiyi-server
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. 启动服务

```bash
# 使用 Phase 3 版本
python main_phase3.py

# 或使用 Makefile
make run-phase3
```

服务将在 http://127.0.0.1:8765 启动

### 3. 配置飞书账号

#### 3.1 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 `App ID` 和 `App Secret`
4. 配置应用权限：
   - `drive:drive:readonly` - 读取云文档
   - `docx:document:readonly` - 读取文档内容

#### 3.2 添加账号到 GuiYi

使用 API 添加飞书账号：

```bash
# 添加公司账号
curl -X POST http://127.0.0.1:8765/api/feishu/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "company",
    "app_id": "cli_xxxxxxxxxxxxx",
    "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxx"
  }'

# 添加个人账号
curl -X POST http://127.0.0.1:8765/api/feishu/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "name": "personal",
    "app_id": "cli_yyyyyyyyyyyyy",
    "app_secret": "yyyyyyyyyyyyyyyyyyyyyyyyyy"
  }'
```

### 4. 手动同步

```bash
# 同步所有飞书账号
curl -X POST http://127.0.0.1:8765/api/sync \
  -H "Content-Type: application/json" \
  -d '{"source": "feishu"}'

# 同步特定账号
curl -X POST http://127.0.0.1:8765/api/sync \
  -H "Content-Type: application/json" \
  -d '{
    "source": "feishu",
    "account": "feishu_company"
  }'
```

### 5. 搜索飞书文档

```bash
# 搜索所有来源
curl -X POST http://127.0.0.1:8765/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "技术规划"}'

# 仅搜索飞书文档
curl -X POST http://127.0.0.1:8765/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "技术规划",
    "source": "feishu"
  }'

# 仅搜索特定账号
curl -X POST http://127.0.0.1:8765/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "技术规划",
    "source": "feishu",
    "account": "feishu_company"
  }'
```

## 📊 API 端点

### 飞书账号管理

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/feishu/accounts` | 添加飞书账号 |
| GET | `/api/feishu/accounts` | 列出所有飞书账号 |
| DELETE | `/api/feishu/accounts/{name}` | 删除飞书账号 |

### 同步管理

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/sync` | 手动触发同步 |
| GET | `/api/sync/status` | 获取同步状态 |
| GET | `/api/sync/logs` | 获取同步日志 |

### 定时任务管理

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/scheduler/jobs` | 添加定时任务 |
| GET | `/api/scheduler/jobs` | 列出所有定时任务 |
| DELETE | `/api/scheduler/jobs/{job_id}` | 删除定时任务 |

## 🗂️ 文件结构

```
guiyi-server/
├── adapters/
│   ├── web_scraper.py          # 网页抓取
│   └── feishu_adapter.py       # 飞书适配器 ✨ NEW
├── sync/
│   ├── __init__.py
│   ├── metadata.py             # 同步元数据管理 ✨ NEW
│   ├── engine.py               # 增量同步引擎 ✨ NEW
│   └── scheduler.py            # 定时任务调度 ✨ NEW
├── storage/
│   ├── obsidian.py             # Obsidian 存储
│   └── keychain.py             # Keychain 凭证管理 ✨ NEW
├── index/
│   └── txtai_index.py          # 语义索引
├── main_phase3.py              # Phase 3 主程序 ✨ NEW
├── requirements.txt            # 依赖清单
└── Makefile                    # 常用命令
```

## 🔐 安全设计

### 凭证存储

- **macOS Keychain**: 所有凭证安全存储在系统 Keychain 中
- **不硬编码**: App ID 和 App Secret 不写入代码或配置文件
- **最小权限**: 飞书应用仅需只读权限

### 数据隐私

- **仅索引**: 飞书文档只建立索引，不存储全文
- **本地处理**: 所有数据处理在本地完成
- **原文链接**: 搜索结果直接跳转到飞书原文

## 📈 性能优化

### 增量同步

- **变更检测**: 通过内容哈希 + 修改时间检测变更
- **跳过未变更**: 未变更的文档不重新索引
- **增量更新**: 只更新有变化的部分

### 同步策略

| 数据源 | 默认同步频率 | 检测方式 |
|--------|------------|---------|
| 飞书 | 每天 9:00 | `updated_at` 字段 |
| 印象笔记 | 每天 12:00 | `updateSequenceNum` |
| 夸克网盘 | 每周一 8:00 | 文件 `mtime` |

## 🧪 测试

### 单元测试

```bash
# 测试飞书适配器
pytest tests/test_feishu_adapter.py -v

# 测试同步引擎
pytest tests/test_sync_engine.py -v

# 测试元数据管理
pytest tests/test_sync_metadata.py -v
```

### 集成测试

```bash
# 启动服务
python main_phase3.py

# 测试 API
curl http://127.0.0.1:8765/api/status
```

## 📝 使用示例

### Python 客户端

```python
import requests

BASE_URL = "http://127.0.0.1:8765"

# 添加飞书账号
requests.post(f"{BASE_URL}/api/feishu/accounts", json={
    "name": "company",
    "app_id": "cli_xxxxx",
    "app_secret": "xxxxx"
})

# 触发同步
requests.post(f"{BASE_URL}/api/sync", json={
    "source": "feishu"
})

# 搜索文档
results = requests.post(f"{BASE_URL}/api/search", json={
    "query": "技术规划",
    "source": "feishu"
}).json()

for result in results:
    print(f"标题: {result['title']}")
    print(f"链接: {result['url']}")
    print(f"相关度: {result['score']:.2%}")
    print()
```

## ⚠️ 注意事项

### 首次运行

1. **向量模型下载**: 首次运行会自动下载向量模型（约 1-2GB）
2. **飞书权限**: 确保飞书应用有正确的权限配置
3. **Keychain 访问**: 首次保存凭证时可能需要授权访问 Keychain

### 飞书 API 限制

- **请求频率**: 飞书 API 有请求频率限制，大量文档可能需要分批同步
- **权限范围**: 某些文档可能因为权限限制无法访问
- **内容大小**: 大型文档可能需要截取摘要

## 🔄 下一步计划

### Phase 4: 更多数据源

- [ ] WPS 本地文件监听
- [ ] 印象笔记 API 对接
- [ ] 夸克网盘接入

### Phase 5: 功能增强

- [ ] 前端账号管理界面
- [ ] 同步进度显示
- [ ] 变更通知
- [ ] 去重检测

## 📚 相关文档

- [技术方案](../../docs/归一GuiYi-需求与技术方案.md)
- [API 文档](../../docs/api-reference.md)
- [Phase 2 测试报告](../../docs/test-report-20260405.md)

## 🐛 故障排查

### 飞书客户端初始化失败

```bash
# 检查凭证是否正确保存
python -c "from storage.keychain import KeychainManager; print(KeychainManager.get_feishu_account('company'))"

# 删除并重新添加账号
curl -X DELETE http://127.0.0.1:8765/api/feishu/accounts/company
```

### 同步失败

```bash
# 查看同步状态
curl http://127.0.0.1:8765/api/sync/status

# 查看服务日志
tail -f /tmp/guiyi.log
```

### 索引未生效

```bash
# 检查索引状态
curl http://127.0.0.1:8765/api/status

# 重启服务重新加载索引
python main_phase3.py
```
