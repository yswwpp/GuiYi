"""
GuiYi Backend - FastAPI 入口（简化版，用于测试）
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import time
import hashlib
from datetime import datetime

# 导入模块
from adapters.web_scraper import WebScraper
from storage.obsidian import ObsidianStorage

app = FastAPI(title="GuiYi Backend", version="0.1.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 启动时间
START_TIME = time.time()

# 初始化组件（暂时不加载索引）
scraper = WebScraper()
storage = ObsidianStorage()
# index = IndexManager()  # 暂时注释，避免加载大模型


# 请求模型
class SaveRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    source: Optional[str] = None
    account: Optional[str] = None
    limit: int = 20  # 增加默认数量，确保相关结果都能显示


# 响应模型
class SearchResult(BaseModel):
    id: str
    title: str
    url: str
    source: str
    account: Optional[str]
    score: float
    text: str


class StatusResponse(BaseModel):
    status: str
    uptime: float
    sources: List[str]
    storage: dict
    message: str


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "GuiYi Backend API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/api/status")
async def get_status():
    """获取服务状态"""
    return {
        "status": "running",
        "uptime": time.time() - START_TIME,
        "sources": ["web"],
        "storage": storage.get_storage_info(),
        "message": "索引功能暂未启用（首次运行需要下载向量模型）"
    }


@app.post("/api/save")
async def save_url(req: SaveRequest):
    """
    保存网页链接

    流程：
    1. 抓取网页内容
    2. 保存到 Obsidian
    """
    try:
        print(f"正在抓取: {req.url}")

        # 抓取网页
        data = scraper.fetch_full(req.url)
        print(f"抓取成功: {data['title']}")

        # 转换为 Markdown
        markdown = scraper.to_markdown(data)

        # 生成文件名
        title = data["title"].replace("/", "-").replace("\\", "-")[:100]
        filename = f"{title}.md"

        # 保存到 Obsidian
        file_path = storage.save_markdown(filename, markdown)
        print(f"已保存到: {file_path}")

        # 生成文档 ID
        doc_id = hashlib.md5(req.url.encode()).hexdigest()

        return {
            "status": "success",
            "url": req.url,
            "title": data["title"],
            "file_path": file_path,
            "doc_id": doc_id,
            "message": "保存成功（索引功能暂未启用）"
        }

    except Exception as e:
        print(f"保存失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search(req: SearchRequest):
    """
    搜索（简化版，仅返回提示）
    """
    return {
        "message": "搜索功能需要下载向量模型后才能使用",
        "query": req.query,
        "results": []
    }


@app.get("/api/files")
async def list_files():
    """列出所有已保存的文件"""
    files = storage.list_files()
    return {
        "total": len(files),
        "files": [f.name for f in files]
    }


if __name__ == "__main__":
    print("🚀 GuiYi Backend 启动中...")
    print(f"📍 API 地址: http://127.0.0.1:8765")
    print(f"📖 API 文档: http://127.0.0.1:8765/docs")
    print("⚠️  注意: 向量索引功能暂未启用（首次运行需要下载模型）")
    uvicorn.run(app, host="127.0.0.1", port=8765)
