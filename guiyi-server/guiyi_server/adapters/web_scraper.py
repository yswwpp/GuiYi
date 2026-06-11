"""
网页抓取器 - 完整存储网页内容到 Obsidian
"""

import trafilatura
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin
import hashlib
import json
from datetime import datetime
import logging
import urllib3

from guiyi_server.config import settings

# 禁用 SSL 警告（仅用于测试）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logger = logging.getLogger(__name__)


class WebScraper:
    """网页抓取器"""

    def __init__(self, assets_dir: str = None):
        """
        初始化抓取器

        Args:
            assets_dir: 图片存储目录
        """
        self.assets_dir = Path(assets_dir or settings.WEB_ASSETS_PATH)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        # 配置 requests session
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

    def fetch_full(self, url: str) -> Dict:
        """
        抓取网页，完整存储

        Args:
            url: 网页 URL

        Returns:
            包含标题、内容、元数据等的字典

        Raises:
            RuntimeError: 抓取失败时抛出
        """
        logger.info(f"开始抓取网页: {url}")
        try:
            # 发送 HTTP 请求（禁用 SSL 验证，仅用于测试）
            response = self.session.get(url, timeout=30, verify=False)
            response.raise_for_status()
            logger.debug(f"HTTP 请求成功: {url} (状态码: {response.status_code})")

            # 修正编码：优先使用 apparent_encoding 或 UTF-8
            if response.apparent_encoding and response.apparent_encoding != 'ISO-8859-1':
                response.encoding = response.apparent_encoding
            elif 'charset' not in response.headers.get('content-type', '').lower():
                # 如果没有明确指定编码，尝试 UTF-8
                response.encoding = 'utf-8'

            html = response.text

            # 提取正文内容
            content = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                favor_precision=True
            )

            if not content:
                logger.error(f"无法提取网页正文内容: {url}")
                raise ValueError("无法提取网页正文内容")

            logger.debug(f"成功提取正文内容，长度: {len(content)} 字符")

            # 提取元数据
            metadata = trafilatura.extract_metadata(html)

            # 修复编码问题：确保正确处理中文
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='ignore')

            # 提取并下载图片
            images = self._extract_images(html, url)

            # 构建结果
            result = {
                "url": url,
                "title": metadata.title if metadata else "无标题",
                "author": metadata.author if metadata else "",
                "published_at": metadata.date if metadata else "",
                "content": content,
                "images": images,
                "saved_at": datetime.now().isoformat(),
                "source": "web",
                "store_locally": True
            }

            logger.info(f"网页抓取成功: {url} (标题: {result['title']})")
            return result

        except requests.Timeout:
            logger.error(f"抓取网页超时: {url}")
            raise RuntimeError(f"抓取网页超时: {url}")
        except requests.HTTPError as e:
            logger.error(f"HTTP 错误: {url} - {e}")
            raise RuntimeError(f"HTTP 错误: {url} - {e}")
        except requests.RequestException as e:
            logger.error(f"网络请求失败: {url} - {e}")
            raise RuntimeError(f"网络请求失败: {url} - {e}")
        except Exception as e:
            logger.error(f"抓取网页失败: {url} - {e}")
            raise RuntimeError(f"抓取网页失败: {url} - {str(e)}")

    def _extract_images(self, html: str, base_url: str) -> List[Dict]:
        """
        提取并下载图片

        Args:
            html: HTML 内容
            base_url: 基础 URL

        Returns:
            图片信息列表
        """
        logger.debug(f"开始提取图片，基础 URL: {base_url}")
        soup = BeautifulSoup(html, 'html.parser')
        images = []

        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if not src:
                continue

            # 处理相对路径
            if src.startswith('//'):
                src = 'https:' + src
            elif not src.startswith('http'):
                src = urljoin(base_url, src)

            # 下载图片
            try:
                logger.debug(f"下载图片: {src}")
                img_response = self.session.get(src, timeout=10, verify=False)
                img_response.raise_for_status()

                # 生成文件名
                img_hash = hashlib.md5(src.encode()).hexdigest()[:12]
                content_type = img_response.headers.get('content-type', '')
                ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
                if ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    ext = 'jpg'

                img_filename = f"{img_hash}.{ext}"
                img_path = self.assets_dir / img_filename

                # 保存图片
                with open(img_path, 'wb') as f:
                    f.write(img_response.content)

                images.append({
                    "original_url": src,
                    "local_path": str(img_path),
                    "filename": img_filename
                })
                logger.debug(f"图片保存成功: {img_filename}")

            except Exception as e:
                logger.warning(f"图片下载失败：{src} - {e}")
                continue

        logger.info(f"图片提取完成，共 {len(images)} 张")
        return images

    def to_markdown(self, data: Dict) -> str:
        """
        转换为 Markdown 格式（带 YAML 元数据）

        Args:
            data: 抓取的网页数据

        Returns:
            Markdown 文本
        """
        # YAML 元数据
        frontmatter = {
            "title": data["title"],
            "url": data["url"],
            "author": data.get("author", ""),
            "published_at": data.get("published_at", ""),
            "saved_at": data["saved_at"],
            "tags": [],
            "source": "web",
            "store_locally": True
        }

        # 构建 Markdown
        lines = [
            "---",
            *[f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in frontmatter.items()],
            "---",
            "",
            f"# {data['title']}",
            "",
            f"**来源**: [{data['url']}]({data['url']})",
            ""
        ]

        # 添加作者和日期
        if data.get("author"):
            lines.append(f"**作者**: {data['author']}")
            lines.append("")
        if data.get("published_at"):
            lines.append(f"**发布时间**: {data['published_at']}")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(data["content"])

        return "\n".join(lines)

    def save_to_obsidian(self, url: str, output_dir: str = None) -> str:
        """
        抓取并保存到 Obsidian

        Args:
            url: 网页 URL
            output_dir: 输出目录

        Returns:
            保存的文件路径
        """
        logger.info(f"开始保存网页到 Obsidian: {url}")
        # 抓取网页
        data = self.fetch_full(url)

        # 转换为 Markdown
        markdown = self.to_markdown(data)

        # 生成文件名（使用标题或 URL）
        title = data["title"].replace("/", "-").replace("\\", "-")[:100]
        filename = f"{title}.md"

        # 保存文件
        output_path = Path(output_dir or Path(settings.OBSIDIAN_VAULT_PATH) / "inbox")
        output_path.mkdir(parents=True, exist_ok=True)

        file_path = output_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        logger.info(f"网页保存成功: {file_path}")
        return str(file_path)


# 测试代码
if __name__ == "__main__":
    scraper = WebScraper()

    # 测试抓取
    test_url = "https://www.example.com"
    try:
        file_path = scraper.save_to_obsidian(test_url)
        print(f"抓取成功: {file_path}")
    except Exception as e:
        print(f"抓取失败: {e}")
