"""
数据库基础模型定义

提供所有数据模型的基础类和通用字段
"""

from sqlalchemy import Column, Integer, DateTime, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

# 创建基础模型类
Base = declarative_base()


class BaseModel(Base):
    """
    所有数据模型的基础类
    
    包含通用字段：
    - id: 主键
    - created_at: 创建时间
    - updated_at: 更新时间
    - status: 状态字段
    """
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )
    status = Column(
        String(20), 
        default="active", 
        nullable=False,
        comment="状态：active-活跃，inactive-非活跃，deleted-已删除"
    )
    
    def to_dict(self):
        """将模型转换为字典格式"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
