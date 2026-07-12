import Foundation

public let foundationTables = Set(["authority_events", "bars", "evidence_lanes", "ingest_runs", "instrument_registrations", "lane_state", "provenance", "raw_blocks", "rollup_state", "schema_migrations"])

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

public struct AuthorityEventRecord: Identifiable, Equatable, Sendable {
    public let id: String
    public let entityKind: String
    public let entityID: String
    public let eventKind: String
    public let supersedesEventID: String?
    public let effectiveFrom: String
    public let effectiveTo: String?
    public let compatibilityState: String
    public let compatibilityReasonsJSON: String
    public let payloadChecksum: String
    public let eventChecksum: String
    public let recordedAt: String
    public let recordedBy: String
}

public struct AuthoritySnapshot: Equatable, Sendable {
    public let databasePath: String
    public let lanes: [LaneRecord]
    public let operations: [OperationRecord]
    public let authorityEvents: [AuthorityEventRecord]
    public let readAt: Date
}

public struct TruthScoreComponent: Codable, Equatable, Sendable {
    public let score: Int?
    public let basis: String
}

public struct TruthExplanation: Codable, Equatable, Sendable {
    public let method: String
    public let components: [String: TruthScoreComponent]
    public let limitations: [String]
}

public struct TruthCoverageRange: Codable, Equatable, Sendable {
    public let start: String?
    public let end: String?
}

public struct TruthCoverage: Codable, Equatable, Sendable {
    public let earliestBar: String
    public let latestBar: String
    public let rowCount: Int
    public let expectedRange: TruthCoverageRange
    public let availableRange: TruthCoverageRange
    public let expectedSessionCount: Int?
    public let availableExpectedSessionCount: Int?
    enum CodingKeys: String, CodingKey {
        case earliestBar = "earliest_bar", latestBar = "latest_bar", rowCount = "row_count"
        case expectedRange = "expected_range", availableRange = "available_range"
        case expectedSessionCount = "expected_session_count", availableExpectedSessionCount = "available_expected_session_count"
    }
}

public struct TruthProviderSummary: Codable, Equatable, Sendable {
    public let provider: String
    public let providerContract: String
    public let providerSymbol: String
    public let confidence: String
    public let score: Int?
    public let basis: String
    enum CodingKeys: String, CodingKey {
        case provider, confidence, score, basis
        case providerContract = "provider_contract", providerSymbol = "provider_symbol"
    }
}

public struct TruthState: Codable, Equatable, Sendable {
    public let contract: String
    public let engineVersion: Int
    public let symbol: String
    public let timeframe: String
    public let truthScore: Int
    public let authorityScore: Int
    public let freshnessScore: Int?
    public let coverageScore: Int?
    public let continuityScore: Int?
    public let validationScore: Int?
    public let providerScore: Int?
    public let authorityState: String
    public let validationState: String
    public let caodt: String
    public let gapClassification: String
    public let gapImpact: String
    public let coverage: TruthCoverage
    public let providerSummary: TruthProviderSummary
    public let epoch: String
    public let explanation: TruthExplanation
    enum CodingKeys: String, CodingKey {
        case contract, symbol, timeframe, caodt, coverage, epoch, explanation
        case engineVersion = "engine_version", truthScore = "truth_score", authorityScore = "authority_score"
        case freshnessScore = "freshness_score", coverageScore = "coverage_score", continuityScore = "continuity_score"
        case validationScore = "validation_score", providerScore = "provider_score", authorityState = "authority_state"
        case validationState = "validation_state", gapClassification = "gap_classification", gapImpact = "gap_impact"
        case providerSummary = "provider_summary"
    }
}

public enum ConsoleSection: String, CaseIterable, Identifiable, Sendable {
    case lanes = "Lanes", authority = "Authority Ledger", acquire = "Acquire", importEvidence = "Import Evidence", addInstrument = "Add Instrument", operations = "Operations"
    case integrity = "Integrity & Backup", settings = "Settings"
    public var id: String { rawValue }
    public var icon: String {
        switch self { case .lanes: "list.bullet.rectangle"; case .authority: "books.vertical"; case .acquire: "arrow.down.circle"; case .importEvidence: "doc.badge.plus"; case .addInstrument: "plus.circle"; case .operations: "clock.arrow.circlepath"; case .integrity: "checkmark.shield"; case .settings: "gearshape" }
    }
}

public enum ConflictMode: String, CaseIterable, Sendable { case preserve, correct }

public enum OperationIntent: Equatable, Sendable {
    case readTruth(symbol: String, timeframe: String)
    case searchInstrument(query: String)
    case registerInstrument(candidate: String)
    case acquire(asset: String, from: String, through: String, mode: ConflictMode)
    case importCSV(file: String, symbol: String, timeframe: String, mode: ConflictMode)
    case validate(symbol: String, timeframe: String, through: String, persist: Bool)
    case verify
    case backup(destination: String)
}

public struct InstrumentAlias: Codable, Equatable, Sendable { public let alias:String; public let normalizedAlias:String; public let aliasType:String; enum CodingKeys:String,CodingKey{case alias;case normalizedAlias="normalized_alias";case aliasType="alias_type"} }
public struct InstrumentCandidate: Codable, Equatable, Sendable {
    public let asset,timeframe,instrumentFamily,localSymbol,displayName,instrumentType,assetClass,representationType,tradingCurrency,exchangeName,providerID,providerContract,providerSymbol,providerInstrumentType,calendarID,gapDoctrineID:String
    public let calendarVersion,gapDoctrineVersion:Int; public let aliases:[InstrumentAlias]; public let exchangeMIC,providerExchange,providerCountry:String?
    enum CodingKeys:String,CodingKey{case asset,timeframe,aliases;case instrumentFamily="instrument_family",localSymbol="local_symbol",displayName="display_name",instrumentType="instrument_type",assetClass="asset_class",representationType="representation_type",tradingCurrency="trading_currency",exchangeName="exchange_name",providerID="provider_id",providerContract="provider_contract",providerSymbol="provider_symbol",providerInstrumentType="provider_instrument_type",calendarID="calendar_id",calendarVersion="calendar_version",gapDoctrineID="gap_doctrine_id",gapDoctrineVersion="gap_doctrine_version",exchangeMIC="exchange_mic",providerExchange="provider_exchange",providerCountry="provider_country"}
}
public struct InstrumentSearchResponse: Codable, Equatable, Sendable { public let found,alreadyRegistered:Bool;public let candidate:InstrumentCandidate?;public let registrationStatus:String?;public init(found:Bool,alreadyRegistered:Bool,candidate:InstrumentCandidate?,registrationStatus:String?){self.found=found;self.alreadyRegistered=alreadyRegistered;self.candidate=candidate;self.registrationStatus=registrationStatus};enum CodingKeys:String,CodingKey{case found,candidate;case alreadyRegistered="already_registered",registrationStatus="registration_status"} }

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
