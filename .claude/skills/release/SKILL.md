# Release Skill

版本发布工作流，确保发布过程标准化和可追溯。

## 触发时机

- 完成重要功能开发
- 修复关键 Bug
- 定期版本迭代

## 发布流程

### 1. 发布前检查

- [ ] 所有测试通过
  ```bash
  cd guiyi-server
  source .venv/bin/activate
  pytest

  cd ../guiyi-client
  xcodebuild test -scheme GuiYi
  ```

- [ ] 代码审查完成
- [ ] 文档更新（README、CHANGELOG）
- [ ] 版本号更新（语义化版本）

### 2. 版本号规范

格式：`MAJOR.MINOR.PATCH`

- **MAJOR**：重大架构变更、不兼容更新
- **MINOR**：新功能、向后兼容
- **PATCH**：Bug 修复、小改进

示例：
- `0.1.0` → `0.1.1`：修复网页抓取 Bug
- `0.1.1` → `0.2.0`：新增飞书多账号支持
- `0.2.0` → `1.0.0`：正式发布版本

### 3. 构建发布版本

**后端打包**：
```bash
cd guiyi-server
source .venv/bin/activate
pyinstaller main.py --name guiyi-backend
```

**前端打包**：
```bash
cd guiyi-client
xcodebuild -project GuiYi.xcodeproj \
  -scheme GuiYi \
  -configuration Release \
  -archivePath build/GuiYi.xcarchive \
  archive
```

### 4. 创建 Git 标签

```bash
git tag -a v0.1.0 -m "Release v0.1.0: 首个可用版本"
git push origin v0.1.0
```

### 5. 生成 CHANGELOG

```markdown
# Changelog

## [0.1.0] - 2026-04-04

### Added
- 网页抓取功能（trafilatura）
- txtai 语义索引
- FastAPI 后台服务
- SwiftUI 悬浮窗 UI
- 全局快捷键支持

### Changed
- 项目结构调整为 Monorepo

### Fixed
- 修复图片下载失败问题
```

### 6. 发布检查清单

#### 后端发布检查

- [ ] Python 依赖版本锁定（requirements.txt）
- [ ] 配置文件模板完整
- [ ] API 文档更新
- [ ] 数据库迁移脚本（如有）

#### 前端发布检查

- [ ] Swift 版本兼容性
- [ ] macOS 版本支持（macOS 12.0+）
- [ ] 应用签名和公证（可选）
- [ ] App 图标和资源完整

### 7. 部署发布

**本地测试部署**：
```bash
# 启动后端服务
cd guiyi-server
source .venv/bin/activate
python main.py

# 运行前端应用
open guiyi-client/build/Release/GuiYi.app
```

**生产部署**：
```bash
# 配置 launchd 自动启动
cp ~/Library/LaunchAgents/com.guiyi.service.plist
launchctl load ~/Library/LaunchAgents/com.guiyi.service.plist

# 安装前端应用到 /Applications
cp -r guiyi-client/build/Release/GuiYi.app /Applications/
```

## 回滚流程

如果发布后发现问题：

1. 停止服务：
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.guiyi.service.plist
   ```

2. 回退到上一版本：
   ```bash
   git checkout v0.0.9
   ```

3. 重新构建和部署

## 发布模板

### GitHub Release Notes

```markdown
# GuiYi v0.1.0

## 🎉 首个可用版本

### ✨ 新功能
- 网页一键保存到 Obsidian
- 语义搜索（自然语言查询）
- 全局快捷键唤醒

### 📦 安装方式
1. 下载 `GuiYi.app`
2. 拖拽到 Applications 文件夹
3. 双击运行

### 🔧 配置
参考 [README.md](./README.md)

### 📝 已知问题
- 飞书多账号支持开发中
- WPS 文件监听待实现
```

## 使用方法

```bash
# 开始发布流程
/release

# 创建指定版本
/release 0.2.0
```
