//
//  SearchView.swift
//  GuiYi
//
//  搜索界面 - 模仿 macOS Spotlight 圆角设计 + AI 增强功能
//

import SwiftUI

struct SearchView: View {
    @State private var searchText: String = ""
    @State private var searchResults: [APIClient.AISearchResult] = []
    @State private var isSearching: Bool = false
    @State private var errorMessage: String = ""
    @State private var searchTask: Task<Void, Never>?
    @State private var showResults: Bool = false

    // AI 增强状态 - 两个独立开关
    @AppStorage("keyword_extraction_enabled") private var keywordExtractionEnabled: Bool = false
    @AppStorage("rerank_enabled") private var rerankEnabled: Bool = false
    @State private var searchPhase: SearchPhase = .idle
    @State private var keywordsExtracted: [String] = []
    @State private var processingTime: Double = 0
    @State private var rerankUsed: Bool = false

    // 已完成搜索的快照（用于反馈提交，避免与用户实时输入混淆）
    @State private var lastCompletedQuery: String = ""
    @State private var lastCompletedResults: [APIClient.AISearchResult] = []
    @State private var lastSearchMode: String = "normal"        // "normal" / "ai"
    @State private var lastKeywordExtractionEnabled: Bool = false
    @State private var lastRerankEnabled: Bool = false
    @State private var lastAIEnhanced: Bool = false
    @State private var lastKeywordsExtracted: [String] = []
    @State private var lastProcessingTime: Double = 0
    @State private var lastRerankUsed: Bool = false

    // 反馈页面状态
    @State private var showFeedbackSheet: Bool = false
    @State private var showFeedbackToast: Bool = false
    @State private var feedbackToastMessage: String = ""

    // 计算属性：是否有任何 AI 功能开启
    private var aiEnabled: Bool {
        keywordExtractionEnabled || rerankEnabled
    }

    enum SearchPhase {
        case idle
        case extractingKeywords
        case vectorSearching
        case reranking
        case completed
    }

    var body: some View {
        VStack(spacing: 0) {
            // 搜索框区域 - Spotlight 风格
            searchBar
                .padding(.top, 8)
                .background(Color(NSColor.controlBackgroundColor).opacity(0.5))  // 搜索框区域背景

            // AI 增强状态指示
            if aiEnabled && searchPhase != .idle {
                searchPhaseIndicator
                    .background(Color(NSColor.controlBackgroundColor).opacity(0.5))
            }

            // 结果区域 (带动画过渡)
            if showResults {
                Divider()
                    .padding(.horizontal, 16)

                resultsContainer
                    .transition(.opacity.combined(with: .move(edge: .top)))

                // 反馈入口（搜索完成且有结果时显示）
                if !isSearching && !searchResults.isEmpty {
                    feedbackEntryBar
                }
            }
        }
        .frame(width: 680)
        .fixedSize(horizontal: false, vertical: true)
        .glassEffect(material: .popover)  // popover 比 hudWindow 更不透明
        .sheet(isPresented: $showFeedbackSheet) {
            SearchFeedbackView(
                query: lastCompletedQuery,
                resultCount: lastCompletedResults.count,
                onSubmit: { rating, reasonCode, reasonText, expectedResult in
                    await submitFeedback(
                        rating: rating,
                        reasonCode: reasonCode,
                        reasonText: reasonText,
                        expectedResult: expectedResult
                    )
                },
                onCancel: {
                    showFeedbackSheet = false
                }
            )
        }
        .overlay(alignment: .bottom) {
            if showFeedbackToast {
                Text(feedbackToastMessage)
                    .font(.system(size: 12))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(
                        RoundedRectangle(cornerRadius: 6)
                            .fill(Color.black.opacity(0.75))
                    )
                    .foregroundColor(.white)
                    .padding(.bottom, 12)
                    .transition(.opacity)
            }
        }
    }

    // MARK: - 搜索框 - Spotlight 风格圆角输入框

