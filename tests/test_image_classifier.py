"""
图片分类器测试用例
"""

import pytest
from crawler.utils.image_classifier import ImageClassifier


class TestImageClassifier:
    """图片分类器测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.config = {
            'filename_rules': {
                '照片': ['photo', 'img', 'picture'],
                '图标': ['icon', 'ico', 'favicon'],
                '背景': ['background', 'bg', 'wallpaper'],
            },
            'size_rules': {
                '图标': {'max_width': 128, 'max_height': 128},
                '缩略图': {'max_width': 300, 'max_height': 300},
                '高清图片': {'min_width': 1920, 'min_height': 1080},
            },
            'enable_content_classification': False
        }
        self.classifier = ImageClassifier(self.config)
    
    def test_classify_by_filename(self):
        """测试基于文件名的分类"""
        # 测试照片分类
        image_info = {
            'filename': 'my_photo.jpg',
            'url': 'https://example.com/images/my_photo.jpg'
        }
        result = self.classifier._classify_by_filename(image_info)
        assert result['category'] == '照片'
        assert result['confidence'] > 0
        
        # 测试图标分类
        image_info = {
            'filename': 'favicon.ico',
            'url': 'https://example.com/favicon.ico'
        }
        result = self.classifier._classify_by_filename(image_info)
        assert result['category'] == '图标'
        
        # 测试无匹配
        image_info = {
            'filename': 'unknown.jpg',
            'url': 'https://example.com/unknown.jpg'
        }
        result = self.classifier._classify_by_filename(image_info)
        assert result['category'] is None
    
    def test_classify_by_size(self):
        """测试基于尺寸的分类"""
        # 测试图标尺寸
        image_info = {'width': 64, 'height': 64}
        result = self.classifier._classify_by_size(image_info)
        assert result['category'] == '图标'
        
        # 测试缩略图尺寸
        image_info = {'width': 200, 'height': 150}
        result = self.classifier._classify_by_size(image_info)
        assert result['category'] == '缩略图'
        
        # 测试高清图片尺寸
        image_info = {'width': 1920, 'height': 1080}
        result = self.classifier._classify_by_size(image_info)
        assert result['category'] == '高清图片'
        
        # 测试无匹配尺寸
        image_info = {'width': 800, 'height': 600}
        result = self.classifier._classify_by_size(image_info)
        assert result['category'] is None
        
        # 测试缺少尺寸信息
        image_info = {}
        result = self.classifier._classify_by_size(image_info)
        assert result['category'] is None
    
    def test_assess_quality(self):
        """测试质量评估"""
        # 测试高质量图片
        image_info = {
            'width': 1920,
            'height': 1080,
            'file_size': 1024 * 1024,  # 1MB
            'format': 'PNG'
        }
        score = self.classifier._assess_quality(image_info)
        assert score > 0.5
        
        # 测试低质量图片
        image_info = {
            'width': 100,
            'height': 100,
            'file_size': 1024,  # 1KB
            'format': 'GIF'
        }
        score = self.classifier._assess_quality(image_info)
        assert score < 0.5
    
    def test_generate_tags(self):
        """测试标签生成"""
        image_info = {
            'width': 1920,
            'height': 1080,
            'format': 'PNG'
        }
        classification_result = {
            'primary_category': '照片',
            'quality_score': 0.8
        }
        
        tags = self.classifier._generate_tags(image_info, classification_result)
        
        assert '照片' in tags
        assert '高清' in tags
        assert 'PNG' in tags
        assert '高质量' in tags
        assert '横图' in tags
    
    def test_classify_image(self):
        """测试完整的图片分类"""
        image_info = {
            'filename': 'photo_1920x1080.jpg',
            'url': 'https://example.com/photos/photo_1920x1080.jpg',
            'width': 1920,
            'height': 1080,
            'file_size': 2 * 1024 * 1024,  # 2MB
            'format': 'JPEG'
        }
        
        result = self.classifier.classify_image(image_info)
        
        assert result['primary_category'] is not None
        assert result['confidence'] > 0
        assert len(result['tags']) > 0
        assert result['quality_score'] > 0
        assert len(result['classification_method']) > 0
    
    def test_detect_duplicates(self):
        """测试重复检测"""
        images = [
            {'md5_hash': 'abc123', 'filename': 'image1.jpg'},
            {'md5_hash': 'def456', 'filename': 'image2.jpg'},
            {'md5_hash': 'abc123', 'filename': 'image1_copy.jpg'},  # 重复
            {'md5_hash': 'ghi789', 'filename': 'image3.jpg'},
        ]
        
        duplicates = self.classifier.detect_duplicates(images)
        
        assert len(duplicates) == 1  # 只有一组重复
        assert 'abc123' in duplicates
        assert len(duplicates['abc123']) == 2  # 两个重复文件
    
    def test_get_classification_statistics(self):
        """测试分类统计"""
        images = [
            {
                'filename': 'photo1.jpg',
                'url': 'https://example.com/photo1.jpg',
                'width': 1920,
                'height': 1080,
                'format': 'JPEG'
            },
            {
                'filename': 'icon.png',
                'url': 'https://example.com/icon.png',
                'width': 64,
                'height': 64,
                'format': 'PNG'
            }
        ]
        
        stats = self.classifier.get_classification_statistics(images)
        
        assert stats['total_images'] == 2
        assert len(stats['categories']) > 0
        assert 'quality_distribution' in stats
        assert 'format_distribution' in stats
        assert 'size_distribution' in stats


if __name__ == '__main__':
    pytest.main([__file__])
