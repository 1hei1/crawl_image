
import asyncio
import os
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from pathlib import Path
from typing import List

# 确保项目根目录在 Python 路径中
import sys
sys.path.insert(0, str(Path(__file__).parent))

from crawler.main_crawler import ImageCrawler
from database.models.image import ImageModel
from database.distributed_ha_manager import DistributedHAManager
from config.ha_config_loader import load_ha_config
from storage.distributed_file_manager import DistributedFileManager
from storage.file_sync_api import create_file_sync_api
from loguru import logger

# --------------------------------------------------------------------------
# 日志流和应用设置
# --------------------------------------------------------------------------

# 创建一个队列来存储日志消息
log_queue = asyncio.Queue()

# 自定义日志处理器，将日志放入队列
async def queue_sink(message):
    await log_queue.put(message.strip())

# 配置 loguru
logger.add(
    "logs/crawler.log",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    enqueue=True,
    rotation="10 MB"
)
logger.add(queue_sink, level="INFO", format="{message}")

# 初始化 FastAPI 应用
app = FastAPI(
    title="图片爬虫 API",
    description="提供一个用于控制和监控图片爬虫的 Web API。",
    version="1.0.0"
)

# --------------------------------------------------------------------------
# 全局变量和状态
# --------------------------------------------------------------------------

# 初始化分布式HA管理器
ha_manager = None
file_manager = None
try:
    # 加载HA配置
    nodes, local_node_name, config = load_ha_config()
    ha_manager = DistributedHAManager(nodes, local_node_name)
    ha_manager.start_monitoring()

    # 初始化分布式文件管理器
    servers = [
        {
            "host": node.server.host,
            "port": node.server.api_port,
            "name": node.name
        }
        for node in nodes if node.name != local_node_name
    ]

    # 暂时跳过文件管理器初始化，避免异步问题
    file_manager = None
    # file_manager = DistributedFileManager(
    #     local_storage_path="data",
    #     servers=servers
    # )
    # file_manager.start_sync_service()

    logger.info(f"✅ 分布式HA管理器初始化成功，当前主节点: {ha_manager.current_primary}")
    # logger.info(f"✅ 分布式文件管理器初始化成功，同步到 {len(servers)} 个服务器")
except Exception as e:
    logger.warning(f"⚠️ HA管理器初始化失败，使用默认数据库: {e}")
    ha_manager = None
    file_manager = None

# 创建一个 ImageCrawler 的单例
try:
    # 如果有HA管理器，创建一个包装的数据库管理器
    if ha_manager:
        from database.enhanced_manager import EnhancedDatabaseManager
        # 创建一个包装管理器，将HA管理器传递给它
        wrapped_db_manager = type('WrappedDBManager', (), {
            'get_session': ha_manager.get_session,
            'create_tables': lambda: None,  # HA管理器已经处理了表创建
            'is_disaster_recovery_enabled': lambda: True,
            'get_database_info': lambda: {"type": "HA_PostgreSQL", "status": "active"},
            'get_health_status': lambda: ha_manager.get_cluster_status(),
            'start_monitoring': lambda: None,
            'stop_monitoring': lambda: None,
            'create_backup': lambda name: None,
            'backup_manager': None,
            'get_failover_status': lambda: ha_manager.get_cluster_status(),
            'get_failover_history': lambda limit: []
        })()
        image_crawler = ImageCrawler(db_manager=wrapped_db_manager)
        logger.info("✅ 使用HA数据库管理器初始化爬虫")
    else:
        image_crawler = ImageCrawler()
        logger.info("✅ 使用默认数据库管理器初始化爬虫")

    CRAWLER_ENABLED = True
except Exception as e:
    logger.error(f"❌ 初始化 ImageCrawler 失败: {e}")
    image_crawler = None
    CRAWLER_ENABLED = False

# 爬虫任务状态
crawl_status = {
    "is_crawling": False,
    "current_url": None,
    "error": None
}

