//
//  SettingsView.swift
//  GuiYi
//
//  设置界面 - 优化布局
//

import SwiftUI
import UniformTypeIdentifiers

struct SettingsView: View {
    @AppStorage("obsidian_vault_path") private var obsidianVaultPath: String = ""
    @AppStorage("api_url") private var apiUrl: String = "http://127.0.0.1:8765"
    @AppStorage("auto_launch") private var autoLaunch: Bool = false
    @AppStorage("show_in_dock") private var showInDock: Bool = false

    var body: some View {
        TabView {
            GeneralSettingsView(
                autoLaunch: $autoLaunch,
                showInDock: $showInDock
            )
            .tabItem { Label("通用", systemImage: "gearshape") }

            SyncSettingsView()
                .tabItem { Label("同步", systemImage: "arrow.triangle.2.circlepath") }

            AISettingsView()
                .tabItem { Label("AI", systemImage: "brain") }

            StorageSettingsView(
                obsidianVaultPath: $obsidianVaultPath
            )
            .tabItem { Label("存储", systemImage: "externaldrive") }

            AdvancedSettingsView(
                apiUrl: $apiUrl
            )
            .tabItem { Label("高级", systemImage: "slider.horizontal.3") }
        }
        .frame(width: 560, height: 480)
        .padding(.top, 8)
    }
}

// MARK: - 通用设置

struct GeneralSettingsView: View {
    @Binding var autoLaunch: Bool
    @Binding var showInDock: Bool

    var body: some View {
        Form {
            Section("启动选项") {
                Toggle("开机自动启动", isOn: $autoLaunch)
                Toggle("在 Dock 中显示", isOn: $showInDock)
            }

            Section("快捷键") {
                HStack {
                    Text("唤醒搜索窗口")
                    Spacer()
                    Text("⌘J")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 3)
                        .background(Color.secondary.opacity(0.1))
                        .cornerRadius(4)
                }

                HStack {
                    Text("打开设置窗口")
                    Spacer()
                    Text("⌃⇧S")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 3)
                        .background(Color.secondary.opacity(0.1))
                        .cornerRadius(4)
                }
            }

