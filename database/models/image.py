"""
图片数据模型定义

存储爬取的图片信息和元数据
"""

from sqlalchemy import Column, String, Integer, Text, Float, Boolean, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class ImageModel(BaseModel):
    """
    图片信息表
    
    存储爬取的图片详细信息，包括：
    - 基本信息：URL、文件名、格式等
    - 技术信息：尺寸、大小、哈希值等
    - 分类信息：分类ID、标签等
    - 存储信息：本地路径、存储状态等
    """
    __tablename__ = "images"
    
    # 基本信息
    url = Column(String(2048), nullable=False, comment="图片原始URL")
    source_url = Column(String(2048), nullable=False, comment="图片来源页面URL")
    filename = Column(String(255), nullable=False, comment="文件名")
    original_filename = Column(String(255), comment="原始文件名")
    file_extension = Column(String(10), nullable=False, comment="文件扩展名")
    mime_type = Column(String(50), comment="MIME类型")
    
    # 技术信息
    file_size = Column(Integer, comment="文件大小（字节）")
    width = Column(Integer, comment="图片宽度（像素）")
    height = Column(Integer, comment="图片高度（像素）")
    aspect_ratio = Column(Float, comment="宽高比")
    color_mode = Column(String(20), comment="颜色模式（RGB、RGBA、L等）")
    has_transparency = Column(Boolean, default=False, comment="是否有透明通道")
    
    # 哈希和去重
    md5_hash = Column(String(32), unique=True, comment="MD5哈希值")
    sha256_hash = Column(String(64), comment="SHA256哈希值")
    perceptual_hash = Column(String(64), comment="感知哈希值（用于相似图片检测）")
    
    # 分类和标签
    category_id = Column(Integer, ForeignKey("categories.id"), comment="分类ID")
    tags = Column(Text, comment="标签（JSON格式存储）")
    auto_tags = Column(Text, comment="自动生成的标签")
    
    # 存储信息
    local_path = Column(String(512), comment="本地存储路径")
    is_downloaded = Column(Boolean, default=False, comment="是否已下载")
    download_attempts = Column(Integer, default=0, comment="下载尝试次数")
    last_download_error = Column(Text, comment="最后一次下载错误信息")
    
    # 质量评估
    quality_score = Column(Float, comment="图片质量评分（0-1）")
    is_duplicate = Column(Boolean, default=False, comment="是否为重复图片")
    duplicate_of = Column(Integer, ForeignKey("images.id"), comment="重复的原图ID")
    
    # 元数据
    exif_data = Column(Text, comment="EXIF数据（JSON格式）")
    alt_text = Column(Text, comment="图片alt文本")
    title = Column(String(255), comment="图片标题")
    description = Column(Text, comment="图片描述")
    
    # 关联关系
    category = relationship("CategoryModel", back_populates="images")
    duplicates = relationship("ImageModel", remote_side=lambda: ImageModel.id)
    
    def __repr__(self):
        return f"<ImageModel(id={self.id}, filename='{self.filename}', url='{self.url[:50]}...')>"
    
    @property
    def file_size_mb(self):
        """返回文件大小（MB）"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0
    
    @property
    def resolution_str(self):
        """返回分辨率字符串"""
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "未知"
    
    def is_high_quality(self, min_width=800, min_height=600):
        """判断是否为高质量图片"""
        if not self.width or not self.height:
            return False
        return self.width >= min_width and self.height >= min_height
