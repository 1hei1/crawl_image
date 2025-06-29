"""
图片智能分类器

基于文件名、尺寸、内容特征等实现图片自动分类
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import hashlib
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class ImageClassifier:
    """
    图片分类器
    
    功能：
    - 基于文件名的分类
    - 基于尺寸的分类
    - 基于内容特征的分类
    - 质量评估
    - 重复检测
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化分类器
        
        Args:
            config: 分类配置
        """
        self.config = config
        self.filename_rules = config.get('filename_rules', {})
        self.size_rules = config.get('size_rules', {})
        self.enable_content_classification = config.get('enable_content_classification', False)
        
        # 编译文件名规则
        self.compiled_filename_rules = {}
        for category, keywords in self.filename_rules.items():
            patterns = [re.compile(rf'\b{keyword}\b', re.IGNORECASE) for keyword in keywords]
            self.compiled_filename_rules[category] = patterns
    
    def classify_image(self, image_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        对图片进行分类
        
        Args:
            image_info: 图片信息字典
            
        Returns:
            分类结果
        """
        result = {
            'categories': [],
            'primary_category': None,
            'confidence': 0.0,
            'tags': [],
            'quality_score': 0.0,
            'classification_method': [],
        }
        
        try:
            # 基于文件名分类
            filename_result = self._classify_by_filename(image_info)
            if filename_result['category']:
                result['categories'].append(filename_result['category'])
                result['classification_method'].append('filename')
                result['confidence'] = max(result['confidence'], filename_result['confidence'])
            
            # 基于尺寸分类
            size_result = self._classify_by_size(image_info)
            if size_result['category']:
                result['categories'].append(size_result['category'])
                result['classification_method'].append('size')
                result['confidence'] = max(result['confidence'], size_result['confidence'])
            
            # 基于内容分类（如果启用）
            if self.enable_content_classification and image_info.get('local_path'):
                content_result = self._classify_by_content(image_info)
                if content_result['category']:
                    result['categories'].append(content_result['category'])
                    result['classification_method'].append('content')
                    result['confidence'] = max(result['confidence'], content_result['confidence'])
            
            # 确定主要分类
            if result['categories']:
                result['primary_category'] = result['categories'][0]
            else:
                result['primary_category'] = '未分类'
            
            # 质量评估
            result['quality_score'] = self._assess_quality(image_info)
            
            # 生成标签
            result['tags'] = self._generate_tags(image_info, result)
            
            logger.debug(f"图片分类完成: {image_info.get('filename', 'unknown')} -> {result['primary_category']}")
            
        except Exception as e:
            logger.error(f"图片分类失败: {e}")
            result['primary_category'] = '未分类'
            result['error'] = str(e)
        
        return result
    
    def _classify_by_filename(self, image_info: Dict[str, Any]) -> Dict[str, Any]:
        """基于文件名分类"""
        filename = image_info.get('filename', '')
        url = image_info.get('url', '')
        
        # 检查文件名和URL
        text_to_check = f"{filename} {url}".lower()
        
        best_category = None
        best_confidence = 0.0
        
        for category, patterns in self.compiled_filename_rules.items():
            matches = 0
            for pattern in patterns:
                if pattern.search(text_to_check):
                    matches += 1
            
            if matches > 0:
                confidence = min(matches / len(patterns), 1.0)
                if confidence > best_confidence:
                    best_category = category
                    best_confidence = confidence
        
        return {
            'category': best_category,
            'confidence': best_confidence
        }
    
    def _classify_by_size(self, image_info: Dict[str, Any]) -> Dict[str, Any]:
        """基于尺寸分类"""
        width = image_info.get('width', 0)
        height = image_info.get('height', 0)
        
        if not width or not height:
            return {'category': None, 'confidence': 0.0}
        
        for category, rules in self.size_rules.items():
            min_width = rules.get('min_width', 0)
            max_width = rules.get('max_width', float('inf'))
            min_height = rules.get('min_height', 0)
            max_height = rules.get('max_height', float('inf'))
            
            if (min_width <= width <= max_width and 
                min_height <= height <= max_height):
                return {
                    'category': category,
                    'confidence': 0.8  # 尺寸分类的置信度
                }
        
        return {'category': None, 'confidence': 0.0}
    
    def _classify_by_content(self, image_info: Dict[str, Any]) -> Dict[str, Any]:
        """基于内容分类（简单实现）"""
        # 这里可以集成机器学习模型进行内容分类
        # 目前提供一个基础的实现
        
        local_path = image_info.get('local_path')
        if not local_path or not Path(local_path).exists():
            return {'category': None, 'confidence': 0.0}
        
        try:
            with Image.open(local_path) as img:
                # 基于颜色特征的简单分类
                colors = self._analyze_colors(img)
                
                # 基于颜色判断可能的类别
                if colors['is_grayscale']:
                    return {'category': '黑白图片', 'confidence': 0.7}
                elif colors['dominant_color'] == 'blue':
                    return {'category': '蓝色主题', 'confidence': 0.6}
                elif colors['dominant_color'] == 'green':
                    return {'category': '绿色主题', 'confidence': 0.6}
                
        except Exception as e:
            logger.warning(f"内容分析失败: {e}")
        
        return {'category': None, 'confidence': 0.0}
    
    def _analyze_colors(self, img: Image.Image) -> Dict[str, Any]:
        """分析图片颜色特征"""
        # 转换为RGB模式
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 缩小图片以提高处理速度
        img.thumbnail((100, 100))
        
        # 转换为numpy数组
        img_array = np.array(img)
        
        # 检查是否为灰度图
        r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
        is_grayscale = np.allclose(r, g) and np.allclose(g, b)
        
        # 计算平均颜色
        avg_color = np.mean(img_array, axis=(0, 1))
        
        # 确定主导颜色
        dominant_color = 'unknown'
        if avg_color[0] > avg_color[1] and avg_color[0] > avg_color[2]:
            dominant_color = 'red'
        elif avg_color[1] > avg_color[0] and avg_color[1] > avg_color[2]:
            dominant_color = 'green'
        elif avg_color[2] > avg_color[0] and avg_color[2] > avg_color[1]:
            dominant_color = 'blue'
        
        return {
            'is_grayscale': is_grayscale,
            'avg_color': avg_color.tolist(),
            'dominant_color': dominant_color,
        }
    
    def _assess_quality(self, image_info: Dict[str, Any]) -> float:
        """评估图片质量"""
        score = 0.0
        
        # 基于尺寸评分
        width = image_info.get('width', 0)
        height = image_info.get('height', 0)
        
        if width and height:
            # 分辨率评分
            resolution = width * height
            if resolution >= 1920 * 1080:  # 高清
                score += 0.4
            elif resolution >= 1280 * 720:  # 标清
                score += 0.3
            elif resolution >= 640 * 480:   # 低清
                score += 0.2
            else:
                score += 0.1
            
            # 宽高比评分
            aspect_ratio = width / height
            if 1.3 <= aspect_ratio <= 1.8:  # 常见比例
                score += 0.2
            elif 0.7 <= aspect_ratio <= 2.5:  # 可接受比例
                score += 0.1
        
        # 基于文件大小评分
        file_size = image_info.get('file_size', 0)
        if file_size:
            if file_size >= 500 * 1024:  # 大于500KB
                score += 0.2
            elif file_size >= 100 * 1024:  # 大于100KB
                score += 0.1
        
        # 基于格式评分
        format_name = image_info.get('format', '').lower()
        if format_name in ['png', 'jpg', 'jpeg']:
            score += 0.2
        elif format_name in ['webp', 'bmp']:
            score += 0.1
        
        return min(score, 1.0)
    
    def _generate_tags(self, image_info: Dict[str, Any], classification_result: Dict[str, Any]) -> List[str]:
        """生成图片标签"""
        tags = []
        
        # 基于分类添加标签
        if classification_result['primary_category']:
            tags.append(classification_result['primary_category'])
        
        # 基于尺寸添加标签
        width = image_info.get('width', 0)
        height = image_info.get('height', 0)
        
        if width and height:
            if width >= 1920 and height >= 1080:
                tags.append('高清')
            elif width <= 300 or height <= 300:
                tags.append('小图')
            
            # 方向标签
            if width > height * 1.5:
                tags.append('横图')
            elif height > width * 1.5:
                tags.append('竖图')
            else:
                tags.append('方图')
        
        # 基于格式添加标签
        format_name = image_info.get('format', '').lower()
        if format_name:
            tags.append(format_name.upper())
        
        # 基于质量添加标签
        quality_score = classification_result.get('quality_score', 0)
        if quality_score >= 0.8:
            tags.append('高质量')
        elif quality_score <= 0.3:
            tags.append('低质量')
        
        return list(set(tags))  # 去重
    
    def detect_duplicates(self, image_list: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """检测重复图片"""
        duplicates = {}
        hash_groups = {}
        
        for image_info in image_list:
            # 基于MD5哈希检测完全重复
            md5_hash = image_info.get('md5_hash')
            if md5_hash:
                if md5_hash not in hash_groups:
                    hash_groups[md5_hash] = []
                hash_groups[md5_hash].append(image_info)
        
        # 找出重复组
        for hash_value, images in hash_groups.items():
            if len(images) > 1:
                duplicates[hash_value] = images
        
        return duplicates
    
    def get_classification_statistics(self, images: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取分类统计信息"""
        stats = {
            'total_images': len(images),
            'categories': {},
            'quality_distribution': {'high': 0, 'medium': 0, 'low': 0},
            'format_distribution': {},
            'size_distribution': {'large': 0, 'medium': 0, 'small': 0},
        }
        
        for image_info in images:
            # 分类统计
            classification = self.classify_image(image_info)
            category = classification['primary_category']
            stats['categories'][category] = stats['categories'].get(category, 0) + 1
            
            # 质量统计
            quality_score = classification['quality_score']
            if quality_score >= 0.7:
                stats['quality_distribution']['high'] += 1
            elif quality_score >= 0.4:
                stats['quality_distribution']['medium'] += 1
            else:
                stats['quality_distribution']['low'] += 1
            
            # 格式统计
            format_name = image_info.get('format', 'unknown')
            stats['format_distribution'][format_name] = stats['format_distribution'].get(format_name, 0) + 1
            
            # 尺寸统计
            width = image_info.get('width', 0)
            height = image_info.get('height', 0)
            if width and height:
                resolution = width * height
                if resolution >= 1920 * 1080:
                    stats['size_distribution']['large'] += 1
                elif resolution >= 640 * 480:
                    stats['size_distribution']['medium'] += 1
                else:
                    stats['size_distribution']['small'] += 1
        
        return stats
