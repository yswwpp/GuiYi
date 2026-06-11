/**
 * Background Service Worker 入口
 */

import './message-router';
import './api-client';
import './sync-manager';
import { syncManager } from './sync-manager';
import { MESSAGE_ACTIONS } from '../shared/constants';

console.log('[WPS GuiYi Extension] Background Service Worker 已启动');

// 初始化同步管理器
syncManager.init().catch(err => {
  console.error('[Background] 初始化失败:', err);
});

// 插件安装时
chrome.runtime.onInstalled.addListener((details) => {
  console.log('[Background] 插件已安装:', details.reason);

  if (details.reason === 'install') {
    // 首次安装，可以打开欢迎页面
    console.log('[Background] 首次安装，欢迎使用 WPS GuiYi Sync');
  }

  if (details.reason === 'update') {
    console.log('[Background] 插件已更新');
  }
});

// 监听标签页更新（用于自动检测 WPS 页面）
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    // 检查是否是 kdocs.cn 页面
    if (tab.url.includes('kdocs.cn')) {
      console.log('[Background] 检测到 WPS 页面:', tab.url);
      // 更新扩展图标状态（可选）
    }
  }
});

// 监听扩展图标点击（可选：打开设置页面）
chrome.action.onClicked.addListener((tab) => {
  // Plasmo 有 Popup，所以这个监听器通常不会触发
  // 如果需要打开设置页面，可以使用：
  // chrome.runtime.openOptionsPage();
});