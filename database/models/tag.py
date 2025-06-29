"""
标签模型

用于管理图片标签和分类标签
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.models.base import Base


class TagModel(Base):
    """标签模型"""

    __tablename__ = 'tags'
    __table_args__ = {'extend_existing': True}

    # 基本字段
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, comment='标签名称')
    slug = Column(String(255), nullable=False, unique=True, comment='标签标识符')
    description = Column(Text, comment='标签描述')

    # 分类字段
    group_name = Column(String(255), comment='标签分组')
    tag_type = Column(String(255), default='manual', comment='标签类型：manual-手动，auto-自动')

    # 统计字段
    usage_count = Column(Integer, default=0, comment='使用次数')

    # 显示设置
    color = Column(String(255), comment='标签颜色')

    # 元数据字段
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment='创建时间')
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment='更新时间')
    status = Column(String(255), nullable=False, comment='状态')
    
    def __repr__(self):
        return f"<TagModel(id={self.id}, name='{self.name}', group='{self.group_name}')>"

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'group_name': self.group_name,
            'tag_type': self.tag_type,
            'usage_count': self.usage_count,
            'color': self.color,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'status': self.status
        }
    
    @classmethod
    def create_default_tags(cls, session):
        """创建默认标签"""
        default_tags = [
            # 颜色标签
            {'name': 'red', 'slug': 'red', 'group_name': 'color', 'description': '红色', 'color': '#FF0000'},
            {'name': 'blue', 'slug': 'blue', 'group_name': 'color', 'description': '蓝色', 'color': '#0000FF'},
            {'name': 'green', 'slug': 'green', 'group_name': 'color', 'description': '绿色', 'color': '#00FF00'},
            {'name': 'yellow', 'slug': 'yellow', 'group_name': 'color', 'description': '黄色', 'color': '#FFFF00'},
            {'name': 'black', 'slug': 'black', 'group_name': 'color', 'description': '黑色', 'color': '#000000'},
            {'name': 'white', 'slug': 'white', 'group_name': 'color', 'description': '白色', 'color': '#FFFFFF'},

            # 内容标签
            {'name': 'nature', 'slug': 'nature', 'group_name': 'content', 'description': '自然风景'},
            {'name': 'people', 'slug': 'people', 'group_name': 'content', 'description': '人物'},
            {'name': 'animal', 'slug': 'animal', 'group_name': 'content', 'description': '动物'},
            {'name': 'building', 'slug': 'building', 'group_name': 'content', 'description': '建筑'},
            {'name': 'food', 'slug': 'food', 'group_name': 'content', 'description': '食物'},
            {'name': 'technology', 'slug': 'technology', 'group_name': 'content', 'description': '科技'},

            # 风格标签
            {'name': 'modern', 'slug': 'modern', 'group_name': 'style', 'description': '现代风格'},
            {'name': 'vintage', 'slug': 'vintage', 'group_name': 'style', 'description': '复古风格'},
            {'name': 'minimalist', 'slug': 'minimalist', 'group_name': 'style', 'description': '极简风格'},
            {'name': 'artistic', 'slug': 'artistic', 'group_name': 'style', 'description': '艺术风格'},
        ]

        for tag_data in default_tags:
            # 检查标签是否已存在
            existing_tag = session.query(cls).filter(cls.name == tag_data['name']).first()
            if not existing_tag:
                # 设置默认值
                tag_data.setdefault('tag_type', 'manual')
                tag_data.setdefault('usage_count', 0)
                tag_data.setdefault('status', 'active')

                tag = cls(**tag_data)
                session.add(tag)

        session.commit()
