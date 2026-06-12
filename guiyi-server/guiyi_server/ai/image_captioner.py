"""
图片描述服务 - 使用 MLX + Qwen2.5-VL 生成图片描述和标签
"""

import os
import gc
import time
import json
import re
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_MODEL_DIR = "/Users/yswwpp/dev/docker_file_sharing/GuiYi/models"
DEFAULT_VLM_MODEL = os.path.join(DEFAULT_MODEL_DIR, "mlx-community/Qwen2.5-VL-7B-Instruct-4bit")
DEFAULT_MAX_SIDE = 1024
DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MIN_SIZE_BYTES = 1024
DEFAULT_IDLE_UNLOAD_MINUTES = 5


class ImageCaptioner:
    """
    图片描述服务

    功能：
    - 模型懒加载：第一次处理图片时才加载模型
    - 单例复用：同一次会话内复用模型实例
    - 空闲释放：长时间未使用自动释放内存
    - 大图缩放：超过最大边长自动缩放
    """

    _instance: Optional['ImageCaptioner'] = None

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        model_path: str = None,
        max_side: int = None,
        max_tokens: int = None,
        temperature: float = None,
        min_size_bytes: int = None,
        idle_unload_minutes: int = None
    ):
        """
        初始化图片描述器

        Args:
            model_path: 模型路径
            max_side: 图片最长边缩放上限
            max_tokens: 最大输出 token 数
            temperature: 生成温度
            min_size_bytes: 最小图片大小（字节）
            idle_unload_minutes: 空闲释放时间（分钟）
        """
        if self._initialized:
            return

        self.model_path = model_path or os.getenv("GUIYI_IMAGE_VLM_MODEL", DEFAULT_VLM_MODEL)
        self.max_side = max_side or int(os.getenv("GUIYI_IMAGE_MAX_SIDE", DEFAULT_MAX_SIDE))
        self.max_tokens = max_tokens or int(os.getenv("GUIYI_IMAGE_MAX_TOKENS", DEFAULT_MAX_TOKENS))
        self.temperature = temperature or float(os.getenv("GUIYI_IMAGE_TEMPERATURE", DEFAULT_TEMPERATURE))
        self.min_size_bytes = min_size_bytes or int(os.getenv("GUIYI_IMAGE_MIN_SIZE_BYTES", DEFAULT_MIN_SIZE_BYTES))
        self.idle_unload_seconds = (idle_unload_minutes or int(os.getenv("GUIYI_IMAGE_IDLE_UNLOAD_MINUTES", DEFAULT_IDLE_UNLOAD_MINUTES))) * 60

        # 模型状态
        self.model = None
        self.processor = None
        self.last_used_at = 0.0
        self._enabled = None

        self._initialized = True
        logger.info(f"ImageCaptioner 初始化完成: model={self.model_path}, max_side={self.max_side}")

    @property
    def enabled(self) -> bool:
        """检查图片索引是否启用"""
        if self._enabled is None:
            self._enabled = os.getenv("GUIYI_IMAGE_INDEX_ENABLED", "false").lower() == "true"
        return self._enabled

    def _ensure_loaded(self):
        """确保模型已加载"""
        if self.model is not None:
            return

        if not self.enabled:
            raise RuntimeError("图片索引未启用，请设置 GUIYI_IMAGE_INDEX_ENABLED=true")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型路径不存在: {self.model_path}，请先下载模型")

        try:
            logger.info(f"正在加载图片描述模型: {self.model_path}")
            start_time = time.time()

            from mlx_vlm import load

            self.model, self.processor = load(self.model_path)

            load_time = time.time() - start_time
            logger.info(f"模型加载完成，耗时 {load_time:.2f} 秒")

        except ImportError as e:
            logger.error(f"MLX VLM 未安装: {e}")
            raise RuntimeError("请安装 mlx-vlm: uv pip install mlx-vlm")

    def unload_if_idle(self):
        """检查并释放空闲模型"""
        if self.model is None:
            return

        if time.monotonic() - self.last_used_at < self.idle_unload_seconds:
            return

        logger.info("模型空闲超时，正在释放...")
        self.model = None
        self.processor = None
        gc.collect()
        logger.info("模型已释放")

    def _resize_image(self, image):
        """缩放图片"""
        from PIL import Image

        width, height = image.size
        max_dim = max(width, height)

        if max_dim <= self.max_side:
            return image

        # 等比缩放
        scale = self.max_side / max_dim
        new_width = int(width * scale)
        new_height = int(height * scale)

        logger.debug(f"图片缩放: {width}x{height} -> {new_width}x{new_height}")
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def _build_prompt(self) -> str:
        """构建提示词"""
        return (
            '请分析这张图片，只输出以下 JSON，不要有其他内容：\n'
            '{"description": "一句话描述图片的主要内容", '
            '"tags": ["标签1", "标签2", "标签3"], '
            '"ocr_text": "图片中的文字，没有则为空字符串"}'
        )

    def _parse_output(self, output: str) -> Dict:
        """解析模型输出"""
        result = {
            "description": "",
            "tags": [],
            "ocr_text": "",
            "raw_output": output
        }

        if not output or not output.strip():
            return result

        # 剥掉 markdown 代码块包装 ```json ... ```
        cleaned = output.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)

        # 尝试解析 JSON
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            json_str = json_match.group()
            try:
                parsed = json.loads(json_str)
                result["description"] = parsed.get("description", "")
                result["tags"] = parsed.get("tags", [])
                result["ocr_text"] = parsed.get("ocr_text", "")
                return result
            except json.JSONDecodeError:
                # 单引号问题：用 ast.literal_eval（允许单引号）
                try:
                    import ast
                    parsed = ast.literal_eval(json_str)
                    result["description"] = parsed.get("description", "")
                    result["tags"] = parsed.get("tags", [])
                    result["ocr_text"] = parsed.get("ocr_text", "")
                    return result
                except Exception:
                    pass

        # 解析自然语言输出
        # 格式通常是："描述内容...标签：xxx、xxx..."

        # 提取标签部分（改用贪婪匹配到行尾，不被句号截断）
        tags_match = re.search(r'标签[：:]\s*(.+?)(?:\n|$)', output, re.DOTALL)
        if tags_match:
            tags_str = tags_match.group(1)
            # 分割标签（支持中文顿号、逗号、空格）
            tags = re.split(r'[、，,\s]+', tags_str)
            result["tags"] = [t.strip() for t in tags if t.strip() and len(t.strip()) > 1][:12]

        # 提取描述（标签之前的内容）
        desc = output
        if tags_match:
            desc = output[:tags_match.start()]

        # 清理描述
        desc = re.sub(r'^图片描述[：:]\s*', '', desc.strip())
        desc = re.sub(r'^这张图片[是为]?\s*', '', desc)
        desc = desc.strip()

        if desc:
            result["description"] = desc

        # 提取图片中的文字
        text_match = re.search(r'(?:图片中的)?文字[：:]\s*([^\n。，]+)', output)
        if text_match:
            result["ocr_text"] = text_match.group(1).strip()

        # 如果没有提取到描述，使用原始输出
        if not result["description"]:
            result["description"] = output.strip()[:500]

        return result

    def describe_and_tag(self, image_path: str) -> Dict:
        """
        生成图片描述和标签

        Args:
            image_path: 图片文件路径

        Returns:
            包含 description, tags, ocr_text, raw_output 的字典
        """
        # 检查文件
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        file_size = os.path.getsize(image_path)
        if file_size < self.min_size_bytes:
            logger.debug(f"图片过小，跳过: {image_path} ({file_size} bytes)")
            return {
                "description": "",
                "tags": [],
                "ocr_text": "",
                "raw_output": "",
                "skipped": True,
                "skip_reason": "file_too_small"
            }

        # 加载模型
        self._ensure_loaded()
        self.last_used_at = time.monotonic()

        try:
            # 生成描述
            from mlx_vlm import generate
            from mlx_vlm.prompt_utils import apply_chat_template
            from mlx_vlm.utils import load_config

            prompt = self._build_prompt()

            # 用 chat template 包装，否则图片 token 不会注入到 prompt 里
            if not hasattr(self, '_model_config'):
                self._model_config = load_config(self.model_path)
            formatted_prompt = apply_chat_template(
                self.processor, self._model_config, prompt, num_images=1
            )

            logger.debug(f"正在处理图片: {image_path}")
            start_time = time.time()

            output = generate(
                self.model,
                self.processor,
                formatted_prompt,
                image=[image_path],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                repetition_penalty=1.5,
                verbose=False
            )

            elapsed = time.time() - start_time
            logger.debug(f"图片处理完成，耗时 {elapsed:.2f} 秒")

            # 解析输出
            # output 是 GenerationResult，需要转换为字符串
            if hasattr(output, 'text'):
                output_text = output.text
            else:
                output_text = str(output)

            result = self._parse_output(output_text)
            result["elapsed_seconds"] = elapsed

            return result

        except Exception as e:
            logger.error(f"图片处理失败: {image_path} - {e}")
            # MLX metal queue 可能在异常后陷入死锁，强制卸载模型让下张图重新加载
            try:
                self.model = None
                self.processor = None
                if hasattr(self, '_model_config'):
                    del self._model_config
                gc.collect()
                logger.warning("模型已卸载（异常恢复），下次将重新加载")
            except Exception:
                pass
            raise

        finally:
            self.last_used_at = time.monotonic()

    def is_available(self) -> bool:
        """检查服务是否可用"""
        if not self.enabled:
            return False

        if not os.path.exists(self.model_path):
            return False

        try:
            import mlx_vlm
            return True
        except ImportError:
            return False

    def get_status(self) -> Dict:
        """获取服务状态"""
        return {
            "enabled": self.enabled,
            "available": self.is_available(),
            "model_path": self.model_path,
            "model_loaded": self.model is not None,
            "idle_seconds": time.monotonic() - self.last_used_at if self.last_used_at > 0 else None,
            "config": {
                "max_side": self.max_side,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "min_size_bytes": self.min_size_bytes,
                "idle_unload_minutes": self.idle_unload_seconds // 60
            }
        }


# 全局实例
_captioner: Optional[ImageCaptioner] = None


def get_image_captioner() -> ImageCaptioner:
    """获取图片描述器单例"""
    global _captioner
    if _captioner is None:
        _captioner = ImageCaptioner()
    return _captioner
