# 本地图片索引技术方案

> GuiYi 项目本地文件夹图片语义索引方案（MLX + Qwen2-VL）

---

## 概述

GuiYi 现有本地文件索引已经支持 Markdown、TXT、PDF、Word、Excel、PPT 等文本文档。图片本身不能直接进入当前 `txtai` 文本向量索引，因此图片索引采用“图片转文本，再复用文本索引”的方案：

1. 本地文件适配器扫描图片文件。
2. 使用本机 MLX 运行 Qwen2-VL 视觉语言模型。
3. 为每张图片生成中文描述、标签和可选 OCR/图中文字摘要。
4. 将生成文本写入现有文档 `content` 字段。
5. 复用现有 `IndexManager`、`sync_metadata` 和搜索接口完成检索。

该方案只读取图片文件，不修改原图，不复制原图到 Obsidian。搜索结果通过 `file://` 路径定位原始图片。

---

## 目标

### 需要实现

- 支持本地目录中的 `.jpg`、`.jpeg`、`.png`、`.webp`、`.bmp` 图片索引。
- 使用本地部署的 `mlx-community/Qwen2-VL-7B-Instruct-4bit` 生成中文图片描述和标签。
- 复用已有本地文件增量同步机制，通过文件大小、修改时间和内容哈希避免重复推理。
- 将图片描述、标签、文件名、相对路径一起纳入文本向量索引。
- 搜索结果保持现有结构：`title`、`url`、`source=local`、`account`、`text`。

### 暂不实现

- 不做以图搜图，不存储 CLIP 视觉向量。
- 不把原图保存到 `data/obsidian_vault/`。
- 不在第三方平台图片附件上启用该能力，第一阶段只处理本地目录图片。
- 不在前端新增图片预览组件，搜索结果先沿用文件路径打开方式。

---

## 当前项目基础

### 已有链路

1. `LocalDirectoryStore` 读取本地目录配置。
2. `LocalFileAdapter` 按目录配置扫描文件。
3. 对文本文档，现有 parser 提取文本；对图片，新增 `ImageParser` 调用 VLM 生成描述和标签。
4. `sync_local_files` 做增量判断、批量索引和同步元数据更新。
5. `IndexManager / txtai` 写入文本向量索引。
6. `SyncMetadata / MySQL` 记录 `content_hash`、`file_size`、`file_mtime`、`ai_summary`、`ai_tags`。
7. `/api/search` 复用现有搜索接口返回结果。

### 相关模块

| 模块 | 当前职责 | 图片索引改造点 |
|-----|---------|---------------|
| `guiyi_server/storage/local_directory_store.py` | 存储本地目录、文件类型、排除规则 | 增加图片扩展名支持，建议默认不开启或由用户显式选择 |
| `guiyi_server/adapters/local_file_adapter.py` | 扫描目录并按扩展名选择 parser | 增加图片扩展名和 `ImageParser` 映射 |
| `guiyi_server/parsers/` | 文本文档解析 | 新增 `image_parser.py`，把图片描述转换为文本 |
| `guiyi_server/ai/` | AI 摘要、关键词、重排 | 新增 `image_captioner.py`，封装 MLX VLM 推理 |
| `guiyi_server/guiyi_server/app.py` | `sync_local_files` 本地文件同步 | 图片沿用该函数，按文件元数据快速跳过 |
| `guiyi_server/index/txtai_index.py` | 文本向量索引 | 不需要增加视觉索引，继续索引生成文本 |
| `guiyi_server/sync/metadata.py` | 记录同步状态、文件大小、mtime、AI 摘要标签 | 复用 `file_size`、`file_mtime`、`content_hash`、`ai_summary`、`ai_tags` |

---

## 图片索引范围

### 支持类型

| 类型 | 扩展名 | 处理方式 | 备注 |
|-----|--------|---------|------|
| JPEG | `.jpg`, `.jpeg` | Qwen2-VL 生成描述和标签 | 第一阶段支持 |
| PNG | `.png` | Qwen2-VL 生成描述和标签 | 支持截图、透明图 |
| WebP | `.webp` | Qwen2-VL 生成描述和标签 | 第一阶段支持 |
| BMP | `.bmp` | Qwen2-VL 生成描述和标签 | 文件可能较大 |
| HEIC | `.heic`, `.heif` | 可选支持 | 需要额外依赖 `pillow-heif`，第一阶段可暂缓 |

### 配置策略

图片索引建议作为本地目录的可选文件类型开启，不建议无条件加入所有已有目录的默认类型。原因：

