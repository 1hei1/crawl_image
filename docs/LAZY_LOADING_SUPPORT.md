# 懒加载图片支持文档

## 🎯 概述

智能图片爬虫系统现在完全支持各种懒加载（Lazy Loading）技术，能够自动识别和提取使用懒加载的图片。

## 🔧 支持的懒加载技术

### 1. 数据属性懒加载

系统按优先级检查以下属性：

```html
<!-- 最常见的懒加载属性 -->
<img src="placeholder.gif" data-original="real-image.jpg" />

<!-- 其他常见属性 -->
<img src="loading.gif" data-src="actual-image.png" />
<img data-lazy-src="lazy-image.jpg" />
<img data-lazy="image.webp" />
<img data-url="photo.jpg" />
<img data-img="picture.png" />
<img data-image="wallpaper.jpg" />

<!-- 高质量图片属性 -->
<img data-large="large-image.jpg" />
<img data-full="full-size.jpg" />
<img data-hd="hd-image.jpg" />
<img data-hi-res="high-res.jpg" />
<img data-zoom="zoomable.jpg" />

<!-- 预览和缩略图 -->
<img data-thumb="thumbnail.jpg" />
<img data-preview="preview.jpg" />
```

### 2. 响应式图片（srcset）

```html
<!-- 响应式图片集 -->
<img srcset="small.jpg 480w, medium.jpg 800w, large.jpg 1200w" 
     src="fallback.jpg" />

<!-- 高分辨率显示 -->
<img srcset="normal.jpg 1x, retina.jpg 2x" 
     src="normal.jpg" />
```

### 3. CSS背景图片

```html
<!-- 内联样式背景图片 -->
<div style="background-image: url('background.jpg');">Content</div>

<!-- 多种CSS格式支持 -->
<div style="background-image:url(image.png);">Content</div>
<div style="background-image: url('image.jpg');">Content</div>
<div style="background-image: url(image.webp);">Content</div>
```

### 4. 非img元素的图片

```html
<!-- div元素的懒加载 -->
<div data-original="div-image.jpg"></div>

<!-- 链接元素的图片 -->
<a data-src="link-image.png">Link</a>

<!-- span元素的图片 -->
<span data-lazy="span-image.jpg"></span>
```

## 🚀 使用示例

### 示例1：您提到的网站格式

```html
<a href="/4Kdongwu/2525.html" target="_blank" title="秃头鹰6K高端电脑桌面壁纸" 
   data-resolution="6000x4000" class="item">
    <img src="/static/images/gray.gif" 
         data-original="https://c.53326.com/d/file/newpc202302/z11cch41yhz.jpg" 
         alt="秃头鹰6K高端电脑桌面壁纸" class="lazy" />
    <div class="resolution">6000x4000</div>
</a>
```

**系统处理：**
- ✅ 忽略占位符图片 `/static/images/gray.gif`
- ✅ 提取真实图片 `https://c.53326.com/d/file/newpc202302/z11cch41yhz.jpg`
- ✅ 转换为绝对URL
- ✅ 验证为有效图片格式

### 示例2：复杂懒加载场景

```html
<!-- 多重懒加载属性 -->
<img src="placeholder.gif" 
     data-original="high-quality.jpg"
     data-src="medium-quality.jpg"
     data-lazy="low-quality.jpg" />
```

**系统处理：**
- ✅ 按优先级选择 `data-original` 的值
- ✅ 只提取最高优先级的图片URL

## 🔍 技术实现

### 属性优先级

系统按以下优先级检查属性：

1. `data-original` - 最高优先级
2. `data-src` - 次高优先级
3. `data-lazy-src` - 懒加载专用
4. `data-lazy` - 简化版本
5. `data-url` - 通用数据URL
6. `data-img` - 图片数据
7. `data-image` - 图片数据
8. `data-large` - 大图
9. `data-full` - 完整图片
10. `data-hd` - 高清图片
11. `data-hi-res` - 高分辨率
12. `data-zoom` - 缩放图片
13. `data-thumb` - 缩略图
14. `data-preview` - 预览图
15. `srcset` - 响应式图片
16. `src` - 标准属性（最后检查）

### 智能过滤

系统会自动过滤：

- ❌ 占位符图片（如 `gray.gif`, `placeholder.png`）
- ❌ Base64编码图片（`data:image/...`）
- ❌ 非图片文件（`.js`, `.css`, `.txt` 等）
- ❌ 广告和追踪像素
- ❌ 图标和favicon

## 📊 测试验证

运行测试脚本验证懒加载功能：

```bash
python test_lazy_loading.py
```

测试结果示例：
```
🧪 测试懒加载图片提取功能
==================================================
📷 IMG标签:
   src: /static/images/gray.gif
   data-original: https://c.53326.com/d/file/newpc202302/z11cch41yhz.jpg
   ✅ 提取到: ['https://c.53326.com/d/file/newpc202302/z11cch41yhz.jpg']

📊 总结:
   总共提取到 9 个图片URL
   
🔍 验证关键懒加载图片:
   ✅ https://c.53326.com/d/file/newpc202302/z11cch41yhz.jpg
```

## 🎯 实际使用

### 爬取懒加载网站

```bash
# 爬取包含懒加载图片的网站
python main.py --quiet crawl https://example.com --name "lazy_test"

# 批量爬取多个懒加载网站
python main.py batch https://site1.com https://site2.com --name "lazy_batch"
```

### 配置优化

在 `config.yaml` 中可以调整相关设置：

```yaml
crawler:
  # 增加并发数以处理更多懒加载图片
  max_concurrent: 15
  
  # 调整延迟以避免触发反爬虫
  request_delay: 2.0
  
  # 支持更多图片格式
  allowed_extensions:
    - ".jpg"
    - ".jpeg" 
    - ".png"
    - ".webp"
    - ".avif"  # 新格式支持
```

## 🚨 注意事项

1. **JavaScript渲染**：某些网站的懒加载需要JavaScript执行，当前版本不支持JavaScript渲染
2. **动态加载**：通过AJAX动态加载的图片可能无法检测到
3. **反爬虫保护**：某些网站可能有额外的反爬虫机制
4. **性能考虑**：懒加载检测会增加少量处理时间

## 🔮 未来改进

- [ ] 支持JavaScript渲染（Selenium集成）
- [ ] 支持AJAX动态内容检测
- [ ] 支持更多懒加载库（如Intersection Observer）
- [ ] 支持WebP和AVIF等新格式的懒加载
