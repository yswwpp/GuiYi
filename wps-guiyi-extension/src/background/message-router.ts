/**
 * 消息路由处理
 */

import { ApiClient } from './api-client';
import { syncManager } from './sync-manager';
import { MESSAGE_ACTIONS } from '../shared/constants';
import type { ExtensionMessage, ExtensionResponse, KdocsDocument } from '../shared/types';

const apiClient = new ApiClient();

/**
 * 处理来自 Content Script 和 Popup 的消息
 */
chrome.runtime.onMessage.addListener(
  (message: ExtensionMessage, sender, sendResponse: (response: ExtensionResponse) => void) => {
    console.log('[Background] 收到消息:', message.action);

    handleMessage(message, sender.tab?.id)
      .then(response => sendResponse(response))
      .catch(error => sendResponse({ error: error.message }));

    return true; // 异步响应
  }
);

/**
 * 消息处理分发
 */
async function handleMessage(message: ExtensionMessage, tabId?: number): Promise<ExtensionResponse> {
  switch (message.action) {

    // Content Script 通知页面加载
    case MESSAGE_ACTIONS.PAGE_LOADED:
      await handlePageLoaded(message.pageInfo!);
      return { success: true };

    // 推送单个文档到后端
    case MESSAGE_ACTIONS.PUSH_DOCUMENT:
      return await handlePushDocument(message.data as KdocsDocument);

    // 获取同步状态
    case MESSAGE_ACTIONS.GET_SYNC_STATUS:
      return await handleGetSyncStatus(message.data as { docToken: string; account?: string });

    // 获取已同步文档列表
    case MESSAGE_ACTIONS.GET_DOCUMENTS:
      return await handleGetDocuments(message.data as { account?: string; limit?: number });

    // 触发同步（从 Popup）
    case MESSAGE_ACTIONS.TRIGGER_SYNC:
      return await handleTriggerSync(tabId);

    default:
      throw new Error(`未知消息类型: ${message.action}`);
  }
}

/**
 * 处理页面加载通知
 */
async function handlePageLoaded(pageInfo: { docToken: string | null; docType: string; docUrl: string }): Promise<void> {
  if (!pageInfo.docToken) return;

  console.log('[Background] WPS 页面加载:', pageInfo.docToken);

  // 检查本地同步状态
  const record = await syncManager.checkSyncStatus(pageInfo.docToken);

  if (!record) {
    console.log('[Background] 新文档，建议同步');
  } else {
    console.log('[Background] 已同步文档，上次同步:', new Date(record.syncedAt).toLocaleString());
  }
}

/**
 * 处理推送文档
 */
async function handlePushDocument(doc: KdocsDocument): Promise<ExtensionResponse> {
  try {
    // 检查内容是否变更
    const hasChanged = await syncManager.hasContentChanged(doc);

    if (!hasChanged) {
      console.log('[Background] 内容无变更，跳过推送');
      return {
        success: true,
        data: { status: 'skipped', reason: 'no_change' }
      };
    }

    // 推送到后端并索引
    const result = await apiClient.pushAndIndex(doc);

    // 标记已同步
    await syncManager.markSynced(doc);

    console.log('[Background] 推送成功:', result.message);

    return {
      success: true,
      data: result
    };
  } catch (error) {
    const err = error as Error;
    console.error('[Background] 推送失败:', err);
    return { error: err.message };
  }
}

/**
 * 处理获取同步状态
 */
async function handleGetSyncStatus(request: { docToken: string; account?: string }): Promise<ExtensionResponse> {
  try {
    // 先检查本地记录
    const localRecord = await syncManager.checkSyncStatus(request.docToken);

    if (localRecord) {
      return {
        success: true,
        data: {
          synced: true,
          lastSync: localRecord.syncedAt,
          contentHash: localRecord.contentHash,
          title: localRecord.title
        }
      };
    }

    // 再检查后端状态
    const status = await apiClient.getSyncStatus(request.docToken, request.account);
    return { success: true, data: status };
  } catch (error) {
    const err = error as Error;
    return { error: err.message };
  }
}

/**
 * 处理获取文档列表
 */
async function handleGetDocuments(params: { account?: string; limit?: number }): Promise<ExtensionResponse> {
  try {
    const documents = await apiClient.getDocuments(params.account, params.limit);
    return { success: true, data: documents };
  } catch (error) {
    const err = error as Error;
    return { error: err.message };
  }
}

/**
 * 处理触发同步
 */
async function handleTriggerSync(tabId?: number): Promise<ExtensionResponse> {
  try {
    // 获取当前活动标签页
    let targetTabId = tabId;
    if (!targetTabId) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      targetTabId = tab?.id;
    }

    if (!targetTabId) {
      throw new Error('无法获取活动标签页');
    }

    // 向 Content Script 发送提取请求
    const extractResponse = await chrome.tabs.sendMessage(targetTabId!, {
      action: MESSAGE_ACTIONS.EXTRACT_DOCUMENT
    });

    if (extractResponse.error) {
      throw new Error(extractResponse.error);
    }

    const doc = extractResponse.document as KdocsDocument;

    // 推送到后端
    const pushResult = await handlePushDocument(doc);

    if (pushResult.error) {
      throw new Error(pushResult.error);
    }

    return {
      success: true,
      document: doc,
      data: pushResult.data
    };
  } catch (error) {
    const err = error as Error;
    console.error('[Background] 同步触发失败:', err);
    return { error: err.message };
  }
}