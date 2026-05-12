# GuiYi AI 增强搜索方案

## Context

用户希望在现有向量搜索基础上添加 AI 增强：
1. **自然语言输入** → AI 提取关键词/意图 → 向量搜索
2. **向量搜索结果** → AI Rerank 重排 → 精准排序

**用户选择**：
- 触发方式：可选开关（手动开启/关闭）**← 重要**
- 重排方式：本地部署 `BAAI/bge-reranker-v2-m3`（免费、离线可用、与索引模型同家族）
- 关键词提取：本地 Ollama `qwen2.5:9b` 或现有 API（可配置）

**目标**：解决「深化金融服务」搜索时目标文档排在第12位的问题，通过 AI 重排提升相关性。

---

## 数据流程

```
用户输入自然语言
       │
       ▼
┌──────────────────────┐
│ 前端检查 AI 开关状态  │
└──────────────────────┘
       │
   ┌───┴───┐
   │ 开关  │
   └───┬───┘
       │
   开启 │   关闭
       │       │
       ▼       ▼
 /api/ai-search  /api/search
       │
       ▼
┌──────────────────┐
│ 阶段1: AI提取关键词│ ← 本地 Qwen 9B（Ollama）或 API
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ 阶段2: 向量搜索   │ ← txtai + BGE-M3
└──────────────────┘
       │
       ▼
┌──────────────────┐
│ 阶段3: Rerank重排 │ ← 本地 bge-reranker-v2-m3
└──────────────────┘
       │
       ▼
   返回最终结果
```

---

## 设计原则：模块化与可插拔

**核心思想**：每个 AI 功能模块独立封装，支持随时替换底层实现。

### 模块架构图

```
┌─────────────────────────────────────────────────────────┐
│                    AISearchService                       │
│  （统一入口，组合各模块，不依赖具体实现）                    │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│KeywordExtractor│ │ VectorSearch │ │ RerankService │
│  （接口）      │ │  （接口）    │ │  （接口）     │
└──────────────┘ └──────────────┘ └──────────────┘
        │                              │
        ▼                              ▼
┌──────────────┐               ┌──────────────┐
│ 提取器实现 A  │               │ 重排器实现 A  │
│ OllamaLocal  │               │ BGEReranker   │
└──────────────┘               └──────────────┘
┌──────────────┐               ┌──────────────┐
│ 提取器实现 B  │               │ 重排器实现 B  │
│ OpenAIAPI    │               │ CohereAPI     │
└──────────────┘               └──────────────┘
┌──────────────┐               ┌──────────────┐
│ 提取器实现 C  │               │ 重排器实现 C  │
│ 百度千帆API  │               │ JinaReranker  │
└──────────────┘               └──────────────┘
     ...可扩展                    ...可扩展
```

### 接口定义

**1. KeywordExtractor 接口**：
```python
class KeywordExtractorBase(ABC):
    """关键词提取器基类 - 所有实现必须继承"""
    
    @abstractmethod
    def extract(self, query: str) -> Optional[Dict]:
        """
        提取关键词
        
        Returns:
            {"keywords": [...], "intent": "...", "enhanced_query": "..."}
            或 None 表示失败
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查服务是否可用"""
        pass

# 具体实现（可插拔）
class OllamaKeywordExtractor(KeywordExtractorBase):
    """本地 Ollama 实现"""
    ...

class OpenAIKeywordExtractor(KeywordExtractorBase):
    """OpenAI 格式 API 实现（兼容百度千帆、DeepSeek 等）"""
    ...

class MockKeywordExtractor(KeywordExtractorBase):
    """Mock 实现（用于测试）"""
    ...
```

**2. RerankService 接口**：
```python
class RerankerBase(ABC):
    """重排器基类 - 所有实现必须继承"""
    
    @abstractmethod
    def rerank(self, query: str, documents: List[Dict], top_n: int) -> List[Dict]:
        """
        对搜索结果重排
        
        Args:
            query: 原始查询
            documents: 搜索结果列表
            top_n: 返回数量
            
        Returns:
            重排后的结果列表（包含 rerank_score）
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查模型/服务是否可用"""
        pass

# 具体实现（可插拔）
class BGEReranker(RerankerBase):
    """本地 BGE Reranker 实现"""
    ...

class CohereReranker(RerankerBase):
    """Cohere API 实现"""
    ...

class JinaReranker(RerankerBase):
    """Jina AI Reranker 实现"""
    ...
```

