# guiyi-server 模块说明

Python 后端服务，负责数据处理、同步、索引。

## 核心职责

1. **数据源适配**：统一不同数据源的接口
2. **增量同步**：智能检测变更，只更新变化的部分
3. **语义索引**：txtai 向量化，支持自然语言搜索
4. **API 服务**：FastAPI 提供 REST API

## 架构设计

### 适配器模式

每个数据源一个适配器，统一接口：

```python
class BaseAdapter(ABC):
    @abstractmethod
    def fetch_all_for_index(self) -> List[Dict]:
        """获取所有文档用于索引"""
        pass
```

### 同步引擎

增量同步机制：

1. 获取当前文档列表
2. 对比上次同步状态（哈希 + 修改时间）
3. 只更新变化的文档
4. 清理已删除文档的索引

## 开发注意事项

### 实现顺序

按照技术文档的阶段逐步实现：

1. ✅ **第一阶段**：网页抓取 + 基础索引
2. 🚧 **第二阶段**：飞书多账号支持
3. 🚧 **第三阶段**：WPS 文件监听
4. 🚧 **第四阶段**：印象笔记 + 夸克网盘
5. 🚧 **第五阶段**：优化和完善

> ⚠️ **重要**：不要一次性实现所有数据源！按阶段逐步完成。

### 代码规范

1. **类型注解**：所有函数必须有类型注解
   ```python
   def fetch_doc(doc_id: str) -> Optional[Dict]:
       pass
   ```

2. **异常处理**：明确的异常处理
   ```python
   try:
       content = scraper.fetch(url)
   except requests.RequestException as e:
       logger.error(f"Failed to fetch {url}: {e}")
       return None
   ```

3. **日志记录**：使用 logging 模块
   ```python
   import logging
   logger = logging.getLogger(__name__)
   ```

4. **配置管理**：使用环境变量或配置文件
   ```python
   from config import settings

   API_PORT = settings.API_PORT
   ```

### 数据库操作

使用 SQLAlchemy ORM：

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///data/sync_metadata.sqlite')
Session = sessionmaker(bind=engine)
```

### 凭证管理

使用 keyring 库访问 macOS Keychain：

```python
import keyring

# 存储凭证
keyring.set_password("guiyi", "feishu_company_app_id", app_id)

# 获取凭证
app_id = keyring.get_password("guiyi", "feishu_company_app_id")
```

## 测试

### 单元测试

```bash
pytest tests/test_adapters.py -v
```

### 集成测试

```bash
pytest tests/test_sync.py -v
```

## API 端点

- `POST /api/save` - 保存网页链接
- `POST /api/search` - 语义搜索
- `POST /api/sync` - 手动触发同步
- `GET /api/status` - 服务状态

## 依赖管理

使用 uv 安装依赖：

```bash
uv pip install fastapi uvicorn trafilatura txtai
```

## 相关文档

- [技术方案](../../docs/归一GuiYi-需求与技术方案.md)
- [API 设计](../../docs/api-design.md)
