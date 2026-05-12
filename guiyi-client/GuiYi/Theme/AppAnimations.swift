//
//  AppAnimations.swift
//  GuiYi
//
//  GuiYi 动画系统 - 定义标准动画曲线和时长
//

import SwiftUI

/// GuiYi 动画系统
struct AppAnimations {

    // MARK: - 动画时长

    /// 快速动画 (hover, click feedback) - 0.12s
    static let fast: Double = 0.12

    /// 标准动画 (展开, 滚动) - 0.25s
    static let standard: Double = 0.25

    /// 慢速动画 (大元素变化) - 0.35s
    static let slow: Double = 0.35

    // MARK: - 预定义动画

    /// 默认曲线 - easeInOut
    static let defaultAnimation = Animation.easeInOut(duration: standard)

    /// 快速反馈 - easeOut
    static let fastFeedback = Animation.easeOut(duration: fast)

    /// 弹性动画 - spring (用于大元素变化)
    static let springAnimation = Animation.spring(
        response: 0.3,
        dampingFraction: 0.7,
        blendDuration: 0.1
    )

    /// 平滑过渡 - timingCurve (类似 CSS ease)
    static let smoothTransition = Animation.timingCurve(
        0.4, 0.0, 0.2, 1.0,
        duration: standard
    )
}

// MARK: - Animation 扩展

extension Animation {

    /// Raycast 风格快速响应动画
    static var raycastFast: Animation {
        .easeOut(duration: 0.12)
    }

    /// 内容展开动画
    static var contentExpand: Animation {
        .spring(response: 0.25, dampingFraction: 0.8)
    }

    /// Hover 状态动画
    static var hoverEffect: Animation {
        .easeInOut(duration: 0.15)
    }

    /// 搜索结果出现动画
    static var resultAppear: Animation {
        .spring(response: 0.2, dampingFraction: 0.85)
    }
}