### 配置驱动的模块切换

通过配置文件选择具体实现，无需修改代码：

```python
# config_store.py
@dataclass
class AIConfig:
    # 关键词提取器配置
    keyword_extractor_type: str = "ollama"  # "ollama" | "openai" | "baidu" | "mock"
    keyword_ollama_model: str = "qwen2.5:9b"
    keyword_ollama_url: str = "http://localhost:11434"
    keyword_api_url: str = ""               # OpenAI 格式 API 地址
    keyword_api_key: str = ""
    keyword_api_model: str = ""
    
    # 重排器配置
    reranker_type: str = "bge"              # "bge" | "cohere" | "jina"
    reranker_bge_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_cohere_url: str = "https://api.cohere.ai/v1"
    reranker_cohere_key: str = ""
    reranker_jina_url: str = ""
    reranker_jina_key: str = ""

# 工厂方法 - 根据配置创建实例
def create_keyword_extractor(config: AIConfig) -> KeywordExtractorBase:
    if config.keyword_extractor_type == "ollama":
        return OllamaKeywordExtractor(config.keyword_ollama_url, config.keyword_ollama_model)
    elif config.keyword_extractor_type == "openai":
        return OpenAIKeywordExtractor(config.keyword_api_url, config.keyword_api_key, config.keyword_api_model)
    elif config.keyword_extractor_type == "mock":
        return MockKeywordExtractor()
    else:
        raise ValueError(f"未知的提取器类型: {config.keyword_extractor_type}")

def create_reranker(config: AIConfig) -> RerankerBase:
    if config.reranker_type == "bge":
        return BGEReranker(config.reranker_bge_model)
    elif config.reranker_type == "cohere":
        return CohereReranker(config.reranker_cohere_url, config.reranker_cohere_key)
    elif config.reranker_type == "jina":
        return JinaReranker(config.reranker_jina_url, config.reranker_jina_key)
    else:
        raise ValueError(f"未知的重排器类型: {config.reranker_type}")
```

### 扩展性设计

**新增实现只需**：
1. 继承基类实现接口
2. 在配置中添加新类型选项
3. 在工厂方法中添加分支

**无需改动**：
- AISearchService 主逻辑
- 其他已有实现
- 前端代码

---

## 实施方案

### Phase 1: 后端 Rerank 服务

**新增文件**: `guiyi-server/ai/rerank_service.py`

```python
from sentence_transformers import CrossEncoder

@dataclass
class RerankConfig:
    enabled: bool = False
    model: str = "BAAI/bge-reranker-v2-m3"  # 本地模型
    top_n: int = 20
    cache_dir: str = "~/.cache/huggingface/hub"  # 模型缓存目录

class RerankService:
    def __init__(self, config: RerankConfig):
        self.config = config
        self.reranker = None  # 延迟加载
    
    def _load_model(self):
        """首次调用时加载模型（自动下载约 1.2GB）"""
        if self.reranker is None:
            self.reranker = CrossEncoder(self.config.model)
    
    def rerank(query, documents, top_n) -> List[Dict]
    def is_enabled() -> bool  # 检查开关状态
```

**核心逻辑**：
- 使用 `sentence_transformers.CrossEncoder` 加载本地模型
- 首次调用自动从 Hugging Face Hub 下载（约 1.2GB，缓存到 `~/.cache/huggingface/`)
- 与现有 bge-m3 索引模型同家族，多语言中文支持一致
- `final_score = vector_score * 0.3 + rerank_score * 0.7`

**优势**：
- 本地部署，无需 API Key 和费用
- 离线可用，无网络延迟
- 推理延迟：20 个结果约 100-300ms（CPU），GPU 更快

### Phase 2: 扩展 AI 配置

**修改文件**: `guiyi-server/ai/config_store.py`

