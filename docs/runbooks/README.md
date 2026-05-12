# GuiYi 运维手册

本文档包含 GuiYi 系统的部署、监控、故障排查等运维操作指南。

---

## 目录

1. [部署指南](#部署指南)
2. [启动和停止服务](#启动和停止服务)
3. [监控和日志](#监控和日志)
4. [故障排查](#故障排查)
5. [备份和恢复](#备份和恢复)

---

## 部署指南

### 系统要求

- macOS 12.0+
- Python 3.11+
- Xcode 14+（仅开发需要）

### 后端部署

1. **安装依赖**
   ```bash
   cd guiyi-server
   uv venv
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

2. **配置 launchd 自动启动**
   ```bash
   # 复制配置文件
   cp docs/runbooks/com.guiyi.service.plist ~/Library/LaunchAgents/

   # 加载服务
   launchctl load ~/Library/LaunchAgents/com.guiyi.service.plist

   # 验证服务状态
   launchctl list | grep guiyi
   ```

3. **验证服务运行**
   ```bash
   curl http://localhost:8765/api/status
   ```

### 前端部署

1. **构建应用**
   ```bash
   cd guiyi-client
   xcodebuild -project GuiYi.xcodeproj \
     -scheme GuiYi \
     -configuration Release \
     -archivePath build/GuiYi.xcarchive \
     archive
   ```

2. **安装到 Applications**
   ```bash
   cp -r build/Release/GuiYi.app /Applications/
   ```

---

## 启动和停止服务

### 后端服务

**启动服务**：
```bash
launchctl load ~/Library/LaunchAgents/com.guiyi.service.plist
```

**停止服务**：
```bash
launchctl unload ~/Library/LaunchAgents/com.guiyi.service.plist
```

**重启服务**：
```bash
launchctl unload ~/Library/LaunchAgents/com.guiyi.service.plist
launchctl load ~/Library/LaunchAgents/com.guiyi.service.plist
```

**手动启动（调试用）**：
```bash
cd guiyi-server
source .venv/bin/activate
python main.py
```

### 前端应用

- 双击 `/Applications/GuiYi.app` 启动
- 或使用 Spotlight 搜索 "GuiYi"

---

## 监控和日志

### 查看后端日志

**实时日志**：
```bash
tail -f /tmp/guiyi.log
```

**错误日志**：
```bash
tail -f /tmp/guiyi.error.log
```

**历史日志**：
```bash
less /tmp/guiyi.log
```

### 查看服务状态

```bash
# 检查服务是否运行
launchctl list | grep guiyi

# 检查端口占用
lsof -i :8765

# 检查进程
ps aux | grep guiyi
```

### 监控索引状态

```bash
# 查看索引大小
du -sh data/index/

# 查看 SQLite 数据库大小
ls -lh data/sync_metadata.sqlite

# 查看同步状态
sqlite3 data/sync_metadata.sqlite "SELECT source, COUNT(*) FROM sync_metadata GROUP BY source;"
```

---

## 故障排查

### 问题 1：后端服务无法启动

**症状**：`launchctl list` 中看不到服务

**排查步骤**：

1. 检查配置文件是否存在
   ```bash
   ls ~/Library/LaunchAgents/com.guiyi.service.plist
   ```

2. 检查 Python 虚拟环境
   ```bash
   ls guiyi-server/.venv/bin/python
   ```

3. 查看错误日志
   ```bash
   cat /tmp/guiyi.error.log
   ```

4. 手动启动测试
   ```bash
   cd guiyi-server
   source .venv/bin/activate
   python main.py
   ```

**常见原因**：
- Python 路径不正确
- 依赖未安装
- 端口被占用

### 问题 2：前端无法连接后端

**症状**：前端显示"服务未运行"

**排查步骤**：

1. 检查后端服务状态
   ```bash
   curl http://localhost:8765/api/status
   ```

2. 检查防火墙设置
   - 系统偏好设置 → 安全性与隐私 → 防火墙

3. 检查 App Sandbox 权限
   - Xcode 项目设置 → Signing & Capabilities → App Sandbox
   - 确保启用 Outgoing Connections

### 问题 3：索引构建失败

**症状**：搜索无结果或报错

**排查步骤**：

1. 检查磁盘空间
   ```bash
   df -h
   ```

2. 检查向量模型是否下载
   ```bash
   ls -lh ~/.cache/huggingface/hub/
   ```

3. 查看错误日志
   ```bash
   grep "index" /tmp/guiyi.error.log
   ```

4. 重建索引（最后手段）
   ```bash
   rm -rf data/index/
   # 重启服务，自动重建
   ```

### 问题 4：飞书同步失败

**症状**：飞书文档无法索引

**排查步骤**：

1. 检查凭证配置
   ```bash
   security find-generic-password -s guiyi -a feishu_company_app_id
   ```

2. 检查 API 权限
   - 飞书开放平台 → 应用权限

3. 查看同步日志
   ```bash
   grep "feishu" /tmp/guiyi.log
   ```

---

## 备份和恢复

### 备份数据

**备份索引和元数据**：
```bash
# 创建备份目录
mkdir -p ~/Backup/GuiYi/$(date +%Y%m%d)

# 备份数据
cp -r data/ ~/Backup/GuiYi/$(date +%Y%m%d)/
```

**自动备份脚本**：
```bash
#!/bin/bash
# backup.sh
BACKUP_DIR=~/Backup/GuiYi/$(date +%Y%m%d)
mkdir -p $BACKUP_DIR
cp -r data/ $BACKUP_DIR/
echo "Backup completed: $BACKUP_DIR"
```

### 恢复数据

```bash
# 停止服务
launchctl unload ~/Library/LaunchAgents/com.guiyi.service.plist

# 恢复数据
cp -r ~/Backup/GuiYi/20260404/data/ ./

# 重启服务
launchctl load ~/Library/LaunchAgents/com.guiyi.service.plist
```

---

## 性能优化

### 索引优化

- 批量索引文档（避免逐条索引）
- 定期清理已删除文档的索引
- 调整向量模型参数（精度 vs 速度）

### 同步优化

- 增量同步，避免全量更新
- 合理设置同步频率（飞书：每天 1 次）
- 使用文件监听替代定时轮询（WPS）

---

## 安全建议

1. **定期更新依赖**
   ```bash
   uv pip install --upgrade $(uv pip list --outdated | awk '{print $1}')
   ```

2. **检查凭证泄露**
   ```bash
   # 不要将凭证提交到 Git
   git log --all --full-history -- "*.env" "*.pem" "credentials.json"
   ```

3. **限制 API 访问**
   - 后端只监听 localhost（127.0.0.1）
   - 不对外暴露端口

---

## 联系支持

如遇到无法解决的问题，请：
1. 查看日志文件
2. 搜索项目 Issue：https://github.com/your-repo/GuiYi/issues
3. 创建新 Issue 并附上日志信息