            Section("关于") {
                HStack {
                    Text("版本")
                    Spacer()
                    Text("1.0.0")
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - AI 设置

struct AISettingsView: View {
    @State private var enabled = false
    @State private var apiBase = ""
    @State private var apiKey = ""
    @State private var model = ""
    @State private var summaryThreshold = 10
    @State private var maxTokens = 1000
    @State private var chunkSize = 8
    @State private var maxContent = 50
    @State private var isLoading = false
    @State private var message: String?
    @State private var showingSuccess = false
    @State private var showAdvanced = false

    // AI 搜索配置
    @State private var aiSearchEnabled = false
    @State private var keywordExtractionEnabled = true
    @State private var rerankEnabled = true
    @State private var keywordExtractorType = "ollama"
    @State private var keywordOllamaUrl = "http://localhost:11434"
    @State private var keywordOllamaModel = "qwen2.5:9b"
    @State private var rerankerType = "bge"
    @State private var rerankerBgeModel = "BAAI/bge-reranker-v2-m3"

    var body: some View {
        Form {
            // AI 总结服务配置
            Section {
                Toggle("启用 AI 总结服务", isOn: $enabled)
            }

            Section("API 配置") {
                HStack {
                    Text("API 地址")
                    Spacer()
                    TextField("", text: $apiBase)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 280)
                }

                HStack {
                    Text("API Key")
                    Spacer()
                    SecureField("", text: $apiKey)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 280)
                }

                HStack {
                    Text("模型")
                    Spacer()
                    TextField("", text: $model)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 280)
                }
            }

            Section("处理参数") {
                HStack {
                    Text("触发阈值")
                    TextField("", value: $summaryThreshold, formatter: NumberFormatter())
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 60)
                    Text("KB")
                    Spacer()
                }

                HStack {
                    Text("分段大小")
                    TextField("", value: $chunkSize, formatter: NumberFormatter())
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 60)
                    Text("KB")
                    Spacer()
                }

                HStack {
                    Text("最大内容")
                    TextField("", value: $maxContent, formatter: NumberFormatter())
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 60)
                    Text("KB")
                    Spacer()
                }
            }

            // AI 搜索增强配置（新增）
            Section("AI 搜索增强") {
                Toggle("启用 AI 搜索增强", isOn: $aiSearchEnabled)
                    .help("AI 提取关键词并智能重排搜索结果")

                if aiSearchEnabled {
                    Toggle("启用关键词提取", isOn: $keywordExtractionEnabled)
                        .help("从自然语言查询中提取关键词")

                    Toggle("启用智能重排", isOn: $rerankEnabled)
                        .help("使用 Rerank 模型优化搜索结果排序")

                    if keywordExtractionEnabled {
                        HStack {
                            Text("关键词提取器")
                            Spacer()
                            Picker("", selection: $keywordExtractorType) {
                                Text("本地 Ollama").tag("ollama")
                                Text("API 调用").tag("openai")
                            }
                            .pickerStyle(.menu)
                            .frame(width: 120)
                        }

                        if keywordExtractorType == "ollama" {
                            HStack {
                                Text("Ollama 地址")
                                Spacer()
                                TextField("", text: $keywordOllamaUrl)
                                    .textFieldStyle(.roundedBorder)
                                    .frame(width: 200)
                            }

                            HStack {
                                Text("Ollama 模型")
                                Spacer()
                                TextField("", text: $keywordOllamaModel)
                                    .textFieldStyle(.roundedBorder)
                                    .frame(width: 200)
                            }
                        }
                    }

                    if rerankEnabled {
                        HStack {
                            Text("重排模型")
                            Spacer()
                            Picker("", selection: $rerankerType) {
                                Text("本地 BGE").tag("bge")
                                Text("Cohere API").tag("cohere")
                                Text("Jina API").tag("jina")
                            }
                            .pickerStyle(.menu)
                            .frame(width: 120)
                        }

                        if rerankerType == "bge" {
                            HStack {
                                Text("BGE 模型")
                                Spacer()
                                TextField("", text: $rerankerBgeModel)
                                    .textFieldStyle(.roundedBorder)
                                    .frame(width: 280)
                            }
                        }
                    }

                    Button("测试 Rerank 连接") {
                        testRerankConnection()
                    }
                    .disabled(isLoading)
                }
            }

            Section {
                DisclosureGroup("高级设置（提示词）", isExpanded: $showAdvanced) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("提示词可在配置文件中自定义：")
                            .font(.caption)
                        Text("~/GuiYi/guiyi-server/data/ai_config.json")
                            .font(.caption)
                            .foregroundColor(.blue)
                    }
                    .padding(.vertical, 4)
                }
            }

            Section {
                HStack {
                    Spacer()
                    Button("测试连接") {
                        testConnection()
                    }
                    .disabled(isLoading)

                    Button("保存配置") {
                        saveConfig()
                    }
                    .disabled(isLoading)
                    .buttonStyle(.borderedProminent)

                    if isLoading {
                        ProgressView()
                            .scaleEffect(0.7)
                    }
                }

                if showingSuccess, let msg = message {
                    HStack {
                        Spacer()
                        Label(msg, systemImage: "checkmark.circle.fill")
                            .foregroundColor(msg.contains("失败") ? .red : .green)
                    }
                    .onAppear {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            showingSuccess = false
                        }
                    }
                }
            }
        }
        .formStyle(.grouped)
        .onAppear { loadConfig() }
    }

    private func loadConfig() {
        isLoading = true
        Task {
            do {
                let response = try await APIClient.shared.getAIConfig()
                await MainActor.run {
                    enabled = response.enabled
                    apiBase = response.apiBase
                    apiKey = response.apiKey ?? ""
                    model = response.model
                    summaryThreshold = response.summaryThresholdKb
                    maxTokens = response.maxTokens
                    chunkSize = response.chunkSizeKb
                    maxContent = response.maxContentKb
                    isLoading = false
                }

                // 加载 AI 搜索配置
                let searchConfig = try await APIClient.shared.getAISearchConfig()
                await MainActor.run {
                    aiSearchEnabled = searchConfig.aiSearchEnabled
                    keywordExtractionEnabled = searchConfig.keywordExtractionEnabled
                    rerankEnabled = searchConfig.rerankEnabled
                    keywordExtractorType = searchConfig.keywordExtractorType
                    keywordOllamaUrl = searchConfig.keywordOllamaUrl
                    keywordOllamaModel = searchConfig.keywordOllamaModel
                    rerankerType = searchConfig.rerankerType
                    rerankerBgeModel = searchConfig.rerankerBgeModel
                }
            } catch {
                await MainActor.run {
                    message = "加载配置失败: \(error.localizedDescription)"
                    showingSuccess = true
                    isLoading = false
                }
            }
        }
    }

    private func saveConfig() {
        isLoading = true
        Task {
            do {
                let cleanApiBase = apiBase.trimmingCharacters(in: .whitespacesAndNewlines)
                let cleanApiKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
                let cleanModel = model.trimmingCharacters(in: .whitespacesAndNewlines)

                _ = try await APIClient.shared.updateAIConfig(
                    enabled: enabled,
                    apiBase: cleanApiBase.isEmpty ? nil : cleanApiBase,
                    apiKey: cleanApiKey.isEmpty ? nil : cleanApiKey,
                    model: cleanModel.isEmpty ? nil : cleanModel,
                    summaryThresholdKb: summaryThreshold,
                    maxTokens: maxTokens,
                    chunkSizeKb: chunkSize,
                    maxContentKb: maxContent
                )

                // 保存 AI 搜索配置
                _ = try await APIClient.shared.updateAISearchConfig(
                    aiSearchEnabled: aiSearchEnabled,
                    keywordExtractionEnabled: keywordExtractionEnabled,
                    rerankEnabled: rerankEnabled,
                    keywordExtractorType: keywordExtractorType,
                    keywordOllamaUrl: keywordOllamaUrl,
                    keywordOllamaModel: keywordOllamaModel,
                    rerankerType: rerankerType,
                    rerankerBgeModel: rerankerBgeModel
                )

                await MainActor.run {
                    message = "配置已保存"
                    showingSuccess = true
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    message = "保存失败: \(error.localizedDescription)"
                    showingSuccess = true
                    isLoading = false
                }
            }
        }
    }

    private func testConnection() {
        isLoading = true
        Task {
            do {
                _ = try await APIClient.shared.testAIConnection(
                    apiBase: apiBase.isEmpty ? nil : apiBase,
                    apiKey: apiKey.isEmpty ? nil : apiKey,
                    model: model.isEmpty ? nil : model
                )
                await MainActor.run {
                    message = "连接成功"
                    showingSuccess = true
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    message = "连接失败: \(error.localizedDescription)"
                    showingSuccess = true
                    isLoading = false
                }
            }
        }
    }

    private func testRerankConnection() {
        isLoading = true
        Task {
            do {
                let success = try await APIClient.shared.testRerankConnection()
                await MainActor.run {
                    message = success ? "Rerank 连接成功" : "Rerank 连接失败"
                    showingSuccess = true
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    message = "Rerank 测试失败: \(error.localizedDescription)"
                    showingSuccess = true
                    isLoading = false
                }
            }
        }
    }
}

