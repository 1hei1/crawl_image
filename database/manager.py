"""
数据库管理器

提供数据库连接、操作和管理功能，支持SQLite和PostgreSQL
"""

import os
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

from database.models.base import Base
from database.models.image import ImageModel
from database.models.category import CategoryModel
from database.models.tag import TagModel
from database.models.crawl_session import CrawlSessionModel

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    数据库管理器
    
    功能：
    - 数据库连接管理
    - 表结构创建和迁移
    - 基础CRUD操作
    - 事务管理
    - 连接池管理
    """
    
    def __init__(self, database_url: str, echo: bool = False):
        """
        初始化数据库管理器
        
        Args:
            database_url: 数据库连接URL
            echo: 是否输出SQL语句
        """
        self.database_url = database_url
        self.echo = echo
        self.engine = None
        self.SessionLocal = None
        self._setup_engine()
    
    def _setup_engine(self):
        """设置数据库引擎"""
        try:
            # 根据数据库类型设置不同的参数
            if self.database_url.startswith('sqlite'):
                # SQLite配置
                self.engine = create_engine(
                    self.database_url,
                    echo=False,  # 禁用SQL日志
                    poolclass=StaticPool,
                    connect_args={
                        "check_same_thread": False,
                        "timeout": 30
                    }
                )
            else:
                # PostgreSQL配置
                self.engine = create_engine(
                    self.database_url,
                    echo=False,  # 禁用SQL日志
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600
                )
            
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info(f"数据库引擎初始化成功: {self.database_url}")
            
        except Exception as e:
            logger.error(f"数据库引擎初始化失败: {e}")
            raise
    
    def create_tables(self):
        """创建所有表"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("数据库表创建成功")
            
            # 创建默认分类
            self._create_default_categories()
            
        except Exception as e:
            logger.error(f"创建数据库表失败: {e}")
            raise
    
    def drop_tables(self):
        """删除所有表"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("数据库表删除成功")
        except Exception as e:
            logger.error(f"删除数据库表失败: {e}")
            raise
    
    def _create_default_categories(self):
        """创建默认分类"""
        default_categories = [
            {"name": "未分类", "slug": "uncategorized", "description": "未分类的图片"},
            {"name": "照片", "slug": "photos", "description": "摄影作品和照片"},
            {"name": "插图", "slug": "illustrations", "description": "插图和绘画作品"},
            {"name": "图标", "slug": "icons", "description": "图标和符号"},
            {"name": "背景", "slug": "backgrounds", "description": "背景图片"},
            {"name": "头像", "slug": "avatars", "description": "头像和肖像"},
        ]
        
        with self.get_session() as session:
            for cat_data in default_categories:
                existing = session.query(CategoryModel).filter(
                    CategoryModel.slug == cat_data["slug"]
                ).first()
                
                if not existing:
                    category = CategoryModel(**cat_data)
                    session.add(category)
            
            session.commit()
            logger.info("默认分类创建完成")
    
    @contextmanager
    def get_session(self) -> Session:
        """获取数据库会话（上下文管理器）"""
        session = self.SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("数据库连接测试成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        info = {
            "database_url": self.database_url,
            "engine_info": str(self.engine),
            "pool_size": getattr(self.engine.pool, 'size', 'N/A'),
            "pool_checked_out": getattr(self.engine.pool, 'checkedout', 'N/A'),
        }
            
        try:
            with self.get_session() as session:
                # 获取表统计信息
                info["tables"] = {
                    "images": session.query(ImageModel).count(),
                    "categories": session.query(CategoryModel).count(),
                    "tags": session.query(TagModel).count(),
                    "crawl_sessions": session.query(CrawlSessionModel).count(),
                }
        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            info["tables"] = "获取失败"
        
        return info