新增配置字段：
```python
@dataclass
class AIConfig:
    # ... 现有字段 ...

    # AI 搜索增强（重要：所有功能都有独立开关）
    ai_search_enabled: bool = False           # 总开关：AI 搜索增强
    keyword_extraction_enabled: bool = True   # 子开关：关键词提取
    rerank_enabled: bool = True               # 子开关：智能重排

    # 关键词提取配置（支持本地模型或 API）
    keyword_model_type: str = "local"         # "local" 或 "api"
    keyword_local_model: str = "qwen2.5:9b"   # 本地模型名称（Ollama）
    keyword_prompt: str = ""                  # 自定义提示词

    # Rerank 配置（本地模型）
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_n: int = 20
```

**开关设计原则**：
- 总开关 `ai_search_enabled`：一键关闭所有 AI 功能
- 子开关可独立控制：只开关键词提取、只开 Rerank、或两者都开
- 关闭时完全不走 AI 流程，节省资源

### Phase 3: 关键词提取服务

**修改文件**: `guiyi-server/ai/ai_service.py`

新增方法：
```python
def extract_keywords(self, query: str) -> Optional[Dict]:
    """从用户查询提取关键词和意图
    
    支持两种模式：
    - 本地模型：调用 Ollama qwen2.5:9b（HTTP API）
    - API 模型：使用现有 AI 配置（百度千帆等）
    """
    config = self.config_store.get_config()
    
    if config.keyword_model_type == "local":
        # 本地 Ollama 调用
        return self._extract_with_ollama(query, config.keyword_local_model)
    else:
        # API 调用（现有实现）
        return self._extract_with_api(query)
    
    # 返回: {"keywords": [...], "intent": "...", "enhanced_query": "..."}
```

**本地模型调用示例**（通过 Ollama HTTP API）：
```python
def _extract_with_ollama(self, query: str, model: str) -> Dict:
    """
    调用本地 Ollama 服务提取关键词
    Ollama 默认运行在 http://localhost:11434
    """
    import requests
    
    prompt = f"""分析以下搜索查询，提取关键词。
查询：{query}

返回 JSON 格式：
{"keywords": ["关键词1", "关键词2", "关键词3"]}"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model,  # 如 "qwen2.5:9b"
            "prompt": prompt,
            "stream": False  # 非流式返回
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        text = result.get("response", "")
        # 解析 JSON 提取关键词
        return self._parse_json_response(text)
    
    return None  # fallback: 跳过关键词提取
```

### Phase 4: 新增 API 端点

**修改文件**: `guiyi-server/main_phase3.py`

新增端点：

| 端点 | 方法 | 功能 |
|-----|------|------|
| `/api/ai-search` | POST | AI 增强搜索 |
| `/api/ai/search-config` | GET | 获取 AI 搜索配置 |
| `/api/ai/search-config` | PUT | 更新 AI 搜索配置 |
| `/api/ai/rerank-test` | POST | 测试 Rerank 模型加载 |

**请求格式**：
```python
class AISearchRequest(BaseModel):
    query: str
    source: Optional[str] = None
    limit: int = 20
    enable_ai_enhance: bool = True
    enable_rerank: bool = True
```

**响应格式**：
```python
class AISearchResponse(BaseModel):
    results: List[AISearchResult]
    ai_enhanced: bool
    keywords_extracted: List[str]
    rerank_used: bool
    processing_time_ms: float
```

### Phase 5: 前端 API 客户端

**修改文件**: `guiyi-client/GuiYi/APIClient.swift`

新增：
- `AISearchResult` / `AISearchResponse` 响应模型
- `aiSearch()` 方法
- `getAISearchConfig()` / `updateAISearchConfig()` 方法

### Phase 6: 前端搜索界面

**修改文件**: `guiyi-client/GuiYi/SearchView.swift`

改动：
1. 新增 AI 增强开关按钮（搜索框右侧 ✨图标）
2. 新增搜索阶段指示器（"提取关键词 → 向量搜索 → 智能重排"）
3. 新增关键词显示（AI 提取的关键词标签）
4. 新增 AI 评分标识（Rerank 结果显示 ✨AI 标记）

### Phase 7: 前端设置界面

