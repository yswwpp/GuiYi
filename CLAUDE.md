# GuiYi 项目记忆

> 本地优先的个人知识收集与检索系统

---

## 项目目的

**GuiYi（归一）** 是一个本地优先的知识管理系统，核心场景：

- **一键保存**：全局快捷键呼出，粘贴链接即保存
- **多源聚合**：支持飞书、本地文件、印象笔记、夸克网盘、网页
- **索引优先**：三方平台内容只建索引，原文档保留在原平台
- **增量同步**：智能检测变更，只更新变化的部分
- **语义检索**：支持自然语言搜索
- **AI 增强**：大文件自动生成摘要和标签

---

## 仓库地图

```
GuiYi/
├── guiyi-server/          # Python 后端服务（FastAPI + txtai）
│   ├── adapters/          # 数据源适配器
│   ├── ai/                # AI 服务（摘要、标签生成）
│   ├── sync/              # 同步引擎
│   ├── index/             # 索引管理
│   ├── parsers/           # 文件解析器
│   └── storage/           # 存储管理
├── guiyi-client/          # Swift 前端（SwiftUI）
│   ├── Views/             # UI 视图
│   ├── Services/          # API 客户端
│   └── Utils/             # 工具类
├── data/                  # 运行时数据（Git 忽略）
│   ├── index/             # txtai 索引
│   └── obsidian_vault/    # Obsidian 存储
├── docs/                  # 项目文档
└── .claude/               # Claude Code 配置
```

---

## 规则与命令

### 开发环境

**Python 环境**：
```bash
cd guiyi-server
source .venv/bin/activate  # 激活虚拟环境
uv pip install <package>   # 使用 uv 安装依赖
```

**Swift 环境**：
- 使用 Xcode 打开 `guiyi-client/GuiYi.xcodeproj`
- 不需要手动配置环境

### 架构约束

1. **前后端分离**：
   - 前端（Swift）负责 UI 交互、快捷键、状态栏
   - 后端（Python）负责数据处理、同步、索引
   - 通过 HTTP API 通信（`http://localhost:8765`）

2. **索引优先策略**：
   - 三方平台（飞书、WPS、印象笔记、夸克）仅索引摘要
   - 网页内容完整存储到 Obsidian
   - 同步元数据存储在 SQLite

3. **增量同步机制**：
   - 通过内容哈希（MD5）检测变更
   - 记录同步状态到 `data/sync_metadata.sqlite`
   - 只更新变化的文档

### 允许的操作

- ✅ 在 `guiyi-server/` 下开发 Python 后端
- ✅ 在 `guiyi-client/` 下开发 Swift 前端
- ✅ 修改 `docs/` 下的文档
- ✅ 更新 `.claude/` 下的配置
- ✅ 运行测试和调试

### 禁止的操作

- ❌ 不要直接修改 `data/` 目录（运行时数据）
- ❌ 不要在根目录创建虚拟环境（在 `guiyi-server/` 下创建）
- ❌ 不要使用 pip 安装依赖（使用 uv）
- ❌ 不要在前后端项目中混合代码

### 常用命令

**后端开发**：
```bash
# 启动开发服务器
cd guiyi-server
source .venv/bin/activate
python main.py

# 运行测试
pytest

# 安装依赖
uv pip install -r requirements.txt
```

**前端开发**：
```bash
# 在 Xcode 中运行项目
# 或使用命令行
cd guiyi-client
xcodebuild -project GuiYi.xcodeproj -scheme GuiYi
```

### 技术栈

**后端**：
- FastAPI + uvicorn
- trafilatura（网页抓取）
- txtai + BAAI/bge-m3（语义索引）
- SQLite + SQLAlchemy
- APScheduler（定时任务）
- watchdog（文件监听）

**前端**：
- Swift + SwiftUI
- HotKey（快捷键）
- URLSession（API 通信）

---

## 重要注意事项

1. **凭证管理**：所有 API Token、Cookie 使用 macOS Keychain 存储（keyring 库）
2. **数据安全**：索引数据存储在本地，不上传云端
3. **Obsidian 路径**：网页内容存储在 `data/obsidian_vault/inbox/`
4. **API 端口**：后端服务监听 `http://localhost:8765`
5. **Python 版本**：使用 Python 3.11+

---

## 相关文档

- [需求与技术方案](./docs/归一GuiYi-需求与技术方案.md)
- [飞书文档索引规则](./docs/feishu-index-rules.md)
- [本地文件索引规则](./docs/local-file-index-rules.md)
- [架构决策记录](./docs/decisions/)
- [运维手册](./docs/runbooks/)
