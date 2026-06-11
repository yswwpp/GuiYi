/**
 * Content Script 入口
 */

import { detectKdocsPage, waitForPageReady } from './kdocs-detector';
import { KdocsDomParser, blocksToText } from './dom-parser';
import { MESSAGE_ACTIONS } from '../shared/constants';
import type { KdocsDocument, ExtensionMessage, ExtensionResponse, KdocsPageInfo, BlockNode } from '../shared/types';

const parser = new KdocsDomParser();

// 监听来自 Background 的消息
chrome.runtime.onMessage.addListener(
  (message: ExtensionMessage, sender, sendResponse: (response: ExtensionResponse) => void) => {
    console.log('[WPS Content] 收到消息:', message.action);

    handleMessage(message)
      .then(response => sendResponse(response))
      .catch(error => sendResponse({ error: error.message }));

    return true; // 异步响应
  }
);

/**
 * 处理消息
 */
async function handleMessage(message: ExtensionMessage): Promise<ExtensionResponse> {
  switch (message.action) {
    case MESSAGE_ACTIONS.REQUEST_EXTRACTION:
    case MESSAGE_ACTIONS.EXTRACT_DOCUMENT:
      return await extractDocument();

    default:
      return { error: `未知消息类型: ${message.action}` };
  }
}

/**
 * 提取当前页面文档
 */
async function extractDocument(): Promise<ExtensionResponse> {
  const pageInfo = detectKdocsPage();

  if (!pageInfo.isKdocs) {
    return { error: '当前页面不是 WPS 文档' };
  }

  if (!pageInfo.docToken) {
    return { error: '无法识别文档 Token' };
  }

  // 等待页面加载完成
  const ready = await waitForPageReady(5000);
  if (!ready) {
    console.warn('[WPS Content] 页面可能未完全加载');
  }

  try {
    const doc = buildDocument(pageInfo);
    console.log('[WPS Content] 文档提取成功:', doc.title);
    return { success: true, document: doc };
  } catch (error) {
    const err = error as Error;
    console.error('[WPS Content] 提取失败:', err);
    return { error: `提取失败: ${err.message}` };
  }
}

/**
 * 构建文档数据
 */
function buildDocument(pageInfo: KdocsPageInfo): KdocsDocument {
  const title = parser.extractTitle();
  let content = '';
  let blocks: BlockNode[] = [];

  // 根据文档类型提取内容
  switch (pageInfo.docType) {
    case 'doc':
      blocks = parser.extractDocContent();
      content = blocksToText(blocks);
      break;
    case 'sheet':
      content = parser.extractSheetContent();
      break;
    case 'ppt':
      blocks = parser.extractPptContent();
      content = blocksToText(blocks);
      break;
    default:
      content = parser.extractGenericContent();
  }

  // 如果内容为空，使用兜底方案
  if (!content || content.length < 50) {
    content = parser.extractGenericContent();
  }

  return {
    id: `wps_default_${pageInfo.docToken}`,
    title,
    content,
    blocks: blocks.length > 0 ? blocks : undefined,
    url: pageInfo.docUrl,
    source: 'wps',
    account: 'wps_default',
    docType: pageInfo.docType,
    docToken: pageInfo.docToken!,
    updatedAt: Date.now(),
    storeLocally: false
  };
}

// ========== 页面加载时自动通知 Background ==========

window.addEventListener('load', async () => {
  const pageInfo = detectKdocsPage();

  if (pageInfo.isKdocs && pageInfo.docToken) {
    // 等待一小段时间确保页面稳定
    await new Promise(resolve => setTimeout(resolve, 2000));

    chrome.runtime.sendMessage({
      action: MESSAGE_ACTIONS.PAGE_LOADED,
      pageInfo
    }).catch(err => {
      // Background 可能未启动，忽略错误
      console.debug('[WPS Content] 无法通知 Background:', err);
    });

    console.log('[WPS Content] 已检测到 WPS 文档:', pageInfo);
  }
});

console.log('[WPS Content] Content Script 已加载');