# --------------------------------------------------------------------------
# Pydantic 模型
# --------------------------------------------------------------------------

class CrawlRequest(BaseModel):
    """爬取请求的数据模型"""
    url: str

class DeleteImagesRequest(BaseModel):
    """删除图片的请求数据模型"""
    image_ids: List[int]

# --------------------------------------------------------------------------
# 后台任务
# --------------------------------------------------------------------------

async def run_crawl_task(url: str):
    """在后台运行爬虫任务"""
    if not CRAWLER_ENABLED:
        logger.error("爬虫未启用，无法执行任务")
        crawl_status["error"] = "爬虫未正确初始化，请检查配置"
        return

    crawl_status["is_crawling"] = True
    crawl_status["current_url"] = url
    crawl_status["error"] = None
    
    logger.info(f"🚀 后台任务开始: 爬取 {url}")
    
    try:
        await image_crawler.crawl_website(url=url)
        logger.info(f"✅ 爬取完成: {url}")
    except Exception as e:
        logger.error(f"❌ 爬取任务失败: {url}, 错误: {e}")
        crawl_status["error"] = str(e)
    finally:
        crawl_status["is_crawling"] = False
        crawl_status["current_url"] = None
        logger.info("后台任务结束")

# --------------------------------------------------------------------------
# API 路由
# --------------------------------------------------------------------------