// MARK: - 同步设置

struct SyncSettingsView: View {
    @State private var syncJobs: [APIClient.SyncJob] = []
    @State private var syncStats: [String: APIClient.SourceStats] = [:]
    @State private var isLoading = false
    @State private var syncMessage: String?
    @State private var showingSuccess = false
    @State private var localDirectories: [APIClient.LocalDirectory] = []
    @State private var supportedFileTypes: [String] = []
    @State private var showingAddDirectory = false

    private let dataSources: [(id: String, name: String, icon: String, color: Color)] = [
        ("feishu", "飞书", "paperplane", Color.blue),
        ("local", "本地文件", "folder", Color.orange),
        ("yinxiang", "印象笔记", "note.text", Color.green),
        ("quark", "夸克网盘", "cloud", Color.blue)
    ]

    private let frequencyOptions: [(label: String, cron: String?)] = [
        ("每小时", "0 */1 * * *"),
        ("每 6 小时", "0 */6 * * *"),
        ("每天 9:00", "0 9 * * *"),
        ("每天 12:00", "0 12 * * *"),
        ("每天 18:00", "0 18 * * *"),
        ("每周一 8:00", "0 8 * * 1"),
        ("手动", nil)
    ]

    var body: some View {
        Form {
            Section("数据源同步") {
                ForEach(dataSources, id: \.id) { source in
                    SyncSourceRowCompact(
                        source: source,
                        stats: syncStats[source.id],
                        syncJob: syncJobs.first { $0.id == "sync_\(source.id)_default" },
                        frequencyOptions: frequencyOptions,
                        onSync: { triggerSync(source: source.id) },
                        onFrequencyChange: { cron in
                            updateSyncFrequency(source: source.id, cron: cron)
                        },
                        onAddDirectory: source.id == "local" ? { showingAddDirectory = true } : nil
                    )
                }
            }

            if !localDirectories.isEmpty {
                Section("本地目录") {
                    ForEach(localDirectories) { dir in
                        LocalDirectoryRowCompact(
                            directory: dir,
                            onToggle: { toggleDirectory(dir) },
                            onDelete: { deleteDirectory(dir) },
                            onSync: { syncLocalDirectory(dir) },
                            onUpdateExcludePaths: { paths in updateExcludePaths(dir, paths) }
                        )
                    }
                }
            }

            Section {
                HStack {
                    Button("刷新状态") {
                        loadSyncJobs()
                        loadSyncStats()
                    }

                    Spacer()

                    if showingSuccess, let msg = syncMessage {
                        Label(msg, systemImage: "checkmark.circle.fill")
                            .foregroundColor(.green)
                            .onAppear {
                                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                    showingSuccess = false
                                }
                            }
                    }
                }
            }
        }
        .formStyle(.grouped)
        .onAppear {
            loadSyncJobs()
            loadSyncStats()
            loadLocalDirectories()
            loadSupportedFileTypes()
        }
        .sheet(isPresented: $showingAddDirectory) {
            AddLocalDirectorySheet(
                supportedFileTypes: supportedFileTypes,
                onAdd: { name, path, fileTypes in
                    addLocalDirectory(name: name, path: path, fileTypes: fileTypes)
                }
            )
        }
    }

    private func loadSyncJobs() {
        isLoading = true
        Task {
            do {
                let response = try await APIClient.shared.getSyncJobs()
                await MainActor.run {
                    syncJobs = response.jobs
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    syncMessage = "连接后端失败: \(error.localizedDescription)"
                    showingSuccess = true
                    isLoading = false
                }
            }
        }
    }

    private func loadSyncStats() {
        Task {
            do {
                let response = try await APIClient.shared.getSyncStats()
                await MainActor.run { syncStats = response.sources }
            } catch {
                print("加载同步统计失败: \(error)")
            }
        }
    }

    private func loadLocalDirectories() {
        Task {
            do {
                let response = try await APIClient.shared.getLocalDirectories()
                await MainActor.run { localDirectories = response.directories }
            } catch {
                print("加载本地目录失败: \(error)")
            }
        }
    }

    private func loadSupportedFileTypes() {
        Task {
            do {
                let response = try await APIClient.shared.getSupportedFileTypes()
                await MainActor.run { supportedFileTypes = response.fileTypes }
            } catch {
                print("加载文件类型失败: \(error)")
            }
        }
    }

    private func updateSyncFrequency(source: String, cron: String?) {
        Task {
            do {
                let oldJobId = "sync_\(source)_default"
                if syncJobs.contains(where: { $0.id == oldJobId }) {
                    _ = try? await APIClient.shared.removeSyncJob(jobId: oldJobId)
                }

                if let cron = cron {
                    _ = try await APIClient.shared.addSyncJob(source: source, cronExpression: cron)
                }

                await MainActor.run {
                    syncMessage = "同步频率已更新"
                    showingSuccess = true
                    loadSyncJobs()
                }
            } catch {
                await MainActor.run {
                    syncMessage = "更新失败: \(error.localizedDescription)"
                    showingSuccess = true
                }
            }
        }
    }

    private func triggerSync(source: String) {
        Task {
            do {
                _ = try await APIClient.shared.triggerSync(source: source)
                await MainActor.run {
                    syncMessage = "同步已开始"
                    showingSuccess = true
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 10) { loadSyncStats() }
                DispatchQueue.main.asyncAfter(deadline: .now() + 30) { loadSyncStats() }
            } catch {
                await MainActor.run {
                    syncMessage = "同步失败: \(error.localizedDescription)"
                    showingSuccess = true
                }
            }
        }
    }

    private func addLocalDirectory(name: String, path: String, fileTypes: [String]) {
        Task {
            do {
                _ = try await APIClient.shared.addLocalDirectory(name: name, path: path, fileTypes: fileTypes)
                await MainActor.run {
                    syncMessage = "目录已添加"
                    showingSuccess = true
                    loadLocalDirectories()
                }
            } catch {
                await MainActor.run {
                    syncMessage = "添加失败: \(error.localizedDescription)"
                    showingSuccess = true
                }
            }
        }
    }

    private func toggleDirectory(_ dir: APIClient.LocalDirectory) {
        Task {
            do {
                _ = try await APIClient.shared.updateLocalDirectory(id: dir.id, enabled: !dir.enabled)
                await MainActor.run { loadLocalDirectories() }
            } catch {
                await MainActor.run {
                    syncMessage = "更新失败: \(error.localizedDescription)"
                    showingSuccess = true
                }
            }
        }
    }

    private func deleteDirectory(_ dir: APIClient.LocalDirectory) {
        Task {
            do {
                _ = try await APIClient.shared.deleteLocalDirectory(id: dir.id)
                await MainActor.run {
                    syncMessage = "目录已删除"
                    showingSuccess = true
                    loadLocalDirectories()
                }
            } catch {
                await MainActor.run {
                    syncMessage = "删除失败: \(error.localizedDescription)"
                    showingSuccess = true
                }
            }
        }
    }

    private func syncLocalDirectory(_ dir: APIClient.LocalDirectory) {
        Task {
            do {
                _ = try await APIClient.shared.triggerSync(source: "local", account: dir.id)
                await MainActor.run {
                    syncMessage = "同步已开始"
                    showingSuccess = true
                }
            } catch {
                await MainActor.run {
                    syncMessage = "同步失败: \(error.localizedDescription)"
                    showingSuccess = true
                }
            }
        }
    }

    private func updateExcludePaths(_ dir: APIClient.LocalDirectory, _ paths: [String]) {
        Task {
            do {
                _ = try await APIClient.shared.updateLocalDirectory(
                    id: dir.id,
                    excludePaths: paths
                )
                await MainActor.run {
                    syncMessage = "排除路径已更新"
                    showingSuccess = true
                    loadLocalDirectories()
                }
            } catch {
                await MainActor.run {
                    syncMessage = "更新失败: \(error.localizedDescription)"
                    showingSuccess = true
                }
            }
        }
    }
}

