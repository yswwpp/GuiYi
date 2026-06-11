/**
 * WPS DOM 解析核心
 */

import type { BlockNode, DocType } from '../shared/types';
import { truncateText } from '../shared/utils';
import { MAX_CONTENT_LENGTH } from '../shared/constants';

/**
 * WPS 文档 DOM 解析器
 */
export class KdocsDomParser {

  /**
   * 解析文档标题
   */
  extractTitle(): string {
    // 优先级1: 标题输入框（可编辑状态）
    const titleInput = document.querySelector(
      '.doc-title input, .title-input, [data-title], header input[type="text"]'
    ) as HTMLInputElement;

    if (titleInput && titleInput.value) {
      return titleInput.value.trim();
    }

    // 优先级2: 标题文本元素
    const titleText = document.querySelector(
      '.doc-title, .document-title, .title-text, [class*="title"]'
    );

    if (titleText && titleText.textContent) {
      return titleText.textContent.trim();
    }

    // 优先级3: 从 URL 参数推断
    const urlParams = new URLSearchParams(window.location.search);
    const urlTitle = urlParams.get('title');
    if (urlTitle) {
      return urlTitle;
    }

    // 优先级4: 使用文档名称（可能有）
    const docName = document.querySelector('[data-doc-name], .file-name');
    if (docName && docName.textContent) {
      return docName.textContent.trim();
    }

    // 默认: 使用文档 token
    const tokenMatch = window.location.href.match(/l\/([a-zA-Z0-9]+)/);
    return tokenMatch ? `WPS文档_${tokenMatch[1].slice(0, 8)}` : '未命名文档';
  }

  /**
   * 解析文字文档内容（Block 结构）
   */
  extractDocContent(): BlockNode[] {
    const blocks: BlockNode[] = [];

    // WPS 文字文档内容区域选择器
    const contentContainer = document.querySelector(
      '.doc-content, .document-content, .editor-content, [data-content], #editor, [data-editor]'
    );

    if (!contentContainer) {
      console.warn('[WPS Parser] 未找到内容容器');
      return blocks;
    }

    // 遍历段落 Block
    const paragraphElements = contentContainer.querySelectorAll(
      'p, .paragraph, [data-block-type="paragraph"], div[data-block], section'
    );

    let position = 0;

    paragraphElements.forEach((elem) => {
      const text = this.extractTextContent(elem);
      if (!text || text.length < 2) return; // 跳过空段落

      const block: BlockNode = {
        type: 'paragraph',
        id: elem.getAttribute('data-block-id') || `block_${position}`,
        content: truncateText(text, 1000),
        position: position++
      };

      // 检测标题级别
      const headingLevel = this.detectHeadingLevel(elem);
      if (headingLevel) {
        block.type = 'heading';
        block.level = headingLevel;
      }

      // 检测列表
      if (elem.classList.contains('list-item') || elem.closest('ul, ol')) {
        block.type = 'listItem';
        block.listType = elem.closest('ol') ? 'ordered' : 'unordered';
      }

      blocks.push(block);
    });

    // 提取表格
    const tables = contentContainer.querySelectorAll('table, .table-block');
    tables.forEach((table, index) => {
      const tableContent = this.extractTableContent(table as HTMLTableElement);
      if (tableContent) {
        blocks.push({
          type: 'table',
          id: `table_${index}`,
          content: tableContent,
          position: position++
        });
      }
    });

    return blocks;
  }

  /**
   * 解析表格文档内容
   */
  extractSheetContent(): string {
    const contentParts: string[] = [];

    // 获取工作表列表
    const sheetTabs = document.querySelectorAll(
      '.sheet-tab, .tab-item, [data-sheet-tab], [class*="sheet-tab"]'
    );

    const sheetNames: string[] = [];
    sheetTabs.forEach(tab => {
      const name = tab.textContent?.trim();
      if (name && !sheetNames.includes(name)) {
        sheetNames.push(name);
      }
    });

    if (sheetNames.length > 0) {
      contentParts.push(`【工作表】 ${sheetNames.join(' | ')}`);
    }

    // 遍历当前活动工作表的内容
    const activeSheet = document.querySelector(
      '.sheet-content.active, .active-sheet, [data-active-sheet], [class*="active-sheet"]'
    );

    if (activeSheet) {
      // 提取单元格数据
      const rows: Map<number, string[]> = new Map();

      // 尝试不同的单元格选择器
      const cells = activeSheet.querySelectorAll(
        '.cell, td, [data-cell], [class*="cell"]'
      );

      cells.forEach(cell => {
        // 尝试从不同属性获取行号
        const rowAttr = cell.getAttribute('data-row');
        const rowFromTR = cell.closest('tr')?.rowIndex;

        const rowNum = rowAttr ? parseInt(rowAttr) : rowFromTR;
        if (rowNum !== undefined && rowNum >= 0) {
          if (!rows.has(rowNum)) rows.set(rowNum, []);
          const text = cell.textContent?.trim() || '';
          if (text) {
            rows.get(rowNum)?.push(text);
          }
        }
      });

      // 如果通过 cells 没获取到，尝试直接遍历 tr
      if (rows.size === 0) {
        activeSheet.querySelectorAll('tr').forEach((tr, idx) => {
          const cols: string[] = [];
          tr.querySelectorAll('td, th').forEach(cell => {
            const text = cell.textContent?.trim();
            if (text) cols.push(text);
          });
          if (cols.length > 0) {
            rows.set(idx, cols);
          }
        });
      }

      // 格式化行内容（限制行数）
      const maxRows = 100;
      let rowCount = 0;
      rows.forEach((cols, rowNum) => {
        if (rowCount >= maxRows) return;
        if (cols.some(c => c)) { // 跳过空行
          contentParts.push(`行${rowNum + 1}: ${cols.join(' | ')}`);
          rowCount++;
        }
      });
    }

    return truncateText(contentParts.join('\n'), MAX_CONTENT_LENGTH);
  }

