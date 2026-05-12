"""
GuiYi Backend - FastAPI 完整版
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import time
import hashlib
from datetime import datetime
import os

# 导入模块
from adapters.web_scraper import WebScraper
from storage.obsidian import ObsidianStorage
from index.txtai_index import IndexManager

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

# 初始化组件
print("正在初始化组件...")
scraper = WebScraper()
storage = ObsidianStorage()

# 延迟加载索引（首次运行需要下载模型）
index = None
index_loaded = False

def get_index():
    """获取索引实例（延迟加载）"""
    global index, index_loaded
    if index is None and not index_loaded:
        try:
            print("首次运行，正在加载向量索引...")
            print("注意：需要下载向量模型（约 1-2GB），请耐心等待")
            index = IndexManager()
            index_loaded = True
            print("✓ 向量索引加载成功")
        except Exception as e:
            print(f"✗ 向量索引加载失败: {e}")
            index_loaded = True
    return index


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


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "GuiYi Backend API",
        "version": "0.1.0",
        "docs": "/docs",
        "index_status": "enabled" if get_index() else "disabled"
    }


@app.get("/api/status")
async def get_status():
    """获取服务状态"""
    idx = get_index()

    response = {
        "status": "running",
        "uptime": time.time() - START_TIME,
        "sources": ["web", "feishu", "wps"],
        "storage": storage.get_storage_info(),
    }

    if idx:
        response["index"] = idx.get_stats()
        response["index_status"] = "enabled"
    else:
        response["index"] = {"total_documents": 0, "model": "not loaded"}
        response["index_status"] = "disabled"

    return response


@app.post("/api/save")
async def save_url(req: SaveRequest):
    """
    保存网页链接

    流程：
    1. 抓取网页内容
    2. 保存到 Obsidian
    3. 建立语义索引（如果启用）
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

        # 构建索引数据
        doc = {
            "id": doc_id,
            "title": data["title"],
            "content": data["content"],
            "url": req.url,
            "source": "web",
            "saved_at": data["saved_at"]
        }

        # 建立索引（如果启用）
        idx = get_index()
        if idx:
            idx.index_document(doc)
            print(f"已建立索引: {doc_id}")
            message = "保存成功并已建立索引"
        else:
            message = "保存成功（索引功能未启用）"

        return {
            "status": "success",
            "url": req.url,
            "title": data["title"],
            "file_path": file_path,
            "doc_id": doc_id,
            "message": message,
            "indexed": idx is not None
        }

    except Exception as e:
        print(f"保存失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search(req: SearchRequest):
    """
    语义搜索

    支持自然语言查询，如：
    - "Python 性能优化"
    - "我上周保存的文章"
    """
    idx = get_index()
    if not idx:
        raise HTTPException(
            status_code=503,
            detail="索引功能未启用，请检查服务日志"
        )

    try:
        results = idx.search(
            query=req.query,
            source=req.source,
            account=req.account,
            limit=req.limit
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files")
async def list_files():
    """列出所有已保存的文件"""
    files = storage.list_files()
    return {
        "total": len(files),
        "files": [f.name for f in files]
    }


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 GuiYi Backend 启动中...")
    print("=" * 60)
    print(f"📍 API 地址: http://127.0.0.1:8765")
    print(f"📖 API 文档: http://127.0.0.1:8765/docs")
    print("=" * 60)
    print("提示:")
    print("  - 首次运行会自动下载向量模型（约 1-2GB）")
    print("  - 索引功能将在第一次搜索或保存时自动启用")
    print("=" * 60)

    uvicorn.run(app, host="127.0.0.1", port=8765)