// 紧凑的同步源行视图
struct SyncSourceRowCompact: View {
    let source: (id: String, name: String, icon: String, color: Color)
    let stats: APIClient.SourceStats?
    let syncJob: APIClient.SyncJob?
    let frequencyOptions: [(label: String, cron: String?)]
    let onSync: () -> Void
    let onFrequencyChange: (String?) -> Void
    let onAddDirectory: (() -> Void)?

    @State private var selectedFrequency: String = ""

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: source.icon)
                .font(.system(size: 14))
                .foregroundColor(source.color)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 2) {
                Text(source.name)
                    .font(.system(size: 13, weight: .medium))

                if let stats = stats, stats.count > 0 {
                    HStack(spacing: 4) {
                        Text("\(stats.count) 条索引")
                            .font(.caption)
                        if let lastSync = stats.lastSync {
                            Text("• \(formatTime(lastSync))")
                                .font(.caption)
                        }
                    }
                    .foregroundColor(.secondary)
                }
            }

            Spacer()

            Menu {
                ForEach(frequencyOptions, id: \.label) { option in
                    Button(option.label) {
                        selectedFrequency = option.label
                        onFrequencyChange(option.cron)
                    }
                }
            } label: {
                Text(currentFrequencyLabel)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.secondary.opacity(0.1))
                    .cornerRadius(4)
            }
            .fixedSize()

            if let onAdd = onAddDirectory {
                Button("添加", action: onAdd)
                    .buttonStyle(.bordered)
                    .controlSize(.small)
            }

            Button("同步", action: onSync)
                .buttonStyle(.bordered)
                .controlSize(.small)
        }
        .padding(.vertical, 4)
    }

    private var currentFrequencyLabel: String {
        guard let job = syncJob else { return "手动" }
        return parseCronToLabel(job.trigger)
    }

    private func parseCronToLabel(_ trigger: String) -> String {
        let t = trigger.lowercased()

        func extractValue(_ name: String) -> String? {
            let pattern = "\(name)='([^']+)'"
            if let range = t.range(of: pattern, options: .regularExpression) {
                let match = String(t[range])
                if let valueRange = match.range(of: "'(.+)'", options: .regularExpression) {
                    return String(match[valueRange].dropFirst().dropLast())
                }
            }
            return nil
        }

        let hour = extractValue("hour") ?? "9"
        let dayOfWeek = extractValue("day_of_week") ?? "*"

        if dayOfWeek == "1" { return "每周一" }
        return "每天 \(hour):00"
    }

    private func formatTime(_ timestamp: Double) -> String {
        let date = Date(timeIntervalSince1970: timestamp)
        let formatter = DateFormatter()
        formatter.dateFormat = "MM-dd HH:mm"
        return formatter.string(from: date)
    }
}

