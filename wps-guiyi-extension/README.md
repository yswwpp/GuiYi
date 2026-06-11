# WPS GuiYi Sync Extension

Chrome 扩展，用于将 WPS 在线文档（kdocs.cn）同步到 GuiYi 知识管理系统。

## 功能

- 自动检测 WPS 在线文档页面
- 提取文档内容（文字/表格/演示文稿）
- 推送到 GuiYi 后端建立索引
- 支持增量同步

## 开发

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建
npm run build

# 打包为 .crx
npm run package
```

## 使用

1. 在 Chrome 开发者模式下加载 `build/chrome-mv3-prod` 目录
2. 打开任意 kdocs.cn 文档
3. 点击插件图标，点击"同步"按钮
4. 文档将被索引到 GuiYi 系统

## 架构

- Content Script: DOM 解析与提取
- Background: 消息路由与 API 通信
- Popup: 同步状态与操作界面
- 后端: GuiYi FastAPI (/api/wps/*)