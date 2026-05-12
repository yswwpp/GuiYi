//
//  GlassEffectModifier.swift
//  GuiYi
//
//  毛玻璃效果修饰符 - 使用 NSVisualEffectView 实现原生毛玻璃背景
//

import SwiftUI

/// 毛玻璃效果修饰符
struct GlassEffectModifier: ViewModifier {
    let material: NSVisualEffectView.Material
    let blendingMode: NSVisualEffectView.BlendingMode

    init(
        material: NSVisualEffectView.Material = .hudWindow,
        blendingMode: NSVisualEffectView.BlendingMode = .behindWindow
    ) {
        self.material = material
        self.blendingMode = blendingMode
    }

    func body(content: Content) -> some View {
        content
            .background(
                VisualEffectView(
                    material: material,
                    blendingMode: blendingMode
                )
            )
    }
}

/// NSVisualEffectView 的 SwiftUI 包装
struct VisualEffectView: NSViewRepresentable {
    let material: NSVisualEffectView.Material
    let blendingMode: NSVisualEffectView.BlendingMode

    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = blendingMode
        view.state = .active
        return view
    }

    func updateNSView(_ nsView: NSVisualEffectView, context: Context) {
        nsView.material = material
        nsView.blendingMode = blendingMode
    }
}

// MARK: - View 扩展

extension View {

    /// 添加毛玻璃效果
    /// - Parameters:
    ///   - material: 材质类型 (默认 .hudWindow)
    ///   - blendingMode: 混合模式 (默认 .behindWindow)
    func glassEffect(
        material: NSVisualEffectView.Material = .hudWindow,
        blendingMode: NSVisualEffectView.BlendingMode = .behindWindow
    ) -> some View {
        modifier(GlassEffectModifier(material: material, blendingMode: blendingMode))
    }
}