    private var searchBar: some View {
        HStack(spacing: 12) {
            // 搜索图标
            Image(systemName: "magnifyingglass")
                .font(.system(size: 20, weight: .medium))
                .foregroundColor(AppColors.textSecondary)

            // 输入框 - 无边框，直接输入
            TextField("搜索知识库...", text: $searchText)
                .textFieldStyle(.plain)
                .font(.system(size: 18))
                .onChange(of: searchText) { _, newValue in
                    handleSearchChange(newValue)
                }

            // AI 增强开关按钮
            aiEnhanceToggle

            // 状态指示
            searchBarStatus
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
    }

    // MARK: - AI 增强开关 - 两个独立开关

    @ViewBuilder
    private var aiEnhanceToggle: some View {
        HStack(spacing: 4) {
            // 关键词提取开关
            Button {
                keywordExtractionEnabled.toggle()
            } label: {
                HStack(spacing: 3) {
                    Image(systemName: "tag.fill")
                        .font(.system(size: 12))
                    Text("关键词")
                        .font(.system(size: 11))
                }
                .foregroundColor(keywordExtractionEnabled ? AppColors.brandAccent : AppColors.textTertiary)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(
                    RoundedRectangle(cornerRadius: 4)
                        .fill(keywordExtractionEnabled ? AppColors.brandAccent.opacity(0.15) : Color.clear)
                )
            }
            .buttonStyle(.plain)
            .help(keywordExtractionEnabled ? "关键词提取已开启" : "点击开启关键词提取")

            // Rerank 开关
            Button {
                rerankEnabled.toggle()
            } label: {
                HStack(spacing: 3) {
                    Image(systemName: "arrow.up.arrow.down")
                        .font(.system(size: 12))
                    Text("重排")
                        .font(.system(size: 11))
                }
                .foregroundColor(rerankEnabled ? AppColors.brandAccent : AppColors.textTertiary)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(
                    RoundedRectangle(cornerRadius: 4)
                        .fill(rerankEnabled ? AppColors.brandAccent.opacity(0.15) : Color.clear)
                )
            }
            .buttonStyle(.plain)
            .help(rerankEnabled ? "智能重排已开启" : "点击开启智能重排")
        }
    }

    // MARK: - 搜索状态

    @ViewBuilder
    private var searchBarStatus: some View {
        if isSearching {
            ProgressView()
                .scaleEffect(0.8)
                .frame(width: 20, height: 20)
        } else if !searchText.isEmpty {
            Button {
                withAnimation(.easeOut(duration: 0.15)) {
                    searchText = ""
                    searchResults = []
                    showResults = false
                    searchPhase = .idle
                }
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 16))
                    .foregroundColor(AppColors.textTertiary)
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: - 搜索阶段指示器

    @ViewBuilder
    private var searchPhaseIndicator: some View {
        HStack(spacing: 8) {
            // 阶段指示器
            phaseIndicator(phase: .extractingKeywords, label: "提取关键词")
            phaseIndicator(phase: .vectorSearching, label: "向量搜索")
            phaseIndicator(phase: .reranking, label: "智能重排")

            Spacer()

            // 处理时间
            if searchPhase == .completed {
                Text("\(Int(processingTime))ms")
                    .font(.caption)
                    .foregroundColor(AppColors.textTertiary)
            }

            // 关键词显示
            if !keywordsExtracted.isEmpty {
                HStack(spacing: 4) {
                    ForEach(keywordsExtracted, id: \.self) { keyword in
                        Text(keyword)
                            .font(.caption2)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 2)
                            .background(AppColors.brandAccent.opacity(0.1))
                            .cornerRadius(3)
                    }
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 6)
    }

    private func phaseIndicator(phase: SearchPhase, label: String) -> some View {
        HStack(spacing: 4) {
            if searchPhase == phase {
                ProgressView()
                    .scaleEffect(0.5)
                    .frame(width: 10, height: 10)
            } else if isPhaseCompleted(phase: phase) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 8))
                    .foregroundColor(AppColors.success)
            }

            Text(label)
                .font(.caption2)
                .foregroundColor(searchPhase == phase ? AppColors.brandAccent : AppColors.textTertiary)
        }
    }

