"""Run GuiYi backend with `python -m guiyi_server`."""

import uvicorn

from guiyi_server.app import app
from guiyi_server.config import settings


if __name__ == "__main__":
    print("GuiYi Backend 启动中...")
    print(f"API 地址: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"API 文档: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
