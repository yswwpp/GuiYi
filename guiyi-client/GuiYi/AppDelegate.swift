//
//  AppDelegate.swift
//  GuiYi
//
//  应用代理 - 管理状态栏和全局事件
//

import SwiftUI
import Carbon

// 自定义窗口类 - 让 borderless 窗口能接收键盘输入
class SearchWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var statusItem: NSStatusItem?
    var hotKeyMonitor: Any?
    var localHotKeyMonitor: Any?
    var searchWindow: NSWindow?
    var settingsWindow: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        createStatusBarItem()
        NSApp.setActivationPolicy(.accessory)
        registerGlobalHotKey()
    }

    func registerGlobalHotKey() {
        let accessEnabled = AXIsProcessTrusted()

        if !accessEnabled {
            print("⚠️ 需要辅助功能权限")
            let options = [kAXTrustedCheckOptionPrompt.takeRetainedValue(): true] as CFDictionary
            AXIsProcessTrustedWithOptions(options)
        }

        // 全局快捷键监听
        hotKeyMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if self?.isCmdJ(event) == true {
                DispatchQueue.main.async { self?.toggleSearchWindow() }
            } else if self?.isCtrlShiftS(event) == true {
                DispatchQueue.main.async { self?.showSettings() }
            }
        }

        // 本地快捷键监听
        localHotKeyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if self?.isCmdJ(event) == true {
                DispatchQueue.main.async { self?.toggleSearchWindow() }
                return nil
            } else if self?.isCtrlShiftS(event) == true {
                DispatchQueue.main.async { self?.showSettings() }
                return nil
            }
            return event
        }
    }

    private func isCmdJ(_ event: NSEvent) -> Bool {
        event.modifierFlags.contains(.command) &&
        !event.modifierFlags.contains(.shift) &&
        !event.modifierFlags.contains(.option) &&
        !event.modifierFlags.contains(.control) &&
        event.keyCode == 38  // J 键的 keyCode
    }

    private func isCtrlShiftS(_ event: NSEvent) -> Bool {
        event.modifierFlags.contains(.control) &&
        event.modifierFlags.contains(.shift) &&
        !event.modifierFlags.contains(.command) &&
        !event.modifierFlags.contains(.option) &&
        event.keyCode == 1  // S 键的 keyCode
    }

    @objc func toggleSearchWindow() {
        if searchWindow != nil {
            searchWindow?.close()
        } else {
            showSearchWindow()
        }
    }

    func createStatusBarItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem?.button {
            button.image = NSImage(systemSymbolName: "magnifyingglass", accessibilityDescription: "GuiYi")
            button.image?.isTemplate = true
        }
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "搜索 (Cmd+J)", action: #selector(toggleSearchWindow), keyEquivalent: "j"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "设置 (Ctrl+Shift+S)...", action: #selector(showSettings), keyEquivalent: ","))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "退出", action: #selector(quitApp), keyEquivalent: "q"))
        statusItem?.menu = menu
    }

    @objc func showSettings() {
        // 如果设置窗口已存在，直接显示
        if let window = settingsWindow {
            NSApp.activate(ignoringOtherApps: true)
            window.makeKeyAndOrderFront(nil)
            return
        }

        let settingsView = SettingsView()
        let hostingController = NSHostingController(rootView: settingsView)

        let window = NSWindow(contentViewController: hostingController)
        window.styleMask = [.titled, .closable]
        window.title = "GuiYi 设置"

        // 设置窗口使用正常背景，不透明
        window.isOpaque = true
        window.backgroundColor = NSColor.windowBackgroundColor
        window.hasShadow = true

        window.setContentSize(NSSize(width: AppSpacing.settingsWindowWidth, height: AppSpacing.settingsWindowHeight))
        window.center()
        window.level = .normal
        window.delegate = self

        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)

        settingsWindow = window
    }

    @objc func quitApp() {
        NSApp.terminate(nil)
    }

    func showSearchWindow() {
        let searchView = SearchView()
        let hostingController = NSHostingController(rootView: searchView)

        // 使用自定义窗口类，让 borderless 窗口能接收键盘输入
        let window = SearchWindow(contentViewController: hostingController)

        // Spotlight 风格：完全无边框，无标题栏按钮
        window.styleMask = [.borderless]
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden

        // 隐藏所有标题栏按钮
        window.standardWindowButton(.closeButton)?.isHidden = true
        window.standardWindowButton(.miniaturizeButton)?.isHidden = true
        window.standardWindowButton(.zoomButton)?.isHidden = true

        // 毛玻璃背景 + 圆角
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = true

        // 设置窗口圆角
        window.contentView?.wantsLayer = true
        window.contentView?.layer?.cornerRadius = 12
        window.contentView?.layer?.masksToBounds = true

        window.setContentSize(NSSize(width: 680, height: 52))
        window.center()
        window.level = .floating
        window.delegate = self

        NSApp.activate(ignoringOtherApps: true)
        window.makeKeyAndOrderFront(nil)

        searchWindow = window
    }

    // MARK: - NSWindowDelegate

    func windowWillClose(_ notification: Notification) {
        if (notification.object as? NSWindow) == searchWindow {
            searchWindow = nil
        } else if (notification.object as? NSWindow) == settingsWindow {
            settingsWindow = nil
        }
    }

    func windowDidResignKey(_ notification: Notification) {
        // 失去焦点时关闭窗口（仅搜索窗口）
        if let window = notification.object as? NSWindow, window == searchWindow {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                if NSApp.keyWindow == nil || NSApp.keyWindow == window {
                    window.close()
                }
            }
        }
    }
}
