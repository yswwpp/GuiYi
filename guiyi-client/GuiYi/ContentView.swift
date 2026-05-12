//
//  ContentView.swift
//  GuiYi
//
//  URL 保存界面 - 毛玻璃背景 + 动画状态反馈
//

import SwiftUI

struct ContentView: View {
    @State private var urlText: String = ""
    @State private var isSaving: Bool = false
    @State private var showSuccess: Bool = false
    @State private var showError: Bool = false
    @State private var errorMessage: String = ""

    var body: some View {
        VStack(spacing: AppSpacing.lg) {
            // 标题
            Text("归一 GuiYi")
                .font(.headline)
                .foregroundColor(AppColors.textSecondary)

            // 输入框
            TextField("粘贴链接后回车...", text: $urlText)
                .textFieldStyle(.roundedBorder)
                .frame(width: 400)
                .onSubmit {
                    saveURL()
                }
                .onAppear {
                    readClipboard()
                }

            // 状态反馈 (带动画)
            statusIndicator
        }
        .padding(AppSpacing.xl)
        .frame(width: 480, height: 160)
        .glassEffect()  // 毛玻璃背景
    }

    // MARK: - 状态指示

    @ViewBuilder
    private var statusIndicator: some View {
        if isSaving {
            ProgressView()
                .scaleEffect(0.8)
                .transition(.opacity)
        }

        if showSuccess {
            HStack(spacing: AppSpacing.sm) {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(AppColors.success)
                Text("已保存到 Obsidian")
                    .font(.caption)
            }
            .transition(.scale.combined(with: .opacity))
        }

        if showError {
            HStack(spacing: AppSpacing.sm) {
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(AppColors.error)
                Text(errorMessage)
                    .font(.caption)
                    .foregroundColor(AppColors.error)
            }
            .transition(.scale.combined(with: .opacity))
        }
    }

    // MARK: - 剪贴板读取

    private func readClipboard() {
        if let clipboardString = NSPasteboard.general.string(forType: .URL) {
            urlText = clipboardString
        } else if let clipboardString = NSPasteboard.general.string(forType: .string) {
            if clipboardString.hasPrefix("http://") || clipboardString.hasPrefix("https://") {
                urlText = clipboardString
            }
        }
    }

    // MARK: - 保存逻辑

    private func saveURL() {
        guard !urlText.isEmpty else { return }

        withAnimation(.raycastFast) {
            isSaving = true
            showSuccess = false
            showError = false
        }

        Task {
            do {
                let response = try await APIClient.shared.save(url: urlText)

                await MainActor.run {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                        isSaving = false
                        showSuccess = true
                        urlText = ""
                    }

                    DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                        NSApp.terminate(nil)
                    }
                }
            } catch {
                await MainActor.run {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                        isSaving = false
                        showError = true
                        errorMessage = error.localizedDescription
                    }

                    DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                        withAnimation(.raycastFast) {
                            showError = false
                            errorMessage = ""
                        }
                    }
                }
            }
        }
    }
}

#Preview {
    ContentView()
}