    private func isPhaseCompleted(phase: SearchPhase) -> Bool {
        let phases: [SearchPhase] = [.extractingKeywords, .vectorSearching, .reranking]
        let currentIndex = phases.firstIndex(of: searchPhase) ?? 0
        let phaseIndex = phases.firstIndex(of: phase) ?? 0
        return currentIndex > phaseIndex || searchPhase == .completed
    }

    // MARK: - 结果容器

    private var resultsContainer: some View {
        ScrollView {
            if !errorMessage.isEmpty {
                errorView
            } else if !searchResults.isEmpty {
                resultsList
            } else if isSearching {
                loadingPlaceholder
            }
        }
        .frame(maxHeight: 400)
        .background(Color(NSColor.controlBackgroundColor).opacity(0.85))  // 添加更明显的背景
    }

    // MARK: - 加载占位

    private var loadingPlaceholder: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.2)
            Text("正在搜索...")
                .font(.subheadline)
                .foregroundColor(AppColors.textSecondary)
        }
        .frame(height: 100)
    }

    // MARK: - 错误视图

    private var errorView: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 32))
                .foregroundColor(AppColors.warning)
            Text(errorMessage)
                .font(.subheadline)
                .foregroundColor(AppColors.textSecondary)
        }
        .padding(40)
    }

    // MARK: - 结果列表

    private var resultsList: some View {
        LazyVStack(spacing: 2) {
            ForEach(Array(searchResults.enumerated()), id: \.element.id) { index, result in
                AISearchResultRow(result: result, index: index, showAiBadge: rerankUsed)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    // MARK: - 搜索逻辑

    private func handleSearchChange(_ query: String) {
        searchTask?.cancel()

        if query.isEmpty {
            withAnimation(.easeOut(duration: 0.2)) {
                searchResults = []
                showResults = false
                searchPhase = .idle
                keywordsExtracted = []
            }
            return
        }

        withAnimation(.easeOut(duration: 0.15)) {
            showResults = true
        }

        searchTask = Task {
            try? await Task.sleep(nanoseconds: 300_000_000)
            if !Task.isCancelled {
                await performSearch(query: query)
            }
        }
    }

    private func performSearch(query: String) async {
        guard !query.isEmpty else {
            await MainActor.run { searchResults = [] }
            return
        }

        await MainActor.run {
            isSearching = true
            errorMessage = ""
            // 根据开关决定搜索阶段
            if keywordExtractionEnabled {
                searchPhase = .extractingKeywords
            } else if rerankEnabled {
                searchPhase = .reranking
            } else {
                searchPhase = .vectorSearching
            }
        }

        do {
            if aiEnabled {
                // AI 增强搜索 - 传递两个独立开关
                let response = try await APIClient.shared.aiSearch(
                    query: query,
                    enableKeywordExtraction: keywordExtractionEnabled,
                    enableRerank: rerankEnabled
                )

                await MainActor.run {
                    isSearching = false
                    searchResults = response.results
                    keywordsExtracted = response.keywordsExtracted
                    processingTime = response.processingTimeMs
                    rerankUsed = response.rerankUsed
                    searchPhase = .completed

                    // 保存「本次已完成搜索」的快照，供反馈提交使用
                    lastCompletedQuery = query
                    lastCompletedResults = response.results
                    lastSearchMode = "ai"
                    lastKeywordExtractionEnabled = keywordExtractionEnabled
                    lastRerankEnabled = rerankEnabled
                    lastAIEnhanced = response.aiEnhanced
                    lastKeywordsExtracted = response.keywordsExtracted
                    lastProcessingTime = response.processingTimeMs
                    lastRerankUsed = response.rerankUsed
                }
            } else {
                // 普通搜索 - 转换结果格式
                let results = try await APIClient.shared.search(query: query)

                await MainActor.run {
                    isSearching = false
                    // 转换为 AISearchResult 格式
                    let converted = results.map { r in
                        APIClient.AISearchResult(
                            id: r.id,
                            title: r.title,
                            url: r.url,
                            source: r.source,
                            account: r.account,
                            docType: r.docType,
                            extension: r.extension,
                            score: r.score,
                            rerankScore: nil,
                            finalScore: r.score,
                            text: r.text,
                            aiKeywords: nil
                        )
                    }
                    searchResults = converted
                    keywordsExtracted = []
                    processingTime = 0
                    rerankUsed = false
                    searchPhase = .completed

                    // 普通搜索的快照
                    lastCompletedQuery = query
                    lastCompletedResults = converted
                    lastSearchMode = "normal"
                    lastKeywordExtractionEnabled = false
                    lastRerankEnabled = false
                    lastAIEnhanced = false
                    lastKeywordsExtracted = []
                    lastProcessingTime = 0
                    lastRerankUsed = false
                }
            }
        } catch {
            await MainActor.run {
                isSearching = false
                searchPhase = .idle
                errorMessage = error.localizedDescription
            }
        }
    }

    // MARK: - 反馈入口栏

    private var feedbackEntryBar: some View {
        HStack {
            Spacer()
            Button {
                showFeedbackSheet = true
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: "bubble.left.and.bubble.right")
                        .font(.system(size: 11))
                    Text("评价本次搜索")
                        .font(.system(size: 11))
                }
                .foregroundColor(AppColors.textTertiary)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color(NSColor.controlBackgroundColor).opacity(0.6))
                )
            }
            .buttonStyle(.plain)
            .help("对本次搜索结果进行评价")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
        .background(Color(NSColor.controlBackgroundColor).opacity(0.85))
    }

    // MARK: - 反馈提交

    private func submitFeedback(
        rating: String,
        reasonCode: String?,
        reasonText: String?,
        expectedResult: String?
    ) async -> Bool {
        let snapshotItems: [APIClient.SearchFeedbackResultItem] = lastCompletedResults.map { r in
            APIClient.SearchFeedbackResultItem(
                id: r.id,
                title: r.title,
                url: r.url,
                source: r.source,
                account: r.account,
                docType: r.docType,
                extension: r.extension,
                score: r.score,
                rerankScore: r.rerankScore,
                finalScore: r.finalScore,
                text: r.text
            )
        }

        let request = APIClient.SearchFeedbackRequest(
            query: lastCompletedQuery,
            source: nil,
            account: nil,
            docType: nil,
            limit: 20,
            searchMode: lastSearchMode,
            keywordExtractionEnabled: lastKeywordExtractionEnabled,
            rerankEnabled: lastRerankEnabled,
            aiEnhanced: lastAIEnhanced,
            rerankUsed: lastRerankUsed,
            keywordsExtracted: lastKeywordsExtracted,
            processingTimeMs: lastSearchMode == "ai" ? lastProcessingTime : nil,
            rating: rating,
            reasonCode: reasonCode,
            reasonText: reasonText,
            expectedResult: expectedResult,
            results: snapshotItems,
            clientCreatedAt: Date().timeIntervalSince1970
        )

        do {
            _ = try await APIClient.shared.submitSearchFeedback(request)
            await MainActor.run {
                showFeedbackSheet = false
                showFeedbackToast(message: "反馈已保存")
            }
            return true
        } catch {
            await MainActor.run {
                showFeedbackToast(message: "反馈保存失败，请稍后重试")
            }
            return false
        }
    }

    private func showFeedbackToast(message: String) {
        feedbackToastMessage = message
        withAnimation(.easeIn(duration: 0.15)) {
            showFeedbackToast = true
        }
        Task {
            try? await Task.sleep(nanoseconds: 1_800_000_000)
            await MainActor.run {
                withAnimation(.easeOut(duration: 0.2)) {
                    showFeedbackToast = false
                }
            }
        }
    }
}

