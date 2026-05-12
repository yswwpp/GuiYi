# GuiYi（归一）

> 本地优先的个人知识收集与检索系统

## 项目简介

**归一 GuiYi** 是一个本地优先的知识管理系统，核心功能：

- 🚀 **一键搜索**：`Cmd + J` 快捷键呼出，Spotlight 风格界面
- 🔍 **语义搜索**：支持自然语言查询（"我上周存的那篇 Python 文章"）
- 📚 **多源聚合**：支持飞书、WPS、印象笔记、夸克网盘、网页
- 🔄 **增量同步**：智能检测变更，只更新变化的部分
- 🔐 **本地优先**：所有数据处理在本地完成，隐私安全

## 当前状态

**已完成**（2026/04/09）：
- ✅ 飞书知识库同步（189 个文档）
- ✅ 全局快捷键搜索界面
- ✅ Spotlight 风格交互

## 快速开始

### 1. 启动后端服务

```bash
cd guiyi-server
source .venv/bin/activate
python main_phase3.py
```

服务地址：http://localhost:8765

### 2. 启动前端应用

```bash
cd guiyi-client
open GuiYi.xcodeproj
# 在 Xcode 中按 Cmd+R 运行
```

### 3. 使用搜索

1. 按 **`Cmd + J`** 唤出搜索框
2. 输入关键词搜索
3. 点击结果打开原文档

## 核心特性

### 索引优先策略

| 数据源 | 存储策略 | 说明 |
|--------|----------|------|
| 飞书 | 仅索引 | 原文档保留在飞书 |
| WPS | 仅索引 | 原文件在本地 |
| 网页 | 完整存储 | 存入 Obsidian |

### 技术架构

```
前端 (Swift/SwiftUI) ←→ HTTP API ←→ 后端 (Python/FastAPI)
                                          ↓
                                    txtai + BAAI/bge-m3
```

## 项目结构

```
GuiYi/
├── guiyi-server/          # Python 后端服务
│   ├── adapters/          # 数据源适配器（飞书等）
│   ├── sync/              # 同步引擎
│   ├── index/             # 向量索引管理
│   └── storage/           # Obsidian 存储
├── guiyi-client/          # Swift 前端应用
├── data/                  # 运行时数据（索引等）
└── docs/                  # 项目文档
```

## 开发进度

详见 [开发进度文档](./docs/phase4-progress-20260409.md)

### 已完成

- [x] 飞书 OAuth 2.0 用户授权
- [x] 飞书知识库递归获取
- [x] 向量索引（BAAI/bge-m3）
- [x] 全局快捷键（Cmd+J）
- [x] Spotlight 风格搜索界面
- [x] 失去焦点自动关闭

### 待完成

- [ ] 电子表格内容获取（需额外授权）
- [ ] 用户令牌刷新机制
- [ ] 定时增量同步
- [ ] 后端服务自启动

## 文档

- [需求与技术方案](./docs/归一GuiYi-需求与技术方案.md)
- [Phase 4 进度](./docs/phase4-progress-20260409.md)
- [API 接口文档](./docs/api-reference.md)

## 许可证

MIT License
