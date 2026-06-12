"""
GuiYi Backend - Phase 3: Feishu Multi-Account Support
支持飞书多账号、增量同步、定时任务
"""

# 设置离线模式（必须在导入其他模块之前）
import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn
import time
import hashlib
import json
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入模块
from guiyi_server.adapters.web_scraper import WebScraper
from guiyi_server.adapters.feishu_adapter import FeishuAdapter, FeishuAccount
from guiyi_server.adapters.local_file_adapter import LocalFileAdapter
from guiyi_server.storage.obsidian import ObsidianStorage
from guiyi_server.storage.keychain import KeychainManager
from guiyi_server.storage.local_directory_store import LocalDirectoryStore, LocalDirectory
from guiyi_server.index.txtai_index import IndexManager
from guiyi_server.sync.metadata import SyncMetadata
from guiyi_server.sync.engine import SyncEngine
from guiyi_server.sync.scheduler import SyncScheduler
from guiyi_server.ai.ai_service import AIService
from guiyi_server.ai.config_store import AIConfigStore
from guiyi_server.ai.rerank_service import RerankConfig, create_reranker
from guiyi_server.ai.keyword_extractor import KeywordExtractorConfig, create_keyword_extractor
from guiyi_server.adapters.yinxiang_adapter import YinxiangAdapter, YinxiangAccount
from guiyi_server.adapters.wps_adapter import WpsAdapter, wps_adapter
from guiyi_server.config import settings

app = FastAPI(
    title="GuiYi Backend - Phase 3",
    version="0.3.0",
    description="支持飞书多账号、增量同步、定时任务"
)

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
logger.info("正在初始化组件...")
scraper = WebScraper(settings.WEB_ASSETS_PATH)
storage = ObsidianStorage(settings.OBSIDIAN_VAULT_PATH)

# 延迟加载索引（首次运行需要下载模型）
index = None
index_loaded = False

def get_index():
    """获取索引实例（延迟加载）"""
    global index, index_loaded
    if index is None and not index_loaded:
        try:
            logger.info("正在加载向量索引...")
            index = IndexManager(settings.INDEX_PATH)
            index_loaded = True
            if getattr(index, "embeddings", None):
                count = index.embeddings.count()
            else:
                count = len(getattr(index, "metadata", {}))
            logger.info(f"✓ 索引加载成功，文档数: {count}")
        except Exception as e:
            logger.error(f"✗ 向量索引加载失败: {e}")
            import traceback
            traceback.print_exc()
            index_loaded = True
    return index

# 初始化同步组件
metadata = SyncMetadata(settings.DB_CONFIG_PATH)
sync_engine = None  # 延迟初始化
scheduler = SyncScheduler(settings.SCHEDULER_JOBS_PATH)

# 飞书适配器
feishu_adapter = FeishuAdapter()

# 印象笔记适配器
yinxiang_adapter = YinxiangAdapter()

# 本地文件适配器
local_file_adapter = LocalFileAdapter()

# AI 服务
ai_config_store = AIConfigStore(settings.AI_CONFIG_PATH)
ai_service = AIService(ai_config_store)


# ==================== 请求/响应模型 ====================

class SaveRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    source: Optional[str] = None
    account: Optional[str] = None
    limit: int = 20  # 增加默认数量，确保相关结果都能显示


class SearchResult(BaseModel):
    id: str
    title: str
    url: str
    source: str
    account: Optional[str]
    score: float
    text: str


class FeishuAccountRequest(BaseModel):
    name: str
    app_id: str
    app_secret: str


class SyncRequest(BaseModel):
    source: str
    account: Optional[str] = None


class LocalDirectoryRequest(BaseModel):
    name: str
    path: str
    file_types: List[str] = []
    exclude_patterns: List[str] = []
    exclude_paths: List[str] = []
    enabled: bool = True
    max_depth: int = 10
    max_file_size_mb: int = 10


class LocalDirectoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    file_types: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    enabled: Optional[bool] = None
    max_depth: Optional[int] = None
    max_file_size_mb: Optional[int] = None


class AIConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    summary_threshold_kb: Optional[int] = None
    max_tokens: Optional[int] = None
    chunk_size_kb: Optional[int] = None
    max_content_kb: Optional[int] = None
    summary_prompt: Optional[str] = None
    partial_prompt: Optional[str] = None
    merge_prompt: Optional[str] = None


class AISearchRequest(BaseModel):
    query: str
    source: Optional[str] = None
    account: Optional[str] = None
    limit: int = 20
    enable_keyword_extraction: bool = True  # 是否启用关键词提取
    enable_rerank: bool = True              # 是否启用 Rerank


class AISearchResult(BaseModel):
    id: str
    title: Optional[str]
    url: Optional[str]
    source: Optional[str]
    account: Optional[str]
    score: float                    # 原始向量分数
    rerank_score: Optional[float]   # Rerank 分数
    final_score: float              # 最终综合分数
    text: str
    ai_keywords: Optional[List[str]] = None  # AI 提取的关键词


class AISearchResponse(BaseModel):
    results: List[AISearchResult]
    ai_enhanced: bool               # 是否使用了 AI 增强
    keywords_extracted: List[str]   # AI 提取的关键词
    rerank_used: bool               # 是否使用了 Rerank
    processing_time_ms: float       # 处理耗时


class AISearchConfigRequest(BaseModel):
    ai_search_enabled: Optional[bool] = None
    keyword_extraction_enabled: Optional[bool] = None
    rerank_enabled: Optional[bool] = None
    keyword_extractor_type: Optional[str] = None
    keyword_ollama_url: Optional[str] = None
    keyword_ollama_model: Optional[str] = None
    keyword_api_url: Optional[str] = None
    keyword_api_key: Optional[str] = None
    keyword_api_model: Optional[str] = None
    keyword_prompt: Optional[str] = None
    reranker_type: Optional[str] = None
    reranker_bge_model: Optional[str] = None
    reranker_cohere_url: Optional[str] = None
    reranker_cohere_key: Optional[str] = None
    reranker_cohere_model: Optional[str] = None
    reranker_jina_url: Optional[str] = None
    reranker_jina_key: Optional[str] = None
    reranker_jina_model: Optional[str] = None
    rerank_top_n: Optional[int] = None


# ==================== 核心路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "GuiYi Backend API - Phase 3",
        "version": "0.3.0",
        "docs": "/docs",
        "features": ["web", "feishu_multi_account", "local_files", "yinxiang", "wps_extension", "incremental_sync", "scheduled_sync"],
        "index_status": "enabled" if get_index() else "disabled"
    }


@app.get("/api/status")
async def get_status():
    """获取服务状态"""
    idx = get_index()

    # 获取本地目录统计
    local_dirs = local_file_adapter.store.list_directories(enabled_only=True)

    response = {
        "status": "running",
        "uptime": time.time() - START_TIME,
        "sources": ["web", "feishu", "local", "yinxiang", "wps"],
        "storage": storage.get_storage_info(),
        "sync": metadata.get_sync_stats(),
        "scheduled_jobs": len(scheduler.get_jobs_info()),
        "local_directories": {
            "total": len(local_dirs),
            "enabled": len([d for d in local_dirs if d.enabled])
        },
        "wps_buffer": len(wps_adapter.buffer.get_all_documents())
    }

    if idx:
        response["index"] = idx.get_stats()
        response["index_status"] = "enabled"
    else:
        response["index"] = {"total_documents": 0, "model": "not loaded"}
        response["index_status"] = "disabled"

    return response