- 图片推理耗时远高于文本解析。
- 用户目录可能包含大量低价值图片、缓存图、表情包。
- 初次全量索引会触发模型下载和较长推理任务。

推荐在新增或更新目录时显式加入图片扩展名：

```json
{
  "file_types": [".md", ".txt", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".webp"]
}
```

---

## 模型与环境

### 推荐模型

| 项目 | 推荐值 |
|-----|--------|
| 推理框架 | MLX |
| VLM 工具包 | `mlx-vlm` |
| 模型 | `mlx-community/Qwen2-VL-7B-Instruct-4bit` |
| 本地模型目录 | `/Users/yswwpp/dev/docker_file_sharing/GuiYi/models/mlx-community/Qwen2-VL-7B-Instruct-4bit` |
| 图片处理 | `Pillow` |
| 运行机器 | Mac M4 Pro 24GB 或以上 |

### 依赖安装

必须遵守 GuiYi 项目规则：在 `guiyi-server/.venv` 中安装，使用 `uv`，不要在根目录创建虚拟环境，不要直接使用 `pip`。

```bash
cd guiyi-server
source .venv/bin/activate
uv pip install mlx mlx-vlm Pillow
```

如果后续支持 HEIC：

```bash
cd guiyi-server
source .venv/bin/activate
uv pip install pillow-heif
```

### 模型下载与存储目录

当前向量索引配置文件位于 `guiyi-server/data/index/documents/config.json`，其中记录的向量模型是 `BAAI/bge-m3`。但 `data/index` 是 txtai/faiss 索引目录，不应该混放大模型权重。

GuiYi 程序用到的所有模型统一放到外部共享模型目录：

```text
/Users/yswwpp/dev/docker_file_sharing/GuiYi/models/
```

该目录是项目的统一模型目录，图片 VLM、向量模型、rerank 模型等后续都应放在这里。例如：

```text
/Users/yswwpp/dev/docker_file_sharing/GuiYi/models/
├── BAAI/
│   └── bge-m3/                                  # 可选：向量模型本地化后的位置
└── mlx-community/
    └── Qwen2-VL-7B-Instruct-4bit/               # 图片描述模型
```

图片模型必须先下载到本地目录，再由 `ImageCaptioner` 使用本地路径加载，避免运行时下载到默认的 `~/.cache/huggingface/`：

```bash
cd guiyi-server
source .venv/bin/activate

mkdir -p /Users/yswwpp/dev/docker_file_sharing/GuiYi/models/mlx-community
huggingface-cli download mlx-community/Qwen2-VL-7B-Instruct-4bit \
  --local-dir /Users/yswwpp/dev/docker_file_sharing/GuiYi/models/mlx-community/Qwen2-VL-7B-Instruct-4bit
```

加载时不使用远程模型 ID，而使用本地路径：

```python
model_path = "/Users/yswwpp/dev/docker_file_sharing/GuiYi/models/mlx-community/Qwen2-VL-7B-Instruct-4bit"
```

如果未来把向量模型也本地化，应将 `GUIYI_EMBEDDING_MODEL_PATH` 指向：

```text
/Users/yswwpp/dev/docker_file_sharing/GuiYi/models/BAAI/bge-m3
```

### 配置项

建议新增环境变量，避免图片模型默认强制加载：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `GUIYI_MODEL_DIR` | `/Users/yswwpp/dev/docker_file_sharing/GuiYi/models` | GuiYi 程序统一模型目录 |
| `GUIYI_IMAGE_INDEX_ENABLED` | `false` | 是否启用图片索引 |
| `GUIYI_IMAGE_VLM_MODEL` | `${GUIYI_MODEL_DIR}/mlx-community/Qwen2-VL-7B-Instruct-4bit` | MLX VLM 本地模型路径 |
| `GUIYI_IMAGE_MAX_SIDE` | `1024` | 推理前最长边缩放上限 |
| `GUIYI_IMAGE_MAX_TOKENS` | `512` | 单张图片输出最大 token |
| `GUIYI_IMAGE_TEMPERATURE` | `0.2` | 生成温度 |
| `GUIYI_IMAGE_BATCH_SIZE` | `1` | 第一阶段建议单张处理 |
| `GUIYI_IMAGE_MIN_SIZE_BYTES` | `1024` | 过小图片跳过 |
| `GUIYI_IMAGE_IDLE_UNLOAD_MINUTES` | `5` | 图片描述模型空闲释放时间，默认 5 分钟，可在设置中调整 |

模型空闲释放时间默认 5 分钟，但需要作为设置项支持修改。

---

## 图片描述服务设计

### 模块位置

新增：

