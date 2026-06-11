/**
 * Popup 脚本 - 纯 JavaScript 版本
 */

const GUIYI_API_BASE = 'http://localhost:8765';
const MESSAGE_ACTIONS = {
  PAGE_LOADED: 'pageLoaded',
  EXTRACT_DOCUMENT: 'extractDocument',
  REQUEST_EXTRACTION: 'requestExtraction',
  TRIGGER_SYNC: 'triggerSync',
  GET_SYNC_STATUS: 'getSyncStatus',
  GET_DOCUMENTS: 'getDocuments',
  PUSH_DOCUMENT: 'pushDocument',
  GET_STATUS: 'getStatus'
};

interface DocumentInfo {
  docToken: string;
  docType: string;
  title?: string;
}

interface SyncRecord {
  docToken: string;
  title?: string;
  syncedAt: number;
}

interface ExtensionResponse {
  success?: boolean;
  error?: string;
  document?: DocumentInfo;
  data?: {
    synced?: boolean;
    lastSync?: number;
  };
}

// 元素引用
const statusBadge = document.getElementById('statusBadge') as HTMLElement;
const contentDiv = document.getElementById('content') as HTMLElement;
const documentListDiv = document.getElementById('documentList') as HTMLElement;

// 状态
let currentPageInfo: DocumentInfo | null = null;
let isWpsPage = false;
let syncing = false;

// 格式化时间戳
function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

// 检查当前页面
async function checkCurrentPage(): Promise<void> {
  try {
    // 获取当前活动标签页
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab || !tab.url) {
      showError('无法获取当前标签页');
      return;
    }

    // 检查是否是 WPS 页面
    isWpsPage = tab.url.includes('kdocs.cn');
    updateStatusBadge();

    if (isWpsPage && tab.id) {
      // 向 Content Script 发送消息获取页面信息
      try {
        const response = await chrome.tabs.sendMessage(tab.id, {
          action: MESSAGE_ACTIONS.EXTRACT_DOCUMENT
        }) as ExtensionResponse;

        if (response.success && response.document) {
          currentPageInfo = response.document;
          showWpsPageInfo(response.document);
        } else if (response.error) {
          showError(response.error);
        }
      } catch {
        // Content Script 可能未加载
        showError('页面尚未加载完成，请稍后再试');
      }
    } else {
      showNotWpsMessage();
    }
  } catch {
    showError('检查页面失败');
  }
}

// 更新状态徽章
function updateStatusBadge(): void {
  statusBadge.textContent = isWpsPage ? 'WPS 页面' : '非 WPS';
  statusBadge.className = 'status-badge ' + (isWpsPage ? 'wps' : 'not-wps');
}

// 显示 WPS 页面信息
function showWpsPageInfo(doc: DocumentInfo): void {
  const docTypeLabel: Record<string, string> = {
    doc: '文字文档',
    sheet: '表格文档',
    ppt: '演示文稿',
    unknown: '未知类型'
  };

  const docTypeIcon: Record<string, string> = {
    doc: '📝',
    sheet: '📊',
    ppt: '📽️',
    unknown: '📄'
  };

  const icon = docTypeIcon[doc.docType] || '📄';
  const label = docTypeLabel[doc.docType] || '文档';

  contentDiv.innerHTML = `
    <div class="panel">
      <div class="doc-info">
        <div class="doc-type">
          <span>${icon}</span>
          <span>${label}</span>
        </div>
        <div style="font-size: 14px; margin-top: 4px; color: #333;">${doc.title || '未命名文档'}</div>
      </div>
      <div class="sync-info" id="syncInfo">
        <span class="not-synced">⏳ 待同步</span>
      </div>
      <button class="sync-button" id="syncButton">立即同步</button>
      <div id="syncMessage" class="message" style="display: none;"></div>
    </div>
  `;

  // 绑定同步按钮
  const syncBtn = document.getElementById('syncButton') as HTMLButtonElement;
  syncBtn.addEventListener('click', handleSync);

  // 获取同步状态
  getSyncStatus(doc.docToken);
}