// MARK: - AI 搜索结果行 - Spotlight 风格

struct AISearchResultRow: View {
    let result: APIClient.AISearchResult
    let index: Int
    let showAiBadge: Bool
    @State private var isHovered: Bool = false

    var body: some View {
        HStack(spacing: 14) {
            // 数据源图标
            SourceIcon(source: result.source, size: 32)

            // 内容区
            VStack(alignment: .leading, spacing: 4) {
                // 标题
                Text(result.title ?? "无标题")
                    .font(.system(size: 14, weight: .medium))
                    .lineLimit(1)

                // 摘要
                Text(result.text)
                    .font(.system(size: 12))
                    .foregroundColor(AppColors.textTertiary)
                    .lineLimit(2)
            }

            Spacer()

            // 匹配度 - 右侧显示
            matchScore
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isHovered ? Color.accentColor.opacity(0.15) : Color.clear)
        )
        .contentShape(Rectangle())
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.1)) {
                isHovered = hovering
            }
        }
        .onTapGesture {
            openResult()
        }
    }

    // MARK: - 匹配度徽章

    @ViewBuilder
    private var matchScore: some View {
        VStack(alignment: .trailing, spacing: 2) {
            // 最终分数
            Text(String(format: "%.0f%%", result.finalScore * 100))
                .font(.system(size: 11, weight: .medium, design: .monospaced))
                .foregroundColor(scoreColor)

            // AI 增强时显示评分来源
            if showAiBadge && result.rerankScore != nil {
                HStack(spacing: 2) {
                    Image(systemName: "sparkles")
                        .font(.system(size: 8))
                    Text("AI")
                        .font(.system(size: 9))
                }
                .foregroundColor(AppColors.brandAccent)
            }

            Text(sourceLabel)
                .font(.system(size: 10))
                .foregroundColor(AppColors.textTertiary)
        }
    }

    private var scoreColor: Color {
        if result.finalScore >= 0.8 { return AppColors.success }
        if result.finalScore >= 0.6 { return AppColors.info }
        return AppColors.textTertiary
    }

    private var sourceLabel: String {
        switch result.source {
        case "feishu": return "飞书"
        case "local": return "本地"
        case "web": return "网页"
        case "yinxiang": return "印象"
        case "quark": return "夸克"
        default: return ""
        }
    }

    private func openResult() {
        if let urlString = result.url, let url = URL(string: urlString) {
            NSWorkspace.shared.open(url)
        }
    }
}

