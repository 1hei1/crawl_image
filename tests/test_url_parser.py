"""
URL解析器测试用例
"""

import pytest
from crawler.utils.url_parser import URLParser


class TestURLParser:
    """URL解析器测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.base_url = "https://example.com"
        self.parser = URLParser(self.base_url)
    
    def test_normalize_url(self):
        """测试URL标准化"""
        # 测试添加协议
        assert URLParser.normalize_url("example.com") == "https://example.com/"
        assert URLParser.normalize_url("http://example.com") == "http://example.com/"
        
        # 测试移除默认端口
        assert URLParser.normalize_url("https://example.com:443") == "https://example.com/"
        assert URLParser.normalize_url("http://example.com:80") == "http://example.com/"
        
        # 测试域名小写
        assert URLParser.normalize_url("https://EXAMPLE.COM") == "https://example.com/"
        
        # 测试移除fragment
        assert URLParser.normalize_url("https://example.com/page#section") == "https://example.com/page"
    
    def test_extract_domain(self):
        """测试域名提取"""
        assert URLParser.extract_domain("https://example.com/path") == "example.com"
        assert URLParser.extract_domain("http://sub.example.com:8080/") == "sub.example.com:8080"
        assert URLParser.extract_domain("invalid-url") == ""
    
    def test_to_absolute_url(self):
        """测试相对URL转绝对URL"""
        # 测试相对路径
        assert self.parser.to_absolute_url("/path/to/image.jpg") == "https://example.com/path/to/image.jpg"
        assert self.parser.to_absolute_url("image.jpg") == "https://example.com/image.jpg"
        
        # 测试协议相对URL
        assert self.parser.to_absolute_url("//cdn.example.com/image.jpg") == "https://cdn.example.com/image.jpg"
        
        # 测试绝对URL
        assert self.parser.to_absolute_url("https://other.com/image.jpg") == "https://other.com/image.jpg"
    
    def test_is_valid_url(self):
        """测试URL有效性验证"""
        assert self.parser.is_valid_url("https://example.com/image.jpg") == True
        assert self.parser.is_valid_url("http://example.com/image.jpg") == True
        assert self.parser.is_valid_url("ftp://example.com/image.jpg") == False
        assert self.parser.is_valid_url("invalid-url") == False
        assert self.parser.is_valid_url("") == False
    
    def test_is_image_url(self):
        """测试图片URL识别"""
        # 测试常见图片扩展名
        assert self.parser.is_image_url("https://example.com/image.jpg") == True
        assert self.parser.is_image_url("https://example.com/image.png") == True
        assert self.parser.is_image_url("https://example.com/image.gif") == True
        assert self.parser.is_image_url("https://example.com/image.webp") == True
        
        # 测试大小写
        assert self.parser.is_image_url("https://example.com/image.JPG") == True
        
        # 测试带参数的URL
        assert self.parser.is_image_url("https://example.com/image.jpg?size=large") == True
        
        # 测试非图片URL
        assert self.parser.is_image_url("https://example.com/page.html") == False
        assert self.parser.is_image_url("https://example.com/script.js") == False
        
        # 测试排除模式
        assert self.parser.is_image_url("https://example.com/ads/banner.jpg") == False
        assert self.parser.is_image_url("https://example.com/thumb_image.jpg") == False
    
    def test_is_same_domain(self):
        """测试同域名判断"""
        assert self.parser.is_same_domain("https://example.com/path") == True
        assert self.parser.is_same_domain("http://example.com/path") == True
        assert self.parser.is_same_domain("https://other.com/path") == False
        assert self.parser.is_same_domain("https://sub.example.com/path") == False
    
    def test_clean_url(self):
        """测试URL清理"""
        # 测试移除不必要的参数
        dirty_url = "https://example.com/image.jpg?utm_source=google&utm_medium=cpc&size=large"
        clean_url = self.parser.clean_url(dirty_url)
        assert "utm_source" not in clean_url
        assert "utm_medium" not in clean_url
        assert "size=large" in clean_url
    
    def test_extract_filename(self):
        """测试文件名提取"""
        assert self.parser.extract_filename("https://example.com/images/photo.jpg") == "photo.jpg"
        assert self.parser.extract_filename("https://example.com/") != ""
        assert self.parser.extract_filename("") == ""
    
    def test_get_url_info(self):
        """测试URL信息获取"""
        url = "/images/photo.jpg"
        info = self.parser.get_url_info(url)
        
        assert info['original_url'] == url
        assert info['absolute_url'] == "https://example.com/images/photo.jpg"
        assert info['domain'] == "example.com"
        assert info['filename'] == "photo.jpg"
        assert info['is_valid'] == True
        assert info['is_image'] == True
        assert info['is_same_domain'] == True


if __name__ == '__main__':
    pytest.main([__file__])
