/**
 * 工具函数
 */

import { KDOCS_DOC_TOKEN_PATTERN, KDOCS_URL_PATTERN } from './constants';
import type { KdocsPageInfo, DocType } from './types';

/**
 * 检测当前页面是否为 kdocs.cn
 */
export function isKdocsPage(url: string): boolean {
  return KDOCS_URL_PATTERN.test(url);
}

/**
 * 从 URL 提取文档 Token
 */
export function extractDocToken(url: string): string | null {
  const match = url.match(KDOCS_DOC_TOKEN_PATTERN);
  return match ? match[1] : null;
}

/**
 * 根据 URL 和 DOM 判断文档类型
 */
export function detectDocType(url: string): DocType {
  // URL 路径判断
  if (url.includes('/sheet/') || url.includes('/sheets/')) {
    return 'sheet';
  }
  if (url.includes('/ppt/') || url.includes('/presentation/')) {
    return 'ppt';
  }
  return 'doc';
}

/**
 * 计算 SHA-256 哈希
 */
export async function hashContent(content: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(content);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
}

/**
 * 截断文本
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.slice(0, maxLength);
}

/**
 * 格式化时间戳
 */
export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * Debounce 函数
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return function (...args: Parameters<T>) {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
      timeoutId = null;
    }, wait);
  };
}