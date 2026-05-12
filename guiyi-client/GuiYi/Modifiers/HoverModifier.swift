//
//  HoverModifier.swift
//  GuiYi
//
//  Hover 效果修饰符 - 为视图添加鼠标悬停时的背景高亮效果
//

import SwiftUI

/// Hover 状态修饰符
struct HoverModifier: ViewModifier {
    @State private var isHovered: Bool = false

    let hoverColor: Color
    let cornerRadius: CGFloat

    init(
        hoverColor: Color = AppColors.hoverBackground,
        cornerRadius: CGFloat = 8
    ) {
        self.hoverColor = hoverColor
        self.cornerRadius = cornerRadius
    }

    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: cornerRadius)
                    .fill(isHovered ? hoverColor : Color.clear)
            )
            .animation(.hoverEffect, value: isHovered)
            .onHover { hovering in
                isHovered = hovering
            }
    }
}

// MARK: - View 扩展

extension View {

    /// 添加 Hover 效果
    /// - Parameters:
    ///   - color: Hover 时的背景颜色
    ///   - cornerRadius: 圆角半径
    func hoverEffect(
        color: Color = AppColors.hoverBackground,
        cornerRadius: CGFloat = 8
    ) -> some View {
        modifier(HoverModifier(hoverColor: color, cornerRadius: cornerRadius))
    }

    /// 添加 Hover 效果 + 点击手势
    /// - Parameter action: 点击回调
    func hoverClickable(action: @escaping () -> Void) -> some View {
        self
            .hoverEffect()
            .contentShape(Rectangle())
            .onTapGesture(perform: action)
    }
}