@app.get("/api/sync/stats")
async def get_sync_stats():
    """
    获取各数据源的同步统计信息

    返回每个数据源的索引数量和最近同步时间
    """
    try:
        source_stats = metadata.get_source_stats()

        # 补充未同步的数据源
        all_sources = ["feishu", "local", "yinxiang", "quark", "web", "wps"]
        for source in all_sources:
            if source not in source_stats:
                source_stats[source] = {
                    "count": 0,
                    "last_sync": None
                }

        return {
            "status": "success",
            "sources": source_stats
        }
    except Exception as e:
        logger.error(f"获取同步统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 网页保存 ====================

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
        logger.info(f"正在抓取: {req.url}")

        # 抓取网页
        data = scraper.fetch_full(req.url)
        logger.info(f"抓取成功: {data['title']}")

        # 转换为 Markdown
        markdown = scraper.to_markdown(data)

        # 生成文件名
        title = data["title"].replace("/", "-").replace("\\", "-")[:100]
        filename = f"{title}.md"

        # 保存到 Obsidian
        file_path = storage.save_markdown(filename, markdown)
        logger.info(f"已保存到: {file_path}")

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
            logger.info(f"已建立索引: {doc_id}")
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
        logger.error(f"保存失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 搜索 ====================

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


@app.post("/api/ai-search")
async def ai_search(req: AISearchRequest):
    """
    AI 增强语义搜索

    流程：
    1. AI 提取关键词和意图（可选）
    2. 使用增强查询执行向量搜索
    3. Rerank 重排结果（可选）

    如果 AI/Rerank 未配置或失败，自动 fallback 到普通搜索
    """
    import time as timing
    start_time = timing.time()

    idx = get_index()
    if not idx:
        raise HTTPException(
            status_code=503,
            detail="索引功能未启用，请检查服务日志"
        )

    config = ai_config_store.get_config()

    ai_enhanced = False
    rerank_used = False
    keywords_extracted = []
    enhanced_query = req.query

    # 检查是否启用任何 AI 功能
    use_keyword_extraction = req.enable_keyword_extraction and config.keyword_extraction_enabled
    use_rerank = req.enable_rerank and config.rerank_enabled

    # 阶段 1：关键词提取（如果启用）
    if use_keyword_extraction and config.ai_search_enabled:
        try:
            # 构建关键词提取器配置
            extractor_config = KeywordExtractorConfig(
                enabled=True,
                extractor_type=config.keyword_extractor_type,
                ollama_url=config.keyword_ollama_url,
                ollama_model=config.keyword_ollama_model,
                api_url=config.keyword_api_url,
                api_key=config.keyword_api_key,
                api_model=config.keyword_api_model,
                custom_prompt=config.keyword_prompt
            )

            extractor = create_keyword_extractor(extractor_config)
            keyword_result = extractor.extract(req.query)

            if keyword_result:
                ai_enhanced = True
                keywords_extracted = keyword_result.get("keywords", [])
                enhanced_query = keyword_result.get("enhanced_query", req.query)
                logger.info(f"AI 提取关键词: {keywords_extracted}, 增强查询: {enhanced_query}")
        except Exception as e:
            logger.warning(f"AI 关键词提取失败，使用原始查询: {e}")

    # 阶段 2：向量搜索
    try:
        # 获取更多结果用于 Rerank
        search_limit = req.limit * 2 if use_rerank else req.limit
        search_results = idx.search(
            query=enhanced_query,
            source=req.source,
            account=req.account,
            limit=search_limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 阶段 3：Rerank 重排（如果启用）
    if use_rerank and len(search_results) > 0:
        try:
            # 构建 Rerank 配置
            rerank_config = RerankConfig(
                enabled=True,
                reranker_type=config.reranker_type,
                bge_model=config.reranker_bge_model,
                cohere_url=config.reranker_cohere_url,
                cohere_key=config.reranker_cohere_key,
                cohere_model=config.reranker_cohere_model,
                jina_url=config.reranker_jina_url,
                jina_key=config.reranker_jina_key,
                jina_model=config.reranker_jina_model,
                top_n=config.rerank_top_n
            )

            reranker = create_reranker(rerank_config)

            if reranker.is_available():
                reranked_results = reranker.rerank(
                    query=req.query,  # 使用原始查询进行 Rerank
                    documents=search_results,
                    top_n=req.limit
                )
                rerank_used = True
                search_results = reranked_results
                logger.info(f"Rerank 完成，返回 {len(search_results)} 个结果")
        except Exception as e:
            logger.warning(f"Rerank 失败，使用原始搜索结果: {e}")

    else:
        # AI 搜索未启用，直接执行普通搜索
        try:
            search_results = idx.search(
                query=req.query,
                source=req.source,
                account=req.account,
                limit=req.limit
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # 格式化结果
    formatted_results = []
    for result in search_results[:req.limit]:
        formatted_results.append(AISearchResult(
            id=result.get("id", ""),
            title=result.get("title"),
            url=result.get("url"),
            source=result.get("source"),
            account=result.get("account"),
            score=result.get("score", 0.0),
            rerank_score=result.get("rerank_score"),
            final_score=result.get("final_score", result.get("score", 0.0)),
            text=result.get("text", "")[:200] if result.get("text") else "",
            ai_keywords=keywords_extracted if ai_enhanced else None
        ))

    processing_time = (timing.time() - start_time) * 1000

    return AISearchResponse(
        results=formatted_results,
        ai_enhanced=ai_enhanced,
        keywords_extracted=keywords_extracted,
        rerank_used=rerank_used,
        processing_time_ms=processing_time
    )


@app.get("/api/files")
async def list_files():
    """列出所有已保存的文件"""
    files = storage.list_files()
    return {
        "total": len(files),
        "files": [f.name for f in files]
    }


# ==================== 飞书账号管理 ====================

@app.post("/api/feishu/accounts")
async def add_feishu_account(req: FeishuAccountRequest):
    """
    添加飞书账号

    凭证会安全存储到 macOS Keychain
    """
    try:
        # 保存凭证到 Keychain
        if not KeychainManager.save_feishu_account(
            name=req.name,
            app_id=req.app_id,
            app_secret=req.app_secret
        ):
            raise HTTPException(
                status_code=500,
                detail="保存凭证失败，请检查 Keychain 权限"
            )

        # 初始化飞书客户端
        account = FeishuAccount(
            name=req.name,
            app_id=req.app_id,
            app_secret=req.app_secret
        )

        if not feishu_adapter.add_account(account):
            # 如果初始化失败，删除已保存的凭证
            KeychainManager.delete_feishu_account(req.name)
            raise HTTPException(
                status_code=400,
                detail="飞书客户端初始化失败，请检查 App ID 和 App Secret"
            )

        logger.info(f"飞书账号添加成功: {req.name}")

        return {
            "status": "success",
            "message": f"飞书账号 [{req.name}] 添加成功",
            "name": req.name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加飞书账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feishu/accounts")
async def list_feishu_accounts():
    """列出所有飞书账号"""
    accounts = []

    for name, account in feishu_adapter.accounts.items():
        accounts.append({
            "name": name,
            "app_id": account.app_id[:10] + "...",  # 只显示前 10 个字符
            "initialized": account.client is not None
        })

    return {
        "total": len(accounts),
        "accounts": accounts
    }


@app.delete("/api/feishu/accounts/{name}")
async def delete_feishu_account(name: str):
    """删除飞书账号"""
    try:
        # 从适配器中移除
        if name in feishu_adapter.accounts:
            del feishu_adapter.accounts[name]

        # 从 Keychain 中删除凭证
        KeychainManager.delete_feishu_account(name)

        logger.info(f"飞书账号删除成功: {name}")

        return {
            "status": "success",
            "message": f"飞书账号 [{name}] 已删除"
        }

    except Exception as e:
        logger.error(f"删除飞书账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class UserTokenRequest(BaseModel):
    user_access_token: str
    refresh_token: str = None


@app.post("/api/feishu/accounts/{name}/token")
async def set_feishu_user_token(name: str, req: UserTokenRequest):
    """
    设置飞书账号的用户访问令牌

    用户令牌用于访问知识库等需要用户身份的 API
    """
    try:
        if name not in feishu_adapter.accounts:
            raise HTTPException(
                status_code=404,
                detail=f"飞书账号 [{name}] 不存在"
            )

        # 设置用户令牌
        feishu_adapter.accounts[name].set_user_access_token(
            req.user_access_token,
            refresh_token=req.refresh_token
        )

        # 保存到 Keychain
        KeychainManager.save_feishu_account(
            name=name,
            app_id=feishu_adapter.accounts[name].app_id,
            app_secret=feishu_adapter.accounts[name].app_secret,
            user_access_token=req.user_access_token,
            refresh_token=req.refresh_token
        )

        logger.info(f"飞书用户令牌设置成功: {name}")

        return {
            "status": "success",
            "message": f"飞书账号 [{name}] 用户令牌已设置"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置用户令牌失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 飞书 OAuth ====================

@app.get("/api/feishu/oauth/url")
async def get_feishu_oauth_url(name: str = "wiki_user"):
    """
    获取飞书 OAuth 授权 URL

    用户访问此 URL 进行授权，授权后会跳转到回调地址
    """
    if name not in feishu_adapter.accounts:
        raise HTTPException(
            status_code=404,
            detail=f"飞书账号 [{name}] 不存在"
        )

    app_id = feishu_adapter.accounts[name].app_id
    redirect_uri = "http://127.0.0.1:8765/api/feishu/oauth/callback"

    # 构建授权 URL
    # 需要的权限范围
    scope = "contact:user.base:readonly wiki:wiki:readonly drive:drive:readonly docs:doc:readonly sheets:spreadsheet:readonly bitable:app:readonly"

    import urllib.parse
    auth_url = (
        f"https://open.feishu.cn/open-apis/authen/v1/authorize"
        f"?app_id={app_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&state={name}"
        f"&scope={urllib.parse.quote(scope)}"
    )

    logger.info(f"生成飞书 OAuth URL: {name}")

    return {
        "auth_url": auth_url,
        "message": "请在浏览器中访问此 URL 进行授权"
    }


@app.get("/api/feishu/oauth/callback")
async def feishu_oauth_callback(code: str, state: str = "wiki_user"):
    """
    飞书 OAuth 回调

    用户授权后，飞书会重定向到此地址并带上 code
    """
    import requests

    try:
        account_name = state
        if account_name not in feishu_adapter.accounts:
            raise HTTPException(
                status_code=400,
                detail=f"无效的 state 参数: {account_name}"
            )

        account = feishu_adapter.accounts[account_name]

        # Step 1: 获取 app_access_token
        app_token_url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
        app_token_data = {
            "app_id": account.app_id,
            "app_secret": account.app_secret
        }
        app_token_resp = requests.post(app_token_url, json=app_token_data)
        app_token_result = app_token_resp.json()

        if app_token_result.get('code') != 0:
            logger.error(f"获取 app_access_token 失败: {app_token_result}")
            raise HTTPException(
                status_code=400,
                detail=f"获取 app_access_token 失败: {app_token_result.get('msg')}"
            )

        app_access_token = app_token_result.get('app_access_token')

        # Step 2: 使用 code 换取 user_access_token
        url = "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {app_access_token}"
        }
        data = {
            "grant_type": "authorization_code",
            "code": code
        }

        response = requests.post(url, json=data, headers=headers)
        result = response.json()

        if result.get('code') != 0:
            logger.error(f"获取 access_token 失败: {result}")
            raise HTTPException(
                status_code=400,
                detail=f"获取 access_token 失败: {result.get('msg')}"
            )

        token_data = result.get('data', {})
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')

        # 设置用户令牌
        account.set_user_access_token(access_token, refresh_token)

        # 保存到 Keychain
        KeychainManager.save_feishu_account(
            name=account_name,
            app_id=account.app_id,
            app_secret=account.app_secret,
            user_access_token=access_token,
            refresh_token=refresh_token
        )

        logger.info(f"飞书 OAuth 授权成功: {account_name}")

        # 返回 HTML 页面提示用户
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>授权成功</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                }}
                .container {{
                    text-align: center;
                    padding: 40px;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .success {{ color: #52c41a; font-size: 48px; }}
                h1 {{ color: #333; }}
                p {{ color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✓</div>
                <h1>授权成功</h1>
                <p>飞书账号已授权，可以关闭此页面</p>
            </div>
            <script>setTimeout(() => window.close(), 3000);</script>
        </body>
        </html>
        """

        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth 回调处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 飞书手动索引 ====================

class FeishuManualIndexRequest(BaseModel):
    url: str  # 飞书文档 URL
    title: Optional[str] = None  # 可选的自定义标题


@app.post("/api/feishu/index-document")
async def index_feishu_document(req: FeishuManualIndexRequest):
    """
    手动索引单个飞书文档

    支持的 URL 格式：
    - https://feishu.cn/docx/xxx
    - https://feishu.cn/sheets/xxx
    - https://xxx.feishu.cn/sheets/xxx
    """
    import re

    try:
        # 解析 URL 提取文档类型和 token
        url = req.url

        # 匹配飞书 URL 格式
        patterns = {
            'docx': r'feishu\.cn/docx/([a-zA-Z0-9]+)',
            'doc': r'feishu\.cn/doc/([a-zA-Z0-9]+)',
            'sheet': r'(?:feishu\.cn|[\w-]+\.feishu\.cn)/sheets/([a-zA-Z0-9]+)',
            'bitable': r'feishu\.cn/base/([a-zA-Z0-9]+)',
        }

        doc_token = None
        obj_type = None

        for dtype, pattern in patterns.items():
            match = re.search(pattern, url)
            if match:
                doc_token = match.group(1)
                obj_type = dtype
                break

        if not doc_token:
            raise HTTPException(status_code=400, detail="无法解析飞书文档 URL")

        logger.info(f"手动索引飞书文档: token={doc_token}, type={obj_type}")

        # 获取账号和用户令牌
        account = feishu_adapter.accounts.get('wiki_user')
        if not account:
            raise HTTPException(status_code=400, detail="飞书账号未配置")

        user_access_token = account.user_access_token
        if not user_access_token:
            raise HTTPException(status_code=400, detail="用户令牌未配置，请先授权")

        # 获取文档内容
        content = feishu_adapter.get_document_content(
            doc_id=f"feishu_manual_{doc_token}",
            doc_token=doc_token,
            account_name='wiki_user',
            user_access_token=user_access_token,
            obj_type=obj_type
        )

        if not content:
            raise HTTPException(status_code=400, detail="获取文档内容失败")

        # 获取文档标题（如果未提供）
        title = req.title
        if not title:
            # 尝试从 URL 或内容推断
            title = f"飞书{obj_type}文档_{doc_token[:8]}"

        # 构建文档对象
        doc = {
            "id": f"feishu_manual_{doc_token}",
            "title": title,
            "content": content,
            "url": url,
            "source": "feishu",
            "account": "feishu_manual",
            "doc_type": obj_type,
            "doc_token": doc_token,
            "obj_type": obj_type,
            "updated_at": datetime.now().timestamp(),
            "store_locally": False
        }

        # 索引文档
        idx = get_index()
        idx.index_documents([doc])

        logger.info(f"飞书文档索引成功: {title}")

        return {
            "status": "success",
            "message": f"文档已索引: {title}",
            "doc_id": doc["id"],
            "content_length": len(content)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"索引飞书文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 印象笔记账号管理 ====================

from pydantic import BaseModel
from typing import Optional, List


class YinxiangAccountRequest(BaseModel):
    """印象笔记账号请求"""
    name: str
    token: str
    note_store_url: str
    is_china: bool = True
    sync_notebooks: Optional[List[str]] = None


class YinxiangTestRequest(BaseModel):
    """印象笔记连接测试请求"""
    token: str
    note_store_url: str


@app.post("/api/yinxiang/accounts")
async def add_yinxiang_account(req: YinxiangAccountRequest):
    """添加印象笔记账号"""
    try:
        account = YinxiangAccount(
            name=req.name,
            token=req.token,
            note_store_url=req.note_store_url,
            is_china=req.is_china,
            sync_notebooks=req.sync_notebooks or []
        )
        yinxiang_adapter.add_account(account)

        # 保存到 Keychain
        KeychainManager.save_yinxiang_account(
            name=req.name,
            token=req.token,
            note_store_url=req.note_store_url
        )

        # 保存账号名到配置文件
        config_path = settings.YINXIANG_ACCOUNTS_PATH
        account_list = []
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    account_list = json.load(f)
            except:
                pass

        if req.name not in account_list:
            account_list.append(req.name)

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(account_list, f, ensure_ascii=False, indent=2)

        logger.info(f"添加印象笔记账号: {req.name}")

        return {
            "status": "success",
            "message": f"账号 {req.name} 添加成功"
        }
    except Exception as e:
        logger.error(f"添加印象笔记账号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/yinxiang/accounts")
async def list_yinxiang_accounts():
    """列出所有印象笔记账号"""
    accounts = []
    for name, account in yinxiang_adapter.accounts.items():
        accounts.append({
            "name": name,
            "note_store_url": account.note_store_url,
            "is_china": account.is_china,
            "sync_notebooks": account.sync_notebooks
        })
    return {"accounts": accounts}


@app.delete("/api/yinxiang/accounts/{name}")
async def delete_yinxiang_account(name: str):
    """删除印象笔记账号"""
    if name not in yinxiang_adapter.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")

    del yinxiang_adapter.accounts[name]

    # 从 Keychain 删除
    KeychainManager.delete_yinxiang_account(name)

    return {"status": "success", "message": f"账号 {name} 已删除"}


@app.post("/api/yinxiang/accounts/{name}/reset-sync")
async def reset_yinxiang_sync_state(name: str):
    """重置印象笔记同步状态（强制全量同步）"""
    if name not in yinxiang_adapter.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")

    yinxiang_adapter.reset_sync_state(name)

    return {"status": "success", "message": f"账号 {name} 同步状态已重置，下次同步将全量获取"}


@app.post("/api/yinxiang/test")
async def test_yinxiang_connection(req: YinxiangTestRequest):
    """测试印象笔记连接"""
    result = yinxiang_adapter.test_connection(
        token=req.token,
        note_store_url=req.note_store_url
    )
    return result


@app.get("/api/yinxiang/accounts/{name}/notebooks")
async def list_yinxiang_notebooks(name: str):
    """列出印象笔记账号的笔记本"""
    if name not in yinxiang_adapter.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")

    notebooks = yinxiang_adapter.list_notebooks(name)
    return {"notebooks": notebooks}


@app.post("/api/yinxiang/accounts/{name}/background-sync")
async def start_yinxiang_background_sync(name: str, background_tasks: BackgroundTasks):
    """
    启动印象笔记后台持续同步

    该任务会在后台持续运行，处理待同步笔记：
    - 同步笔记内容
    - 遇到限流时自动等待并重试
    - 直到全部笔记同步完成

    适合首次全量同步或大量笔记待处理时使用
    """
    if name not in yinxiang_adapter.accounts:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 添加后台任务
    background_tasks.add_task(yinxiang_continuous_sync, name)

    return {
        "status": "started",
        "message": f"账号 {name} 后台同步已启动，将自动处理限流直到完成"
    }


def yinxiang_continuous_sync(account_name: str):
    """
    印象笔记后台持续同步任务

    处理流程：
    1. 获取待处理笔记列表
    2. 逐个获取笔记内容
    3. 遇到限流时等待 rateLimitDuration 后继续
    4. 完成后更新同步状态
    """
    import time

    logger.info(f"开始印象笔记后台持续同步: {account_name}")

    # 确保索引已初始化
    idx = get_index()
    if not idx:
        logger.error("索引未初始化，无法同步")
        return

    # 初始化同步引擎
    global sync_engine
    if sync_engine is None:
        sync_engine = SyncEngine(metadata, idx)

    # 循环同步直到完成
    max_iterations = 100  # 最大循环次数，防止无限循环
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # 执行一次同步
        try:
            stats = sync_engine.sync_source(
                "yinxiang",
                yinxiang_adapter,
                account_name
            )

            added = stats.get('added', 0)
            updated = stats.get('updated', 0)
            skipped = stats.get('skipped', 0)

            logger.info(f"印象笔记同步进度 (第{iteration}轮): 新增 {added}, 更新 {updated}, 跳过 {skipped}")

            # 检查是否完成
            # 如果没有新增、更新，且 skipped 都是因为已同步，则认为完成
            if added == 0 and updated == 0:
                # 检查是否还有待处理的笔记
                sync_state = yinxiang_adapter._sync_state_cache
                pending_key = f"{account_name}_pending"
                pending_count = len(sync_state.get(pending_key, []))

                if pending_count == 0:
                    logger.info(f"印象笔记后台同步完成: {account_name}")
                    break
                else:
                    logger.info(f"仍有 {pending_count} 条待处理笔记，继续同步...")
                    # 等待一段时间再继续（避免立即请求触发限流）
                    time.sleep(30)

        except Exception as e:
            logger.error(f"印象笔记同步失败: {e}")
            break

    logger.info(f"印象笔记后台同步任务结束: {account_name}, 共执行 {iteration} 轮")


# ==================== WPS 插件集成 ====================

class WpsPushRequest(BaseModel):
    """WPS 文档推送请求"""
    id: Optional[str] = None
    title: str
    content: str
    url: str
    source: str = "wps"
    account: Optional[str] = "default"
    docType: str  # doc/sheet/ppt
    docToken: str
    updatedAt: Optional[float] = None
    blocks: Optional[List[Dict]] = None


@app.post("/api/wps/push")
async def wps_push_document(req: WpsPushRequest):
    """
    接收 Chrome 插件推送的 WPS 文档

    流程：
    1. 接收文档数据
    2. 存入缓冲区
    """
    try:
        doc_data = req.dict()

        # 接收文档
        result = wps_adapter.receive_document(doc_data)

        logger.info(f"WPS 文档已接收: {result['title']}")

        return {
            "status": "success",
            "message": f"文档已接收: {result['title']}",
            **result
        }

    except ValueError as e:
        logger.error(f"WPS 文档接收失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"WPS 文档处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/wps/push-and-index")
async def wps_push_and_index(req: WpsPushRequest):
    """
    接收文档并立即索引

    流程：
    1. 接收文档
    2. 存入缓冲区
    3. 立即建立索引
    """
    try:
        doc_data = req.dict()

        # 接收文档
        result = wps_adapter.receive_document(doc_data)

        # 确保索引已初始化
        idx = get_index()
        if not idx:
            return {
                "status": "received",
                "indexed": False,
                "message": "文档已接收但索引未启用",
                **result
            }

        # 从缓冲区获取文档并索引
        doc_token = result['doc_token']
        doc = wps_adapter.buffer.get_document(doc_token)

        if doc:
            # 构建索引文本
            index_text = f"{doc['title']} {doc['title']} {doc['title']} {doc['content'][:1500]}"
            doc_id = doc['id']

            # 添加到索引
            idx.index_document(doc)
            logger.info(f"WPS 文档已索引: {req.title}")

            # 计算内容哈希
            content_hash = hashlib.md5(doc['content'].encode('utf-8')).hexdigest()

            # 记录同步状态
            metadata.upsert_doc(
                doc_id=doc_id,
                source="wps",
                account=doc.get('account', 'wps_default'),
                url=doc['url'],
                title=doc['title'],
                content_hash=content_hash,
                last_modified=doc.get('updated_at', datetime.now().timestamp())
            )

            # 记录日志
            metadata.log_sync(
                source="wps",
                action="index",
                doc_id=doc_id,
                doc_title=doc['title']
            )

        return {
            "status": "success",
            "indexed": True,
            "message": f"文档已接收并索引: {req.title}",
            **result
        }

    except ValueError as e:
        logger.error(f"WPS 文档接收失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"WPS 文档推送索引失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/wps/status")
async def wps_get_status(doc_token: Optional[str] = None, account: Optional[str] = None):
    """
    获取 WPS 文档同步状态

    返回文档是否已同步、上次同步时间、内容哈希等
    """
    try:
        if doc_token:
            doc_id = f"wps_{account or 'default'}_{doc_token}"
            state = metadata.get_doc_state(doc_id)

            if state:
                return {
                    "synced": True,
                    "last_sync": state.get('last_synced'),
                    "content_hash": state.get('content_hash'),
                    "title": state.get('title')
                }
            else:
                return {
                    "synced": False,
                    "last_sync": None,
                    "content_hash": None
                }
        else:
            # 返回整体统计
            stats = metadata.get_sync_stats(source="wps", account=account)
            return {
                "synced": True,
                "stats": stats
            }

    except Exception as e:
        logger.error(f"获取 WPS 同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/wps/documents")
async def wps_list_documents(account: Optional[str] = None, limit: int = 50):
    """
    获取已同步的 WPS 文档列表
    """
    try:
        docs = metadata.get_all_synced_docs(source="wps", account=account)

        # 限制数量
        docs = docs[:limit]

        return {
            "total": len(docs),
            "documents": [
                {
                    "id": doc['id'],
                    "title": doc['title'],
                    "url": doc['url'],
                    "last_synced": doc.get('last_synced')
                }
                for doc in docs
            ]
        }

    except Exception as e:
        logger.error(f"获取 WPS 文档列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/wps/sync")
async def wps_trigger_sync(background_tasks: BackgroundTasks, account: Optional[str] = None):
    """
    触发 WPS 文档批量同步

    流程：
    1. 获取缓冲区所有文档
    2. 使用 SyncEngine 同步到索引
    """
    try:
        # 确保索引已初始化
        idx = get_index()
        if not idx:
            raise HTTPException(status_code=500, detail="索引未初始化")

        # 初始化同步引擎
        global sync_engine
        if sync_engine is None:
            sync_engine = SyncEngine(metadata, idx)

        # 获取缓冲区文档
        docs = wps_adapter.fetch_all_for_index(account)

        if not docs:
            return {
                "status": "success",
                "stats": {"added": 0, "updated": 0, "skipped": 0},
                "message": "缓冲区无待同步文档"
            }

        # 执行同步
        stats = {"added": 0, "updated": 0, "skipped": 0}

        for doc in docs:
            doc_id = doc['id']
            content_hash = hashlib.md5(doc['content'].encode('utf-8')).hexdigest()

            # 检查是否已同步
            existing_state = metadata.get_doc_state(doc_id)

            if existing_state and existing_state.get('content_hash') == content_hash:
                stats['skipped'] += 1
                continue

            # 索引文档
            idx.index_document(doc)

            # 更新元数据
            metadata.upsert_doc(
                doc_id=doc_id,
                source="wps",
                account=doc.get('account', 'wps_default'),
                url=doc['url'],
                title=doc['title'],
                content_hash=content_hash,
                last_modified=doc.get('updated_at', datetime.now().timestamp())
            )

            if existing_state:
                stats['updated'] += 1
            else:
                stats['added'] += 1

            logger.info(f"WPS 文档已索引: {doc['title']}")

        return {
            "status": "success",
            "stats": stats,
            "message": f"同步完成: 新增 {stats['added']}, 更新 {stats['updated']}, 跳过 {stats['skipped']}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WPS 同步失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/wps/documents/{doc_token}")
async def wps_delete_document(doc_token: str, account: Optional[str] = None):
    """
    删除已索引的 WPS 文档
    """
    try:
        doc_id = f"wps_{account or 'default'}_{doc_token}"

        # 标记为删除
        metadata.mark_deleted(doc_id)

        # 从缓冲区移除
        wps_adapter.buffer.remove_document(doc_token)

        return {
            "status": "success",
            "message": f"文档已删除: {doc_token}"
        }

    except Exception as e:
        logger.error(f"删除 WPS 文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/wps/buffer")
async def wps_list_buffer():
    """
    查看缓冲区中的文档（未索引的）
    """
    try:
        docs = wps_adapter.buffer.get_all_documents()

        return {
            "total": len(docs),
            "documents": [
                {
                    "doc_token": doc['doc_token'],
                    "title": doc['title'],
                    "received_at": doc.get('received_at'),
                    "content_length": len(doc.get('content', ''))
                }
                for doc in docs
            ]
        }

    except Exception as e:
        logger.error(f"获取缓冲区列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/wps/buffer")
async def wps_clear_buffer():
    """
    清空缓冲区
    """
    try:
        wps_adapter.clear_buffer()

        return {
            "status": "success",
            "message": "缓冲区已清空"
        }

    except Exception as e:
        logger.error(f"清空缓冲区失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 本地目录管理 ====================

import uuid as uuid_module


@app.get("/api/local-directories/file-types")
async def get_supported_file_types():
    """获取支持的文件类型列表"""
    return {
        "file_types": LocalDirectoryStore.get_supported_file_types(),
        "default_exclude_patterns": LocalDirectoryStore.get_default_exclude_patterns()
    }


@app.post("/api/local-directories")
async def add_local_directory(req: LocalDirectoryRequest):
    """
    添加本地目录配置

    目录配置会存储到本地 SQLite 数据库
    """
    try:
        # 检查路径是否存在
        expanded_path = os.path.expanduser(req.path)
        if not os.path.isdir(expanded_path):
            raise HTTPException(
                status_code=400,
                detail=f"目录不存在: {req.path}"
            )

        # 生成目录 ID
        dir_id = f"local_{uuid_module.uuid4().hex[:12]}"

        # 创建目录配置
        directory = LocalDirectory(
            id=dir_id,
            name=req.name,
            path=req.path,
            file_types=req.file_types if req.file_types else LocalDirectoryStore.get_supported_file_types(),
            exclude_patterns=req.exclude_patterns if req.exclude_patterns else LocalDirectoryStore.get_default_exclude_patterns(),
            exclude_paths=req.exclude_paths or [],
            enabled=req.enabled,
            max_depth=req.max_depth,
            max_file_size_mb=req.max_file_size_mb
        )

        # 保存配置
        if not local_file_adapter.store.add_directory(directory):
            raise HTTPException(
                status_code=500,
                detail="保存目录配置失败"
            )

        # 统计文件数量
        file_count = local_file_adapter.count_files(dir_id)

        logger.info(f"本地目录添加成功: {req.name} -> {req.path}")

        return {
            "status": "success",
            "id": dir_id,
            "name": req.name,
            "path": req.path,
            "file_count": file_count,
            "message": f"本地目录 [{req.name}] 添加成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加本地目录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/local-directories")
async def list_local_directories():
    """列出所有本地目录配置"""
    directories = local_file_adapter.store.list_directories()

    result = []
    for d in directories:
        # 统计文件数量
        file_count = local_file_adapter.count_files(d.id)

        result.append({
            "id": d.id,
            "name": d.name,
            "path": d.path,
            "file_types": d.file_types,
            "exclude_patterns": d.exclude_patterns,
            "exclude_paths": d.exclude_paths,
            "enabled": d.enabled,
            "max_depth": d.max_depth,
            "max_file_size_mb": d.max_file_size_mb,
            "file_count": file_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None
        })

    return {
        "total": len(result),
        "directories": result
    }


@app.get("/api/local-directories/{dir_id}")
async def get_local_directory(dir_id: str):
    """获取单个目录配置"""
    directory = local_file_adapter.store.get_directory(dir_id)

    if not directory:
        raise HTTPException(status_code=404, detail="目录配置不存在")

    file_count = local_file_adapter.count_files(dir_id)

    return {
        "id": directory.id,
        "name": directory.name,
        "path": directory.path,
        "file_types": directory.file_types,
        "exclude_patterns": directory.exclude_patterns,
        "exclude_paths": directory.exclude_paths,
        "enabled": directory.enabled,
        "max_depth": directory.max_depth,
        "max_file_size_mb": directory.max_file_size_mb,
        "file_count": file_count,
        "created_at": directory.created_at.isoformat() if directory.created_at else None,
        "updated_at": directory.updated_at.isoformat() if directory.updated_at else None
    }


@app.patch("/api/local-directories/{dir_id}")
async def update_local_directory(dir_id: str, req: LocalDirectoryUpdateRequest):
    """更新目录配置"""
    try:
        # 检查目录是否存在
        directory = local_file_adapter.store.get_directory(dir_id)
        if not directory:
            raise HTTPException(status_code=404, detail="目录配置不存在")

        # 构建更新字段
        update_fields = {}
        if req.name is not None:
            update_fields['name'] = req.name
        if req.file_types is not None:
            update_fields['file_types'] = req.file_types
        if req.exclude_patterns is not None:
            update_fields['exclude_patterns'] = req.exclude_patterns
        if req.exclude_paths is not None:
            update_fields['exclude_paths'] = req.exclude_paths
        if req.enabled is not None:
            update_fields['enabled'] = req.enabled
        if req.max_depth is not None:
            update_fields['max_depth'] = req.max_depth
        if req.max_file_size_mb is not None:
            update_fields['max_file_size_mb'] = req.max_file_size_mb

        if not update_fields:
            raise HTTPException(status_code=400, detail="没有要更新的字段")

        # 执行更新
        if not local_file_adapter.store.update_directory(dir_id, **update_fields):
            raise HTTPException(status_code=500, detail="更新目录配置失败")

        logger.info(f"本地目录更新成功: {dir_id}")

        return {
            "status": "success",
            "id": dir_id,
            "message": "目录配置已更新"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新本地目录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/local-directories/{dir_id}")
async def delete_local_directory(dir_id: str):
    """删除目录配置"""
    try:
        if not local_file_adapter.store.delete_directory(dir_id):
            raise HTTPException(status_code=404, detail="目录配置不存在")

        logger.info(f"本地目录删除成功: {dir_id}")

        return {
            "status": "success",
            "id": dir_id,
            "message": "目录配置已删除"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除本地目录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AI 配置管理 ====================

@app.get("/api/ai/config")
async def get_ai_config():
    """获取 AI 配置"""
    config = ai_config_store.get_config()
    return {
        "enabled": config.enabled,
        "api_base": config.api_base,
        "api_key": config.api_key[:8] + "..." if config.api_key else "",  # 只显示前 8 位
        "model": config.model,
        "summary_threshold_kb": config.summary_threshold_kb,
        "max_tokens": config.max_tokens,
        "chunk_size_kb": config.chunk_size_kb,
        "max_content_kb": config.max_content_kb,
        "summary_prompt": config.summary_prompt,
        "partial_prompt": config.partial_prompt,
        "merge_prompt": config.merge_prompt
    }


@app.put("/api/ai/config")
async def update_ai_config(req: AIConfigRequest):
    """更新 AI 配置"""
    update_data = {}
    if req.enabled is not None:
        update_data["enabled"] = req.enabled
    if req.api_base is not None:
        update_data["api_base"] = req.api_base
    if req.api_key is not None:
        update_data["api_key"] = req.api_key
    if req.model is not None:
        update_data["model"] = req.model
    if req.summary_threshold_kb is not None:
        update_data["summary_threshold_kb"] = req.summary_threshold_kb
    if req.max_tokens is not None:
        update_data["max_tokens"] = req.max_tokens
    if req.chunk_size_kb is not None:
        update_data["chunk_size_kb"] = req.chunk_size_kb
    if req.max_content_kb is not None:
        update_data["max_content_kb"] = req.max_content_kb
    if req.summary_prompt is not None:
        update_data["summary_prompt"] = req.summary_prompt
    if req.partial_prompt is not None:
        update_data["partial_prompt"] = req.partial_prompt
    if req.merge_prompt is not None:
        update_data["merge_prompt"] = req.merge_prompt

    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的配置")

    if not ai_config_store.update_config(**update_data):
        raise HTTPException(status_code=500, detail="更新配置失败")

    logger.info(f"AI 配置已更新: {list(update_data.keys())}")

    return {
        "status": "success",
        "message": "AI 配置已更新"
    }


@app.post("/api/ai/test")
async def test_ai_connection(req: AIConfigRequest = None):
    """测试 AI 服务连接"""
    # 如果提供了参数，用参数测试；否则用当前配置测试
    if req and (req.api_base or req.api_key or req.model):
        api_base = req.api_base or "https://api.openai.com/v1"
        api_key = req.api_key
        model = req.model or "gpt-4o-mini"

        if not api_key:
            raise HTTPException(status_code=400, detail="需要提供 API Key")
    else:
        if not ai_config_store.is_enabled():
            raise HTTPException(status_code=400, detail="AI 服务未启用或未配置 API Key")

        config = ai_config_store.get_config()
        api_base = config.api_base
        api_key = config.api_key
        model = config.model

    # 调用测试
    if ai_service.test_connection(api_base, api_key, model):
        return {
            "status": "success",
            "message": "AI 服务连接正常"
        }
    else:
        raise HTTPException(status_code=400, detail="AI 服务连接失败")


# ==================== AI 搜索配置管理 ====================

@app.get("/api/ai/search-config")
async def get_ai_search_config():
    """获取 AI 搜索配置"""
    config = ai_config_store.get_config()
    return {
        "ai_search_enabled": config.ai_search_enabled,
        "keyword_extraction_enabled": config.keyword_extraction_enabled,
        "rerank_enabled": config.rerank_enabled,
        "keyword_extractor_type": config.keyword_extractor_type,
        "keyword_ollama_url": config.keyword_ollama_url,
        "keyword_ollama_model": config.keyword_ollama_model,
        "keyword_api_url": config.keyword_api_url,
        "keyword_api_key": config.keyword_api_key[:8] + "..." if config.keyword_api_key else "",
        "keyword_api_model": config.keyword_api_model,
        "keyword_prompt": config.keyword_prompt,
        "reranker_type": config.reranker_type,
        "reranker_bge_model": config.reranker_bge_model,
        "reranker_cohere_url": config.reranker_cohere_url,
        "reranker_cohere_key": config.reranker_cohere_key[:8] + "..." if config.reranker_cohere_key else "",
        "reranker_cohere_model": config.reranker_cohere_model,
        "reranker_jina_url": config.reranker_jina_url,
        "reranker_jina_key": config.reranker_jina_key[:8] + "..." if config.reranker_jina_key else "",
        "reranker_jina_model": config.reranker_jina_model,
        "rerank_top_n": config.rerank_top_n
    }


@app.put("/api/ai/search-config")
async def update_ai_search_config(req: AISearchConfigRequest):
    """更新 AI 搜索配置"""
    update_data = {}

    # 开关配置
    if req.ai_search_enabled is not None:
        update_data["ai_search_enabled"] = req.ai_search_enabled
    if req.keyword_extraction_enabled is not None:
        update_data["keyword_extraction_enabled"] = req.keyword_extraction_enabled
    if req.rerank_enabled is not None:
        update_data["rerank_enabled"] = req.rerank_enabled

    # 关键词提取配置
    if req.keyword_extractor_type is not None:
        update_data["keyword_extractor_type"] = req.keyword_extractor_type
    if req.keyword_ollama_url is not None:
        update_data["keyword_ollama_url"] = req.keyword_ollama_url
    if req.keyword_ollama_model is not None:
        update_data["keyword_ollama_model"] = req.keyword_ollama_model
    if req.keyword_api_url is not None:
        update_data["keyword_api_url"] = req.keyword_api_url
    if req.keyword_api_key is not None:
        update_data["keyword_api_key"] = req.keyword_api_key
    if req.keyword_api_model is not None:
        update_data["keyword_api_model"] = req.keyword_api_model
    if req.keyword_prompt is not None:
        update_data["keyword_prompt"] = req.keyword_prompt

    # Rerank 配置
    if req.reranker_type is not None:
        update_data["reranker_type"] = req.reranker_type
    if req.reranker_bge_model is not None:
        update_data["reranker_bge_model"] = req.reranker_bge_model
    if req.reranker_cohere_url is not None:
        update_data["reranker_cohere_url"] = req.reranker_cohere_url
    if req.reranker_cohere_key is not None:
        update_data["reranker_cohere_key"] = req.reranker_cohere_key
    if req.reranker_cohere_model is not None:
        update_data["reranker_cohere_model"] = req.reranker_cohere_model
    if req.reranker_jina_url is not None:
        update_data["reranker_jina_url"] = req.reranker_jina_url
    if req.reranker_jina_key is not None:
        update_data["reranker_jina_key"] = req.reranker_jina_key
    if req.reranker_jina_model is not None:
        update_data["reranker_jina_model"] = req.reranker_jina_model
    if req.rerank_top_n is not None:
        update_data["rerank_top_n"] = req.rerank_top_n

    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的配置")

    if not ai_config_store.update_config(**update_data):
        raise HTTPException(status_code=500, detail="更新配置失败")

    logger.info(f"AI 搜索配置已更新: {list(update_data.keys())}")

    return {
        "status": "success",
        "message": "AI 搜索配置已更新"
    }


@app.post("/api/ai/rerank-test")
async def test_rerank():
    """测试 Rerank 模型/服务是否可用"""
    config = ai_config_store.get_config()

    try:
        rerank_config = RerankConfig(
            enabled=True,
            reranker_type=config.reranker_type,
            bge_model=config.reranker_bge_model,
            cohere_url=config.reranker_cohere_url,
            cohere_key=config.reranker_cohere_key,
            cohere_model=config.reranker_cohere_model,
            jina_url=config.reranker_jina_url,
            jina_key=config.reranker_jina_key,
            jina_model=config.reranker_jina_model
        )

        reranker = create_reranker(rerank_config)

        if reranker.is_available():
            return {
                "status": "success",
                "message": f"Rerank 服务可用 (类型: {config.reranker_type})"
            }
        else:
            return {
                "status": "error",
                "message": f"Rerank 服务不可用 (类型: {config.reranker_type})"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rerank 测试失败: {e}")


@app.post("/api/ai/keyword-test")
async def test_keyword_extractor():
    """测试关键词提取器是否可用"""
    config = ai_config_store.get_config()

    try:
        extractor_config = KeywordExtractorConfig(
            enabled=True,
            extractor_type=config.keyword_extractor_type,
            ollama_url=config.keyword_ollama_url,
            ollama_model=config.keyword_ollama_model,
            api_url=config.keyword_api_url,
            api_key=config.keyword_api_key,
            api_model=config.keyword_api_model
        )

        extractor = create_keyword_extractor(extractor_config)

        if extractor.is_available():
            # 尝试简单提取
            result = extractor.extract("测试查询")
            return {
                "status": "success",
                "message": f"关键词提取器可用 (类型: {config.keyword_extractor_type})",
                "test_result": result
            }
        else:
            return {
                "status": "error",
                "message": f"关键词提取器不可用 (类型: {config.keyword_extractor_type})"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关键词提取器测试失败: {e}")


# ==================== 同步管理 ====================

@app.get("/api/scheduled-jobs")
async def get_scheduled_jobs():
    """获取定时任务列表和下次执行时间"""
    try:
        jobs = scheduler.scheduler.get_jobs()
        job_list = []
        for job in jobs:
            job_list.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        return {
            "total": len(job_list),
            "jobs": job_list
        }
    except Exception as e:
        return {"error": str(e), "jobs": []}


@app.post("/api/sync")
async def trigger_sync(req: SyncRequest, background_tasks: BackgroundTasks):
    """
    手动触发同步

    支持的数据源：
    - feishu: 飞书文档
    - wps: WPS 本地文件
    - yinxiang: 印象笔记
    - quark: 夸克网盘
    """
    global sync_engine

    # 延迟初始化同步引擎
    if sync_engine is None:
        idx = get_index()
        if not idx:
            raise HTTPException(
                status_code=503,
                detail="索引功能未启用，无法执行同步"
            )
        sync_engine = SyncEngine(metadata, idx)

    # 后台任务：同步
    background_tasks.add_task(
        perform_sync,
        source=req.source,
        account=req.account
    )

    return {
        "status": "syncing",
        "source": req.source,
        "account": req.account
    }


def perform_sync(source: str, account: str = None):
    """执行同步（后台任务）"""
    global sync_engine

    # 确保 sync_engine 已初始化
    if sync_engine is None:
        idx = get_index()
        if not idx:
            logger.error("索引未初始化，无法执行同步")
            return
        sync_engine = SyncEngine(metadata, idx)

    try:
        if source == "feishu":
            # 获取用户访问令牌（如果有的话）
            user_access_token = None
            account_obj = None

            # 尝试从已注册的账号获取用户令牌
            if account and account in feishu_adapter.accounts:
                account_obj = feishu_adapter.accounts[account]
                user_access_token = account_obj.user_access_token

            # 如果没有指定账号，尝试使用 wiki_user 账号
            if not account and "wiki_user" in feishu_adapter.accounts:
                account = "wiki_user"
                account_obj = feishu_adapter.accounts["wiki_user"]
                user_access_token = account_obj.user_access_token

            # 尝试同步
            stats = sync_engine.sync_source(
                "feishu",
                feishu_adapter,
                account,
                user_access_token=user_access_token
            )

            # 如果同步失败且返回 0 个文档，可能是 token 过期
            if stats.get('added', 0) == 0 and stats.get('skipped', 0) == 0 and account_obj:
                logger.info("同步返回 0 个文档，尝试刷新用户令牌...")
                if account_obj.refresh_user_token():
                    # 保存新的令牌
                    KeychainManager.save_feishu_account(
                        name=account_obj.name,
                        app_id=account_obj.app_id,
                        app_secret=account_obj.app_secret,
                        user_access_token=account_obj.user_access_token,
                        refresh_token=account_obj.refresh_token
                    )
                    # 重新同步
                    logger.info("令牌刷新成功，重新同步...")
                    stats = sync_engine.sync_source(
                        "feishu",
                        feishu_adapter,
                        account,
                        user_access_token=account_obj.user_access_token
                    )

            logger.info(f"飞书同步完成: {stats}")

        elif source == "local":
            # 本地文件同步
            stats = sync_local_files(account)
            logger.info(f"本地文件同步完成: {stats}")

        elif source == "wps":
            # TODO: 实现 WPS 同步
            logger.warning("WPS 同步尚未实现")

        elif source == "yinxiang":
            # 印象笔记同步
            if not yinxiang_adapter.accounts:
                logger.warning("没有配置印象笔记账号")
                return

            # 确保索引已初始化
            idx = get_index()
            if not idx:
                logger.error("索引未初始化，无法同步")
                return

            # 初始化同步引擎
            if sync_engine is None:
                sync_engine = SyncEngine(metadata, idx)

            # 获取账号名
            account_name = account if account else list(yinxiang_adapter.accounts.keys())[0]
            logger.info(f"开始印象笔记同步: {account_name}")

            # sync_source 会调用 adapter.fetch_all_for_index()
            stats = sync_engine.sync_source(
                "yinxiang",
                yinxiang_adapter,
                account_name
            )
            logger.info(f"印象笔记同步完成: {stats}")

        elif source == "quark":
            # TODO: 实现夸克网盘同步
            logger.warning("夸克网盘同步尚未实现")

        else:
            logger.error(f"未知数据源: {source}")

    except Exception as e:
        logger.error(f"同步失败 [{source}]: {e}")
        import traceback
        traceback.print_exc()


def sync_local_files(directory_id: str = None) -> dict:
    """
    同步本地文件到索引

    支持功能：
    1. 增量同步：通过内容哈希检测文件变化
    2. AI 总结：大文件自动调用 AI 生成摘要和标签
    3. 快速跳过：文件大小和修改时间未变则跳过
    4. 图片索引：支持图片文件的语义描述和标签

    Args:
        directory_id: 目录 ID（可选，不指定则同步所有启用的目录）

    Returns:
        同步统计信息
    """
    idx = get_index()
    if not idx:
        logger.error("索引功能未启用，无法同步本地文件")
        return {"error": "索引功能未启用"}

    stats = {
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "ai_summarized": 0,
        "images_processed": 0
    }

    # 检查 AI 服务是否启用
    use_ai = ai_config_store.is_enabled()
    if use_ai:
        logger.info(f"AI 总结服务已启用，阈值: {ai_config_store.get_config().summary_threshold_kb}KB")

    # 检查图片索引是否启用
    image_index_enabled = os.getenv("GUIYI_IMAGE_INDEX_ENABLED", "false").lower() == "true"
    if image_index_enabled:
        logger.info("图片索引服务已启用")

    try:
        # 获取文件列表
        docs = local_file_adapter.fetch_all_for_index(account=directory_id)
        logger.info(f"扫描到 {len(docs)} 个本地文件")

        # 批量获取所有已存在的文档状态（减少数据库查询）
        existing_docs = metadata.get_all_synced_docs(source="local", account=directory_id)
        existing_states = {d["id"]: d for d in existing_docs}
        logger.info(f"已有 {len(existing_states)} 个本地文档在索引中")

        # 批量处理：收集需要索引的文档
        docs_to_index = []
        metadata_updates = []

        BATCH_SIZE = 50  # 每批处理 50 个文件

        for i, doc in enumerate(docs):
            try:
                doc_id = doc["id"]
                file_path = doc.get("file_path", "")
                title = doc.get("title", "unnamed")
                file_size = doc.get("file_size", 0)

                # 快速检测：检查文件大小和修改时间
                last_state = existing_states.get(doc_id)
                if last_state:
                    # 获取当前文件信息
                    file_info = AIService.get_file_info(file_path)
                    cached_size = last_state.get("file_size", 0)
                    cached_mtime = last_state.get("file_mtime", 0)

                    # 如果大小和修改时间都没变，直接跳过（无需读取内容）
                    if (file_info["size"] == cached_size and
                        file_info["mtime"] == cached_mtime and
                        cached_size > 0):
                        stats["skipped"] += 1
                        continue

                # 检查是否是图片文件
                is_image = LocalFileAdapter.is_image_file(file_path)

                # 获取文件内容（只读）
                ai_summary = None
                ai_tags = []
                if is_image:
                    content_result = local_file_adapter.get_document_content_with_metadata(
                        doc_id=doc_id,
                        file_path=file_path
                    )
                    content = content_result.get("content")
                    ai_summary = content_result.get("ai_summary")
                    ai_tags = content_result.get("ai_tags") or []
                    if content:
                        stats["images_processed"] += 1
                        logger.debug(f"  图片处理完成: {title}")
                else:
                    content = local_file_adapter.get_document_content(
                        doc_id=doc_id,
                        file_path=file_path
                    )

                if not content:
                    stats["skipped"] += 1
                    continue

                # 获取文件信息
                file_info = AIService.get_file_info(file_path)
                file_size = file_info["size"]

                # AI 总结处理（图片文件已有描述/标签，跳过）
                if not is_image and use_ai and ai_config_store.should_summarize(file_size):
                    logger.debug(f"  文件较大 ({file_size/1024:.1f}KB)，调用 AI 总结...")
                    ai_result = ai_service.summarize_document(
                        content=content,
                        title=title,
                        file_type=doc.get("obj_type", "")
                    )
                    if ai_result:
                        ai_summary = ai_result.get("summary", "")
                        ai_tags = ai_result.get("tags", [])
                        stats["ai_summarized"] += 1
                        logger.debug(f"  AI 总结完成: {title[:30]}...")

                # 构建索引内容
                if ai_summary:
                    # 使用 AI 生成的摘要和标签
                    index_content = f"{title}\n\n[AI 摘要]\n{ai_summary}\n\n[标签] {', '.join(ai_tags)}\n\n[原文片段]\n{content[:500]}"
                else:
                    # 直接使用原文
                    index_content = f"{title}\n\n{content}"

                doc["content"] = index_content
                doc["ai_summary"] = ai_summary
                doc["ai_tags"] = ai_tags

                # 计算内容哈希
                content_hash = hashlib.md5(content.encode()).hexdigest()

                # 检查是否需要更新
                if last_state is None:
                    # 新增
                    docs_to_index.append(doc)
                    metadata_updates.append({
                        "doc_id": doc_id,
                        "source": "local",
                        "account": doc.get("account"),
                        "url": doc.get("url", ""),
                        "title": title,
                        "content_hash": content_hash,
                        "file_size": file_info["size"],
                        "file_mtime": file_info["mtime"],
                        "ai_summary": ai_summary,
                        "ai_tags": json.dumps(ai_tags) if ai_tags else None,
                        "last_modified": datetime.now().timestamp()
                    })
                    stats["added"] += 1

                elif last_state["content_hash"] != content_hash:
                    # 更新
                    docs_to_index.append(doc)
                    metadata_updates.append({
                        "doc_id": doc_id,
                        "source": "local",
                        "account": doc.get("account"),
                        "url": doc.get("url", ""),
                        "title": title,
                        "content_hash": content_hash,
                        "file_size": file_info["size"],
                        "file_mtime": file_info["mtime"],
                        "ai_summary": ai_summary,
                        "ai_tags": json.dumps(ai_tags) if ai_tags else None,
                        "last_modified": datetime.now().timestamp()
                    })
                    stats["updated"] += 1

                else:
                    # 内容未变，但仍需更新 file_size 和 file_mtime（用于下次快速跳过）
                    metadata.update_file_info(doc_id, file_info["size"], file_info["mtime"])
                    stats["skipped"] += 1

                # 批量处理
                if len(docs_to_index) >= BATCH_SIZE:
                    logger.info(f"  批量索引 {len(docs_to_index)} 个文档 (进度: {i+1}/{len(docs)})...")
                    idx.index_documents(docs_to_index)

                    # 批量更新元数据
                    for m in metadata_updates:
                        try:
                            metadata.upsert_doc(**m)
                        except Exception:
                            pass

                    docs_to_index = []
                    metadata_updates = []

                # 每 100 个文件打印进度
                if (i + 1) % 100 == 0:
                    logger.info(f"  已处理: {i+1}/{len(docs)}, 新增 {stats['added']}, 跳过 {stats['skipped']}, AI总结 {stats['ai_summarized']}, 图片 {stats['images_processed']}")

            except Exception as e:
                logger.error(f"  [{i+1}/{len(docs)}] [!] 失败: {doc.get('title', 'unknown')} - {e}")
                stats["failed"] += 1

        # 处理剩余的文档
        if docs_to_index:
            logger.info(f"  批量索引最后 {len(docs_to_index)} 个文档...")
            idx.index_documents(docs_to_index)

            for m in metadata_updates:
                try:
                    metadata.upsert_doc(**m)
                except Exception:
                    pass

        # 保存索引
        idx.save()
        logger.info(f"本地文件同步完成: 新增 {stats['added']}, 更新 {stats['updated']}, 跳过 {stats['skipped']}, 失败 {stats['failed']}, AI总结 {stats['ai_summarized']}, 图片 {stats['images_processed']}")

    except Exception as e:
        logger.error(f"本地文件同步失败: {e}")
        import traceback
        traceback.print_exc()

    return stats


@app.get("/api/sync/status")
async def get_sync_status():
    """获取同步状态"""
    return {
        "stats": metadata.get_sync_stats(),
        "scheduled_jobs": scheduler.get_jobs_info()
    }


@app.get("/api/sync/logs")
async def get_sync_logs(limit: int = 100):
    """获取同步日志"""
    # TODO: 从数据库读取同步日志
    return {
        "total": 0,
        "logs": []
    }


# ==================== 定时任务管理 ====================

@app.post("/api/scheduler/jobs")
async def add_scheduled_job(
    source: str,
    account: str = None,
    cron_expression: str = None,
    interval_hours: int = None
):
    """添加定时同步任务"""
    try:
        job_id = scheduler.add_sync_job(
            source=source,
            sync_func=perform_sync,
            account=account,
            cron_expression=cron_expression,
            interval_hours=interval_hours
        )

        return {
            "status": "success",
            "job_id": job_id,
            "message": "定时任务添加成功"
        }

    except Exception as e:
        logger.error(f"添加定时任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scheduler/jobs")
async def list_scheduled_jobs():
    """列出所有定时任务"""
    return {
        "total": len(scheduler.get_jobs_info()),
        "jobs": scheduler.get_jobs_info()
    }


@app.delete("/api/scheduler/jobs/{job_id}")
async def remove_scheduled_job(job_id: str):
    """删除定时任务"""
    if scheduler.remove_sync_job(job_id):
        return {
            "status": "success",
            "message": f"任务 {job_id} 已删除"
        }
    else:
        raise HTTPException(status_code=404, detail="任务不存在")


@app.put("/api/scheduler/jobs/{job_id}")
async def update_scheduled_job(
    job_id: str,
    cron_expression: str = None,
    interval_hours: int = None
):
    """更新定时同步任务"""
    if scheduler.update_sync_job(
        job_id=job_id,
        sync_func=perform_sync,
        cron_expression=cron_expression,
        interval_hours=interval_hours
    ):
        return {
            "status": "success",
            "message": f"任务 {job_id} 已更新"
        }
    else:
        raise HTTPException(status_code=404, detail="任务不存在")


# ==================== 启动和关闭 ====================

def load_saved_feishu_accounts():
    """加载已保存的飞书账号"""
    # 尝试加载 wiki_user 账号（这是主要的飞书知识库账号）
    saved_accounts = ["wiki_user"]  # 可以扩展为从数据库读取

    for name in saved_accounts:
        credentials = KeychainManager.get_feishu_account(name)
        if credentials:
            try:
                account = FeishuAccount(
                    name=name,
                    app_id=credentials["app_id"],
                    app_secret=credentials["app_secret"],
                    user_access_token=credentials.get("user_access_token"),
                    refresh_token=credentials.get("refresh_token")
                )

                if feishu_adapter.add_account(account):
                    logger.info(f"✓ 已加载飞书账号: {name}")
            except Exception as e:
                logger.warning(f"加载飞书账号 [{name}] 失败: {e}")


def load_saved_yinxiang_accounts():
    """加载已保存的印象笔记账号"""
    import json

    # 从配置文件读取账号列表
    config_path = settings.YINXIANG_ACCOUNTS_PATH

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                account_list = json.load(f)
        except Exception as e:
            logger.warning(f"加载印象笔记账号配置失败: {e}")
            account_list = []
    else:
        account_list = []

    for name in account_list:
        credentials = KeychainManager.get_yinxiang_account(name)
        if credentials:
            try:
                account = YinxiangAccount(
                    name=name,
                    token=credentials["token"],
                    note_store_url=credentials["note_store_url"]
                )
                yinxiang_adapter.add_account(account)
                logger.info(f"✓ 已加载印象笔记账号: {name}")
            except Exception as e:
                logger.warning(f"加载印象笔记账号 [{name}] 失败: {e}")


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("=" * 60)
    logger.info("🚀 GuiYi Backend Phase 3 启动中...")
    logger.info("=" * 60)

    if os.getenv("GUIYI_SKIP_STARTUP_ACCOUNT_LOAD", "false").lower() == "true":
        logger.info("已跳过启动期账号凭证加载")
    else:
        # 加载已保存的飞书账号
        load_saved_feishu_accounts()

        # 加载已保存的印象笔记账号
        load_saved_yinxiang_accounts()

    # 启动定时调度器
    scheduler.start()

    # 设置默认定时任务
    scheduler.setup_default_jobs(perform_sync)

    logger.info("=" * 60)
    logger.info("📍 API 地址: http://127.0.0.1:8765")
    logger.info("📖 API 文档: http://127.0.0.1:8765/docs")
    logger.info("=" * 60)
    logger.info("提示:")
    logger.info("  - 首次运行会自动下载向量模型（约 1-2GB）")
    logger.info("  - 索引功能将在第一次搜索或保存时自动启用")
    logger.info("  - 已启用飞书多账号支持")
    logger.info("  - 已启用定时同步调度器")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info("正在关闭服务...")

    # 停止调度器
    scheduler.stop()

    logger.info("服务已关闭")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
