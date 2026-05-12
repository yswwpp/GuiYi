"""
GuiYi Backend - FastAPI 入口
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import time
import hashlib
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
logger.info("初始化组件...")
scraper = WebScraper()
storage = ObsidianStorage()
index = IndexManager()
logger.info("组件初始化完成")


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
    index: dict


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "GuiYi Backend API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """获取服务状态"""
    return StatusResponse(
        status="running",
        uptime=time.time() - START_TIME,
        sources=["web", "feishu", "wps"],
        storage=storage.get_storage_info(),
        index=index.get_stats()
    )


@app.post("/api/save")
async def save_url(req: SaveRequest, background_tasks: BackgroundTasks):
    """
    保存网页链接

    流程：
    1. 抓取网页内容
    2. 保存到 Obsidian
    3. 建立语义索引
    """
    logger.info(f"收到保存请求: {req.url}")
    try:
        # 抓取网页
        logger.debug(f"开始抓取网页: {req.url}")
        data = scraper.fetch_full(req.url)

        # 转换为 Markdown
        markdown = scraper.to_markdown(data)

        # 生成文件名
        title = data["title"].replace("/", "-").replace("\\", "-")[:100]
        filename = f"{title}.md"

        # 保存到 Obsidian
        logger.debug(f"保存到 Obsidian: {filename}")
        file_path = storage.save_markdown(filename, markdown)

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

        # 建立索引
        logger.debug(f"建立索引: {doc_id}")
        index.index_document(doc)

        logger.info(f"保存成功: {req.url} -> {file_path}")
        return {
            "status": "success",
            "url": req.url,
            "title": data["title"],
            "file_path": file_path,
            "doc_id": doc_id
        }

    except Exception as e:
        logger.error(f"保存失败: {req.url} - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search", response_model=List[SearchResult])
async def search(req: SearchRequest):
    """
    语义搜索

    支持自然语言查询，如：
    - "Python 性能优化"
    - "我上周保存的文章"
    """
    logger.info(f"收到搜索请求: query='{req.query}', source={req.source}, account={req.account}")
    try:
        results = index.search(
            query=req.query,
            source=req.source,
            account=req.account,
            limit=req.limit
        )
        logger.info(f"搜索完成，返回 {len(results)} 个结果")
        return results
    except Exception as e:
        logger.error(f"搜索失败: {e}")
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
    print("🚀 GuiYi Backend 启动中...")
    print(f"📍 API 地址: http://127.0.0.1:8765")
    print(f"📖 API 文档: http://127.0.0.1:8765/docs")
    uvicorn.run(app, host="127.0.0.1", port=8765)
