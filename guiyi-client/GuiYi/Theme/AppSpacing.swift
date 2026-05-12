//
//  AppSpacing.swift
//  GuiYi
//
//  GuiYi 间距系统 - 统一管理布局间距和尺寸
//

import SwiftUI

/// GuiYi 间距系统
struct AppSpacing {

    // MARK: - 基础间距

    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 24
    static let xxl: CGFloat = 32

    // MARK: - 组件间距

    /// 搜索框内边距
    static let searchPadding: CGFloat = 14

    /// 结果行内边距
    static let resultRowPadding: CGFloat = 14

    /// 卡片内边距
    static let cardPadding: CGFloat = 16

    /// 设置面板内边距
    static let settingsPadding: CGFloat = 20

    // MARK: - 尺寸

    /// 数据源图标大小
    static let sourceIconSize: CGFloat = 28

    /// 窗口宽度
    static let searchWindowWidth: CGFloat = 600
    static let settingsWindowWidth: CGFloat = 500
    static let settingsWindowHeight: CGFloat = 500

    /// 窗口圆角
    static let windowCornerRadius: CGFloat = 12
}