// 紧凑的本地目录行
struct LocalDirectoryRowCompact: View {
    let directory: APIClient.LocalDirectory
    let onToggle: () -> Void
    let onDelete: () -> Void
    let onSync: () -> Void
    let onUpdateExcludePaths: ([String]) -> Void

    @State private var showingExcludeEditor = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Toggle("", isOn: Binding(
                    get: { directory.enabled },
                    set: { _ in onToggle() }
                ))
                .labelsHidden()

                VStack(alignment: .leading, spacing: 2) {
                    Text(directory.name)
                        .font(.system(size: 12, weight: .medium))
                    Text(directory.path)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .help(directory.path)
                }

                Spacer()

                if let count = directory.fileCount {
                    Text("\(count) 文件")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Button {
                    showingExcludeEditor = true
                } label: {
                    Image(systemName: "folder.badge.minus")
                        .font(.system(size: 10))
                }
                .buttonStyle(.plain)
                .foregroundColor(.orange)
                .help("排除子目录")

                Button("同步", action: onSync)
                    .buttonStyle(.bordered)
                    .controlSize(.mini)

                Button(role: .destructive, action: onDelete) {
                    Image(systemName: "trash")
                        .font(.system(size: 10))
                }
                .buttonStyle(.plain)
                .foregroundColor(.red)
            }