// MARK: - 飞书 Logo Shape

struct FeishuLogo: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()

        let w = rect.width
        let h = rect.height
        let centerX = w / 2
        let centerY = h / 2

        let outerSize = min(w, h) * 0.45

        path.move(to: CGPoint(x: centerX, y: centerY - outerSize))
        path.addLine(to: CGPoint(x: centerX + outerSize, y: centerY))
        path.addLine(to: CGPoint(x: centerX, y: centerY + outerSize))
        path.addLine(to: CGPoint(x: centerX - outerSize, y: centerY))
        path.closeSubpath()

        let innerSize = outerSize * 0.4

        var innerPath = Path()
        innerPath.move(to: CGPoint(x: centerX, y: centerY - innerSize))
        innerPath.addLine(to: CGPoint(x: centerX + innerSize, y: centerY))
        innerPath.addLine(to: CGPoint(x: centerX, y: centerY + innerSize))
        innerPath.addLine(to: CGPoint(x: centerX - innerSize, y: centerY))
        innerPath.closeSubpath()

        return path.subtracting(innerPath)
    }
}

// MARK: - 印象笔记 Logo Shape (大象简化版)

struct YinxiangLogo: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()

        let w = rect.width
        let h = rect.height

        // 大象简化轮廓 - 侧视图
        // 头部（圆形）
        let headCenterX = w * 0.25
        let headCenterY = h * 0.35
        let headRadius = min(w, h) * 0.22

        // 头部轮廓
        path.addEllipse(in: CGRect(
            x: headCenterX - headRadius,
            y: headCenterY - headRadius,
            width: headRadius * 2,
            height: headRadius * 2
        ))

        // 耳朵（大的半圆）
        let earCenterX = w * 0.35
        let earCenterY = h * 0.25
        let earRadius = min(w, h) * 0.28

        path.addEllipse(in: CGRect(
            x: earCenterX - earRadius * 0.5,
            y: earCenterY - earRadius,
            width: earRadius,
            height: earRadius * 1.5
        ))

        // 身体（椭圆形）
        let bodyCenterX = w * 0.55
        let bodyCenterY = h * 0.55
        let bodyWidth = min(w, h) * 0.45
        let bodyHeight = min(w, h) * 0.35

        path.addEllipse(in: CGRect(
            x: bodyCenterX - bodyWidth * 0.5,
            y: bodyCenterY - bodyHeight * 0.5,
            width: bodyWidth,
            height: bodyHeight
        ))

        return path
    }
}

