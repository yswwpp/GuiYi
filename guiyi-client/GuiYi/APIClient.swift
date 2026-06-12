//
//  APIClient.swift
//  GuiYi
//
//  API 客户端 - 与后端服务通信
//

import Foundation

/// API 错误类型
enum APIError: Error, LocalizedError {
    case connectionError
    case invalidResponse
    case serverError(String)
    case decodingError

    var errorDescription: String? {
        switch self {
        case .connectionError:
            return "无法连接到后端服务"
        case .invalidResponse:
            return "无效的响应"
        case .serverError(let message):
            return message
        case .decodingError:
            return "数据解析失败"
        }
    }
}

/// API 客户端
class APIClient {
    static let shared = APIClient()
    static let baseURL = "http://127.0.0.1:8765"  // 使用 IPv4 地址

    private let session: URLSession

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config)
    }

    // MARK: - 响应模型

    struct SaveResponse: Codable {
        let status: String
        let url: String
        let title: String
        let filePath: String
        let docId: String
        let message: String?
        let indexed: Bool?

        enum CodingKeys: String, CodingKey {
            case status, url, title, message, indexed
            case filePath = "file_path"
            case docId = "doc_id"
        }
    }

    struct SearchResult: Codable, Identifiable {
        let id: String
        let title: String?
        let url: String?
        let source: String?
        let account: String?
        let score: Double
        let text: String
    }

    struct StatusResponse: Codable {
        let status: String
        let uptime: Double
        let sources: [String]
        let storage: StorageInfo
        let index: IndexInfo

        struct StorageInfo: Codable {
            let totalFiles: Int
            let totalSizeMb: Double

            enum CodingKeys: String, CodingKey {
                case totalFiles = "total_files"
                case totalSizeMb = "total_size_mb"
            }
        }

        struct IndexInfo: Codable {
            let totalDocuments: Int
            let model: String

            enum CodingKeys: String, CodingKey {
                case totalDocuments = "total_documents"
                case model
            }
        }
    }

    struct FilesResponse: Codable {
        let total: Int
        let files: [String]
    }

    // MARK: - API 方法

    /// 保存网页
    func save(url urlString: String) async throws -> SaveResponse {
        guard let apiURL = URL(string: "\(APIClient.baseURL)/api/save") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: apiURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["url": urlString]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("保存失败 (状态码: \(httpResponse.statusCode))")
        }

        do {
            return try JSONDecoder().decode(SaveResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 搜索
    func search(query: String, source: String? = nil, limit: Int = 10) async throws -> [SearchResult] {
        guard let url = URL(string: "\(APIClient.baseURL)/api/search") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = ["query": query, "limit": limit]
        if let source = source {
            body["source"] = source
        }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("搜索失败 (状态码: \(httpResponse.statusCode))")
        }

        do {
            return try JSONDecoder().decode([SearchResult].self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 获取状态
    func getStatus() async throws -> StatusResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/status") else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("获取状态失败")
        }

        do {
            return try JSONDecoder().decode(StatusResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 获取文件列表
    func getFiles() async throws -> FilesResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/files") else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("获取文件列表失败")
        }

        do {
            return try JSONDecoder().decode(FilesResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    // MARK: - 同步任务 API

    struct SyncJob: Codable, Identifiable {
        let id: String
        let name: String
        let trigger: String
        let nextRunTime: String?

        enum CodingKeys: String, CodingKey {
            case id, name, trigger
            case nextRunTime = "next_run_time"
        }
    }

    struct SyncJobsResponse: Codable {
        let total: Int
        let jobs: [SyncJob]
    }

    struct SyncStatusResponse: Codable {
        let status: String
        let source: String?
        let account: String?
    }

    /// 获取同步任务列表
    func getSyncJobs() async throws -> SyncJobsResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/scheduler/jobs") else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("获取同步任务失败")
        }

        do {
            return try JSONDecoder().decode(SyncJobsResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 添加同步任务
    func addSyncJob(source: String, account: String? = nil, cronExpression: String? = nil, intervalHours: Int? = nil) async throws -> [String: String] {
        var queryItems = [URLQueryItem(name: "source", value: source)]
        if let account = account {
            queryItems.append(URLQueryItem(name: "account", value: account))
        }
        if let cronExpression = cronExpression {
            queryItems.append(URLQueryItem(name: "cron_expression", value: cronExpression))
        }
        if let intervalHours = intervalHours {
            queryItems.append(URLQueryItem(name: "interval_hours", value: String(intervalHours)))
        }

        var components = URLComponents(string: "\(APIClient.baseURL)/api/scheduler/jobs")!
        components.queryItems = queryItems

        guard let url = components.url else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("添加同步任务失败")
        }

        do {
            return try JSONDecoder().decode([String: String].self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 删除同步任务
    func removeSyncJob(jobId: String) async throws -> Bool {
        guard let url = URL(string: "\(APIClient.baseURL)/api/scheduler/jobs/\(jobId)") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("删除同步任务失败")
        }

        return true
    }

    /// 立即触发同步
    func triggerSync(source: String, account: String? = nil) async throws -> SyncStatusResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/sync") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = ["source": source]
        if let account = account {
            body["account"] = account
        }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("同步失败")
        }

        do {
            return try JSONDecoder().decode(SyncStatusResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    // MARK: - 同步统计 API

    struct SourceStats: Codable {
        let count: Int
        let lastSync: Double?

        enum CodingKeys: String, CodingKey {
            case count
            case lastSync = "last_sync"
        }
    }

    struct SyncStatsResponse: Codable {
        let status: String
        let sources: [String: SourceStats]
    }

    /// 获取各数据源的同步统计
    func getSyncStats() async throws -> SyncStatsResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/sync/stats") else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("获取同步统计失败")
        }

        do {
            return try JSONDecoder().decode(SyncStatsResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }
}

// MARK: - Helper Models

private struct ErrorResponse: Codable {
    let detail: String
}

// MARK: - 本地目录 API

extension APIClient {
    struct LocalDirectory: Codable, Identifiable {
        let id: String
        let name: String
        let path: String
        let fileTypes: [String]
        let excludePatterns: [String]
        let excludePaths: [String]
        let enabled: Bool
        let maxDepth: Int
        let maxFileSizeMb: Int
        let fileCount: Int?
        let createdAt: String?
        let updatedAt: String?

        enum CodingKeys: String, CodingKey {
            case id, name, path, enabled
            case fileTypes = "file_types"
            case excludePatterns = "exclude_patterns"
            case excludePaths = "exclude_paths"
            case maxDepth = "max_depth"
            case maxFileSizeMb = "max_file_size_mb"
            case fileCount = "file_count"
            case createdAt = "created_at"
            case updatedAt = "updated_at"
        }
    }

    struct LocalDirectoriesResponse: Codable {
        let total: Int
        let directories: [LocalDirectory]
    }

    struct FileTypesResponse: Codable {
        let fileTypes: [String]
        let defaultExcludePatterns: [String]

        enum CodingKeys: String, CodingKey {
            case fileTypes = "file_types"
            case defaultExcludePatterns = "default_exclude_patterns"
        }
    }

    /// 获取支持的文件类型
    func getSupportedFileTypes() async throws -> FileTypesResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/local-directories/file-types") else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("获取文件类型失败")
        }

        do {
            return try JSONDecoder().decode(FileTypesResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 获取本地目录列表
    func getLocalDirectories() async throws -> LocalDirectoriesResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/local-directories") else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("获取本地目录失败")
        }

        do {
            return try JSONDecoder().decode(LocalDirectoriesResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 添加本地目录
    func addLocalDirectory(
        name: String,
        path: String,
        fileTypes: [String]? = nil,
        excludePatterns: [String]? = nil,
        excludePaths: [String]? = nil,
        enabled: Bool = true,
        maxDepth: Int = 10,
        maxFileSizeMb: Int = 10
    ) async throws -> LocalDirectory {
        guard let url = URL(string: "\(APIClient.baseURL)/api/local-directories") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [
            "name": name,
            "path": path,
            "enabled": enabled,
            "max_depth": maxDepth,
            "max_file_size_mb": maxFileSizeMb
        ]
        if let fileTypes = fileTypes {
            body["file_types"] = fileTypes
        }
        if let excludePatterns = excludePatterns {
            body["exclude_patterns"] = excludePatterns
        }
        if let excludePaths = excludePaths {
            body["exclude_paths"] = excludePaths
        }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("添加本地目录失败")
        }

        do {
            return try JSONDecoder().decode(LocalDirectory.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 更新本地目录
    func updateLocalDirectory(
        id: String,
        name: String? = nil,
        fileTypes: [String]? = nil,
        excludePatterns: [String]? = nil,
        excludePaths: [String]? = nil,
        enabled: Bool? = nil,
        maxDepth: Int? = nil,
        maxFileSizeMb: Int? = nil
    ) async throws -> Bool {
        guard let url = URL(string: "\(APIClient.baseURL)/api/local-directories/\(id)") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [:]
        if let name = name { body["name"] = name }
        if let fileTypes = fileTypes { body["file_types"] = fileTypes }
        if let excludePatterns = excludePatterns { body["exclude_patterns"] = excludePatterns }
        if let excludePaths = excludePaths { body["exclude_paths"] = excludePaths }
        if let enabled = enabled { body["enabled"] = enabled }
        if let maxDepth = maxDepth { body["max_depth"] = maxDepth }
        if let maxFileSizeMb = maxFileSizeMb { body["max_file_size_mb"] = maxFileSizeMb }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("更新本地目录失败")
        }

        return true
    }

    /// 删除本地目录
    func deleteLocalDirectory(id: String) async throws -> Bool {
        guard let url = URL(string: "\(APIClient.baseURL)/api/local-directories/\(id)") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("删除本地目录失败")
        }

        return true
    }
}

// MARK: - AI 配置 API

extension APIClient {
    struct AIConfigResponse: Codable {
        let enabled: Bool
        let apiBase: String
        let apiKey: String?
        let model: String
        let summaryThresholdKb: Int
        let maxTokens: Int
        let chunkSizeKb: Int
        let maxContentKb: Int
        let summaryPrompt: String?
        let partialPrompt: String?
        let mergePrompt: String?

        enum CodingKeys: String, CodingKey {
            case enabled
            case apiBase = "api_base"
            case apiKey = "api_key"
            case model
            case summaryThresholdKb = "summary_threshold_kb"
            case maxTokens = "max_tokens"
            case chunkSizeKb = "chunk_size_kb"
            case maxContentKb = "max_content_kb"
            case summaryPrompt = "summary_prompt"
            case partialPrompt = "partial_prompt"
            case mergePrompt = "merge_prompt"
        }
    }

    /// 获取 AI 配置
    func getAIConfig() async throws -> AIConfigResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/ai/config") else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("获取 AI 配置失败")
        }

        do {
            return try JSONDecoder().decode(AIConfigResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 更新 AI 配置
    func updateAIConfig(
        enabled: Bool? = nil,
        apiBase: String? = nil,
        apiKey: String? = nil,
        model: String? = nil,
        summaryThresholdKb: Int? = nil,
        maxTokens: Int? = nil,
        chunkSizeKb: Int? = nil,
        maxContentKb: Int? = nil,
        summaryPrompt: String? = nil,
        partialPrompt: String? = nil,
        mergePrompt: String? = nil
    ) async throws -> Bool {
        guard let url = URL(string: "\(APIClient.baseURL)/api/ai/config") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [:]
        if let enabled = enabled { body["enabled"] = enabled }
        if let apiBase = apiBase { body["api_base"] = apiBase }
        if let apiKey = apiKey { body["api_key"] = apiKey }
        if let model = model { body["model"] = model }
        if let summaryThresholdKb = summaryThresholdKb { body["summary_threshold_kb"] = summaryThresholdKb }
        if let maxTokens = maxTokens { body["max_tokens"] = maxTokens }
        if let chunkSizeKb = chunkSizeKb { body["chunk_size_kb"] = chunkSizeKb }
        if let maxContentKb = maxContentKb { body["max_content_kb"] = maxContentKb }
        if let summaryPrompt = summaryPrompt { body["summary_prompt"] = summaryPrompt }
        if let partialPrompt = partialPrompt { body["partial_prompt"] = partialPrompt }
        if let mergePrompt = mergePrompt { body["merge_prompt"] = mergePrompt }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("更新 AI 配置失败")
        }

        return true
    }

    /// 测试 AI 连接
    func testAIConnection(
        apiBase: String? = nil,
        apiKey: String? = nil,
        model: String? = nil
    ) async throws -> Bool {
        guard let url = URL(string: "\(APIClient.baseURL)/api/ai/test") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // 如果提供了参数，传递给后端
        if apiBase != nil || apiKey != nil || model != nil {
            var body: [String: Any] = [:]
            if let apiBase = apiBase { body["api_base"] = apiBase }
            if let apiKey = apiKey { body["api_key"] = apiKey }
            if let model = model { body["model"] = model }
            request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("AI 服务连接失败")
        }

        return true
    }

    // MARK: - AI 增强搜索 API

    /// AI 搜索结果
    struct AISearchResult: Codable, Identifiable {
        let id: String
        let title: String?
        let url: String?
        let source: String?
        let account: String?
        let score: Double              // 原始向量分数
        let rerankScore: Double?       // Rerank 分数
        let finalScore: Double         // 最终综合分数
        let text: String
        let aiKeywords: [String]?      // AI 提取的关键词

        enum CodingKeys: String, CodingKey {
            case id, title, url, source, account, score, text
            case rerankScore = "rerank_score"
            case finalScore = "final_score"
            case aiKeywords = "ai_keywords"
        }
    }

    /// AI 搜索响应
    struct AISearchResponse: Codable {
        let results: [AISearchResult]
        let aiEnhanced: Bool
        let keywordsExtracted: [String]
        let rerankUsed: Bool
        let processingTimeMs: Double

        enum CodingKeys: String, CodingKey {
            case results
            case aiEnhanced = "ai_enhanced"
            case keywordsExtracted = "keywords_extracted"
            case rerankUsed = "rerank_used"
            case processingTimeMs = "processing_time_ms"
        }
    }

    /// AI 搜索配置响应
    struct AISearchConfigResponse: Codable {
        let aiSearchEnabled: Bool
        let keywordExtractionEnabled: Bool
        let rerankEnabled: Bool
        let keywordExtractorType: String
        let keywordOllamaUrl: String
        let keywordOllamaModel: String
        let keywordApiUrl: String?
        let keywordApiKey: String?
        let keywordApiModel: String?
        let keywordPrompt: String?
        let rerankerType: String
        let rerankerBgeModel: String
        let rerankerCohereUrl: String?
        let rerankerCohereKey: String?
        let rerankerCohereModel: String?
        let rerankerJinaUrl: String?
        let rerankerJinaKey: String?
        let rerankerJinaModel: String?
        let rerankTopN: Int

        enum CodingKeys: String, CodingKey {
            case aiSearchEnabled = "ai_search_enabled"
            case keywordExtractionEnabled = "keyword_extraction_enabled"
            case rerankEnabled = "rerank_enabled"
            case keywordExtractorType = "keyword_extractor_type"
            case keywordOllamaUrl = "keyword_ollama_url"
            case keywordOllamaModel = "keyword_ollama_model"
            case keywordApiUrl = "keyword_api_url"
            case keywordApiKey = "keyword_api_key"
            case keywordApiModel = "keyword_api_model"
            case keywordPrompt = "keyword_prompt"
            case rerankerType = "reranker_type"
            case rerankerBgeModel = "reranker_bge_model"
            case rerankerCohereUrl = "reranker_cohere_url"
            case rerankerCohereKey = "reranker_cohere_key"
            case rerankerCohereModel = "reranker_cohere_model"
            case rerankerJinaUrl = "reranker_jina_url"
            case rerankerJinaKey = "reranker_jina_key"
            case rerankerJinaModel = "reranker_jina_model"
            case rerankTopN = "rerank_top_n"
        }
    }

    /// AI 增强搜索 - 两个独立开关
    func aiSearch(
        query: String,
        source: String? = nil,
        limit: Int = 20,
        enableKeywordExtraction: Bool = true,
        enableRerank: Bool = true
    ) async throws -> AISearchResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/ai-search") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [
            "query": query,
            "limit": limit,
            "enable_keyword_extraction": enableKeywordExtraction,
            "enable_rerank": enableRerank
        ]
        if let source = source {
            body["source"] = source
        }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.serverError(errorResponse.detail)
            }
            throw APIError.serverError("AI 搜索失败 (状态码: \(httpResponse.statusCode))")
        }

        do {
            return try JSONDecoder().decode(AISearchResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 获取 AI 搜索配置
    func getAISearchConfig() async throws -> AISearchConfigResponse {
        guard let url = URL(string: "\(APIClient.baseURL)/api/ai/search-config") else {
            throw APIError.invalidResponse
        }

        let (data, response) = try await session.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError("获取 AI 搜索配置失败")
        }

        do {
            return try JSONDecoder().decode(AISearchConfigResponse.self, from: data)
        } catch {
            throw APIError.decodingError
        }
    }

    /// 更新 AI 搜索配置
    func updateAISearchConfig(
        aiSearchEnabled: Bool? = nil,
        keywordExtractionEnabled: Bool? = nil,
        rerankEnabled: Bool? = nil,
        keywordExtractorType: String? = nil,
        keywordOllamaUrl: String? = nil,
        keywordOllamaModel: String? = nil,
        keywordApiUrl: String? = nil,
        keywordApiKey: String? = nil,
        keywordApiModel: String? = nil,
        rerankerType: String? = nil,
        rerankerBgeModel: String? = nil
    ) async throws -> Bool {
        guard let url = URL(string: "\(APIClient.baseURL)/api/ai/search-config") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [:]
        if let aiSearchEnabled = aiSearchEnabled { body["ai_search_enabled"] = aiSearchEnabled }
        if let keywordExtractionEnabled = keywordExtractionEnabled { body["keyword_extraction_enabled"] = keywordExtractionEnabled }
        if let rerankEnabled = rerankEnabled { body["rerank_enabled"] = rerankEnabled }
        if let keywordExtractorType = keywordExtractorType { body["keyword_extractor_type"] = keywordExtractorType }
        if let keywordOllamaUrl = keywordOllamaUrl { body["keyword_ollama_url"] = keywordOllamaUrl }
        if let keywordOllamaModel = keywordOllamaModel { body["keyword_ollama_model"] = keywordOllamaModel }
        if let keywordApiUrl = keywordApiUrl { body["keyword_api_url"] = keywordApiUrl }
        if let keywordApiKey = keywordApiKey { body["keyword_api_key"] = keywordApiKey }
        if let keywordApiModel = keywordApiModel { body["keyword_api_model"] = keywordApiModel }
        if let rerankerType = rerankerType { body["reranker_type"] = rerankerType }
        if let rerankerBgeModel = rerankerBgeModel { body["reranker_bge_model"] = rerankerBgeModel }
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        return httpResponse.statusCode == 200
    }

    /// 测试 Rerank 连接
    func testRerankConnection() async throws -> Bool {
        guard let url = URL(string: "\(APIClient.baseURL)/api/ai/rerank-test") else {
            throw APIError.invalidResponse
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (_, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        return httpResponse.statusCode == 200
    }
}
