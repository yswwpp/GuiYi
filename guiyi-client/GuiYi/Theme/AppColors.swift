//
//  AppColors.swift
//  GuiYi
//
//  GuiYi 颜色系统 - 集中管理所有颜色，支持深色/浅色模式
//

import SwiftUI

/// GuiYi 颜色系统
struct AppColors {

    // MARK: - 品牌颜色

    /// 主品牌色 - 紫蓝渐变感 (类似 Raycast)
    static let brandPrimary = Color(hex: "6366F1")  // Indigo

    /// 品牌次要色
    static let brandSecondary = Color(hex: "8B5CF6")  // Violet

    /// 品牌强调色
    static let brandAccent = Color(hex: "EC4899")  // Pink

    // MARK: - 背景颜色

    /// 搜索窗口背景 (支持毛玻璃)
    static let searchBackground = Color.clear

    /// 设置窗口背景
    static let settingsBackground = Color(NSColor.windowBackgroundColor)

    /// 卡片背景
    static let cardBackground = Color.white.opacity(0.08)

    /// Hover 状态背景
    static let hoverBackground = Color.white.opacity(0.12)

    /// 深色模式 Hover 背景
    static let hoverBackgroundDark = Color.white.opacity(0.08)

    // MARK: - 文字颜色

    /// 主文字
    static let textPrimary = Color.primary

    /// 次要文字
    static let textSecondary = Color.secondary

    /// 弱化文字
    static let textTertiary = Color.gray

    // MARK: - 状态颜色

    static let success = Color(hex: "22C55E")  // Green
    static let warning = Color(hex: "F59E0B")  // Amber
    static let error = Color(hex: "EF4444")    // Red
    static let info = Color(hex: "3B82F6")     // Blue

    // MARK: - 数据源颜色

    /// 飞书 - 官方蓝 #3370FF
    static let sourceFeishu = Color(hex: "3370FF")

    /// 本地文件 - 橙色
    static let sourceLocal = Color(hex: "F97316")

    /// 网页 - 绿色
    static let sourceWeb = Color(hex: "22C55E")

    /// 印象笔记 - 官方绿 #009933
    static let sourceYinxiang = Color(hex: "009933")

    /// 夸克网盘 - 蓝色
    static let sourceQuark = Color(hex: "3399FF")

    /// 默认/未知
    static let sourceDefault = Color.gray

    // MARK: - 辅助方法

    /// 根据数据源类型返回颜色
    static func colorForSource(_ source: String?) -> Color {
        switch source {
        case "feishu": return sourceFeishu
        case "local": return sourceLocal
        case "web": return sourceWeb
        case "yinxiang": return sourceYinxiang
        case "quark": return sourceQuark
        default: return sourceDefault
        }
    }

    /// 根据数据源类型返回图标名称
    static func iconForSource(_ source: String?) -> String {
        switch source {
        case "feishu": return "paperplane.fill"
        case "local": return "folder.fill"
        case "web": return "globe"
        case "yinxiang": return "note.text"
        case "quark": return "cloud.fill"
        default: return "doc.text"
        }
    }
}

// MARK: - Color 扩展: 支持 Hex 初始化

extension Color {
    /// 从 Hex 字符串创建颜色
    /// 支持 3位、6位、8位格式
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}