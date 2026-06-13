# GuiYi Agent Instructions

GuiYi is a local-first personal knowledge collection and retrieval system.

## Must-Follow Rules

- Development and deployment environments are fully isolated.
- Deployment backend runs from `~/deploy/GuiYi/` on `127.0.0.1:8765`.
- Deployment data is `~/dev/docker_file_sharing/GuiYi/data`; deployment models are `~/dev/docker_file_sharing/GuiYi/models`.
- Development backend runs from this repository on `127.0.0.1:8766`.
- Development data is `./data-dev`; development models are `./models-dev`.
- Deployment MySQL schema is `guiyi`; development MySQL schema is `guiyi_dev`.
- Never point development code at deployment data or deployment model directories.
- Never write the deployment MySQL schema from development or tests.
- Development startup defaults to no scheduled sync. Enable scheduled sync only when explicitly testing sync behavior.
- Do not commit local runtime assets or secrets: `.env.dev`, `*.dev.env`, `data-dev/`, `models-dev/`, credentials, logs, or virtual environments.
- Use `uv` for Python dependency management. Do not use plain `pip` for project dependency installation.

## Repository Boundaries

- Backend code lives in `guiyi-server/`.
- Swift client code lives in `guiyi-client/`.
- Project docs live in `docs/`.
- Cross-workspace project memory lives in `.ai/` and is committed.
- `.codex/` is a local symlink entry and is not committed.
- This project does not use `.claude/`.

## Read Before Editing

- Development/deployment flow: `docs/runbooks/development-local.md` and `docs/runbooks/deployment-local.md`.
- General architecture and storage model: `docs/architecture.md`.
- Feishu indexing behavior: `docs/feishu-index-rules.md`.
- Local file indexing behavior: `docs/local-file-index-rules.md`.
- Local image indexing behavior: `docs/local-image-index-rules.md`.
- Search feedback behavior: `docs/PRD/新增需求4_搜索反馈闭环设计.md`.

Read the relevant document before changing startup scripts, sync behavior, indexing, storage, database schema, credentials, or frontend/backend connection logic.

## Common Commands

```bash
# Start isolated development backend
cd guiyi-server
source .venv/bin/activate
./scripts/start_dev.sh

# Run backend tests
cd guiyi-server
source .venv/bin/activate
pytest

# Install backend dependencies
cd guiyi-server
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Current Storage Facts

- Runtime metadata is stored in MySQL, not SQLite.
- `sync_metadata`, `sync_logs`, `local_directories`, `search_feedback`, and `search_feedback_results` are MySQL tables.
- txtai index files and Obsidian content remain filesystem data under the active data directory.
