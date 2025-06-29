"""
主爬虫类

整合所有爬虫功能的主要接口
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
import time
from datetime import datetime, timezone

from crawler.core.async_crawler import AsyncCrawler, TaskScheduler
from crawler.core.spider import ImageSpider
from crawler.core.downloader import ImageDownloader
from database.enhanced_manager import EnhancedDatabaseManager
from database.models.image import ImageModel
from database.models.crawl_session import CrawlSessionModel
from config.manager import ConfigManager

logger = logging.getLogger(__name__)


class ImageCrawler:
    """
    主图片爬虫类
    
    功能：
    - 统一的爬虫接口
    - 数据库集成
    - 配置管理
    - 进度跟踪
    - 结果存储
    """
    
    def __init__(self, config_file: Optional[str] = None, db_manager=None):
        """
        初始化爬虫

        Args:
            config_file: 配置文件路径
            db_manager: 外部数据库管理器（可选，用于HA系统）
        """
        # 加载配置
        self.config_manager = ConfigManager(config_file)
        self.settings = self.config_manager.get_settings()

        # 使用外部数据库管理器或创建默认管理器
        if db_manager is not None:
            self.db_manager = db_manager
            logger.info("✅ 使用外部数据库管理器（HA系统）")
        else:
            # 初始化增强数据库管理器（支持容灾备份）
            database_url = self.config_manager.get_database_url()
            self.db_manager = EnhancedDatabaseManager(
                database_url,
                self.settings.disaster_recovery
            )
            logger.info("✅ 使用默认数据库管理器")

        # 创建数据库表（如果使用默认管理器）
        if db_manager is None:
            self.db_manager.create_tables()
        
        # 任务调度器
        self.task_scheduler = TaskScheduler(
            max_concurrent_crawlers=self.settings.crawler.max_concurrent
        )
        
        # 当前会话
        self.current_session: Optional[CrawlSessionModel] = None

        # 启动容灾备份监控（如果启用）
        self._start_disaster_recovery()

        logger.info("图片爬虫初始化完成")
    
    async def crawl_website(self, 
                           url: str, 
                           session_name: Optional[str] = None,
                           progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        爬取网站图片
        
        Args:
            url: 目标网站URL
            session_name: 会话名称
            progress_callback: 进度回调函数
            
        Returns:
            爬取结果
        """
        # 创建爬取会话
        session_id = await self._create_crawl_session(url, session_name)
        
        try:
            # 准备配置
            crawler_config = {
                'max_concurrent': self.settings.crawler.max_concurrent,
                'max_depth': self.settings.crawler.max_depth,
                'max_images': self.settings.crawler.max_images,
                'max_pages': 100,  # 可以从配置中获取
                'download_path': self.settings.crawler.download_path,
                'anti_crawler': {
                    'use_random_user_agent': self.settings.anti_crawler.use_random_user_agent,
                    'default_headers': self.settings.anti_crawler.default_headers,
                    'use_proxy': self.settings.anti_crawler.use_proxy,
                    'proxy_list': self.settings.anti_crawler.proxy_list,
                    'random_delay': self.settings.anti_crawler.random_delay,
                    'min_delay': self.settings.anti_crawler.min_delay,
                    'max_delay': self.settings.anti_crawler.max_delay,
                }
            }
            
            # 创建进度回调包装器
            async def wrapped_progress_callback(stats):
                await self._update_session_progress(session_id, stats)
                if progress_callback:
                    await progress_callback(stats)
            
            # 执行爬取
            result = await self.task_scheduler.schedule_crawl(
                task_id=f"session_{session_id}",
                start_url=url,
                config=crawler_config
            )
            
            # 保存结果到数据库（添加超时）
            try:
                await asyncio.wait_for(
                    self._save_crawl_results(session_id, result),
                    timeout=60.0  # 60秒超时
                )
            except asyncio.TimeoutError:
                logger.error(f"保存爬取结果超时: {session_id}")
            except Exception as e:
                logger.error(f"保存爬取结果失败: {session_id} -> {e}")

            # 标记会话完成（添加超时）
            try:
                await asyncio.wait_for(
                    self._complete_crawl_session(session_id, result),
                    timeout=30.0  # 30秒超时
                )
            except asyncio.TimeoutError:
                logger.error(f"完成爬取会话超时: {session_id}")
            except Exception as e:
                logger.error(f"完成爬取会话失败: {session_id} -> {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
            await self._fail_crawl_session(session_id, str(e))
            raise
    
    async def crawl_multiple_websites(self, 
                                    urls: List[str],
                                    session_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        批量爬取多个网站
        
        Args:
            urls: URL列表
            session_name: 会话名称前缀
            
        Returns:
            爬取结果列表
        """
        tasks = []
        for i, url in enumerate(urls):
            task_name = f"{session_name}_{i}" if session_name else f"batch_{i}"
            
            crawler_config = {
                'max_concurrent': self.settings.crawler.max_concurrent,
                'max_depth': self.settings.crawler.max_depth,
                'max_images': self.settings.crawler.max_images,
                'download_path': self.settings.crawler.download_path,
                'anti_crawler': {
                    'use_random_user_agent': self.settings.anti_crawler.use_random_user_agent,
                    'default_headers': self.settings.anti_crawler.default_headers,
                    'use_proxy': self.settings.anti_crawler.use_proxy,
                    'proxy_list': self.settings.anti_crawler.proxy_list,
                    'random_delay': self.settings.anti_crawler.random_delay,
                    'min_delay': self.settings.anti_crawler.min_delay,
                    'max_delay': self.settings.anti_crawler.max_delay,
                }
            }
            
            tasks.append({
                'task_id': task_name,
                'start_url': url,
                'config': crawler_config
            })
        
        # 执行批量爬取
        results = await self.task_scheduler.schedule_multiple_crawls(tasks)
        
        return results
    
    async def _create_crawl_session(self, target_url: str, session_name: Optional[str] = None) -> int:
        """创建爬取会话"""
        with self.db_manager.get_session() as db_session:
            crawl_session = CrawlSessionModel(
                session_name=session_name or f"crawl_{int(time.time())}",
                target_url=target_url,
                status="running",
                start_time=datetime.now(timezone.utc),
                config_data={
                    'max_depth': self.settings.crawler.max_depth,
                    'max_images': self.settings.crawler.max_images,
                    'max_concurrent': self.settings.crawler.max_concurrent,
                }
            )
            
            db_session.add(crawl_session)
            db_session.commit()
            
            self.current_session = crawl_session
            logger.info(f"创建爬取会话: {crawl_session.id}")
            
            return crawl_session.id
    
    async def _update_session_progress(self, session_id: int, stats: Dict[str, Any]):
        """更新会话进度"""
        with self.db_manager.get_session() as db_session:
            session = db_session.query(CrawlSessionModel).filter(
                CrawlSessionModel.id == session_id
            ).first()
            
            if session:
                session.processed_pages = stats.get('pages_crawled', 0)
                session.total_images_found = stats.get('images_found', 0)
                session.images_downloaded = stats.get('images_downloaded', 0)
                session.images_failed = stats.get('images_failed', 0)
                
                db_session.commit()
    
    async def _save_crawl_results(self, session_id: int, result: Dict[str, Any]):
        """保存爬取结果到数据库"""
        if not result.get('success', False):
            return

        downloaded_images = result.get('downloaded_images', [])
        if not downloaded_images:
            logger.info("没有下载的图片需要保存")
            return

        logger.info(f"开始保存 {len(downloaded_images)} 张图片信息到数据库...")

        try:
            with self.db_manager.get_session() as db_session:
                # 获取默认分类
                from database.models.category import CategoryModel
                default_category = db_session.query(CategoryModel).filter(
                    CategoryModel.slug == "uncategorized"
                ).first()

                # 批量检查已存在的图片
                existing_urls = set()
                if downloaded_images:
                    existing_images = db_session.query(ImageModel.url).filter(
                        ImageModel.url.in_(downloaded_images)
                    ).all()
                    existing_urls = {img.url for img in existing_images}

                # 获取URL到文件名的映射
                url_to_filename = result.get('url_to_filename', {})

                # 批量创建新图片记录
                new_images = []
                for image_url in downloaded_images:
                    if image_url not in existing_urls:
                        # 使用实际的文件名，如果没有映射则从URL提取
                        actual_filename = url_to_filename.get(image_url)
                        if actual_filename:
                            filename = actual_filename
                            file_extension = Path(actual_filename).suffix or '.jpg'
                        else:
                            # 回退到从URL提取（兼容旧版本）
                            filename = Path(image_url).name
                            file_extension = Path(image_url).suffix or '.jpg'

                        image = ImageModel(
                            url=image_url,
                            source_url=result.get('start_url', ''),
                            filename=filename,
                            file_extension=file_extension,
                            category_id=default_category.id if default_category else None,
                            is_downloaded=True,
                        )
                        new_images.append(image)

                # 批量添加到数据库
                if new_images:
                    db_session.add_all(new_images)
                    db_session.commit()
                    logger.info(f"保存了 {len(new_images)} 张新图片信息到数据库")
                else:
                    logger.info("所有图片都已存在，无需保存")

        except Exception as e:
            logger.error(f"保存图片信息到数据库失败: {e}")
            # 不抛出异常，避免影响会话完成
    
    async def _complete_crawl_session(self, session_id: int, result: Dict[str, Any]):
        """完成爬取会话"""
        try:
            logger.info(f"正在完成爬取会话: {session_id}")

            with self.db_manager.get_session() as db_session:
                session = db_session.query(CrawlSessionModel).filter(
                    CrawlSessionModel.id == session_id
                ).first()

                if session:
                    session.mark_completed()
                    session.summary_log = f"爬取完成: {result.get('summary', '')}"

                    db_session.commit()
                    logger.info(f"爬取会话完成: {session_id}")
                else:
                    logger.warning(f"未找到会话: {session_id}")

        except Exception as e:
            logger.error(f"完成爬取会话失败: {session_id} -> {e}")
            # 不抛出异常，避免影响整个爬取流程
    
    async def _fail_crawl_session(self, session_id: int, error_message: str):
        """标记爬取会话失败"""
        with self.db_manager.get_session() as db_session:
            session = db_session.query(CrawlSessionModel).filter(
                CrawlSessionModel.id == session_id
            ).first()
            
            if session:
                session.mark_failed(error_message)
                db_session.commit()
                logger.error(f"爬取会话失败: {session_id} -> {error_message}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取爬虫统计信息"""
        with self.db_manager.get_session() as db_session:
            total_images = db_session.query(ImageModel).count()
            downloaded_images = db_session.query(ImageModel).filter(
                ImageModel.is_downloaded == True
            ).count()
            total_sessions = db_session.query(CrawlSessionModel).count()
            
            return {
                'total_images': total_images,
                'downloaded_images': downloaded_images,
                'total_sessions': total_sessions,
                'active_tasks': len(self.task_scheduler.get_active_tasks()),
                'database_info': self.db_manager.get_database_info(),
            }

    def _start_disaster_recovery(self):
        """启动容灾备份功能"""
        try:
            if self.db_manager.is_disaster_recovery_enabled():
                logger.info("🛡️ 启动容灾备份监控...")

                # 启动监控服务
                try:
                    self.db_manager.start_monitoring()
                    logger.info("✅ 监控服务启动成功")
                except Exception as e:
                    logger.error(f"❌ 启动监控服务失败: {e}")

                # 创建初始备份（可选，如果失败不影响系统启动）
                try:
                    backup_path = self.db_manager.create_backup("initial_backup")
                    if backup_path:
                        logger.info(f"✅ 初始备份创建成功: {backup_path}")
                    else:
                        logger.warning("⚠️ 初始备份创建失败，但系统将继续运行")
                except Exception as e:
                    logger.warning(f"⚠️ 创建初始备份失败: {e}，但系统将继续运行")

                # 确保备用数据库有表结构，然后同步数据（可选，如果失败不影响系统启动）
                try:
                    self._ensure_backup_database_schema()
                    self._sync_to_backup_databases()
                except Exception as e:
                    logger.warning(f"⚠️ 数据同步失败: {e}，但系统将继续运行")

                logger.info("✅ 容灾备份系统已启动")
            else:
                logger.info("ℹ️ 容灾备份功能未启用")

        except Exception as e:
            logger.error(f"❌ 启动容灾备份失败: {e}，但系统将继续运行")

    def _sync_to_backup_databases(self):
        """同步数据到备用数据库"""
        try:
            if not self.db_manager.backup_manager:
                return

            backup_manager = self.db_manager.backup_manager
            primary_db = backup_manager.current_primary

            if not primary_db:
                return

            # 检查主数据库是否有数据
            try:
                with backup_manager.get_session(primary_db) as session:
                    from database.models.image import ImageModel
                    image_count = session.query(ImageModel).count()

                    if image_count == 0:
                        logger.info("ℹ️ 主数据库为空，跳过数据同步")
                        return

                    logger.info(f"📊 主数据库包含 {image_count} 条图片记录")
            except Exception as e:
                logger.warning(f"检查主数据库数据时出错: {e}")
                return

            # 获取所有备用数据库
            backup_dbs = [
                name for name, config in backup_manager.databases.items()
                if name != primary_db and config.type == 'secondary' and config.is_active
            ]

            if backup_dbs:
                logger.info(f"🔄 开始同步数据到 {len(backup_dbs)} 个备用数据库...")

                sync_success_count = 0
                for backup_db in backup_dbs:
                    try:
                        # 检查备用数据库是否已有数据
                        try:
                            with backup_manager.get_session(backup_db) as session:
                                from database.models.image import ImageModel
                                backup_image_count = session.query(ImageModel).count()

                                if backup_image_count >= image_count:
                                    logger.info(f"ℹ️ 备用数据库 {backup_db} 数据已是最新，跳过同步")
                                    sync_success_count += 1
                                    continue
                        except Exception:
                            # 如果无法查询备用数据库，继续尝试同步
                            pass

                        logger.info(f"🔄 正在同步到 {backup_db}...")
                        success = backup_manager.sync_databases(primary_db, backup_db)
                        if success:
                            logger.info(f"✅ 数据同步成功: {primary_db} -> {backup_db}")
                            sync_success_count += 1
                        else:
                            logger.warning(f"⚠️ 数据同步失败: {primary_db} -> {backup_db}")
                    except Exception as e:
                        logger.error(f"❌ 同步到 {backup_db} 失败: {e}")

                logger.info(f"🔄 数据同步完成，成功同步到 {sync_success_count}/{len(backup_dbs)} 个备用数据库")
            else:
                logger.info("ℹ️ 没有可用的备用数据库进行同步")

        except Exception as e:
            logger.error(f"❌ 数据同步失败: {e}")

    def _ensure_backup_database_schema(self):
        """确保备用数据库有正确的表结构"""
        try:
            if not self.db_manager.backup_manager:
                return

            backup_manager = self.db_manager.backup_manager
            primary_db = backup_manager.current_primary

            if not primary_db:
                return

            # 获取所有备用数据库
            backup_dbs = [
                name for name, config in backup_manager.databases.items()
                if name != primary_db and config.type == 'secondary' and config.is_active
            ]

            if backup_dbs:
                logger.info(f"🔧 检查 {len(backup_dbs)} 个备用数据库的表结构...")

                for backup_db in backup_dbs:
                    try:
                        engine = backup_manager.engines[backup_db]

                        # 检查表是否存在
                        from sqlalchemy import inspect
                        inspector = inspect(engine)
                        tables = inspector.get_table_names()

                        required_tables = ['images', 'categories', 'crawl_sessions', 'tags']
                        missing_tables = [table for table in required_tables if table not in tables]

                        if missing_tables:
                            logger.info(f"🔧 在 {backup_db} 中创建缺少的表: {missing_tables}")

                            # 创建缺少的表
                            from database.models.base import Base
                            Base.metadata.create_all(bind=engine)

                            # 验证表是否创建成功
                            inspector = inspect(engine)
                            tables = inspector.get_table_names()
                            still_missing = [table for table in required_tables if table not in tables]

                            if still_missing:
                                logger.error(f"❌ 在 {backup_db} 中创建表失败，仍缺少: {still_missing}")
                            else:
                                logger.info(f"✅ 在 {backup_db} 中成功创建所有必要的表")
                        else:
                            logger.info(f"✅ {backup_db} 的表结构完整")

                    except Exception as e:
                        logger.error(f"❌ 检查 {backup_db} 表结构失败: {e}")

                logger.info("🔧 备用数据库表结构检查完成")
            else:
                logger.info("ℹ️ 没有可用的备用数据库需要检查表结构")

        except Exception as e:
            logger.error(f"❌ 确保备用数据库表结构失败: {e}")

    def stop_disaster_recovery(self):
        """停止容灾备份功能"""
        try:
            if self.db_manager.is_disaster_recovery_enabled():
                logger.info("🛡️ 停止容灾备份监控...")
                self.db_manager.stop_monitoring()
                logger.info("✅ 容灾备份系统已停止")
        except Exception as e:
            logger.error(f"❌ 停止容灾备份失败: {e}")

    def get_disaster_recovery_status(self) -> Dict[str, Any]:
        """获取容灾备份状态"""
        try:
            if not self.db_manager.is_disaster_recovery_enabled():
                return {"enabled": False, "message": "容灾备份功能未启用"}

            return {
                "enabled": True,
                "database_status": self.db_manager.get_database_info(),
                "health_status": self.db_manager.get_health_status(),
                "failover_status": self.db_manager.get_failover_status(),
                "failover_history": self.db_manager.get_failover_history(5)
            }
        except Exception as e:
            logger.error(f"获取容灾状态失败: {e}")
            return {"enabled": False, "error": str(e)}

    def stop_all_tasks(self):
        """停止所有活跃任务"""
        self.task_scheduler.stop_all_tasks()
