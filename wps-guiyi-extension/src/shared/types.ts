/**
 * 共享类型定义
 */

// 文档类型
export type DocType = 'doc' | 'sheet' | 'ppt' | 'unknown';

// Block 类型
export type BlockType = 'paragraph' | 'heading' | 'listItem' | 'table' | 'slide' | 'image';

// 列表类型
export type ListType = 'ordered' | 'unordered';

// 同步状态
export type SyncStatusType = typeof SYNC_STATUS[keyof typeof SYNC_STATUS];
import { SYNC_STATUS } from './constants';

// ========== WPS 文档数据结构 ==========

/**
 * WPS 文档数据（推送到后端）
 */
export interface KdocsDocument {
  id: string;                  // wps_{account}_{token}
  title: string;
  content: string;             // 纯文本内容（用于索引）
  blocks?: BlockNode[];        // Block 结构（可选）
  url: string;
  source: 'wps';
  account: string;
  docType: DocType;
  docToken: string;
  updatedAt: number;           // timestamp (ms)
  storeLocally: false;
}

/**
 * Block 节点（结构化内容）
 */
export interface BlockNode {
  type: BlockType;
  id: string;
  content: string;
  level?: number;              // heading level (1-6)
  listType?: ListType;
  style?: Record<string, string>;
  metadata?: Record<string, unknown>;
  children?: BlockNode[];      // 嵌套列表
  position?: number;           // 在文档中的位置
}

// ========== 页面信息 ==========

/**
 * WPS 页面检测结果
 */
export interface KdocsPageInfo {
  isKdocs: boolean;
  docType: DocType;
  docToken: string | null;
  docUrl: string;
}

// ========== 消息类型 ==========

/**
 * 扩展消息
 */
export interface ExtensionMessage {
  action: string;
  data?: unknown;
  pageInfo?: KdocsPageInfo;
}

/**
 * 扩展消息响应
 */
export interface ExtensionResponse {
  success?: boolean;
  error?: string;
  document?: KdocsDocument;
  data?: unknown;
}

// ========== 同步状态 ==========

/**
 * 本地同步记录
 */
export interface LocalSyncRecord {
  docToken: string;
  title: string;
  syncedAt: number;
  contentHash: string;
}

/**
 * 同步状态响应
 */
export interface SyncStatusResponse {
  synced: boolean;
  lastSync?: number;
  contentHash?: string;
}

/**
 * 同步结果
 */
export interface SyncResult {
  status: 'success' | 'error';
  message?: string;
  document?: KdocsDocument;
  pushResult?: unknown;
}

// ========== API 响应 ==========

/**
 * GuiYi API 推送响应
 */
export interface GuiyiPushResponse {
  status: 'success' | 'received';
  message: string;
  doc_id: string;
  doc_token: string;
  title: string;
}

/**
 * GuiYi API 文档列表响应
 */
export interface GuiyiDocumentsResponse {
  total: number;
  documents: Array<{
    id: string;
    title: string;
    url: string;
    last_synced: number;
  }>;
}