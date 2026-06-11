"""Compatibility entrypoint for the Phase 3 GuiYi backend."""

from main import app


if __name__ == "__main__":
    import uvicorn

    from guiyi_server.config import settings

    print("GuiYi Backend Phase 3 已合并到主入口。")
    print(f"API 地址: http://{settings.API_HOST}:{settings.API_PORT}")
    print(f"API 文档: http://{settings.API_HOST}:{settings.API_PORT}/docs")
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