// MARK: - 搜索反馈视图

struct SearchFeedbackView: View {
    let query: String
    let resultCount: Int
    /// 提交回调，返回是否提交成功（成功后 sheet 由 SearchView 控制关闭）
    let onSubmit: (_ rating: String, _ reasonCode: String?, _ reasonText: String?, _ expectedResult: String?) async -> Bool
    let onCancel: () -> Void

    @State private var rating: String = ""               // good / neutral / bad
    @State private var reasonCode: String = ""
    @State private var reasonText: String = ""
    @State private var expectedResult: String = ""
    @State private var isSubmitting: Bool = false
    @State private var validationError: String = ""

    /// 原因分类（与后端 reason_code 对齐）
    private let reasonOptions: [(code: String, label: String)] = [
        ("missing_expected_doc", "没搜到应该出现的内容"),
        ("bad_ranking", "结果排序不对"),
        ("irrelevant_results", "结果太泛或不相关"),
        ("wrong_summary", "摘要/预览不足以判断"),
        ("wrong_ai_keywords", "AI 关键词理解错"),
        ("rerank_worse", "智能重排后变差"),
        ("source_missing", "某个数据源缺失"),
        ("other", "其他"),
    ]

    /// 文本字段最大长度（与后端一致）
    private let maxTextLength = 2000

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // 标题
            HStack {
                Image(systemName: "bubble.left.and.bubble.right.fill")
                    .foregroundColor(AppColors.brandAccent)
                Text("评价本次搜索")
                    .font(.system(size: 16, weight: .semibold))
                Spacer()
            }

            // 搜索词信息
            VStack(alignment: .leading, spacing: 4) {
                Text("搜索词")
                    .font(.caption)
                    .foregroundColor(AppColors.textTertiary)
                Text(query)
                    .font(.system(size: 13))
                    .lineLimit(2)
                Text("共 \(resultCount) 条结果")
                    .font(.caption2)
                    .foregroundColor(AppColors.textTertiary)
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(Color(NSColor.controlBackgroundColor).opacity(0.5))
            )

            // 评价
            VStack(alignment: .leading, spacing: 8) {
                Text("您的评价")
                    .font(.system(size: 13, weight: .medium))
                HStack(spacing: 8) {
                    ratingButton(value: "good", label: "满意", icon: "hand.thumbsup")
                    ratingButton(value: "neutral", label: "一般", icon: "minus.circle")
                    ratingButton(value: "bad", label: "不满意", icon: "hand.thumbsdown")
                }
            }