  /**
   * 解析演示文稿内容
   */
  extractPptContent(): BlockNode[] {
    const slides: BlockNode[] = [];

    // 获取幻灯片列表
    let slideElements = document.querySelectorAll(
      '.slide, .ppt-slide, [data-slide], [class*="slide"]'
    );

    if (slideElements.length === 0) {
      // 尝试其他选择器
      const slideContainer = document.querySelector('[class*="slide-container"], [class*="presentation"]');
      if (slideContainer) {
        slideElements = slideContainer.querySelectorAll('div[class*="slide"]');
      }
    }

    slideElements.forEach((slide, index) => {
      const slideContent: BlockNode = {
        type: 'slide',
        id: `slide_${index}`,
        content: '',
        metadata: {},
        position: index
      };

      // 提取幻灯片标题
      const slideTitle = slide.querySelector(
        '.slide-title, h1, h2, .title, [class*="title"]'
      );
      if (slideTitle) {
        slideContent.metadata!.title = slideTitle.textContent?.trim();
      }

      // 提取幻灯片内容
      const slideTexts = slide.querySelectorAll(
        '.text-box, .content-box, p, span, div'
      );
      const texts: string[] = [];
      slideTexts.forEach(elem => {
        const text = elem.textContent?.trim();
        if (text && text.length > 1 && !texts.includes(text)) {
          texts.push(text);
        }
      });

      slideContent.content = truncateText(texts.join('\n'), 1000);
      slides.push(slideContent);
    });

    return slides;
  }

  /**
   * 通用内容提取（兜底方案）
   */
  extractGenericContent(): string {
    // 尝试获取编辑器区域的纯文本
    const editor = document.querySelector(
      '[data-editor], .editor, #editor, main, article'
    );

    if (editor) {
      return truncateText((editor as HTMLElement).innerText || editor.textContent || '', MAX_CONTENT_LENGTH);
    }

    // 最后兜底：整个页面的纯文本
    return truncateText(document.body.innerText || '', MAX_CONTENT_LENGTH);
  }

  // ========== 私有方法 ==========

  /**
   * 提取纯文本内容（递归）
   */
  private extractTextContent(element: Element): string {
    // 直接使用 textContent
    return element.textContent?.trim() || '';
  }

  /**
   * 提取表格内容
   */
  private extractTableContent(table: HTMLTableElement): string {
    const rows: string[] = [];

    table.querySelectorAll('tr').forEach(tr => {
      const cells: string[] = [];
      tr.querySelectorAll('td, th').forEach(cell => {
        const text = cell.textContent?.trim() || '';
        if (text) cells.push(text);
      });
      if (cells.length > 0) {
        rows.push(cells.join(' | '));
      }
    });

    return rows.join('\n');
  }

  /**
   * 检测标题级别
   */
  private detectHeadingLevel(element: Element): number | null {
    // 检查标签名
    const tagName = element.tagName.toLowerCase();
    if (tagName === 'h1') return 1;
    if (tagName === 'h2') return 2;
    if (tagName === 'h3') return 3;
    if (tagName === 'h4') return 4;
    if (tagName === 'h5') return 5;
    if (tagName === 'h6') return 6;

    // 检查 class
    const classMatch = element.className.match(/heading-(\d)|h(\d)/);
    if (classMatch) {
      return parseInt(classMatch[1] || classMatch[2]);
    }

    // 检查 data 属性
    const dataLevel = element.getAttribute('data-heading-level');
    if (dataLevel) {
      return parseInt(dataLevel);
    }

    // 检查字体大小（启发式）
    const fontSize = window.getComputedStyle(element).fontSize;
    const size = parseFloat(fontSize);
    if (size >= 24) return 1;
    if (size >= 20) return 2;
    if (size >= 18) return 3;

    return null;
  }
}

/**
 * 将 Block 数组转换为纯文本用于索引
 */
export function blocksToText(blocks: BlockNode[]): string {
  const lines: string[] = [];

  blocks.forEach(block => {
    switch (block.type) {
      case 'heading':
        const prefix = '#'.repeat(block.level || 1);
        lines.push(`${prefix} ${block.content}`);
        break;
      case 'paragraph':
        lines.push(block.content);
        break;
      case 'listItem':
        const marker = block.listType === 'ordered' ? '1.' : '-';
        lines.push(`${marker} ${block.content}`);
        break;
      case 'table':
        lines.push('--- 表格 ---');
        lines.push(block.content);
        break;
      case 'slide':
        const title = block.metadata?.title as string || '';
        lines.push(`--- 幻灯片 ${(block.position || 0) + 1} ---`);
        if (title) lines.push(`标题: ${title}`);
        lines.push(block.content);
        break;
      default:
        if (block.content) lines.push(block.content);
    }
  });

  return lines.join('\n\n');
}