            if !directory.excludePaths.isEmpty {
                HStack(spacing: 4) {
                    Image(systemName: "minus.circle")
                        .font(.system(size: 9))
                        .foregroundColor(.orange)
                    ForEach(directory.excludePaths, id: \.self) { path in
                        Text(path)
                            .font(.system(size: 9))
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(Color.orange.opacity(0.1))
                            .cornerRadius(3)
                    }
                }
                .padding(.leading, 36)
            }
        }
        .padding(.vertical, 2)
        .sheet(isPresented: $showingExcludeEditor) {
            ExcludePathsEditor(
                excludePaths: directory.excludePaths,
                onSave: { paths in
                    onUpdateExcludePaths(paths)
                    showingExcludeEditor = false
                }
            )
        }
    }
}

// 排除子目录编辑器
struct ExcludePathsEditor: View {
    let excludePaths: [String]
    let onSave: ([String]) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var paths: [String] = []
    @State private var newPath = ""

    var body: some View {
        VStack(spacing: 16) {
            Text("排除子目录")
                .font(.headline)

            Text("输入相对于目录根的路径，如：武汉农村电子商务有限公司项目/tools")
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            List {
                ForEach(paths, id: \.self) { path in
                    HStack {
                        Text(path)
                            .font(.system(size: 12))
                        Spacer()
                        Button {
                            paths.removeAll { $0 == path }
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                                .font(.system(size: 11))
                                .foregroundColor(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                }

                HStack {
                    TextField("相对路径", text: $newPath)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(size: 12))
                    Button("添加") {
                        let trimmed = newPath.trimmingCharacters(in: .whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                        if !trimmed.isEmpty && !paths.contains(trimmed) {
                            paths.append(trimmed)
                        }
                        newPath = ""
                    }
                    .disabled(newPath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .frame(minHeight: 120)

            HStack {
                Button("取消") { dismiss() }
                Spacer()
                Button("保存") {
                    onSave(paths)
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
        .frame(width: 420, height: 320)
        .onAppear { paths = excludePaths }
    }
}

// 添加本地目录表单
struct AddLocalDirectorySheet: View {
    let supportedFileTypes: [String]
    let onAdd: (String, String, [String]) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var path = ""
    @State private var selectedFileTypes: Set<String> = []
    @State private var showFilePicker = false

    private var commonFileTypes: [String] {
        [".md", ".txt", ".py", ".js", ".ts", ".java", ".go", ".json", ".yaml", ".yml"]
    }

    var body: some View {
        VStack(spacing: 20) {
            Text("添加本地目录")
                .font(.headline)

            Form {
                Section("目录信息") {
                    TextField("名称", text: $name)

                    HStack {
                        TextField("路径", text: $path)
                        Button("选择...") { showFilePicker = true }
                    }
                }

                Section("文件类型") {
                    ScrollView {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 60))], spacing: 6) {
                            ForEach(commonFileTypes, id: \.self) { type in
                                FileTypeChip(
                                    type: type,
                                    isSelected: selectedFileTypes.contains(type),
                                    onTap: {
                                        if selectedFileTypes.contains(type) {
                                            selectedFileTypes.remove(type)
                                        } else {
                                            selectedFileTypes.insert(type)
                                        }
                                    }
                                )
                            }
                        }
                    }
                    .frame(maxHeight: 120)
                }
            }
            .formStyle(.grouped)

            HStack {
                Button("取消") { dismiss() }

                Spacer()

                Button("添加") {
                    let types = selectedFileTypes.isEmpty ? Array(commonFileTypes) : Array(selectedFileTypes)
                    onAdd(name, path, types)
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.isEmpty || path.isEmpty)
            }
        }
        .padding()
        .frame(width: 400, height: 350)
        .fileImporter(isPresented: $showFilePicker, allowedContentTypes: [.folder], allowsMultipleSelection: false) { result in
            if case .success(let urls) = result, let url = urls.first {
                path = url.path
                if name.isEmpty { name = url.lastPathComponent }
            }
        }
        .onAppear { selectedFileTypes = Set(commonFileTypes) }
    }
}

// 文件类型选择芯片
struct FileTypeChip: View {
    let type: String
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Text(type)
            .font(.caption)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(isSelected ? Color.accentColor : Color.secondary.opacity(0.1))
            .foregroundColor(isSelected ? .white : .primary)
            .cornerRadius(4)
            .onTapGesture(perform: onTap)
    }
}

// MARK: - 存储设置

struct StorageSettingsView: View {
    @Binding var obsidianVaultPath: String
    @State private var showFilePicker = false

    var body: some View {
        Form {
            Section("Obsidian 库路径") {
                HStack {
                    TextField("选择 Obsidian 库路径", text: $obsidianVaultPath)
                        .disabled(true)
                    Button("选择...") { showFilePicker = true }
                }

                Text("网页内容将保存到该路径下的 inbox 目录")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Section("存储统计") {
                HStack {
                    Text("已保存文件")
                    Spacer()
                    Text("-- 个")
                        .foregroundColor(.secondary)
                }
                HStack {
                    Text("存储大小")
                    Spacer()
                    Text("-- MB")
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
        .fileImporter(isPresented: $showFilePicker, allowedContentTypes: [.folder], allowsMultipleSelection: false) { result in
            if case .success(let urls) = result, let url = urls.first {
                obsidianVaultPath = url.path
            }
        }
    }
}

// MARK: - 高级设置

struct AdvancedSettingsView: View {
    @Binding var apiUrl: String

    var body: some View {
        Form {
            Section("API 设置") {
                HStack {
                    Text("API 地址")
                    Spacer()
                    TextField("", text: $apiUrl)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 200)
                }

                Button("测试连接") {
                    testConnection()
                }
            }

            Section("调试信息") {
                HStack {
                    Text("应用版本")
                    Spacer()
                    Text("1.0.0")
                        .foregroundColor(.secondary)
                }

                HStack {
                    Text("后端状态")
                    Spacer()
                    Text("--")
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }

    private func testConnection() {
        Task {
            do {
                let status = try await APIClient.shared.getStatus()
                print("✓ 连接成功: \(status.status)")
            } catch {
                print("✗ 连接失败: \(error)")
            }
        }
    }
}

#Preview {
    SettingsView()
}