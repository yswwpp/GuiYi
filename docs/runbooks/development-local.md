# GuiYi 本机开发调试指南

> 本文档定义 GuiYi 在本机开发时的隔离规则。目标是：开发实例可以使用接近真实的数据调试，但不影响本机部署实例。

---

## 核心原则

- **开发环境和部署环境完全隔离**：代码、配置、数据、模型、端口、MySQL schema 都分开。
- **开发配置不进 Git**：`.env.dev`、`guiyi-server.dev.env`、`data-dev/`、`models-dev/` 都是本机私有资产。
- **开发实例默认不跑定时同步**：需要验证同步时显式打开，避免误用真实凭证同步第三方数据。
- **真实数据只通过快照进入开发环境**：不要让开发后端直接连接部署数据目录。

---

## 环境边界

| 项目 | 部署环境 | 开发环境 |
|------|----------|----------|
| 后端代码 | `~/deploy/GuiYi/guiyi-server` | `~/dev/project/tools/GuiYi/guiyi-server` |
| API 端口 | `127.0.0.1:8765` | `127.0.0.1:8766` |
| 数据目录 | `~/dev/docker_file_sharing/GuiYi/data` | `./data-dev` |
| 模型目录 | `~/dev/docker_file_sharing/GuiYi/models` | `./models-dev` |
| MySQL schema | `guiyi` | `guiyi_dev` |
| 后端启动方式 | launchd | `guiyi-server/scripts/start_dev.sh` |
| 前端 | `/Applications/GuiYi.app` | Xcode Debug 运行 |

开发环境不得直接使用部署环境的数据目录、模型目录或 MySQL schema。

---

## 本地目录布局

在项目根目录下保留这些本机私有目录和配置：

```text
GuiYi/
├── guiyi-server/
│   ├── .venv/
│   └── scripts/start_dev.sh
├── data-dev/
├── models-dev/
├── .env.dev                 # 可选，本机私有
└── guiyi-server.dev.env     # 可选，本机私有
```

`.gitignore` 已忽略这些本地资产。不要把真实凭证、开发数据、模型副本提交到 Git。

---

## 首次准备

### 1. Python 虚拟环境

```bash
cd ~/dev/project/tools/GuiYi/guiyi-server
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. MySQL 开发 schema

MySQL 不要求跑在本机；按实际数据库实例创建开发 schema。本机当前部署配置指向远端 MySQL，开发环境也可以连接同一 MySQL 实例，但必须使用独立 schema。

建议开发 schema 和开发用户都独立：

```sql
CREATE DATABASE IF NOT EXISTS guiyi_dev
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'guiyi_dev'@'%' IDENTIFIED BY 'change-me';
GRANT ALL PRIVILEGES ON guiyi_dev.* TO 'guiyi_dev'@'%';
FLUSH PRIVILEGES;
```

如果沿用现有应用用户，则至少要授权该用户访问开发 schema：

```sql
GRANT ALL PRIVILEGES ON guiyi_dev.* TO 'guiyi_user'@'%';
FLUSH PRIVILEGES;
```

### 3. 开发数据库配置

创建 `data-dev/db_config.json`：

```json
{
  "database": {
    "host": "10.8.0.122",
    "port": 6612,
    "user": "guiyi_dev 或 guiyi_user",
    "password": "change-me",
    "database": "guiyi_dev"
  }
}
```

`guiyi-server/scripts/start_dev.sh` 会在启动前检查这个文件，并拒绝使用生产 schema `guiyi`。

### 4. 开发模型目录

完整隔离时，把部署模型复制到项目开发模型目录：

```bash
mkdir -p ~/dev/project/tools/GuiYi/models-dev
rsync -a \
  ~/dev/docker_file_sharing/GuiYi/models/ \
  ~/dev/project/tools/GuiYi/models-dev/
```

如果只验证 API 或关键词搜索，可以暂时不复制大模型，并在 `.env.dev` 里使用 `GUIYI_SEARCH_MODE=keyword`。

---

## 开发配置

项目根目录可放 `.env.dev` 或 `guiyi-server.dev.env`。两者都不提交 Git；如果同时存在，`start_dev.sh` 优先读取 `guiyi-server.dev.env`。

示例：

```bash
GUIYI_ENV=dev
API_HOST=127.0.0.1
API_PORT=8766
API_DEBUG=true

