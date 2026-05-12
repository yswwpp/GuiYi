//
//  HotKeyManager.swift
//  GuiYi
//
//  全局快捷键管理器
//

import SwiftUI
import Carbon

class HotKeyManager {
    static let shared = HotKeyManager()

    private var eventHandler: EventHandlerRef?
    private var hotKeyRef: EventHotKeyRef?
    private var callback: (() -> Void)?

    private init() {}

    /// 注册全局快捷键
    func registerHotKey(modifierFlags: NSEvent.ModifierFlags, keyCode: UInt16, callback: @escaping () -> Void) {
        self.callback = callback

        // 检查辅助功能权限
        let accessEnabled = AXIsProcessTrusted()

        if !accessEnabled {
            print("⚠️ 需要辅助功能权限才能使用全局快捷键")
            print("请在系统偏好设置 → 安全性与隐私 → 隐私 → 辅助功能中授权")
            return
        }

        // 注册全局事件监听
        NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            // 检查修饰键（只按 Cmd，不按其他键）
            let isOnlyCommand = event.modifierFlags.rawValue == NSEvent.ModifierFlags.command.rawValue

            // 检查按键（J = 38）
            if isOnlyCommand && event.keyCode == keyCode {
                print("✓ 检测到快捷键: Cmd+J")
                self?.callback?()
            }
        }

        print("✓ 全局快捷键已注册: Cmd+J")
    }

    /// 注册默认快捷键 Cmd+J
    func registerDefaultHotKey(callback: @escaping () -> Void) {
        // J 键的 keyCode 是 38
        registerHotKey(modifierFlags: .command, keyCode: 38, callback: callback)
    }

    /// 检查辅助功能权限
    static func checkAccessibilityPermission() -> Bool {
        return AXIsProcessTrusted()
    }

    deinit {
        if let handler = eventHandler {
            RemoveEventHandler(handler)
        }
        if let hotKey = hotKeyRef {
            UnregisterEventHotKey(hotKey)
        }
    }
}
