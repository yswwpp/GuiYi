# guiyi-client 模块说明

Swift 前端应用，负责用户交互、快捷键、状态栏集成。

## 核心职责

1. **全局快捷键**：Cmd+Shift+S 唤醒悬浮窗
2. **悬浮窗 UI**：类似 Alfred 的简洁界面
3. **状态栏集成**：常驻状态栏，显示服务状态
4. **API 调用**：与后端服务通信

## 架构设计

### SwiftUI 视图层次

```
GuiYiApp (应用入口)
├── ContentView (主视图 - 悬浮窗)
│   ├── URLInputField
│   ├── StatusIndicator
│   └── SaveButton
└── SettingsView (设置视图)
    ├── DataSourceConfig
    └── ShortcutConfig
```

### 状态管理

- `@State`：视图内部状态（输入框内容、加载状态）
- `@ObservedObject`：共享状态（服务连接状态）

### API 客户端

使用 URLSession 调用后端 API：

```swift
class APIClient {
    static let baseURL = "http://localhost:8765"

    static func save(url: String) async throws {
        let request = URLRequest(url: URL(string: "\(baseURL)/api/save")!)
        let (_, response) = try await URLSession.shared.data(for: request)
        // 处理响应
    }
}
```

## 开发注意事项

### 实现顺序

按照技术文档的阶段逐步实现：

1. ✅ **第一阶段**：基础 SwiftUI 项目
2. 🚧 **第二阶段**：全局快捷键 + 悬浮窗
3. 🚧 **第三阶段**：状态栏集成
4. 🚧 **第四阶段**：设置界面
5. 🚧 **第五阶段**：优化和完善

> ⚠️ **重要**：先实现核心 UI 和交互，再添加高级功能。

### SwiftUI 最佳实践

1. **视图职责单一**：每个视图只负责一件事
   ```swift
   struct URLInputField: View {
       @Binding var url: String
       var body: some View {
           TextField("粘贴链接...", text: $url)
       }
   }
   ```

2. **异步操作**：使用 `async/await`
   ```swift
   Task {
       do {
           try await APIClient.save(url: url)
           showSuccess = true
       } catch {
           showError = true
       }
   }
   ```

3. **内存管理**：避免循环引用
   ```swift
   class ViewModel: ObservableObject {
       weak var delegate: ViewModelDelegate?
   }
   ```

### 快捷键管理

使用 HotKey 库：

```swift
import HotKey

class HotKeyManager {
    let hotKey = HotKey(key: .s, modifiers: [.command, .shift])

    init() {
        hotKey.keyDownHandler = {
            // 显示悬浮窗
            NSApp.activate(ignoringOtherApps: true)
        }
    }
}
```

### 剪贴板访问

```swift
let pasteboard = NSPasteboard.general
if let url = pasteboard.string(forType: .URL) {
    // 自动填充 URL
}
```

### 通知和反馈

```swift
import UserNotifications

func showNotification(title: String, body: String) {
    let content = UNMutableNotificationContent()
    content.title = title
    content.body = body

    let request = UNNotificationRequest(
        identifier: UUID().uuidString,
        content: content,
        trigger: nil
    )

    UNUserNotificationCenter.current().add(request)
}
```

## 测试

### 单元测试

在 Xcode 中：
- `Cmd + U` 运行测试

### UI 测试

使用 XCUITest 框架。

## 发布配置

### App Sandbox

如果需要访问网络，配置 App Sandbox：
- 在 Xcode 项目设置中启用 Outgoing Connections

### 应用签名

对于分发，需要：
1. Apple Developer 账号
2. 配置证书和 Provisioning Profile
3. 启用 Hardened Runtime

## 相关文档

- [技术方案](../../docs/归一GuiYi-需求与技术方案.md)
- [UI 设计稿](../../docs/ui-design.md)