GUIYI_DATA_DIR=/Users/yswwpp/dev/project/tools/GuiYi/data-dev
GUIYI_EMBEDDING_MODEL_PATH=/Users/yswwpp/dev/project/tools/GuiYi/models-dev/BAAI/bge-m3
GUIYI_IMAGE_VLM_MODEL=/Users/yswwpp/dev/project/tools/GuiYi/models-dev/mlx-community/Qwen2.5-VL-7B-Instruct-4bit
GUIYI_SEARCH_MODE=keyword

GUIYI_SKIP_STARTUP_ACCOUNT_LOAD=true
GUIYI_SCHEDULER_ENABLED=false
```

`GUIYI_SCHEDULER_ENABLED=false` 是开发默认值。只有验证定时同步时才改成 `true`。

---

## 启动开发后端

部署后端可以继续运行在 `8765`。开发后端使用 `8766`：

```bash
cd ~/dev/project/tools/GuiYi/guiyi-server
source .venv/bin/activate
./scripts/start_dev.sh
```

验证：

```bash
curl http://127.0.0.1:8766/api/status
```

`start_dev.sh` 有基础守卫：

- 拒绝使用部署数据目录。
- 拒绝使用部署端口 `8765`。
- 拒绝使用部署模型目录。
- 默认跳过启动期账号加载。
- 默认关闭定时同步调度器。

---

## 从部署数据生成开发快照

开发数据量不足时，用快照方式复制真实数据到 `data-dev/`：

```bash
cd ~/dev/project/tools/GuiYi
./guiyi-server/scripts/snapshot_prod_to_dev.sh
```

注意：

- 脚本会用 `rsync --delete` 覆盖 `data-dev/`，执行前会确认。
- 脚本只复制文件数据，不复制 MySQL schema。
- 如需复制 MySQL 数据，使用 `mysqldump` 从生产 schema 导入 `guiyi_dev`，不要让开发实例直接连接生产 schema。

示例：

```bash
mysqldump -u guiyi -p guiyi > /tmp/guiyi-prod.sql
mysql -u guiyi_dev -p guiyi_dev < /tmp/guiyi-prod.sql
```

导入前确认 dump 中没有 `USE guiyi;` 或写死生产库名的语句。

---

## 前端调试

前端 Debug 应连接开发后端 `http://127.0.0.1:8766`。

```bash
open ~/dev/project/tools/GuiYi/guiyi-client/GuiYi.xcodeproj
```

不要同时让 `/Applications/GuiYi.app` 和 Xcode Debug App 响应同一组全局快捷键。推荐后续实现：

- Release 使用 `Cmd+J`。
- Debug 使用不同快捷键，或默认禁用全局快捷键。
- Debug 菜单或状态栏显示 `GuiYi Dev`。

---

## 上线到本机部署

开发验证通过后，再同步代码到部署目录并重启 launchd。部署数据仍使用 `~/dev/docker_file_sharing/GuiYi/data`：

```bash
rsync -av --delete \
  --exclude='.venv' --exclude='data' --exclude='logs' --exclude='__pycache__' \
  ~/dev/project/tools/GuiYi/guiyi-server/ \
  ~/deploy/GuiYi/guiyi-server/

~/deploy/GuiYi/load.sh
```

依赖变更时，在部署虚拟环境内安装：

```bash
~/deploy/GuiYi/.venv/bin/python -m pip install -r ~/deploy/GuiYi/guiyi-server/requirements.txt
```

---

## 禁止事项

- 不要在开发环境使用 `~/dev/docker_file_sharing/GuiYi/data` 作为 `GUIYI_DATA_DIR`。
- 不要在开发环境使用 `~/dev/docker_file_sharing/GuiYi/models` 作为模型目录。
- 不要在开发环境写入生产 MySQL schema。
- 不要把 `.env.dev`、`guiyi-server.dev.env`、`data-dev/`、`models-dev/` 提交到 Git。
- 不要为了调试端口冲突而随意停止部署服务；优先使用开发端口 `8766`。