**修改文件**: `guiyi-client/GuiYi/SettingsView.swift`

在 AI 设置标签页新增：
- **总开关**："启用 AI 搜索增强" Toggle（一键关闭所有）
- **子开关**："启用关键词提取" Toggle
- **子开关**："启用智能重排" Toggle
- 关键词模型选择：本地（Ollama）或 API
- 本地模型名称输入框（如 `qwen2.5:9b`）
- 重排模型名称（默认 `BAAI/bge-reranker-v2-m3`）

**UI 设计要点**：
- 开关层级清晰：总开关 → 子开关
- 关闭总开关时，子选项灰显不可操作
- 开关状态持久化到本地配置

---

## 关键文件路径

| 操作 | 文件路径 |
|------|---------|
| 新增 | `guiyi-server/ai/rerank_service.py` |
| 修改 | `guiyi-server/ai/config_store.py` |
| 修改 | `guiyi-server/ai/ai_service.py` |
| 修改 | `guiyi-server/main_phase3.py` |
| 修改 | `guiyi-client/GuiYi/APIClient.swift` |
| 修改 | `guiyi-client/GuiYi/SearchView.swift` |
| 修改 | `guiyi-client/GuiYi/SettingsView.swift` |

---

## Fallback 策略

| 失败场景 | 处理方式 |
|---------|---------|
| AI 搜索总开关关闭 | 直接调用 `/api/search`，跳过所有 AI 流程 |
| 关键词提取开关关闭 | 使用原始查询搜索，跳过关键词增强 |
| Rerank 开关关闭 | 只做向量搜索，不重排 |
| 本地 Ollama 不可用 | 尝试 API 方式，或跳过关键词提取 |
| Rerank 模型未加载 | 跳过重排，返回原始向量结果 |
| 任何 AI 步骤失败 | 自动降级，确保搜索功能始终可用 |

---

## 提示词设计（待完善）

### 关键词提取提示词

需要解决的问题：
- **稳定性**：JSON 输出格式要稳定，不要输出多余内容
- **准确性**：提取的关键词要有搜索价值，不要过度泛化
- **意图识别**：区分"找文档"、"找某个概念"、"找时间范围内文档"等

初步设计：
```
分析用户搜索查询，提取关键信息。

查询：{query}

请分析并返回：
1. 核心关键词（3-5个，保留原始语义）
2. 搜索意图（查找文档/问题求解/浏览探索）
3. 可能的时间范围（如果有）
4. 可能的数据源范围（如果用户提到）

严格按以下 JSON 格式返回，不要添加其他内容：
{"keywords": ["词1", "词2"], "intent": "意图", "time_range": "时间", "source_hint": "来源"}

注意：
- 关键词保持原词或相近词，不要替换成通用词
- 如果查询本身已经很精确，直接提取核心词汇
- 不要臆造用户没说的信息
```

---

## 验证方案

1. **后端测试**：
   ```bash
   # 测试 AI 搜索端点（开关开启）
   curl -X POST http://localhost:8765/api/ai-search \
     -H "Content-Type: application/json" \
     -d '{"query": "深化金融服务", "limit": 20}'
   
   # 测试开关关闭时的普通搜索
   curl -X POST http://localhost:8765/api/ai-search \
     -H "Content-Type: application/json" \
     -d '{"query": "深化金融服务", "enable_ai_enhance": false}'
   ```

2. **功能测试**：
   - 开启 AI 增强 → 搜索"深化金融服务" → 检查目标文档排名提升
   - 关闭总开关 → 搜索应直接走向量搜索，无 AI 处理
   - 关闭关键词提取 → 搜索查询不被增强
   - 关闭 Rerank → 结果按原始向量分数排序
   - 搜索阶段指示器正常显示（开关开启时）
   - AI 关键词标签正确显示

3. **本地模型测试**：
   - 确保 Ollama 运行 `qwen2.5:9b`
   - 测试关键词提取是否正常
   - 确保 bge-reranker-v2-m3 模型已下载

4. **设置测试**：
   - 打开设置 → 检查开关层级清晰
   - 关闭总开关 → 子选项灰显
   - 配置本地模型名称 → 保存生效