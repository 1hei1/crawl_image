"""
初始数据库架构迁移

创建基础表结构和索引
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    """升级数据库架构"""
    
    # 创建分类表
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('auto_rules', sa.Text(), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('image_count', sa.Integer(), nullable=True),
        sa.Column('total_size', sa.Integer(), nullable=True),
        sa.Column('color', sa.String(length=7), nullable=True),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('is_visible', sa.String(length=10), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    
    # 创建图片表
    op.create_table(
        'images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('file_extension', sa.String(length=10), nullable=False),
        sa.Column('mime_type', sa.String(length=50), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('aspect_ratio', sa.Float(), nullable=True),
        sa.Column('color_mode', sa.String(length=20), nullable=True),
        sa.Column('has_transparency', sa.Boolean(), nullable=True),
        sa.Column('md5_hash', sa.String(length=32), nullable=True),
        sa.Column('sha256_hash', sa.String(length=64), nullable=True),
        sa.Column('perceptual_hash', sa.String(length=64), nullable=True),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('auto_tags', sa.Text(), nullable=True),
        sa.Column('local_path', sa.String(length=512), nullable=True),
        sa.Column('is_downloaded', sa.Boolean(), nullable=True),
        sa.Column('download_attempts', sa.Integer(), nullable=True),
        sa.Column('last_download_error', sa.Text(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=True),
        sa.Column('duplicate_of', sa.Integer(), nullable=True),
        sa.Column('exif_data', sa.Text(), nullable=True),
        sa.Column('alt_text', sa.Text(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.ForeignKeyConstraint(['duplicate_of'], ['images.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('md5_hash')
    )
    
    # 创建标签表
    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('group_name', sa.String(length=50), nullable=True),
        sa.Column('tag_type', sa.String(length=20), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('color', sa.String(length=7), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug')
    )
    
    # 创建爬取会话表
    op.create_table(
        'crawl_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('session_name', sa.String(length=100), nullable=True),
        sa.Column('target_url', sa.String(length=2048), nullable=False),
        sa.Column('session_type', sa.String(length=20), nullable=True),
        sa.Column('config_data', sa.JSON(), nullable=True),
        sa.Column('max_depth', sa.Integer(), nullable=True),
        sa.Column('max_images', sa.Integer(), nullable=True),
        sa.Column('allowed_domains', sa.Text(), nullable=True),
        sa.Column('image_filters', sa.JSON(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('total_pages', sa.Integer(), nullable=True),
        sa.Column('processed_pages', sa.Integer(), nullable=True),
        sa.Column('total_images_found', sa.Integer(), nullable=True),
        sa.Column('images_downloaded', sa.Integer(), nullable=True),
        sa.Column('images_failed', sa.Integer(), nullable=True),
        sa.Column('images_skipped', sa.Integer(), nullable=True),
        sa.Column('total_size_bytes', sa.Integer(), nullable=True),
        sa.Column('average_image_size', sa.Float(), nullable=True),
        sa.Column('download_speed_mbps', sa.Float(), nullable=True),
        sa.Column('high_quality_count', sa.Integer(), nullable=True),
        sa.Column('duplicate_count', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('summary_log', sa.Text(), nullable=True),
        sa.Column('peak_memory_mb', sa.Float(), nullable=True),
        sa.Column('cpu_usage_percent', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('idx_images_url', 'images', ['url'])
    op.create_index('idx_images_source_url', 'images', ['source_url'])
    op.create_index('idx_images_filename', 'images', ['filename'])
    op.create_index('idx_images_category_id', 'images', ['category_id'])
    op.create_index('idx_images_is_downloaded', 'images', ['is_downloaded'])
    op.create_index('idx_images_created_at', 'images', ['created_at'])
    op.create_index('idx_categories_parent_id', 'categories', ['parent_id'])
    op.create_index('idx_crawl_sessions_target_url', 'crawl_sessions', ['target_url'])
    op.create_index('idx_crawl_sessions_status', 'crawl_sessions', ['status'])


def downgrade():
    """降级数据库架构"""
    op.drop_table('crawl_sessions')
    op.drop_table('tags')
    op.drop_table('images')
    op.drop_table('categories')
