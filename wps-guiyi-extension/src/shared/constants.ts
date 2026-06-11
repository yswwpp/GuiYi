/**
 * 共享常量定义
 */

// GuiYi 后端 API 地址
export const GUIYI_API_BASE = 'http://localhost:8765';

// WPS 文档 URL 模式
export const KDOCS_URL_PATTERN = /kdocs\.cn/;
export const KDOCS_DOC_TOKEN_PATTERN = /kdocs\.cn\/(?:view\/)?l\/([a-zA-Z0-9]+)/;

// 同步状态
export const SYNC_STATUS = {
  NOT_SYNCED: 'not_synced',
  SYNCING: 'syncing',
  SYNCED: 'synced',
  ERROR: 'error'
} as const;

// 消息类型
export const MESSAGE_ACTIONS = {
  // Content Script -> Background
  PAGE_LOADED: 'pageLoaded',
  EXTRACT_DOCUMENT: 'extractDocument',

  // Background -> Content Script
  REQUEST_EXTRACTION: 'requestExtraction',

  // Popup -> Background
  TRIGGER_SYNC: 'triggerSync',
  GET_SYNC_STATUS: 'getSyncStatus',
  GET_DOCUMENTS: 'getDocuments',

  // Background -> GuiYi API
  PUSH_DOCUMENT: 'pushDocument',
  GET_STATUS: 'getStatus'
} as const;

// 内容长度限制
export const MAX_CONTENT_LENGTH = 50000;
export const MAX_PREVIEW_LENGTH = 5000;

// Debounce 时间（毫秒）
export const SYNC_DEBOUNCE_TIME = 5000;