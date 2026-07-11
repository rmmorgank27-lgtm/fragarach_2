import Foundation

public let foundationTables = Set(["bars", "ingest_runs", "instrument_registrations", "lane_state", "provenance", "raw_blocks", "rollup_state", "schema_migrations"])

public struct ValidationSummary: Codable, Equatable, Sendable {
    public let format: String
    public let symbol: String
    public let timeframe: String
    public let calendarID: String
    public let calendarVersion: Int
    public let calendarChecksum: String
    public let gapDoctrineID: String
    public let gapDoctrineVersion: Int
    public let gapDoctrineChecksum: String
    public let validatorVersion: String
    public let throughDate: String
    public let expectedSessionCount: Int
    public let presentExpectedSessionCount: Int
    public let missingExpectedSessionCount: Int
    public let outsideExpectedSessionCount: Int
    public let emptyWeekCount: Int
    public let emptyMonthCount: Int
    public let latestExpectedSession: String?
    public let latestExpectedSessionPresent: Bool
    public let materialGapCount: Int
    public let nonMaterialGapCount: Int
    public let resultChecksum: String
    public let validationObservedAt: String

    enum CodingKeys: String, CodingKey {
        case format, symbol, timeframe
        case calendarID = "calendar_id", calendarVersion = "calendar_version", calendarChecksum = "calendar_checksum"
        case gapDoctrineID = "gap_doctrine_id", gapDoctrineVersion = "gap_doctrine_version", gapDoctrineChecksum = "gap_doctrine_checksum"
        case validatorVersion = "validator_version", throughDate = "through_date"
        case expectedSessionCount = "expected_session_count", presentExpectedSessionCount = "present_expected_session_count"
        case missingExpectedSessionCount = "missing_expected_session_count", outsideExpectedSessionCount = "outside_expected_session_count"
        case emptyWeekCount = "empty_week_count", emptyMonthCount = "empty_month_count"
        case latestExpectedSession = "latest_expected_session", latestExpectedSessionPresent = "latest_expected_session_present"
        case materialGapCount = "material_gap_count", nonMaterialGapCount = "non_material_gap_count"
        case resultChecksum = "result_checksum", validationObservedAt = "validation_observed_at"
    }
}

public struct LaneRecord: Identifiable, Equatable, Sendable {
    public var id: String { "\(asset):\(timeframe)" }
    public let asset: String
    public let timeframe: String
    public let highWatermark: Int64?
    public let stateVersion: Int
    public let lastIngestRunID: String?
    public let updatedAt: String
    public let barCount: Int
    public let earliestBar: Int64?
    public let latestBar: Int64?
    public let validation: ValidationSummary?
}

public struct OperationRecord: Identifiable, Equatable, Sendable {
    public let id: String
    public let kind: String
    public let status: String
    public let startedAt: String
    public let finishedAt: String?
    public let rawBlockID: String?
    public let detailJSON: String?
    public let provenanceTotal: Int
    public let inserted: Int
    public let unchanged: Int
    public let conflicts: Int
    public let corrected: Int
}

public struct AuthoritySnapshot: Equatable, Sendable {
    public let databasePath: String
    public let lanes: [LaneRecord]
    public let operations: [OperationRecord]
    public let readAt: Date
}

public enum ConsoleSection: String, CaseIterable, Identifiable, Sendable {
    case lanes = "Lanes", acquire = "Acquire", importEvidence = "Import", operations = "Operations"
    case integrity = "Integrity & Backup", settings = "Settings"
    public var id: String { rawValue }
    public var icon: String {
        switch self { case .lanes: "list.bullet.rectangle"; case .acquire: "arrow.down.circle"; case .importEvidence: "doc.badge.plus"; case .operations: "clock.arrow.circlepath"; case .integrity: "checkmark.shield"; case .settings: "gearshape" }
    }
}

public enum ConflictMode: String, CaseIterable, Sendable { case preserve, correct }

public enum OperationIntent: Equatable, Sendable {
    case acquire(asset: String, from: String, through: String, mode: ConflictMode)
    case importCSV(file: String, symbol: String, timeframe: String, mode: ConflictMode)
    case validate(symbol: String, timeframe: String, through: String, persist: Bool)
    case verify
    case backup(destination: String)
}

public enum LaneQuery {
    public static func apply(_ lanes: [LaneRecord], search: String, timeframe: String?) -> [LaneRecord] {
        lanes.filter { (search.isEmpty || $0.asset.localizedCaseInsensitiveContains(search)) && (timeframe == nil || $0.timeframe == timeframe) }.sorted { $0.id < $1.id }
    }
}

public struct ReviewGate: Equatable, Sendable {
    public private(set) var reviewed: OperationIntent?
    public init() {}
    public mutating func review(_ intent: OperationIntent) { reviewed = intent }
    public mutating func confirm(_ intent: OperationIntent) -> Bool { defer { reviewed = nil }; return reviewed == intent }
    public mutating func cancel() { reviewed = nil }
}

public struct ProcessResult: Equatable, Sendable {
    public let operationID: UUID
    public let exitCode: Int32
    public let stdout: String
    public let stderr: String
    public var JSON: [String: Any]? { (try? JSONSerialization.jsonObject(with: Data(stdout.utf8))) as? [String: Any] }
    public static func == (lhs: Self, rhs: Self) -> Bool { lhs.operationID == rhs.operationID && lhs.exitCode == rhs.exitCode && lhs.stdout == rhs.stdout && lhs.stderr == rhs.stderr }
}
