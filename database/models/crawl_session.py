"""
爬取会话模型定义

记录每次爬取任务的详细信息和统计数据
"""

from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from datetime import datetime, timezone
from database.models.base import BaseModel


class CrawlSessionModel(BaseModel):
    """
    爬取会话表
    
    记录每次爬取任务的信息，包括：
    - 任务配置和参数
    - 执行状态和进度
    - 统计数据和结果
    - 错误信息和日志
    """
    __tablename__ = "crawl_sessions"
    
    # 基本信息
    session_name = Column(String(100), comment="会话名称")
    target_url = Column(String(2048), nullable=False, comment="目标网站URL")
    session_type = Column(String(20), default="manual", comment="会话类型：manual-手动，scheduled-定时")
    
    # 配置信息
    config_data = Column(JSON, comment="爬取配置（JSON格式）")
    max_depth = Column(Integer, default=3, comment="最大爬取深度")
    max_images = Column(Integer, comment="最大图片数量限制")
    allowed_domains = Column(Text, comment="允许的域名列表")
    image_filters = Column(JSON, comment="图片过滤规则")
    
    # 执行状态
    status = Column(String(20), default="pending", comment="执行状态：pending-等待，running-运行中，completed-完成，failed-失败，cancelled-取消")
    start_time = Column(DateTime(timezone=True), comment="开始时间")
    end_time = Column(DateTime(timezone=True), comment="结束时间")
    duration_seconds = Column(Float, comment="执行时长（秒）")
    
    # 进度信息
    total_pages = Column(Integer, default=0, comment="总页面数")
    processed_pages = Column(Integer, default=0, comment="已处理页面数")
    total_images_found = Column(Integer, default=0, comment="发现的图片总数")
    images_downloaded = Column(Integer, default=0, comment="成功下载的图片数")
    images_failed = Column(Integer, default=0, comment="下载失败的图片数")
    images_skipped = Column(Integer, default=0, comment="跳过的图片数")
    
    # 统计信息
    total_size_bytes = Column(Integer, default=0, comment="下载总大小（字节）")
    average_image_size = Column(Float, comment="平均图片大小（字节）")
    download_speed_mbps = Column(Float, comment="平均下载速度（MB/s）")
    
    # 质量统计
    high_quality_count = Column(Integer, default=0, comment="高质量图片数量")
    duplicate_count = Column(Integer, default=0, comment="重复图片数量")
    error_count = Column(Integer, default=0, comment="错误数量")
    
    # 错误和日志
    last_error = Column(Text, comment="最后一个错误信息")
    error_log = Column(Text, comment="错误日志")
    summary_log = Column(Text, comment="执行摘要")
    
    # 资源使用
    peak_memory_mb = Column(Float, comment="峰值内存使用（MB）")
    cpu_usage_percent = Column(Float, comment="CPU使用率（%）")
    
    def __repr__(self):
        return f"<CrawlSessionModel(id={self.id}, target_url='{self.target_url[:50]}...', status='{self.status}')>"
    
    @property
    def success_rate(self):
        """计算成功率"""
        if self.total_images_found == 0:
            return 0
        return round((self.images_downloaded / self.total_images_found) * 100, 2)
    
    @property
    def total_size_mb(self):
        """返回总大小（MB）"""
        if self.total_size_bytes:
            return round(self.total_size_bytes / (1024 * 1024), 2)
        return 0
    
    @property
    def duration_formatted(self):
        """返回格式化的执行时长"""
        if not self.duration_seconds:
            return "未知"
        
        hours = int(self.duration_seconds // 3600)
        minutes = int((self.duration_seconds % 3600) // 60)
        seconds = int(self.duration_seconds % 60)
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟{seconds}秒"
        elif minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        else:
            return f"{seconds}秒"
    
    def update_progress(self, **kwargs):
        """更新进度信息"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def mark_completed(self):
        """标记为完成状态"""
        self.status = "completed"
        self.end_time = datetime.now(timezone.utc)
        if self.start_time and self.end_time:
            # 确保两个时间都是同一类型
            start_time = self.start_time
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            self.duration_seconds = (self.end_time - start_time).total_seconds()

    def mark_failed(self, error_message):
        """标记为失败状态"""
        self.status = "failed"
        self.end_time = datetime.now(timezone.utc)
        self.last_error = error_message
        if self.start_time and self.end_time:
            # 确保两个时间都是同一类型
            start_time = self.start_time
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            self.duration_seconds = (self.end_time - start_time).total_seconds()