@app.post("/crawl", status_code=202)
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    启动一个爬虫任务
    """
    if not CRAWLER_ENABLED:
        raise HTTPException(status_code=503, detail="爬虫服务不可用")

    if crawl_status["is_crawling"]:
        raise HTTPException(status_code=409, detail=f"任务进行中: {crawl_status['current_url']}")
    
    url = request.url
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail="无效的 URL")
        
    background_tasks.add_task(run_crawl_task, url)
    
    return {"message": f"爬取任务已启动: {url}"}


@app.get("/status")
async def get_status():
    """
    获取爬虫的当前状态
    """
    return JSONResponse(content={
        "crawling_active": crawl_status["is_crawling"],
        "current_target": crawl_status["current_url"],
        "last_error": crawl_status["error"],
    })

async def log_streamer(request: Request):
    """流式传输日志"""
    try:
        while True:
            if await request.is_disconnected():
                break
            log_message = await log_queue.get()
            yield f"data: {log_message}\n\n"
            log_queue.task_done()
    except asyncio.CancelledError:
        logger.info("日志流客户端断开连接")

@app.get("/stream-logs")
async def stream_logs(request: Request):
    return StreamingResponse(log_streamer(request), media_type="text/event-stream")

# --------------------------------------------------------------------------
# 数据库和图片操作 API
# --------------------------------------------------------------------------

@app.get("/api/images")
async def get_images():
    """
    获取所有图片记录
    """
    if not CRAWLER_ENABLED:
        raise HTTPException(status_code=503, detail="爬虫服务不可用")
    
    try:
        with image_crawler.db_manager.get_session() as session:
            images = session.query(ImageModel).all()
            return [{ "id": img.id, "url": img.url, "file_path": img.local_path, "filename": img.filename } for img in images]
    except Exception as e:
        logger.error(f"获取图片列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取图片列表失败")

@app.delete("/api/images")
async def delete_images(request: DeleteImagesRequest):
    """
    批量删除图片 - 优化版本
    """
    if not CRAWLER_ENABLED:
        raise HTTPException(status_code=503, detail="爬虫服务不可用")

    # 如果图片数量很多，启动后台任务
    if len(request.image_ids) > 50:
        task_id = f"delete_task_{int(time.time())}"
        asyncio.create_task(
            _batch_delete_images_background(request.image_ids, task_id)
        )
        return {
            "message": f"已启动后台删除任务，共 {len(request.image_ids)} 张图片",
            "task_id": task_id,
            "background": True
        }
    else:
        # 小批量直接处理
        return await _batch_delete_images_sync(request.image_ids)

@app.get("/api/db-status")
async def get_db_status():
    """
    获取数据库健康状态
    """
    if not CRAWLER_ENABLED:
        return {"status": "unknown", "message": "爬虫服务不可用"}

    try:
        if ha_manager:
            # 如果使用HA管理器，返回集群状态
            status = ha_manager.get_cluster_status()
            status["ha_enabled"] = True
            return status
        elif hasattr(image_crawler.db_manager, 'is_disaster_recovery_enabled') and image_crawler.db_manager.is_disaster_recovery_enabled():
            # 使用默认数据库管理器的健康监控
            health_status = image_crawler.db_manager.get_health_status()
            health_status["ha_enabled"] = False
            return health_status
        else:
            return {"status": "unknown", "message": "数据库健康监控未启用", "ha_enabled": False}
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取数据库状态失败")

@app.get("/api/ha-status")
async def get_ha_status():
    """
    获取高可用系统状态
    """
    if not ha_manager:
        return {
            "ha_enabled": False,
            "message": "高可用系统未启用"
        }

    try:
        status = ha_manager.get_cluster_status()
        status["ha_enabled"] = True
        return status
    except Exception as e:
        logger.error(f"获取HA状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取HA状态失败")

@app.get("/api/sync-status")
async def get_sync_status():
    """
    获取数据同步状态
    """
    if not ha_manager:
        return {
            "sync_enabled": False,
            "message": "高可用系统未启用"
        }

    try:
        sync_status = ha_manager.get_sync_status()
        sync_status["sync_enabled"] = True
        return sync_status
    except Exception as e:
        logger.error(f"获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取同步状态失败")

@app.post("/api/force-sync")
async def force_sync():
    """
    强制执行全量数据同步
    """
    if not ha_manager:
        raise HTTPException(status_code=400, detail="高可用系统未启用")

    try:
        success = ha_manager.force_sync_all()
        if success:
            return {
                "status": "success",
                "message": "全量同步已启动"
            }
        else:
            return {
                "status": "failed",
                "message": "全量同步启动失败"
            }
    except Exception as e:
        logger.error(f"强制同步失败: {e}")
        raise HTTPException(status_code=500, detail="强制同步失败")

@app.post("/api/ha-failover/{target_node}")
async def manual_failover(target_node: str):
    """
    手动故障转移
    """
    if not ha_manager:
        raise HTTPException(status_code=503, detail="高可用系统未启用")

    try:
        success = ha_manager.manual_failover(target_node)
        if success:
            return {"status": "success", "message": f"故障转移到 {target_node} 成功"}
        else:
            raise HTTPException(status_code=400, detail="故障转移失败")
    except Exception as e:
        logger.error(f"手动故障转移失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/storage-status")
async def get_storage_status():
    """
    获取存储状态
    """
    if not file_manager:
        return {
            "distributed_storage": False,
            "message": "分布式存储未启用"
        }

    try:
        stats = file_manager.get_storage_stats()
        stats["distributed_storage"] = True
        return stats
    except Exception as e:
        logger.error(f"获取存储状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取存储状态失败")

@app.post("/api/force-file-sync")
async def force_file_sync():
    """
    强制文件同步
    """
    if not file_manager:
        raise HTTPException(status_code=503, detail="分布式存储未启用")

    try:
        # 扫描本地所有文件并添加到同步队列
        sync_count = 0

        for file_path in file_manager.images_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(file_manager.images_path)
                await file_manager._add_sync_task(str(relative_path))
                sync_count += 1

        return {
            "status": "success",
            "message": f"已添加 {sync_count} 个文件到同步队列"
        }
    except Exception as e:
        logger.error(f"强制文件同步失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------
# 文件同步API集成
# --------------------------------------------------------------------------

# 如果启用了分布式文件管理，集成文件同步API
if file_manager:
    try:
        file_sync_api = create_file_sync_api(file_manager)
        app.mount("/file-sync", file_sync_api.app, name="file_sync")
        logger.info("✅ 文件同步API已集成")
    except Exception as e:
        logger.error(f"❌ 文件同步API集成失败: {e}")

# --------------------------------------------------------------------------
# 静态文件服务
# --------------------------------------------------------------------------

app.mount("/static/data", StaticFiles(directory="data"), name="data")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", include_in_schema=False)
async def read_index():
    index_path = Path("frontend/index.html")
    if not index_path.exists():
        return JSONResponse(status_code=404, content={"message": "index.html not found"})
    return FileResponse(str(index_path))

# --------------------------------------------------------------------------
# 主程序入口
# --------------------------------------------------------------------------
# 批量删除功能
# --------------------------------------------------------------------------

# 批量删除任务状态跟踪
delete_tasks_status = {}

async def _batch_delete_images_sync(image_ids: list) -> dict:
    """同步批量删除图片（小批量）"""
    deleted_count = 0
    errors = []

    try:
        with image_crawler.db_manager.get_session() as session:
            # 批量查询图片信息
            images = session.query(ImageModel).filter(
                ImageModel.id.in_(image_ids)
            ).all()

            # 收集文件路径
            files_to_delete = []
            images_to_delete = []

            for image in images:
                if image.local_path and os.path.exists(image.local_path):
                    files_to_delete.append(image.local_path)
                images_to_delete.append(image)

            # 批量删除文件
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                except Exception as e:
                    errors.append(f"删除文件失败 {file_path}: {e}")

            # 批量删除数据库记录
            for image in images_to_delete:
                session.delete(image)
                deleted_count += 1

            session.commit()

    except Exception as e:
        logger.error(f"批量删除图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量删除失败: {e}")

    return {
        "message": f"成功删除 {deleted_count} 张图片",
        "deleted_count": deleted_count,
        "errors": errors
    }

async def _batch_delete_images_background(image_ids: list, task_id: str):
    """后台批量删除图片（大批量）"""
    delete_tasks_status[task_id] = {
        "status": "running",
        "total": len(image_ids),
        "processed": 0,
        "deleted": 0,
        "errors": [],
        "start_time": time.time()
    }

    try:
        batch_size = 20  # 每批处理20个

        for i in range(0, len(image_ids), batch_size):
            batch_ids = image_ids[i:i + batch_size]

            try:
                with image_crawler.db_manager.get_session() as session:
                    # 批量查询当前批次的图片
                    images = session.query(ImageModel).filter(
                        ImageModel.id.in_(batch_ids)
                    ).all()

                    # 删除文件和数据库记录
                    for image in images:
                        try:
                            # 删除文件
                            if image.local_path and os.path.exists(image.local_path):
                                os.remove(image.local_path)

                            # 删除数据库记录
                            session.delete(image)
                            delete_tasks_status[task_id]["deleted"] += 1

                        except Exception as e:
                            delete_tasks_status[task_id]["errors"].append(
                                f"删除图片 {image.id} 失败: {e}"
                            )

                    session.commit()

            except Exception as e:
                delete_tasks_status[task_id]["errors"].append(
                    f"处理批次失败: {e}"
                )

            delete_tasks_status[task_id]["processed"] += len(batch_ids)

            # 短暂休息，避免过度占用资源
            await asyncio.sleep(0.1)

        delete_tasks_status[task_id]["status"] = "completed"
        delete_tasks_status[task_id]["end_time"] = time.time()

    except Exception as e:
        delete_tasks_status[task_id]["status"] = "failed"
        delete_tasks_status[task_id]["error"] = str(e)
        delete_tasks_status[task_id]["end_time"] = time.time()

@app.get("/api/delete-task/{task_id}")
async def get_delete_task_status(task_id: str):
    """获取删除任务状态"""
    if task_id not in delete_tasks_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    return delete_tasks_status[task_id]

# --------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