// 显示非 WPS 页面消息
function showNotWpsMessage(): void {
  contentDiv.innerHTML = `
    <div class="not-wps-message">
      <p>当前页面不是 WPS 文档</p>
      <p>请打开 kdocs.cn 文档后使用</p>
    </div>
  `;
}

// 显示错误
function showError(message: string): void {
  contentDiv.innerHTML = `
    <div class="panel" style="background: #ffe0e0;">
      <div style="color: #c00; font-size: 13px;">${message}</div>
    </div>
  `;
}

// 获取同步状态
async function getSyncStatus(docToken: string): Promise<void> {
  try {
    const response = await chrome.runtime.sendMessage({
      action: MESSAGE_ACTIONS.GET_SYNC_STATUS,
      data: { docToken }
    }) as ExtensionResponse;

    if (response.success && response.data) {
      const syncInfo = document.getElementById('syncInfo') as HTMLElement;
      if (response.data.synced) {
        const lastSyncStr = response.data.lastSync ? formatTimestamp(response.data.lastSync) : '';
        syncInfo.innerHTML = `
          <span class="synced">✅ 已同步</span>
          ${lastSyncStr ? `<span style="margin-left: 8px; color: #666;">${lastSyncStr}</span>` : ''}
        `;
      }
    }
  } catch {
    // 无法获取状态，忽略
  }
}

// 处理同步
async function handleSync(): Promise<void> {
  if (syncing) return;

  const syncButton = document.getElementById('syncButton') as HTMLButtonElement;
  const syncMessage = document.getElementById('syncMessage') as HTMLElement;

  syncing = true;
  syncButton.textContent = '同步中...';
  syncButton.classList.add('syncing');
  syncButton.disabled = true;
  syncMessage.style.display = 'none';

  try {
    const response = await chrome.runtime.sendMessage({
      action: MESSAGE_ACTIONS.TRIGGER_SYNC
    }) as ExtensionResponse;

    if (response.success) {
      syncMessage.textContent = response.document
        ? `同步成功：${response.document.title || '文档'}`
        : '同步成功！';
      syncMessage.className = 'message success';
      syncMessage.style.display = 'block';

      // 更新同步状态显示
      const syncInfo = document.getElementById('syncInfo') as HTMLElement;
      syncInfo.innerHTML = `<span class="synced">✅ 已同步</span>`;

      // 更新文档列表
      loadRecentDocuments();
    } else if (response.error) {
      syncMessage.textContent = `同步失败：${response.error}`;
      syncMessage.className = 'message error';
      syncMessage.style.display = 'block';
    }
  } catch {
    syncMessage.textContent = '同步失败，请检查后端服务';
    syncMessage.className = 'message error';
    syncMessage.style.display = 'block';
  } finally {
    syncing = false;
    syncButton.textContent = '立即同步';
    syncButton.classList.remove('syncing');
    syncButton.disabled = false;
  }
}

// 加载最近同步的文档
async function loadRecentDocuments(): Promise<void> {
  try {
    const result = await chrome.storage.local.get('wps_sync_records');
    const records: SyncRecord[] = result.wps_sync_records || [];

    if (records.length === 0) {
      documentListDiv.innerHTML = `
        <div class="list-header">最近同步</div>
        <div class="document-list empty">暂无已同步文档</div>
      `;
      return;
    }

    // 按时间排序，限制数量
    const sortedRecords = records
      .sort((a: SyncRecord, b: SyncRecord) => b.syncedAt - a.syncedAt)
      .slice(0, 10);

    const itemsHtml = sortedRecords.map((doc: SyncRecord) => `
      <div class="list-item">
        <div class="item-title">${doc.title || '未命名文档'}</div>
        <div class="item-time">${formatTimestamp(doc.syncedAt)}</div>
      </div>
    `).join('');

    documentListDiv.innerHTML = `
      <div class="list-header">最近同步 (${sortedRecords.length})</div>
      ${itemsHtml}
    `;
  } catch {
    documentListDiv.innerHTML = `
      <div class="list-header">最近同步</div>
      <div class="document-list empty">加载失败</div>
    `;
  }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
  checkCurrentPage();
  loadRecentDocuments();
});