```text
guiyi-server/guiyi_server/ai/image_captioner.py
guiyi-server/guiyi_server/parsers/image_parser.py
```

### `ImageCaptioner` 职责

`ImageCaptioner` 只负责图片到结构化文本结果：

```python
{
    "description": "一段中文图片描述",
    "tags": ["截图", "界面", "按钮", "设置"],
    "ocr_text": "可选：图片中文字",
    "raw_output": "模型原始输出"
}
```

设计要求：

- 模型懒加载：第一次处理图片时才加载 MLX 模型。
- 单例复用：同一次同步任务内复用模型实例，避免每张图片重复加载。
- 空闲释放：连续一段时间没有调用图片描述功能时，释放模型、processor 和相关缓存占用；再次使用时重新加载模型。
- 空闲释放时间默认 5 分钟，但需要在设置中可配置。
- 只读打开图片：使用 `Image.open(file_path).convert("RGB")`。
- 大图缩放：最长边超过 `GUIYI_IMAGE_MAX_SIDE` 时等比缩放后推理。
- 解析容错：优先解析 JSON，失败时回退到“描述：/标签：”格式，再失败则整段作为描述。
- 异常隔离：单张图片失败不影响整个目录同步。

### 内存生命周期

图片描述模型占用内存明显高于普通文本 parser，不能在后端启动时常驻加载。推荐 `ImageCaptioner` 维护以下状态：

```python
class ImageCaptioner:
    def __init__(self, idle_unload_minutes: int = 5):
        self.model = None
        self.processor = None
        self.config = None
        self.last_used_at = 0.0
        self.idle_unload_seconds = max(1, idle_unload_minutes) * 60

    def describe_and_tag(self, image_path: str) -> dict:
        self._ensure_loaded()
        self.last_used_at = time.monotonic()
        try:
            return self._generate(image_path)
        finally:
            self.last_used_at = time.monotonic()

    def unload_if_idle(self) -> None:
        if self.model is None:
            return
        if time.monotonic() - self.last_used_at < self.idle_unload_seconds:
            return

        self.model = None
        self.processor = None
        self.config = None
        gc.collect()
```

释放检查可以放在两处：

1. 每次图片处理前后调用 `unload_if_idle()`。
2. 后端启动一个轻量定时任务，每 60 秒检查一次是否超过配置的空闲释放时间。

释放动作只释放图片描述模型，不影响 `IndexManager` 的向量模型和 txtai 索引。

### Prompt 模板

建议让模型输出 JSON，便于解析：

```text
请用中文分析这张图片。你需要生成可用于本地知识库搜索的内容。

要求：
1. 描述图片主体、场景、颜色、文字、界面元素、动作、物品和可能用途。
2. 如果图片中有清晰可读的文字，请提取到 ocr_text；如果没有，返回空字符串。
3. 提取 5 到 12 个中文关键词标签。
4. 不要编造图片中不存在的信息。

请只返回 JSON：
{
  "description": "图片描述",
  "tags": ["标签1", "标签2"],
  "ocr_text": "图片中文字或空字符串"
}
```

---

## `ImageParser` 设计

`ImageParser` 对外保持和现有 parser 一致的接口：`parse(file_path: str) -> str`。

输出文本建议如下：

```text
[图片描述]
这是一张 macOS 应用界面截图，画面中展示了...

[图片标签]
macOS, 应用界面, 搜索, 设置, 截图

[图片文字]
搜索, 同步, 本地目录

[图片文件信息]
文件名: example.png
扩展名: png
```

这样可以直接被现有 `sync_local_files` 读取、计算 `content_hash` 并写入 `IndexManager`。

### 文档记录字段

本地图片文档记录沿用当前本地文件结构：

```python
{
    "id": "local_{directory_id}_{path_md5}",
    "title": "example.png",
    "content": "",
    "url": "file:///Users/xxx/Pictures/example.png",
    "source": "local",
    "account": directory.id,
    "doc_type": "file",
    "obj_type": "png",
    "file_path": "/Users/xxx/Pictures/example.png",
    "directory_name": "图片目录",
    "relative_path": "screenshots/example.png",
    "store_locally": False
}
```

建议额外在进入索引前补充：

```python
doc["content_kind"] = "image_caption"
doc["ai_summary"] = description
doc["ai_tags"] = tags
```

当前 `IndexManager` 只保存基础元数据，第一阶段可以不修改搜索结果结构；如果前端需要展示“图片”徽标，再扩展 `metadata.json` 的字段。

---

## 增量同步策略

图片索引必须避免重复调用 VLM。沿用现有 `sync_local_files` 的快速跳过逻辑：

