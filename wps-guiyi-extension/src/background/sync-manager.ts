/**
 * 同步状态管理（本地存储）
 */

import type { LocalSyncRecord, KdocsDocument } from '../shared/types';
import { hashContent } from '../shared/utils';

const STORAGE_KEY = 'wps_sync_records';

/**
 * 同步状态管理器
 */
export class SyncManager {
  private records: LocalSyncRecord[] = [];

  /**
   * 初始化：加载已有记录
   */
  async init(): Promise<void> {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    this.records = result[STORAGE_KEY] || [];
    console.log('[SyncManager] 已加载记录:', this.records.length);
  }

  /**
   * 检查文档同步状态
   */
  async checkSyncStatus(docToken: string): Promise<LocalSyncRecord | undefined> {
    return this.records.find(r => r.docToken === docToken);
  }

  /**
   * 标记文档已同步
   */
  async markSynced(doc: KdocsDocument): Promise<void> {
    const contentHash = await hashContent(doc.content);

    const record: LocalSyncRecord = {
      docToken: doc.docToken,
      title: doc.title,
      syncedAt: Date.now(),
      contentHash
    };

    // 更新或添加记录
    const existingIndex = this.records.findIndex(r => r.docToken === doc.docToken);
    if (existingIndex >= 0) {
      this.records[existingIndex] = record;
    } else {
      this.records.push(record);
    }

    // 保存
    await this.saveRecords();
    console.log('[SyncManager] 已标记同步:', doc.docToken);
  }

  /**
   * 获取所有同步记录
   */
  async getRecords(): Promise<LocalSyncRecord[]> {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    return result[STORAGE_KEY] || [];
  }

  /**
   * 获取最近同步的文档
   */
  async getRecentRecords(limit: number = 10): Promise<LocalSyncRecord[]> {
    const records = await this.getRecords();
    return records
      .sort((a, b) => b.syncedAt - a.syncedAt)
      .slice(0, limit);
  }

  /**
   * 清除同步记录
   */
  async clearRecords(): Promise<void> {
    this.records = [];
    await chrome.storage.local.remove(STORAGE_KEY);
    console.log('[SyncManager] 已清除所有记录');
  }

  /**
   * 检查内容是否变更（对比哈希）
   */
  async hasContentChanged(doc: KdocsDocument): Promise<boolean> {
    const record = await this.checkSyncStatus(doc.docToken);
    if (!record) return true;

    const currentHash = await hashContent(doc.content);
    return currentHash !== record.contentHash;
  }

  // ========== 私有方法 ==========

  /**
   * 保存记录到 storage
   */
  private async saveRecords(): Promise<void> {
    await chrome.storage.local.set({ [STORAGE_KEY]: this.records });
  }
}

// 导出单例
export const syncManager = new SyncManager();