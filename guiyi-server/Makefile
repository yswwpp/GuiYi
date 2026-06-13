# GuiYi Backend Makefile
# ======================

.PHONY: help install run run-phase3 test clean lint format

# 默认目标
help:
	@echo "GuiYi Backend - 常用命令"
	@echo ""
	@echo "使用方法: make [目标]"
	@echo ""
	@echo "可用目标:"
	@echo "  install       安装依赖"
	@echo "  run           启动服务"
	@echo "  dev-local     启动本机隔离开发服务"
	@echo "  run-phase3    兼容命令：启动服务"
	@echo "  test          运行测试"
	@echo "  test-cov      运行测试并生成覆盖率报告"
	@echo "  lint          代码检查"
	@echo "  format        格式化代码"
	@echo "  clean         清理临时文件"
	@echo "  status        查看服务状态"
	@echo "  save          保存网页 (需要 URL 参数)"
	@echo "  search        搜索内容 (需要 QUERY 参数)"
	@echo "  feishu-add    添加飞书账号"
	@echo "  feishu-list   列出飞书账号"
	@echo "  sync          触发同步"
	@echo ""

# 安装依赖
install:
	@echo "安装依赖..."
	uv pip install -r requirements.txt
	@echo "依赖安装完成"

# 启动服务
run:
	@echo "启动 GuiYi Backend..."
	python -m guiyi_server

# 兼容旧的 Phase 3 启动命令
run-phase3:
	@echo "run-phase3 已合并到主入口，正在启动 GuiYi Backend..."
	python -m guiyi_server

# 运行测试
test:
	@echo "运行测试..."
	pytest tests/ -v

# 运行测试并生成覆盖率报告
test-cov:
	@echo "运行测试并生成覆盖率报告..."
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term
	@echo "覆盖率报告已生成: htmlcov/index.html"

# 代码检查
lint:
	@echo "代码检查..."
	black --check .
	isort --check-only .
	mypy .

# 格式化代码
format:
	@echo "格式化代码..."
	black .
	isort .
	@echo "格式化完成"

# 清理临时文件
clean:
	@echo "清理临时文件..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete
	@echo "清理完成"

# 查看服务状态
status:
	@echo "查看服务状态..."
	curl -s http://localhost:8765/api/status | python -m json.tool || echo "服务未运行"

# 保存网页
save:
ifndef URL
	@echo "错误: 请提供 URL 参数"
	@echo "用法: make save URL=https://example.com"
else
	@echo "保存网页: $(URL)"
	curl -X POST http://localhost:8765/api/save \
		-H "Content-Type: application/json" \
		-d '{"url": "$(URL)"}' | python -m json.tool
endif

# 搜索内容
search:
ifndef QUERY
	@echo "错误: 请提供 QUERY 参数"
	@echo "用法: make search QUERY='搜索关键词'"
else
	@echo "搜索: $(QUERY)"
	curl -X POST http://localhost:8765/api/search \
		-H "Content-Type: application/json" \
		-d '{"query": "$(QUERY)", "limit": 10}' | python -m json.tool
endif

# 列出文件
files:
	@echo "列出已保存文件..."
	curl -s http://localhost:8765/api/files | python -m json.tool

# 开发模式（自动重载，使用本机隔离开发环境）
dev:
	@./scripts/start_dev.sh

# 本机隔离开发模式（自动重载）
dev-local:
	@./scripts/start_dev.sh

# 数据库初始化
init-db:
	@echo "初始化数据库..."
	@python -c "from guiyi_server.config import settings; print(f'数据库配置: {settings.DB_CONFIG_PATH}')"

# 检查环境
check-env:
	@echo "检查环境..."
	@python --version
	@echo ""
	@echo "已安装的包:"
	@uv pip list

# 添加飞书账号
feishu-add:
ifndef NAME
	@echo "错误: 请提供 NAME 参数"
	@echo "用法: make feishu-add NAME=company APP_ID=cli_xxx APP_SECRET=xxx"
else ifndef APP_ID
	@echo "错误: 请提供 APP_ID 参数"
	@echo "用法: make feishu-add NAME=company APP_ID=cli_xxx APP_SECRET=xxx"
else ifndef APP_SECRET
	@echo "错误: 请提供 APP_SECRET 参数"
	@echo "用法: make feishu-add NAME=company APP_ID=cli_xxx APP_SECRET=xxx"
else
	@echo "添加飞书账号: $(NAME)"
	curl -X POST http://localhost:8765/api/feishu/accounts \
		-H "Content-Type: application/json" \
		-d '{"name": "$(NAME)", "app_id": "$(APP_ID)", "app_secret": "$(APP_SECRET)"}' | python -m json.tool
endif

# 列出飞书账号
feishu-list:
	@echo "列出飞书账号..."
	curl -s http://localhost:8765/api/feishu/accounts | python -m json.tool

# 删除飞书账号
feishu-delete:
ifndef NAME
	@echo "错误: 请提供 NAME 参数"
	@echo "用法: make feishu-delete NAME=company"
else
	@echo "删除飞书账号: $(NAME)"
	curl -X DELETE http://localhost:8765/api/feishu/accounts/$(NAME) | python -m json.tool
endif

# 触发同步
sync:
ifndef SOURCE
	@echo "错误: 请提供 SOURCE 参数 (feishu/wps/yinxiang/quark)"
	@echo "用法: make sync SOURCE=feishu"
else
	@echo "触发同步: $(SOURCE)"
	curl -X POST http://localhost:8765/api/sync \
		-H "Content-Type: application/json" \
		-d '{"source": "$(SOURCE)", "account": "$(ACCOUNT)"}' | python -m json.tool
endif

# 查看同步状态
sync-status:
	@echo "查看同步状态..."
	curl -s http://localhost:8765/api/sync/status | python -m json.tool

# 查看定时任务
jobs:
	@echo "查看定时任务..."
	curl -s http://localhost:8765/api/scheduler/jobs | python -m json.tool