1. 扫描本地目录。
2. 判断文件扩展名是否在目录配置的 `file_types` 中。
3. 如果扩展名未启用，直接跳过。
4. 如果扩展名已启用，读取上次同步状态。
5. 如果已有同步状态，并且 `file_size` 与 `file_mtime` 都未变化，直接快速跳过，不加载图片、不调用模型。
6. 如果是新增图片，或文件大小/修改时间发生变化，读取图片并调用 Qwen2-VL 生成描述、标签和可选图中文字。
7. 用生成文本计算 `content_hash`。
8. 如果是新增图片或 `content_hash` 变化，更新 `txtai` 索引和 `sync_metadata`。
9. 如果 `content_hash` 未变化，只更新文件信息，供下次快速跳过。

### 哈希口径

图片文件内容无法直接进入文本索引，因此有两个可选哈希口径：

| 口径 | 优点 | 缺点 | 建议 |
|-----|------|------|------|
| 生成文本 MD5 | 与现有 `sync_local_files` 完全一致 | prompt 或模型变化会导致同图重新索引 | 第一阶段使用 |
| 图片二进制 MD5 | 能准确识别原图变化 | 需要读取原图字节，和当前文本同步逻辑不同 | 后续优化 |

第一阶段建议继续使用生成文本 MD5。模型版本或 prompt 变化需要全量重建时，可以通过清理对应目录的 `sync_metadata` 或增加 `caption_version` 触发。

### 元数据保存

复用 `sync_metadata` 表：

| 字段 | 图片索引用法 |
|-----|-------------|
| `content_hash` | 图片描述文本 MD5 |
| `file_size` | 原图文件大小 |
| `file_mtime` | 原图修改时间 |
| `ai_summary` | 图片中文描述 |
| `ai_tags` | 标签 JSON 字符串 |
| `last_modified` | 本次索引时间或文件 mtime |

---

## 索引文本结构

图片进入 `IndexManager` 的 `content` 应包含标题、相对路径、描述、标签和图中文字：

```python
index_content = f"""
{title}

[图片路径]
{relative_path}

[图片描述]
{description}

[图片标签]
{", ".join(tags)}

[图片文字]
{ocr_text}
""".strip()
```

原因：

- 标题会在 `IndexManager` 中被重复加权，文件名搜索仍然有效。
- 相对路径常包含业务语义，例如 `screenshots/支付流程/`。
- 标签适合短词检索。
- 图片中文字适合搜索截图、票据、白板、页面截图。

---

## API 与前端影响

### 目录文件类型接口

`GET /api/local-directories/file-types` 建议返回图片类型，但前端应把图片类型作为可选项展示：

```json
{
  "file_types": [".md", ".txt", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".webp", ".bmp"],
  "default_exclude_patterns": [".git", "node_modules"]
}
```

### 添加目录

```bash
curl -X POST http://localhost:8765/api/local-directories \
  -H "Content-Type: application/json" \
  -d '{
    "name": "知识库图片与文档",
    "path": "/Users/xxx/Documents/Knowledge",
    "file_types": [".md", ".txt", ".pdf", ".jpg", ".jpeg", ".png", ".webp"],
    "exclude_patterns": [".git", "node_modules", ".venv"],
    "enabled": true,
    "max_depth": 10,
    "max_file_size_mb": 20
  }'
```

### 更新已有目录

已有目录不会自动包含新增图片类型，需要更新 `file_types`：

```bash
curl -X PATCH http://localhost:8765/api/local-directories/{dir_id} \
  -H "Content-Type: application/json" \
  -d '{
    "file_types": [".md", ".txt", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".webp"]
  }'
```

### 搜索结果

搜索接口无需变更。图片结果示例：

```json
{
  "id": "local_xxx_abcd1234",
  "title": "meeting-whiteboard.png",
  "url": "file:///Users/xxx/Documents/meeting-whiteboard.png",
  "source": "local",
  "account": "local_xxx",
  "score": 0.73,
  "text": "[图片描述]\n这是一张会议白板照片..."
}
```

---

## 实施步骤

### 第一阶段：最小可用

1. 在 `requirements.txt` 增加可选图片索引依赖：`mlx`、`mlx-vlm`、`Pillow`。
2. 新增 `guiyi_server/ai/image_captioner.py`。
3. 新增 `guiyi_server/parsers/image_parser.py`。
4. 在 `LocalFileAdapter.PARSERS` 增加图片扩展名映射。
5. 在 `LocalDirectoryStore.get_supported_file_types()` 返回图片扩展名。
6. 保持 `sync_local_files` 主流程不变，让图片像普通 parser 一样返回文本。
7. 使用小目录测试 5 到 10 张图片，确认搜索可命中。

