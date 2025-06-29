"""
图片分类模型定义

管理图片的分类和标签系统
"""

from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class CategoryModel(BaseModel):
    """
    图片分类表
    
    用于组织和管理图片分类，支持：
    - 层级分类结构
    - 自动分类规则
    - 分类统计信息
    """
    __tablename__ = "categories"
    
    # 基本信息
    name = Column(String(100), nullable=False, unique=True, comment="分类名称")
    slug = Column(String(100), nullable=False, unique=True, comment="分类标识符")
    description = Column(Text, comment="分类描述")
    
    # 层级结构
    parent_id = Column(Integer, ForeignKey("categories.id"), comment="父分类ID")
    level = Column(Integer, default=0, comment="分类层级（0为顶级）")
    sort_order = Column(Integer, default=0, comment="排序顺序")
    
    # 分类规则
    auto_rules = Column(Text, comment="自动分类规则（JSON格式）")
    keywords = Column(Text, comment="关键词列表（JSON格式）")
    
    # 统计信息
    image_count = Column(Integer, default=0, comment="包含图片数量")
    total_size = Column(Integer, default=0, comment="总文件大小（字节）")
    
    # 显示设置
    color = Column(String(7), comment="分类颜色（十六进制）")
    icon = Column(String(50), comment="分类图标")
    is_visible = Column(String(10), default="true", comment="是否可见")
    
    # 关联关系
    parent = relationship("CategoryModel", remote_side=lambda: CategoryModel.id, back_populates="children")
    children = relationship("CategoryModel", back_populates="parent")
    images = relationship("ImageModel", back_populates="category")
    
    def __repr__(self):
        return f"<CategoryModel(id={self.id}, name='{self.name}', level={self.level})>"
    
    @property
    def full_path(self):
        """返回完整的分类路径"""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name
    
    @property
    def total_size_mb(self):
        """返回总大小（MB）"""
        if self.total_size:
            return round(self.total_size / (1024 * 1024), 2)
        return 0
    
    def get_all_children(self):
        """获取所有子分类（递归）"""
        children = []
        for child in self.children:
            children.append(child)
            children.extend(child.get_all_children())
        return children
    
    def update_statistics(self, session):
        """更新分类统计信息"""
        from .image import ImageModel
        
        # 统计直接属于此分类的图片
        direct_images = session.query(ImageModel).filter(
            ImageModel.category_id == self.id,
            ImageModel.status == "active"
        ).all()
        
        self.image_count = len(direct_images)
        self.total_size = sum(img.file_size or 0 for img in direct_images)
        
        # 递归更新父分类统计
        if self.parent:
            self.parent.update_statistics(session)
