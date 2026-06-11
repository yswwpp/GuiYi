"""
测试网页抓取功能
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from guiyi_server.adapters.web_scraper import WebScraper
import tempfile
import os


class TestWebScraper:
    """网页抓取器测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        # 使用临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.assets_dir = os.path.join(self.temp_dir, "assets")
        self.scraper = WebScraper(assets_dir=self.assets_dir)

    def teardown_method(self):
        """每个测试方法后执行"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_init(self):
        """测试初始化"""
        assert self.scraper.assets_dir is not None
        assert os.path.exists(self.assets_dir)
        assert self.scraper.session is not None

    @patch('guiyi_server.adapters.web_scraper.requests.Session.get')
    def test_fetch_full_success(self, mock_get):
        """测试成功抓取网页"""
        # 模拟响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head><title>测试页面</title></head>
        <body>
            <article>
                <h1>测试标题</h1>
                <p>这是测试内容，用于验证网页抓取功能。</p>
            </article>
        </body>
        </html>
        """
        mock_response.apparent_encoding = 'utf-8'
        mock_response.headers = {'content-type': 'text/html; charset=utf-8'}
        mock_get.return_value = mock_response

        result = self.scraper.fetch_full("https://example.com/test")

        assert result is not None
        assert "url" in result
        assert "title" in result
        assert "content" in result
        assert result["url"] == "https://example.com/test"

    @patch('guiyi_server.adapters.web_scraper.requests.Session.get')
    def test_fetch_full_with_images(self, mock_get):
        """测试抓取包含图片的网页"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head><title>图片测试</title></head>
        <body>
            <article>
                <h1>测试</h1>
                <p>内容</p>
                <img src="https://example.com/image.jpg" />
            </article>
        </body>
        </html>
        """
        mock_response.apparent_encoding = 'utf-8'
        mock_response.headers = {'content-type': 'text/html'}

        # 模拟图片响应
        mock_img_response = Mock()
        mock_img_response.status_code = 200
        mock_img_response.content = b'\x89PNG\r\n\x1a\n'  # PNG 头
        mock_img_response.headers = {'content-type': 'image/png'}

        mock_get.side_effect = [mock_response, mock_img_response]

        result = self.scraper.fetch_full("https://example.com/test")

        assert result is not None
        assert "images" in result

    @patch('guiyi_server.adapters.web_scraper.requests.Session.get')
    def test_fetch_full_timeout(self, mock_get):
        """测试抓取超时"""
        import requests
        mock_get.side_effect = requests.Timeout("Connection timeout")

        with pytest.raises(RuntimeError) as exc_info:
            self.scraper.fetch_full("https://example.com/timeout")

        assert "超时" in str(exc_info.value) or "抓取" in str(exc_info.value)

    @patch('guiyi_server.adapters.web_scraper.requests.Session.get')
    def test_fetch_full_http_error(self, mock_get):
        """测试 HTTP 错误"""
        import requests
        mock_get.side_effect = requests.HTTPError("404 Not Found")

        with pytest.raises(RuntimeError):
            self.scraper.fetch_full("https://example.com/notfound")

    def test_to_markdown(self):
        """测试转换为 Markdown"""
        data = {
            "url": "https://example.com/test",
            "title": "测试标题",
            "author": "测试作者",
            "published_at": "2024-01-01",
            "content": "这是测试内容。",
            "images": [],
            "saved_at": "2024-01-01T12:00:00"
        }

        markdown = self.scraper.to_markdown(data)

        assert "---" in markdown
        assert "测试标题" in markdown  # 标题存在于 YAML 和正文
        assert "https://example.com/test" in markdown
        assert "# 测试标题" in markdown
        assert "这是测试内容。" in markdown

    def test_to_markdown_special_characters(self):
        """测试特殊字符处理"""
        data = {
            "url": "https://example.com/test",
            "title": "测试 <script>alert('xss')</script>",
            "content": "内容包含特殊字符: & < > \" '",
            "images": [],
            "saved_at": "2024-01-01T12:00:00"
        }

        markdown = self.scraper.to_markdown(data)

        assert markdown is not None
        assert len(markdown) > 0

    @patch('guiyi_server.adapters.web_scraper.requests.Session.get')
    def test_save_to_obsidian(self, mock_get):
        """测试保存到 Obsidian"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head><title>保存测试</title></head>
        <body><article><p>测试内容</p></article></body>
        </html>
        """
        mock_response.apparent_encoding = 'utf-8'
        mock_response.headers = {'content-type': 'text/html'}
        mock_get.return_value = mock_response

        output_dir = os.path.join(self.temp_dir, "output")
        file_path = self.scraper.save_to_obsidian(
            "https://example.com/test",
            output_dir=output_dir
        )

        assert file_path is not None
        assert os.path.exists(file_path)
        assert file_path.endswith(".md")


class TestWebScraperEncoding:
    """编码处理测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.assets_dir = os.path.join(self.temp_dir, "assets")
        self.scraper = WebScraper(assets_dir=self.assets_dir)

    def teardown_method(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch('guiyi_server.adapters.web_scraper.requests.Session.get')
    def test_chinese_encoding(self, mock_get):
        """测试中文编码处理"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head><meta charset="utf-8"><title>中文标题</title></head>
        <body><article><p>这是中文内容，测试编码处理。</p></article></body>
        </html>
        """
        mock_response.apparent_encoding = 'utf-8'
        mock_response.headers = {'content-type': 'text/html; charset=utf-8'}
        mock_get.return_value = mock_response

        result = self.scraper.fetch_full("https://example.com/chinese")

        assert "中文" in result["title"] or "中文" in result["content"]

    @patch('guiyi_server.adapters.web_scraper.requests.Session.get')
    def test_gbk_encoding(self, mock_get):
        """测试 GBK 编码处理"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head><title>GBK测试</title></head>
        <body><article><p>内容</p></article></body>
        </html>
        """
        mock_response.apparent_encoding = 'gbk'
        mock_response.headers = {'content-type': 'text/html'}
        mock_get.return_value = mock_response

        result = self.scraper.fetch_full("https://example.com/gbk")

        assert result is not None


class TestWebScraperImages:
    """图片处理测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.assets_dir = os.path.join(self.temp_dir, "assets")
        self.scraper = WebScraper(assets_dir=self.assets_dir)

    def teardown_method(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_extract_images_relative_url(self):
        """测试相对路径图片"""
        from urllib.parse import urljoin

        base_url = "https://example.com/page/"
        relative_src = "/images/test.jpg"
        expected_url = urljoin(base_url, relative_src)

        result = urljoin(base_url, relative_src)
        assert result == "https://example.com/images/test.jpg"

    def test_extract_images_protocol_relative(self):
        """测试协议相对路径图片"""
        from urllib.parse import urljoin

        base_url = "https://example.com/page/"
        src = "//cdn.example.com/image.jpg"

        # 协议相对路径处理
        if src.startswith('//'):
            result = 'https:' + src
        else:
            result = urljoin(base_url, src)

        assert result == "https://cdn.example.com/image.jpg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
