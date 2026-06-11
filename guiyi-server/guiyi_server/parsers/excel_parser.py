"""
Excel 文档解析器
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ExcelParser:
    """Excel 文档解析器"""

    SUPPORTED_EXTENSIONS = ['.xlsx', '.xls']

    @staticmethod
    def parse(file_path: str, max_length: int = 50000) -> Optional[str]:
        """
        解析 Excel 文档

        Args:
            file_path: 文件路径
            max_length: 最大内容长度

        Returns:
            文档内容（只读操作）
        """
        try:
            from openpyxl import load_workbook

            # 只读模式打开
            wb = load_workbook(file_path, read_only=True, data_only=True)

            all_content = []

            # 遍历所有工作表
            for sheet_name in wb.sheetnames[:5]:  # 最多取前 5 个工作表
                sheet = wb[sheet_name]
                all_content.append(f"【{sheet_name}】")

                # 读取数据（最多 100 行）
                row_count = 0
                for row in sheet.iter_rows(values_only=True):
                    if row_count >= 100:
                        break

                    # 过滤空行
                    row_text = " | ".join([str(cell) if cell is not None else "" for cell in row])
                    if row_text.strip():
                        all_content.append(row_text)
                    row_count += 1

            wb.close()

            content = "\n".join(all_content)
            return content[:max_length] if len(content) > max_length else content

        except Exception as e:
            logger.error(f"解析 Excel 文档失败: {file_path} - {e}")
            return None