            // 不满意时显示原因
            if rating == "bad" {
                VStack(alignment: .leading, spacing: 8) {
                    Text("问题原因")
                        .font(.system(size: 13, weight: .medium))
                    LazyVGrid(columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ], spacing: 6) {
                        ForEach(reasonOptions, id: \.code) { opt in
                            reasonButton(code: opt.code, label: opt.label)
                        }
                    }
                }
            }

            // 补充说明
            VStack(alignment: .leading, spacing: 4) {
                Text("补充说明（可选）")
                    .font(.system(size: 13, weight: .medium))
                TextEditor(text: $reasonText)
                    .font(.system(size: 12))
                    .frame(height: 50)
                    .padding(4)
                    .background(
                        RoundedRectangle(cornerRadius: 4)
                            .stroke(Color.gray.opacity(0.3))
                    )
                    .onChange(of: reasonText) { _, newValue in
                        if newValue.count > maxTextLength {
                            reasonText = String(newValue.prefix(maxTextLength))
                        }
                    }
            }

            // 期望结果
            VStack(alignment: .leading, spacing: 4) {
                Text("期望结果（可选）")
                    .font(.system(size: 13, weight: .medium))
                TextEditor(text: $expectedResult)
                    .font(.system(size: 12))
                    .frame(height: 50)
                    .padding(4)
                    .background(
                        RoundedRectangle(cornerRadius: 4)
                            .stroke(Color.gray.opacity(0.3))
                    )
                    .onChange(of: expectedResult) { _, newValue in
                        if newValue.count > maxTextLength {
                            expectedResult = String(newValue.prefix(maxTextLength))
                        }
                    }
            }

            // 校验错误提示
            if !validationError.isEmpty {
                Text(validationError)
                    .font(.caption)
                    .foregroundColor(.red)
            }

            // 操作按钮
            HStack {
                Spacer()
                Button("取消") {
                    onCancel()
                }
                .keyboardShortcut(.cancelAction)
                .disabled(isSubmitting)

                Button(action: handleSubmit) {
                    if isSubmitting {
                        ProgressView()
                            .scaleEffect(0.6)
                            .frame(width: 60, height: 16)
                    } else {
                        Text("提交")
                            .frame(width: 60)
                    }
                }
                .keyboardShortcut(.defaultAction)
                .disabled(rating.isEmpty || isSubmitting)
            }
        }
        .padding(20)
        .frame(width: 480)
    }

    // MARK: - 子视图

    private func ratingButton(value: String, label: String, icon: String) -> some View {
        Button {
            rating = value
            validationError = ""
        } label: {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 18))
                Text(label)
                    .font(.system(size: 11))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(rating == value ? AppColors.brandAccent.opacity(0.2) : Color(NSColor.controlBackgroundColor).opacity(0.5))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(rating == value ? AppColors.brandAccent : Color.gray.opacity(0.3), lineWidth: 1)
            )
            .foregroundColor(rating == value ? AppColors.brandAccent : AppColors.textSecondary)
        }
        .buttonStyle(.plain)
    }

    private func reasonButton(code: String, label: String) -> some View {
        Button {
            reasonCode = (reasonCode == code) ? "" : code
            validationError = ""
        } label: {
            HStack {
                Image(systemName: reasonCode == code ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 12))
                Text(label)
                    .font(.system(size: 11))
                Spacer()
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 4)
                    .fill(reasonCode == code ? AppColors.brandAccent.opacity(0.15) : Color.clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 4)
                    .stroke(reasonCode == code ? AppColors.brandAccent : Color.gray.opacity(0.3), lineWidth: 1)
            )
            .foregroundColor(reasonCode == code ? AppColors.brandAccent : AppColors.textSecondary)
        }
        .buttonStyle(.plain)
    }

    // MARK: - 提交

    private func handleSubmit() {
        validationError = ""
        // 前端校验
        if rating.isEmpty {
            validationError = "请选择评价"
            return
        }
        if rating == "bad" && reasonCode.isEmpty {
            validationError = "请选择问题原因"
            return
        }

        isSubmitting = true
        Task {
            let success = await onSubmit(
                rating,
                reasonCode.isEmpty ? nil : reasonCode,
                reasonText.isEmpty ? nil : reasonText,
                expectedResult.isEmpty ? nil : expectedResult
            )
            await MainActor.run {
                isSubmitting = false
                if !success {
                    // 失败时保留输入内容，由父视图通过 toast 提示
                    validationError = "保存失败，请稍后重试"
                }
            }
        }
    }
}