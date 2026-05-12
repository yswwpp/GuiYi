//
//  SourceIconModifier.swift
//  GuiYi
//
//  数据源图标修饰符 - 统一的数据源图标显示样式
//

import SwiftUI

/// 数据源图标修饰符
struct SourceIconModifier: ViewModifier {
    let source: String?
    let size: CGFloat

    init(source: String?, size: CGFloat = AppSpacing.sourceIconSize) {
        self.source = source
        self.size = size
    }

    func body(content: Content) -> some View {
        ZStack {
            // 背景圆形
            Circle()
                .fill(AppColors.colorForSource(source))
                .frame(width: size, height: size)

            // 图标内容
            if source == "feishu" {
                // 飞书使用自定义 Logo
                FeishuLogo()
                    .fill(Color.white)
                    .frame(width: size * 0.65, height: size * 0.65)
            } else if source == "yinxiang" {
                // 印象笔记使用大象 Logo
                YinxiangLogo()
                    .fill(Color.white)
                    .frame(width: size * 0.65, height: size * 0.65)
            } else {
                // 其他使用 SF Symbols
                Image(systemName: AppColors.iconForSource(source))
                    .font(.system(size: size * 0.5, weight: .medium))
                    .foregroundColor(.white)
            }
        }
    }
}

// MARK: - View 扩展

extension View {
    /// 数据源图标样式
    func sourceIconStyle(for source: String?, size: CGFloat = AppSpacing.sourceIconSize) -> some View {
        modifier(SourceIconModifier(source: source, size: size))
    }
}

// MARK: - 独立的数据源图标组件

/// 数据源图标组件
struct SourceIcon: View {
    let source: String?
    let size: CGFloat

    init(source: String?, size: CGFloat = AppSpacing.sourceIconSize) {
        self.source = source
        self.size = size
    }

    var body: some View {
        ZStack {
            Circle()
                .fill(AppColors.colorForSource(source))
                .frame(width: size, height: size)

            if source == "feishu" {
                FeishuLogo()
                    .fill(Color.white)
                    .frame(width: size * 0.65, height: size * 0.65)
            } else if source == "yinxiang" {
                YinxiangLogo()
                    .fill(Color.white)
                    .frame(width: size * 0.65, height: size * 0.65)
            } else {
                Image(systemName: AppColors.iconForSource(source))
                    .font(.system(size: size * 0.5, weight: .medium))
                    .foregroundColor(.white)
            }
        }
    }
}