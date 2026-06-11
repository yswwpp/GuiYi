/**
 * GuiYi API 通信客户端
 */

import { GUIYI_API_BASE } from '../shared/constants';
import type { KdocsDocument, GuiyiPushResponse, GuiyiDocumentsResponse, SyncStatusResponse } from '../shared/types';

/**
 * GuiYi 后端 API 客户端
 */
export class ApiClient {

  /**
   * 推送文档到 GuiYi 后端
   */
  async pushDocument(doc: KdocsDocument): Promise<GuiyiPushResponse> {
    const response = await fetch(`${GUIYI_API_BASE}/api/wps/push`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(doc)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`推送失败 (${response.status}): ${errorText}`);
    }

    return await response.json();
  }

  /**
   * 推送文档并立即索引
   */
  async pushAndIndex(doc: KdocsDocument): Promise<GuiyiPushResponse> {
    const response = await fetch(`${GUIYI_API_BASE}/api/wps/push-and-index`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(doc)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`推送索引失败 (${response.status}): ${errorText}`);
    }

    return await response.json();
  }

  /**
   * 获取同步状态
   */
  async getSyncStatus(docToken: string, account?: string): Promise<SyncStatusResponse> {
    const params = new URLSearchParams();
    params.set('doc_token', docToken);
    if (account) params.set('account', account);

    const response = await fetch(`${GUIYI_API_BASE}/api/wps/status?${params}`);

    if (!response.ok) {
      throw new Error(`获取状态失败: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * 获取已同步文档列表
   */
  async getDocuments(account?: string, limit?: number): Promise<GuiyiDocumentsResponse> {
    const params = new URLSearchParams();
    if (account) params.set('account', account);
    if (limit) params.set('limit', String(limit));

    const response = await fetch(`${GUIYI_API_BASE}/api/wps/documents?${params}`);

    if (!response.ok) {
      throw new Error(`获取文档列表失败: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * 触发批量同步
   */
  async triggerBatchSync(account?: string): Promise<{ status: string; stats: unknown }> {
    const response = await fetch(`${GUIYI_API_BASE}/api/wps/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ account })
    });

    if (!response.ok) {
      throw new Error(`触发同步失败: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * 检查后端服务是否可用
   */
  async checkHealth(): Promise<boolean> {
    try {
      const response = await fetch(`${GUIYI_API_BASE}/api/health`, {
        method: 'GET',
        timeout: 5000
      } as RequestInit);
      return response.ok;
    } catch {
      return false;
    }
  }
}