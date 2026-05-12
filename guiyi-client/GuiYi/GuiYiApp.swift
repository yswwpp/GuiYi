//
//  GuiYiApp.swift
//  GuiYi
//

import SwiftUI

@main
struct GuiYiApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        // 状态栏应用不需要主窗口
        Settings {
            EmptyView()
        }
    }
}