### 第二阶段：质量与稳定性

1. 增加图片模型启用开关，未启用时图片 parser 返回空并记录日志。
2. 增加模型加载健康检查接口或状态字段。
3. 增加 caption 解析单元测试，覆盖 JSON 输出、中文冒号输出、解析失败回退。
4. 在 `metadata.json` 中保存 `content_kind=image_caption`，方便前端展示图片类型。
5. 增加批处理或并发队列，但默认并发仍保持 1，避免内存波动。

### 第三阶段：扩展能力

1. 支持 HEIC/HEIF。
2. 对截图类图片引入专门 prompt，强化 UI 文字和控件提取。
3. 支持手动重建某个目录的图片描述。
4. 增加图片缩略图预览和“在 Finder 中显示”前端动作。
5. 引入 CLIP 视觉向量，实现以图搜图。

---

## 质量与测试

### 单元测试

建议新增：

```text
guiyi-server/tests/test_image_parser.py
guiyi-server/tests/test_image_captioner_parse.py
```

测试点：

- 图片扩展名能被 `LocalFileAdapter` 扫描。
- `ImageParser.parse()` 返回非空文本。
- JSON 格式输出能解析为 `description/tags/ocr_text`。
- 非 JSON 输出能回退解析。
- 图片模型未启用时不会导致整个同步失败。

### 手动验证

```bash
cd guiyi-server
source .venv/bin/activate
python main.py
```

触发同步：

```bash
curl -X POST http://localhost:8765/api/sync \
  -H "Content-Type: application/json" \
  -d '{"source": "local", "account": "{dir_id}"}'
```

搜索图片语义：

```bash
curl -X POST http://localhost:8765/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "白板上的项目计划", "source": "local", "limit": 10}'
```

---

## 性能建议

| 场景 | 建议 |
|-----|------|
| 初次索引大量图片 | 先用小目录验证，再逐步扩大范围 |
| 4K 或更大图片 | 推理前最长边缩放到 1024 |
| 截图很多 | 保留 `ocr_text`，截图搜索主要依赖文字 |
| 图片过小 | 小于 `GUIYI_IMAGE_MIN_SIZE_BYTES` 可跳过 |
| 模型加载慢 | 后端启动不加载，首次图片同步懒加载 |
| 同步中断 | 依靠 `sync_metadata` 继续增量处理 |

---

## 风险与处理

| 风险 | 影响 | 处理 |
|-----|------|------|
| 首次模型下载较大 | 初次运行等待时间长 | 文档说明模型缓存位置，允许提前下载 |
| VLM 输出格式不稳定 | 标签解析失败 | JSON 优先，正则回退，原始输出兜底 |
| 大量图片同步慢 | 同步任务耗时增加 | 图片类型显式开启，批量大小默认 1 |
| Python/依赖兼容问题 | MLX 安装或导入失败 | 将图片依赖视为可选能力，未安装时普通文本索引不受影响 |
| 图片描述不准确 | 搜索召回质量波动 | 调整 prompt，允许重建图片 caption |
| 敏感图片进入索引 | 本地搜索可见敏感描述 | 继续依赖目录白名单和禁止路径，不自动索引系统目录 |

---

## 与原方案的适配差异

外部技术方案的核心结论是正确的：使用 MLX + Qwen2-VL 将图片生成中文描述和标签，再送入已有向量索引。结合 GuiYi 当前项目，需要做以下调整：

- 环境创建不新建独立 `mlx_image_index`，而是在 `guiyi-server/.venv` 中用 `uv` 安装依赖。
- 不新增独立 `add_to_index` 脚本，改为复用 `LocalFileAdapter -> sync_local_files -> IndexManager`。
- 不直接遍历任意目录，目录来源仍由 `LocalDirectoryStore` 管理。
- 不修改 `data/` 运行时目录。
- 图片原文件不复制、不写回，只保存生成文本和同步元数据。
- 图片能力默认建议显式开启，避免影响已有文本文档同步性能。

---

## 相关文档

- [本地文件索引规则](./local-file-index-rules.md)
- [需求与技术方案](./归一GuiYi-需求与技术方案.md)
- [架构说明](./architecture.md)

---

**文档版本**: 1.0  
**最后更新**: 2026-06-06  
**适用范围**: GuiYi 本地目录图片索引  
**推荐模型**: `mlx-community/Qwen2-VL-7B-Instruct-4bit`
