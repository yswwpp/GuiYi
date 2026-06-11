/**
 * WPS 页面检测
 */

import { isKdocsPage, extractDocToken, detectDocType } from '../shared/utils';
import type { KdocsPageInfo, DocType } from '../shared/types';

/**
 * 检测当前页面信息
 */
export function detectKdocsPage(): KdocsPageInfo {
  const url = window.location.href;
  const hostname = window.location.hostname;

  // 判断是否是 kdocs.cn 页面
  const isKdocs = isKdocsPage(url);

  if (!isKdocs) {
    return {
      isKdocs: false,
      docType: 'unknown',
      docToken: null,
      docUrl: url
    };
  }

  // 解析文档 token
  const docToken = extractDocToken(url);

  // 判断文档类型（先从 URL，再从 DOM）
  let docType: DocType = detectDocType(url);

  // DOM 元素判断（更准确）
  const sheetContainer = document.querySelector(
    '.sheet-container, [data-sheet], .excel-container, [class*="spreadsheet"]'
  );
  const pptContainer = document.querySelector(
    '.ppt-container, [data-ppt], .slide-container, [class*="presentation"]'
  );

  if (sheetContainer) {
    docType = 'sheet';
  } else if (pptContainer) {
    docType = 'ppt';
  }

  return {
    isKdocs,
    docType,
    docToken,
    docUrl: url
  };
}

/**
 * 检查页面是否加载完成
 */
export function isPageReady(): boolean {
  // 检查编辑器容器是否存在
  const editorContainer = document.querySelector(
    '.editor-container, .doc-content, #editor, [data-editor]'
  );

  // 检查是否有内容
  const hasContent = document.body.innerText?.length > 100;

  return !!editorContainer && hasContent;
}

/**
 * 等待页面加载完成
 */
export function waitForPageReady(timeout = 10000): Promise<boolean> {
  return new Promise((resolve) => {
    const startTime = Date.now();

    const check = () => {
      if (isPageReady()) {
        resolve(true);
        return;
      }

      if (Date.now() - startTime > timeout) {
        resolve(false);
        return;
      }

      setTimeout(check, 500);
    };

    check();
  });
}