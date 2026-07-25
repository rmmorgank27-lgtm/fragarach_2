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
    public let instrument: String
    public let timeframe: String
    public let source: String
    public let warningsJSON: String
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
    public let registrations: [InstrumentRegistrationRecord]
    public let lanes: [LaneRecord]
    public let operations: [OperationRecord]
    public let authorityEvents: [AuthorityEventRecord]
    public let readAt: Date
}

public struct GovernedObservationGap: Identifiable, Equatable, Sendable {
    public var id: String { "\(previousObservationTimestamp):\(nextObservationTimestamp)" }
    public let previousObservationTimestamp: Int64
    public let nextObservationTimestamp: Int64
    public let gapDuration: Int64
    public let expectedCadence: Int64
    public let classification: String
    public let reason: String?
}

public struct GovernedContinuity: Equatable, Sendable {
    public let expectedCadence: Int64
    public let observedCadence: Int64?
    public let gaps: [GovernedObservationGap]
    public let latestState: String
    public let warnings: [String]

    /// Market closures remain visible to the profile renderer, but they are
    /// not missing observations and must not degrade the continuity summary.
    public var observedGaps: [GovernedObservationGap] {
        gaps.filter { $0.classification != "EXPECTED_MARKET_CLOSURE" }
    }
    public var expectedMarketClosures: [GovernedObservationGap] {
        gaps.filter { $0.classification == "EXPECTED_MARKET_CLOSURE" }
    }
    public var gapCount: Int { observedGaps.count }
    public var largestGap: GovernedObservationGap? {
        observedGaps.max { $0.gapDuration < $1.gapDuration }
    }
    public var mostRecentGap: GovernedObservationGap? { observedGaps.last }
}

/// One viewport-sized aggregate of governed price action. Price History never
/// receives the underlying individual bar rows.
public struct PriceHistoryProfilePoint: Identifiable, Equatable, Sendable {
    public var id: Int64 { timestamp }
    public let timestamp: Int64
    public let high: Double
    public let low: Double
    public let close: Double
}

/// Read-only, operational Price History payload. It intentionally contains a
/// summary row, observed discontinuities, and a bounded profile only.
public struct PriceHistoryOverview: Equatable, Sendable {
    public let symbol: String
    public let timeframe: String
    public let authority: String
    public let governedInputRevision: String
    public let latestGovernedObservation: Int64?
    public let earliestGovernedObservation: Int64?
    public let totalBarCount: Int
    public let validationState: String
    public let continuity: GovernedContinuity
    public let profile: [PriceHistoryProfilePoint]
    public let metadataWarning: String?
}

public struct InstrumentRegistrationRecord: Identifiable, Equatable, Sendable {
    public var id: String { "\(asset):\(timeframe)" }
    public let asset: String
    public let timeframe: String
    public let displayName: String
    public let assetClass: String
    public let representationType: String
    public let providerID: String
    public let providerContract: String
    public let providerSymbol: String
    public let registrationStatus: String
    public let registeredAt: String
    public let retired: Bool
}

public struct TruthScoreComponent: Codable, Equatable, Sendable {
    public let score: Int?
    public let basis: String
}

public struct TruthExplanation: Codable, Equatable, Sendable {
    public let method: String
    public let weights: [String: Int]?
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
    public let provider: String?
    public let providerContract: String?
    public let providerSymbol: String?
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
    public let integrityScore: Int?
    public let freshnessScore: Int?
    public let historicalDepthScore: Int?
    public let coverageScore: Int?
    public let continuityScore: Int?
    public let validationScore: Int?
    public let providerScore: Int?
    public let authorityState: String
    public let validationState: String
    public let caodt: String
    public let latestCanonicalObservation: String
    public let gapClassification: String
    public let gapImpact: String
    public let coverage: TruthCoverage
    public let providerSummary: TruthProviderSummary
    public let epoch: String
    public let explanation: TruthExplanation
    enum CodingKeys: String, CodingKey {
        case contract, symbol, timeframe, caodt, coverage, epoch, explanation
        case latestCanonicalObservation = "latest_canonical_observation"
        case engineVersion = "engine_version", truthScore = "truth_score", authorityScore = "authority_score"
        case integrityScore = "integrity_score", historicalDepthScore = "historical_depth_score"
        case freshnessScore = "freshness_score", coverageScore = "coverage_score", continuityScore = "continuity_score"
        case validationScore = "validation_score", providerScore = "provider_score", authorityState = "authority_state"
        case validationState = "validation_state", gapClassification = "gap_classification", gapImpact = "gap_impact"
        case providerSummary = "provider_summary"
    }
}

public struct EstateAggregation: Codable, Equatable, Sendable {
    public let truthScore: String
    public let authorityState: String
    public let caodt: String
    public let generatedAt: String
    enum CodingKeys: String, CodingKey {
        case truthScore = "truth_score", authorityState = "authority_state", caodt
        case generatedAt = "generated_at"
    }
}

public struct EstateSummary: Codable, Equatable, Sendable {
    public let overallTruthScore: Int?
    public let overallAuthorityState: String
    public let latestCanonicalObservation: String?
    public let caodt: String?
    public let overallCAODT: String?
    public let totalSymbols: Int
    public let totalLanes: Int
    public let requiredLanes: Int
    public let commissionedLanes: Int
    public let operationalLanes: Int
    public let missingCommissions: Int
    public let notEnabledLanes: Int?
    public let operationalCoveragePercent: Int?
    public let greenCount: Int
    public let amberCount: Int
    public let redCount: Int
    public let authorityVersion: Int
    public let generatedAt: String?
    public let aggregation: EstateAggregation
    enum CodingKeys: String, CodingKey {
        case overallTruthScore = "overall_truth_score", overallAuthorityState = "overall_authority_state"
        case latestCanonicalObservation = "latest_canonical_observation", caodt
        case overallCAODT = "overall_caodt", totalSymbols = "total_symbols", totalLanes = "total_lanes"
        case requiredLanes = "required_lanes", commissionedLanes = "commissioned_lanes"
        case operationalLanes = "operational_lanes", missingCommissions = "missing_commissions"
        case notEnabledLanes = "not_enabled_lanes"
        case operationalCoveragePercent = "operational_coverage_percent"
        case greenCount = "green_count", amberCount = "amber_count", redCount = "red_count"
        case authorityVersion = "authority_version", generatedAt = "generated_at", aggregation
    }
}

public struct EstateSearchMetadata: Codable, Equatable, Sendable {
    public let canonicalSymbol: String
    public let displayName: String
    public let aliases: [InstrumentAlias]
    public let market: String
    public let assetClass: String
    public let exchange: String
    public let providerFamily: String?
    enum CodingKeys: String, CodingKey {
        case canonicalSymbol = "canonical_symbol", displayName = "display_name", aliases, market
        case assetClass = "asset_class", exchange, providerFamily = "provider_family"
    }
}

public struct EstateProviderSummary: Codable, Equatable, Sendable {
    public let provider: String?
    public let providerContract: String?
    public let providerSymbol: String?
    public let providerFreshness: String
    public let providerConfidence: String
    public let entitlement: String
    public let unknownValues: [String]
    enum CodingKeys: String, CodingKey {
        case provider, entitlement
        case providerContract = "provider_contract", providerSymbol = "provider_symbol"
        case providerFreshness = "provider_freshness", providerConfidence = "provider_confidence"
        case unknownValues = "unknown_values"
    }
}

public struct EstateGapSummary: Codable, Equatable, Sendable {
    public let currentGapCount: Int?
    public let recentGapCount: Int?
    public let historicalGapCount: Int?
    public let totalGapCount: Int?
    public let gapClassification: String
    public let operationalImpact: String
    enum CodingKeys: String, CodingKey {
        case currentGapCount = "current_gap_count", recentGapCount = "recent_gap_count"
        case historicalGapCount = "historical_gap_count", totalGapCount = "total_gap_count"
        case gapClassification = "gap_classification", operationalImpact = "operational_impact"
    }
}

public struct AcquisitionCapabilityLastSuccess:Codable,Equatable,Sendable { public let provider:String?;public let providerSymbol:String?;public let mappingClass:String?;public let finishedAt:String?;enum CodingKeys:String,CodingKey{case provider;case providerSymbol="provider_symbol",mappingClass="mapping_class",finishedAt="finished_at"} }
public struct AcquisitionCapabilityRow:Codable,Equatable,Sendable,Identifiable {
    public var id:String{"\(canonicalSymbol):\(timeframe):\(provider)"}
    public let canonicalSymbol:String;public let canonicalRepresentation:String;public let timeframe:String;public let provider:String;public let providerSymbol:String?;public let providerRepresentation:String?;public let mappingStatus:String;public let mappingClass:String?;public let capabilityState:String;public let eligibility:String;public let credentialStatus:String;public let entitlementStatus:String;public let ratePolicyStatus:String;public let historyRangeSupport:String;public let priority:Int;public let rejectionReason:String?;public let authoritySource:String;public let existingCommissionedLane:Bool;public let lastSuccessfulProvider:AcquisitionCapabilityLastSuccess?
    enum CodingKeys:String,CodingKey{case timeframe,provider,eligibility,priority;case canonicalSymbol="canonical_symbol",canonicalRepresentation="canonical_representation",providerSymbol="provider_symbol",providerRepresentation="provider_representation",mappingStatus="mapping_status",mappingClass="mapping_class",capabilityState="capability_state",credentialStatus="credential_status",entitlementStatus="entitlement_status",ratePolicyStatus="rate_policy_status",historyRangeSupport="history_range_support",rejectionReason="rejection_reason",authoritySource="authority_source",existingCommissionedLane="existing_commissioned_lane",lastSuccessfulProvider="last_successful_provider"}
}
public struct EstateIntegrityDimension:Codable,Equatable,Sendable {public let state:String;public let score:Int?}
public struct EstateFreshnessDimension:Codable,Equatable,Sendable {public let state:String?;public let label:String;public let lag:SchedulerLag?}
public struct EstateAcquisitionDimension:Codable,Equatable,Sendable {public let state:String;public let eligibleProviders:[String];public let providerCapabilities:[AcquisitionCapabilityRow];enum CodingKeys:String,CodingKey{case state;case eligibleProviders="eligible_providers",providerCapabilities="provider_capabilities"}}

public struct EstateTruthLane: Codable, Equatable, Sendable, Identifiable {
    public var id: String { "\(symbol):\(timeframe)" }
    public let symbol: String
    public let timeframe: String
    public let latestCanonicalObservation: String
    public let authorityGenerated: String
    public let authorityRevision: String
    public let truthState: TruthState
    public let searchMetadata: EstateSearchMetadata
    public let providerSummary: EstateProviderSummary
    public let gapSummary: EstateGapSummary
    public let evidenceIntegrity:EstateIntegrityDimension?
    public let freshnessDimension:EstateFreshnessDimension?
    public let acquisitionDimension:EstateAcquisitionDimension?
    public let overallOperationalState:String?
    public let operationalStateLabel:String?
    enum CodingKeys: String, CodingKey {
        case symbol, timeframe
        case latestCanonicalObservation = "latest_canonical_observation"
        case authorityGenerated = "authority_generated", authorityRevision = "authority_revision"
        case truthState = "truth_state", searchMetadata = "search_metadata"
        case providerSummary = "provider_summary", gapSummary = "gap_summary"
        case evidenceIntegrity="evidence_integrity",freshnessDimension="freshness_dimension",acquisitionDimension="acquisition_dimension",overallOperationalState="overall_operational_state",operationalStateLabel="operational_state_label"
    }
}

public struct TimeframeCapability:Codable,Equatable,Sendable,Identifiable{public var id:String{timeframe};public let timeframe:String;public let policyState:String;public let authorityState:String;public let providerMappingState:String;public let provider:String?;public let providerSymbol:String?;public let providerContract:String?;public let calendarAuthority:String?;public let sessionAuthority:String?;public let entitlementState:String;public let evidenceState:String;public let validationState:String;public let truthState:String;public let servable:Bool;public let consumptionAvailable:Bool;public let automationEligible:Bool?;public let requiredOperatorAction:String?;public let initialFetchEligible:Bool;public let initialFetchBlockers:[String];public let reasonCodes:[String];public let providerCapabilities:[AcquisitionCapabilityRow]?;public let lastSuccessfulProvider:AcquisitionCapabilityLastSuccess?;enum CodingKeys:String,CodingKey{case timeframe,provider,servable;case policyState="policy_state",authorityState="authority_state",providerMappingState="provider_mapping_state",providerSymbol="provider_symbol",providerContract="provider_contract",calendarAuthority="calendar_authority",sessionAuthority="session_authority",entitlementState="entitlement_state",evidenceState="evidence_state",validationState="validation_state",truthState="truth_state",consumptionAvailable="consumption_available",automationEligible="automation_eligible",requiredOperatorAction="required_operator_action",initialFetchEligible="initial_fetch_eligible",initialFetchBlockers="initial_fetch_blockers",reasonCodes="reason_codes",providerCapabilities="provider_capabilities",lastSuccessfulProvider="last_successful_provider"}}
public struct SymbolTimeframeCapability:Codable,Equatable,Sendable,Identifiable{public var id:String{symbol};public let symbol:String;public let assetClass:String;public let authorisedTimeframes:[String];public let declaredTimeframes:[String];public let activeTimeframes:[String];public let servableTimeframes:[String];public let intentionallyDeferredTimeframes:[String];public let blockedTimeframes:[String];public let timeframes:[TimeframeCapability];enum CodingKeys:String,CodingKey{case symbol,timeframes;case assetClass="asset_class",authorisedTimeframes="authorised_timeframes",declaredTimeframes="declared_timeframes",activeTimeframes="active_timeframes",servableTimeframes="servable_timeframes",intentionallyDeferredTimeframes="intentionally_deferred_timeframes",blockedTimeframes="blocked_timeframes"}}

public struct CommissionedLaneState:Codable,Equatable,Sendable,Identifiable {
    public let id:String
    public let symbol:String
    public let assetClass:String
    public let timeframe:String
    public let required:Bool
    public let enabled:Bool?
    public let nonBlocking:Bool?
    public let commissioned:Bool
    public let operational:Bool
    public let missingCommission:Bool
    public let commissioningState:String
    public let operationalState:String
    public let evidenceCount:Int
    enum CodingKeys:String,CodingKey {
        case id,symbol,timeframe,required,commissioned,operational
        case enabled,nonBlocking="non_blocking"
        case assetClass="asset_class",missingCommission="missing_commission"
        case commissioningState="commissioning_state",operationalState="operational_state"
        case evidenceCount="evidence_count"
    }
}

public enum EstateLanePresentation {
    public static func operationalState(
        commissioned:Bool,resolvedState:String,providerEligible:Bool
    )->String {
        guard commissioned else{return "Not Commissioned"}
        switch resolvedState {
        case "Current":return "Current"
        case "Behind","Critically Behind":return "Behind"
        case "Missing":return providerEligible ? "Behind":"Unavailable"
        case "Unavailable":return "Unavailable"
        default:return resolvedState
        }
    }
    public static func commissioning(_ commissioned:Bool)->String {
        commissioned ? "Commissioned":"Not Commissioned"
    }
    public static func automation(_ commissioned:Bool)->String {
        commissioned ? "Enabled":"Disabled"
    }
}

public struct EstateTruthState: Codable, Equatable, Sendable {
    public let contract: String
    public let latestCanonicalObservation: String?
    public let caodt: String?
    public let authorityGenerated: String
    public let authorityRevision: String
    public let estateSummary: EstateSummary
    public let truthMatrix: [EstateTruthLane]
    public let commissioningMatrix:[CommissionedLaneState]
    public let timeframeCapabilities:[SymbolTimeframeCapability]?
    enum CodingKeys: String, CodingKey {
        case contract, caodt, estateSummary = "estate_summary", truthMatrix = "truth_matrix",commissioningMatrix="commissioning_matrix",timeframeCapabilities="timeframe_capabilities"
        case latestCanonicalObservation = "latest_canonical_observation"
        case authorityGenerated = "authority_generated", authorityRevision = "authority_revision"
    }
}

public struct MarketHistoryBar: Codable, Equatable, Sendable, Identifiable {
    public var id: String { timestamp }
    public let timestamp: String
    public let open: String
    public let high: String
    public let low: String
    public let close: String
}

public struct MarketHistoryResponse: Codable, Equatable, Sendable {
    public let ohlc: [MarketHistoryBar]
    public let caodt: String?
    public let status: String
    public let warnings: [String]
    enum CodingKeys: String, CodingKey {
        case ohlc = "OHLC", caodt = "CAODT", status = "Status", warnings = "Warnings"
    }
}

public struct SyntheticProduct:Codable,Equatable,Sendable,Identifiable {
    public let id:String;public let symbol:String;public let targetTimeframe:String;public let evidenceClass:String;public let immediateSourceSymbol:String;public let immediateSourceTimeframe:String;public let immediateSourceEvidenceClass:String;public let originatingRealSymbol:String;public let originatingRealTimeframe:String;public let aggregationRule:String;public let aggregationRuleVersion:Int;public let calendarAuthority:String;public let sessionAlignment:String;public let authorisedConsumers:[String];public let registrationStatus:String;public let status:String;public let sourceRevision:String?;public let syntheticRevision:Int;public let generatedAt:String?;public let firstSyntheticObservation:Int64?;public let latestSyntheticObservation:Int64?;public let observationCount:Int
    enum CodingKeys:String,CodingKey{case id,symbol,status;case targetTimeframe="target_timeframe",evidenceClass="evidence_class",immediateSourceSymbol="immediate_source_symbol",immediateSourceTimeframe="immediate_source_timeframe",immediateSourceEvidenceClass="immediate_source_evidence_class",originatingRealSymbol="originating_real_symbol",originatingRealTimeframe="originating_real_timeframe",aggregationRule="aggregation_rule",aggregationRuleVersion="aggregation_rule_version",calendarAuthority="calendar_authority",sessionAlignment="session_alignment",authorisedConsumers="authorised_consumers",registrationStatus="registration_status",sourceRevision="source_revision",syntheticRevision="synthetic_revision",generatedAt="generated_at",firstSyntheticObservation="first_synthetic_observation",latestSyntheticObservation="latest_synthetic_observation",observationCount="observation_count"}
}
public struct SyntheticSummary:Codable,Equatable,Sendable {public let total:Int;public let available:Int;public let stale:Int;public let incomplete:Int;public let unavailable:Int}
public struct SyntheticSnapshot:Codable,Equatable,Sendable {public let contract:String;public let repository:String;public let products:[SyntheticProduct];public let summary:SyntheticSummary}

public struct SchedulerLag: Codable, Equatable, Sendable {
    public let count: Int?
    public let unit: String?
}

public struct SchedulerAuthorityHealth: Codable, Equatable, Sendable {
    public let state: String
    public let detail: String
}

public struct SchedulerSummary: Codable, Equatable, Sendable {
    public let total: Int
    public let current: Int
    public let waiting: Int
    public let running: Int
    public let behind: Int
    public let unavailable: Int
    public let failed: Int
    public let paused: Int?
    enum CodingKeys: String, CodingKey {
        case total
        case current = "Current", waiting = "Waiting", running = "Running"
        case behind = "Behind", unavailable = "Unavailable", failed = "Failed", paused = "Paused"
    }
}

public struct SchedulerLane: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let symbol: String
    public let timeframe: String
    public let schedulerState: String
    public let latestCanonicalObservation: String?
    public let expectedLatest: String?
    public let expectedEdgeStatus:String?
    public let lag: SchedulerLag
    public let nextScheduledAcquisition: String?
    public let lastAcquisition: String?
    public let durationSeconds: Double?
    public let result: String?
    public let reason: String?
    public let routingDecision: String?
    public let providersConsidered: [SchedulerProviderDecision]
    public let acquisitionPlan: SchedulerLaneAcquisitionPlan?
    public let providersRejected: [SchedulerProviderDecision]
    public let currentProvider: String?
    public let attemptHistory: [SchedulerProviderAttempt]
    public let publicationResult: SchedulerPublicationResult?
    public let publicationState: String?
    public let publicationJobID: String?
    public let manualRequest: String?
    public let market:String?
    public let lifecycleState:String?
    public let pauseState:String?
    public let pauseEffectiveSources:[String]
    public let providerCapabilities:[AcquisitionCapabilityRow]
    public let freshnessSeverity:String?
    public let operationalState:String?
    enum CodingKeys: String, CodingKey {
        case id, symbol, timeframe, lag, result, reason
        case schedulerState = "scheduler_state"
        case latestCanonicalObservation = "latest_canonical_observation"
        case expectedLatest = "expected_latest"
        case expectedEdgeStatus = "expected_edge_status"
        case nextScheduledAcquisition = "next_scheduled_acquisition"
        case lastAcquisition = "last_acquisition"
        case durationSeconds = "duration_seconds"
        case routingDecision = "routing_decision", providersConsidered = "providers_considered", acquisitionPlan = "acquisition_plan"
        case providersRejected = "providers_rejected", currentProvider = "current_provider"
        case attemptHistory = "attempt_history", publicationResult = "publication_result", publicationState = "publication_state", publicationJobID = "publication_job_id"
        case manualRequest = "manual_request"
        case market,lifecycleState="lifecycle_state",pauseState="pause_state",pauseEffectiveSources="pause_effective_sources",providerCapabilities="provider_capabilities",freshnessSeverity="freshness_severity",operationalState="operational_state"
    }
    public init(from decoder: Decoder) throws {
        let c=try decoder.container(keyedBy:CodingKeys.self)
        id=try c.decode(String.self,forKey:.id);symbol=try c.decode(String.self,forKey:.symbol);timeframe=try c.decode(String.self,forKey:.timeframe);schedulerState=try c.decode(String.self,forKey:.schedulerState)
        latestCanonicalObservation=try c.decodeIfPresent(String.self,forKey:.latestCanonicalObservation);expectedLatest=try c.decodeIfPresent(String.self,forKey:.expectedLatest);expectedEdgeStatus=try c.decodeIfPresent(String.self,forKey:.expectedEdgeStatus);lag=try c.decode(SchedulerLag.self,forKey:.lag);nextScheduledAcquisition=try c.decodeIfPresent(String.self,forKey:.nextScheduledAcquisition);lastAcquisition=try c.decodeIfPresent(String.self,forKey:.lastAcquisition);durationSeconds=try c.decodeIfPresent(Double.self,forKey:.durationSeconds);result=try c.decodeIfPresent(String.self,forKey:.result);reason=try c.decodeIfPresent(String.self,forKey:.reason)
        routingDecision=try c.decodeIfPresent(String.self,forKey:.routingDecision);providersConsidered=try c.decodeIfPresent([SchedulerProviderDecision].self,forKey:.providersConsidered) ?? [];acquisitionPlan=try c.decodeIfPresent(SchedulerLaneAcquisitionPlan.self,forKey:.acquisitionPlan);providersRejected=try c.decodeIfPresent([SchedulerProviderDecision].self,forKey:.providersRejected) ?? [];currentProvider=try c.decodeIfPresent(String.self,forKey:.currentProvider);attemptHistory=try c.decodeIfPresent([SchedulerProviderAttempt].self,forKey:.attemptHistory) ?? [];publicationResult=try c.decodeIfPresent(SchedulerPublicationResult.self,forKey:.publicationResult);publicationState=try c.decodeIfPresent(String.self,forKey:.publicationState);publicationJobID=try c.decodeIfPresent(String.self,forKey:.publicationJobID);manualRequest=try c.decodeIfPresent(String.self,forKey:.manualRequest);market=try c.decodeIfPresent(String.self,forKey:.market);lifecycleState=try c.decodeIfPresent(String.self,forKey:.lifecycleState);pauseState=try c.decodeIfPresent(String.self,forKey:.pauseState);pauseEffectiveSources=try c.decodeIfPresent([String].self,forKey:.pauseEffectiveSources) ?? [];providerCapabilities=try c.decodeIfPresent([AcquisitionCapabilityRow].self,forKey:.providerCapabilities) ?? [];freshnessSeverity=try c.decodeIfPresent(String.self,forKey:.freshnessSeverity);operationalState=try c.decodeIfPresent(String.self,forKey:.operationalState)
    }
}

public struct SchedulerLaneAcquisitionPlan: Codable, Equatable, Sendable {
    public let intent: String?
    public let canonicalEdge: String?
    public let expectedEdge: String?
    public let expectedEdgeStatus: String?
    public let requestBounds: SchedulerRequestBounds?
    public let eligibility: String?
    public let blockingReason: String?
    public let executable: Bool
    public let provider: String?
    public let providerSymbol: String?
    public let providersConsidered: [SchedulerProviderDecision]
    enum CodingKeys: String, CodingKey {
        case intent, eligibility, executable, provider
        case canonicalEdge = "canonical_edge", expectedEdge = "expected_edge"
        case expectedEdgeStatus = "expected_edge_status", requestBounds = "request_bounds"
        case blockingReason = "blocking_reason", providerSymbol = "provider_symbol"
        case providersConsidered = "providers_considered"
    }
}

public struct SchedulerRequestBounds: Codable, Equatable, Sendable {
    public let start: String
    public let end: String
}

public struct SchedulerProviderDecision: Codable, Equatable, Sendable, Identifiable {
    public var id:String{"\(provider):\(reason ?? "ELIGIBLE")"}
    public let market:String?;public let timeframe:String?;public let provider:String;public let eligible:Bool;public let reason:String?;public let providerSymbol:String?;public let estimatedRequestCount:Int;public let providerRepresentation:String?;public let representationType:String?;public let mappingStatus:String?;public let mappingClass:String?;public let mappingAuthoritySource:String?;public let fallbackRank:Int?;public let routingPolicy:String?;public let quoteEquivalence:String?;public let quoteEquivalenceReason:String?
    enum CodingKeys:String,CodingKey{case market,timeframe,provider,eligible,reason;case providerSymbol="provider_symbol",estimatedRequestCount="estimated_request_count",providerRepresentation="provider_representation",representationType="representation_type",mappingStatus="mapping_status",mappingClass="mapping_class",mappingAuthoritySource="mapping_authority_source",fallbackRank="fallback_rank",routingPolicy="routing_policy",quoteEquivalence="quote_equivalence",quoteEquivalenceReason="quote_equivalence_reason"}
}
public struct SchedulerProviderAttempt: Codable, Equatable, Sendable, Identifiable {
    public var id:String{"\(provider):\(at)"};public let provider:String;public let result:String;public let reason:String;public let detail:String?;public let at:String;public let durationSeconds:Double
    enum CodingKeys:String,CodingKey{case provider,result,reason,detail,at;case durationSeconds="duration_seconds"}
}
public struct SchedulerPublicationResult: Codable, Equatable, Sendable { public let provider:String;public let inserted:Int;public let corrected:Int;public let status:String?;public let result:String?;public let providerSymbol:String?;public let mappingClass:String?;enum CodingKeys:String,CodingKey{case provider,inserted,corrected,status,result;case providerSymbol="provider_symbol",mappingClass="mapping_class"};public var displayStatus:String{result ?? status ?? "UNKNOWN"} }

public struct SchedulerProvider: Codable, Equatable, Sendable, Identifiable {
    public var id:String{provider};public let provider:String;public let enabled:Bool;public let supportedAssetClasses:[String];public let supportedTimeframes:[String];public let approvedSymbolMappings:Int;public let credentialRequirement:String;public let credentials:String;public let credentialState:String?;public let credentialAuthorityRevision:String?;public let credentialLastValidation:String?;public let credentialValidationSource:String?;public let entitlement:String;public let requestLimit:Int;public let requestWindowSeconds:Int;public let maximumRowsPerRequest:Int;public let historyLimitations:Int?;public let costClass:Int;public let priority:Int;public let health:String;public let cooldownUntil:String?;public let lastSuccess:String?;public let lastFailure:String?;public let budgetUnit:String?;public let budgetPolicy:String?;public let ratePolicyVerified:Bool?;public let queueCeiling:Int?;public let protectedCapacity:Int?;public let adaptiveTarget:Int?;public let targetUtilizationPercent:Int?;public let dynamicReservedCapacity:Int?;public let dispatchAvailable:Int?;public let budgetUsed:Int?;public let budgetAvailable:Int?;public let activeRequests:Int?;public let concurrencyLimit:Int?;public let effectiveThroughput:Double?;public let nextBudgetRelease:String?;public let nextScheduledDemand:String?;public let actualDispatchedCalls:Int?;public let activeReservations:Int?;public let capacityReserved:Int?;public let responsesReceived:Int?;public let rateLimitResponses:Int?;public let transientFailures:Int?;public let providerWaitReason:String?;public let providerWaitScope:String?;public let planLimit:Int?;public let operationalCreditLimit:Int?;public let windowStartedAt:String?;public let windowEndsAt:String?;public let creditsConsumed:Int?;public let creditsRemaining:Int?;public let nextDispatchAt:String?;public let last429At:String?;public let requestsLastMinute:Int?;public let currentDispatchRate:Double?
    enum CodingKeys:String,CodingKey{case provider,enabled,credentials,entitlement,priority,health;case supportedAssetClasses="supported_asset_classes",supportedTimeframes="supported_timeframes",approvedSymbolMappings="approved_symbol_mappings",credentialRequirement="credential_requirement",credentialState="credential_state",credentialAuthorityRevision="credential_authority_revision",credentialLastValidation="credential_last_validation",credentialValidationSource="credential_validation_source",requestLimit="request_limit",requestWindowSeconds="request_window_seconds",maximumRowsPerRequest="maximum_rows_per_request",historyLimitations="history_limitations",costClass="cost_class",cooldownUntil="cooldown_until",lastSuccess="last_success",lastFailure="last_failure",budgetUnit="budget_unit",budgetPolicy="budget_policy",ratePolicyVerified="rate_policy_verified",queueCeiling="queue_ceiling",protectedCapacity="protected_capacity",adaptiveTarget="adaptive_target",targetUtilizationPercent="target_utilization_percent",dynamicReservedCapacity="dynamic_reserved_capacity",dispatchAvailable="dispatch_available",budgetUsed="budget_used",budgetAvailable="budget_available",activeRequests="active_requests",concurrencyLimit="concurrency_limit",effectiveThroughput="effective_throughput",nextBudgetRelease="next_budget_release",nextScheduledDemand="next_scheduled_demand",actualDispatchedCalls="actual_dispatched_calls",activeReservations="active_reservations",capacityReserved="capacity_reserved",responsesReceived="responses_received",rateLimitResponses="rate_limit_responses",transientFailures="transient_failures",providerWaitReason="provider_wait_reason",providerWaitScope="provider_wait_scope",planLimit="plan_limit",operationalCreditLimit="operational_credit_limit",windowStartedAt="window_started_at",windowEndsAt="window_ends_at",creditsConsumed="credits_consumed",creditsRemaining="credits_remaining",nextDispatchAt="next_dispatch_at",last429At="last_429_at",requestsLastMinute="requests_last_minute",currentDispatchRate="current_dispatch_rate"}
}

public struct CredentialAuthorityProvider:Codable,Equatable,Sendable,Identifiable {public var id:String{provider};public let provider:String;public let credentialState:String;public let authorityRevision:String;public let lastValidation:String?;public let validationSource:String;enum CodingKeys:String,CodingKey{case provider;case credentialState="credential_state",authorityRevision="authority_revision",lastValidation="last_validation",validationSource="validation_source"}}
public struct CredentialAuthoritySnapshot:Codable,Equatable,Sendable {public let contract:String;public let generatedAt:String;public let authorityRevision:String;public let providers:[CredentialAuthorityProvider];enum CodingKeys:String,CodingKey{case contract,providers;case generatedAt="generated_at",authorityRevision="authority_revision"}}
public struct SchedulerRateBudget: Codable, Equatable, Sendable, Identifiable { public var id:String{provider};public let provider:String;public let limit:Int;public let windowSeconds:Int;public let callsUsed:Int;public let callsAvailable:Int;public let nextAvailable:String?;public let queueCallsUsed:Int?;public let queueCeiling:Int?;public let protectedCapacity:Int?;public let queueAvailable:Int?;public let planLimit:Int?;public let operationalLimit:Int?;public let windowStartedAt:String?;public let windowEndsAt:String?;public let creditsConsumed:Int?;public let creditsRemaining:Int?;public let nextDispatchAt:String?;public let last429At:String?;public let requestsLastMinute:Int?;public let currentDispatchRate:Double?;enum CodingKeys:String,CodingKey{case provider,limit;case windowSeconds="window_seconds",callsUsed="calls_used",callsAvailable="calls_available",nextAvailable="next_available",queueCallsUsed="queue_calls_used",queueCeiling="queue_ceiling",protectedCapacity="protected_capacity",queueAvailable="queue_available",planLimit="plan_limit",operationalLimit="operational_limit",windowStartedAt="window_started_at",windowEndsAt="window_ends_at",creditsConsumed="credits_consumed",creditsRemaining="credits_remaining",nextDispatchAt="next_dispatch_at",last429At="last_429_at",requestsLastMinute="requests_last_minute",currentDispatchRate="current_dispatch_rate"} }
public struct SchedulerMissingRange: Codable, Equatable, Sendable { public let start:String?;public let end:String }
public struct SchedulerQueueItem: Codable, Equatable, Sendable, Identifiable { public let id:String;public let lane:String;public let symbol:String;public let timeframe:String;public let missingRange:SchedulerMissingRange;public let selectedProvider:String?;public let fallbackPosition:Int;public let queueReason:String;public let estimatedRequests:Int;public let budgetWait:String?;public let nextAttempt:String?;public let missedBoundaries:Int;public let workClass:String?;public let operationalState:String?;public let waitingReason:String?;public let enqueuedAt:String?;public let traceID:String?;public let attemptNumber:Int?;public let currentStage:String?;public let stopReason:String?;public let activeWorkerID:String?;enum CodingKeys:String,CodingKey{case id,lane,symbol,timeframe;case missingRange="missing_range",selectedProvider="selected_provider",fallbackPosition="fallback_position",queueReason="queue_reason",estimatedRequests="estimated_requests",budgetWait="budget_wait",nextAttempt="next_attempt",missedBoundaries="missed_boundaries",workClass="work_class",operationalState="operational_state",waitingReason="waiting_reason",enqueuedAt="enqueued_at",traceID="trace_id",attemptNumber="attempt_number",currentStage="current_stage",stopReason="stop_reason",activeWorkerID="active_worker_id"} }
public struct SchedulerRoutingDecision: Codable, Equatable, Sendable, Identifiable { public let id:String;public let lane:String;public let symbol:String;public let timeframe:String;public let selectedProvider:String?;public let selectionReason:String?;public let fallbackSequence:[String];public let providersConsidered:[SchedulerProviderDecision];enum CodingKeys:String,CodingKey{case id,lane,symbol,timeframe;case selectedProvider="selected_provider",selectionReason="selection_reason",fallbackSequence="fallback_sequence",providersConsidered="providers_considered"} }
public struct SchedulerManualRequest: Codable, Equatable, Sendable, Identifiable { public let id:String;public let symbol:String;public let timeframe:String;public let missingStart:String;public let missingEnd:String;public let expectedCanonicalEdge:String;public let priority:String;public let reason:String;public let providersAttempted:[String];public let acceptedImportFormat:String;public let createdAt:String;public let status:String;public let requestAgeSeconds:Double?;public let latestFailure:SchedulerProviderAttempt?;public let instrumentLifecycleState:String?;public let laneCommissioningState:String?;public let pauseState:String?;public let providersConsidered:[SchedulerProviderDecision]?;public let providersRejected:[SchedulerProviderDecision]?;public let recommendedOperatorAction:String?;public let createdProviderFactRevision:Int?;public let lastEvaluatedProviderFactRevision:Int?;public let createdCapabilityProjectionRevision:String?;public let lastEvaluatedCapabilityProjectionRevision:String?;public let lastEvaluatedAt:String?;public let reconciliationStatus:String?;public let reconciliationReason:String?;public let providersCurrentlyEligible:[String]?;public let providersCurrentlyIneligible:[SchedulerProviderDecision]?;public let replacementQueueIdentifier:String?;public let providersConsideredAtCreation:[SchedulerProviderDecision]?;public let providersAttemptedAtCreation:[String]?;public let originalRejectionReasons:[SchedulerProviderDecision]?;enum CodingKeys:String,CodingKey{case id,symbol,timeframe,priority,reason,status;case missingStart="missing_start",missingEnd="missing_end",expectedCanonicalEdge="expected_canonical_edge",providersAttempted="providers_attempted",acceptedImportFormat="accepted_import_format",createdAt="created_at",requestAgeSeconds="request_age_seconds",latestFailure="latest_failure",instrumentLifecycleState="instrument_lifecycle_state",laneCommissioningState="lane_commissioning_state",pauseState="pause_state",providersConsidered="providers_considered",providersRejected="providers_rejected",recommendedOperatorAction="recommended_operator_action",createdProviderFactRevision="created_provider_fact_revision",lastEvaluatedProviderFactRevision="last_evaluated_provider_fact_revision",createdCapabilityProjectionRevision="created_capability_projection_revision",lastEvaluatedCapabilityProjectionRevision="last_evaluated_capability_projection_revision",lastEvaluatedAt="last_evaluated_at",reconciliationStatus="reconciliation_status",reconciliationReason="reconciliation_reason",providersCurrentlyEligible="providers_currently_eligible",providersCurrentlyIneligible="providers_currently_ineligible",replacementQueueIdentifier="replacement_queue_identifier",providersConsideredAtCreation="providers_considered_at_creation",providersAttemptedAtCreation="providers_attempted_at_creation",originalRejectionReasons="original_rejection_reasons"} }

public struct SchedulerPauseRecord:Codable,Equatable,Sendable,Identifiable { public var id:String{pauseIdentifier};public let pauseIdentifier:String;public let scopeType:String;public let scopeIdentifier:String;public let reason:String;public let createdTime:String;public let temporary:Bool;public let relatedIngestionSession:String?;public let status:String;public let activeWorkRemaining:Int;public let resumedTime:String?;enum CodingKeys:String,CodingKey{case reason,temporary,status;case pauseIdentifier="pause_identifier",scopeType="scope_type",scopeIdentifier="scope_identifier",createdTime="created_time",relatedIngestionSession="related_ingestion_session",activeWorkRemaining="active_work_remaining",resumedTime="resumed_time"} }
public struct SchedulerArchivedWork:Codable,Equatable,Sendable,Identifiable { public let id:String;public let kind:String;public let sourceIdentifier:String;public let lane:String;public let reason:String;public let archivedAt:String;public let actionable:Bool;enum CodingKeys:String,CodingKey{case id,kind,lane,reason,actionable;case sourceIdentifier="source_identifier",archivedAt="archived_at"} }
public struct SchedulerUnavailableLane:Codable,Equatable,Sendable,Identifiable { public let id:String;public let symbol:String;public let timeframe:String;public let market:String?;public let latestCanonicalEdge:String?;public let expectedEdge:String?;public let structuredReason:String;public let calendarIdentifier:String?;public let calendarStatus:String?;public let timezone:String?;public let sessionCloseRule:String?;public let calculationTime:String?;public let exactFailureReason:String?;public let lastSuccessfulAcquisition:String?;public let recommendedAction:String;enum CodingKeys:String,CodingKey{case id,symbol,timeframe,market,timezone;case latestCanonicalEdge="latest_canonical_edge",expectedEdge="expected_edge",structuredReason="structured_reason",calendarIdentifier="calendar_identifier",calendarStatus="calendar_status",sessionCloseRule="session_close_rule",calculationTime="calculation_time",exactFailureReason="exact_failure_reason",lastSuccessfulAcquisition="last_successful_acquisition",recommendedAction="recommended_action"} }

public struct SchedulerQueueSummary: Codable, Equatable, Sendable {
    public let totalQueued:Int;public let readyNow:Int;public let running:Int;public let waitingForBudget:Int;public let coolingDown:Int;public let blocked:Int;public let manualRequired:Int;public let oldestQueuedAgeSeconds:Double?;public let oldestReadyAgeSeconds:Double?;public let lastDispatch:String?;public let estimatedClearTimeSeconds:Double?;public let estimatedClearTimeLabel:String
    enum CodingKeys:String,CodingKey{case totalQueued="total_queued",readyNow="ready_now",running,waitingForBudget="waiting_for_budget",coolingDown="cooling_down",blocked,manualRequired="manual_required",oldestQueuedAgeSeconds="oldest_queued_age_seconds",oldestReadyAgeSeconds="oldest_ready_age_seconds",lastDispatch="last_dispatch",estimatedClearTimeSeconds="estimated_clear_time_seconds",estimatedClearTimeLabel="estimated_clear_time_label"}
}

public struct SchedulerDispatchState:Codable,Equatable,Sendable {public let state:String;public let reason:String;public let oldestReadyAgeSeconds:Double?;public let lastDispatchAttempt:String?;public let lastSchedulerLockHolder:String?;public let lastCycleOverrunReason:String?;public let nextWake:String?;public let nextWakeReason:String?;enum CodingKeys:String,CodingKey{case state,reason;case oldestReadyAgeSeconds="oldest_ready_age_seconds",lastDispatchAttempt="last_dispatch_attempt",lastSchedulerLockHolder="last_scheduler_lock_holder",lastCycleOverrunReason="last_cycle_overrun_reason",nextWake="next_wake",nextWakeReason="next_wake_reason"}}

public struct SchedulerThroughputProvider:Codable,Equatable,Sendable,Identifiable {public var id:String{provider};public let provider:String;public let targetUtilizationPercent:Int;public let targetRequestsPerWindow:Int;public let targetRequestsPerMinute:Int;public let currentRequestsPerMinute:Int;public let reservedCapacity:Int;public let availableCapacity:Int;public let healthFactor:Double;public let backoffReason:String?;enum CodingKeys:String,CodingKey{case provider;case targetUtilizationPercent="target_utilization_percent",targetRequestsPerWindow="target_requests_per_window",targetRequestsPerMinute="target_requests_per_minute",currentRequestsPerMinute="current_requests_per_minute",reservedCapacity="reserved_capacity",availableCapacity="available_capacity",healthFactor="health_factor",backoffReason="backoff_reason"}}
public struct SchedulerThroughput:Codable,Equatable,Sendable {public let policy:String;public let policyLabel:String;public let queueDepth:Int;public let pressure:Double;public let oldestQueuedAgeSeconds:Double?;public let targetUtilizationPercent:Int;public let targetRequestsPerMinute:Int;public let currentRequestsPerMinute:Int;public let safeCapacityPerMinute:Int;public let reservedCapacity:Int;public let availableCapacity:Int;public let batchSize:Int;public let estimatedCompletionSeconds:Double?;public let reasons:[String];public let providers:[SchedulerThroughputProvider];enum CodingKeys:String,CodingKey{case policy,pressure,reasons,providers;case policyLabel="policy_label",queueDepth="queue_depth",oldestQueuedAgeSeconds="oldest_queued_age_seconds",targetUtilizationPercent="target_utilization_percent",targetRequestsPerMinute="target_requests_per_minute",currentRequestsPerMinute="current_requests_per_minute",safeCapacityPerMinute="safe_capacity_per_minute",reservedCapacity="reserved_capacity",availableCapacity="available_capacity",batchSize="batch_size",estimatedCompletionSeconds="estimated_completion_seconds"}}

public struct SchedulerActivity: Codable, Equatable, Sendable {
    public let symbol: String
    public let timeframe: String
    public let stage: String
    public let startedAt: String
    public let traceID:String?
    public let attemptNumber:Int?
    enum CodingKeys: String, CodingKey { case symbol, timeframe, stage; case startedAt = "started_at",traceID="trace_id",attemptNumber="attempt_number" }
}

public struct SchedulerTraceSummary:Codable,Equatable,Sendable,Identifiable {
    public var id:String{lane}
    public let lane:String;public let traceID:String?;public let queueAgeSeconds:Double?;public let currentStage:String?;public let lastSuccessfulStage:String?;public let stopReason:String?;public let attemptCount:Int;public let provider:String?;public let canonicalEdgeBefore:String?;public let canonicalEdgeAfter:String?;public let queueDisposition:String?;public let finalLaneState:String?
    enum CodingKeys:String,CodingKey{case lane,provider;case traceID="trace_id",queueAgeSeconds="queue_age_seconds",currentStage="current_stage",lastSuccessfulStage="last_successful_stage",stopReason="stop_reason",attemptCount="attempt_count",canonicalEdgeBefore="canonical_edge_before",canonicalEdgeAfter="canonical_edge_after",queueDisposition="queue_disposition",finalLaneState="final_lane_state"}
}

public struct SchedulerExecution:Codable,Equatable,Sendable {
    public let cycleID:String?;public let startedAt:String?;public let completedAt:String?;public let durationMS:Double?;public let nextIntendedCycle:String?;public let cycleOverrun:Bool?;public let cycleOverrunMS:Double?;public let cycleOverrunReason:String?;public let queueDepthBefore:Int?;public let queueDepthAfter:Int?;public let eligibleCount:Int?;public let selectedCount:Int?;public let dispatchAttemptedCount:Int?;public let workerAllocatedCount:Int?;public let requestStartedCount:Int?;public let requestCompletedCount:Int?;public let canonicalAdvancedCount:Int?;public let queueCompletedCount:Int?;public let oldestQueueAgeAfter:Double?;public let oldestReadyItemAgeSeconds:Double?;public let activeWorkers:Int?;public let providerBudgetRemaining:Int?;public let dispatchableCredits:Int?;public let creditsConsumed:Int?;public let creditsRemaining:Int?;public let dispatchRatePerMinute:Double?;public let workerUtilisation:Double?;public let databaseWaitMS:Double?;public let estateSnapshotDurationMS:Double?;public let publicationDurationMS:Double?;public let lastDispatchAttemptAt:String?;public let lastSchedulerLockHolder:String?;public let noWorkerStartedReason:String?;public let schedulerDispatchSlotsMissedDatabase:Int?;public let throughputLimitedBy:String?;public let requestsFailedByDomain:[String:Int]?;public let traceSummaries:[SchedulerTraceSummary]
    enum CodingKeys:String,CodingKey{case cycleID="cycle_id",startedAt="started_at",completedAt="completed_at",durationMS="duration_ms",nextIntendedCycle="next_intended_cycle",cycleOverrun="cycle_overrun",cycleOverrunMS="cycle_overrun_ms",cycleOverrunReason="cycle_overrun_reason",queueDepthBefore="queue_depth_before",queueDepthAfter="queue_depth_after",eligibleCount="eligible_count",selectedCount="selected_count",dispatchAttemptedCount="dispatch_attempted_count",workerAllocatedCount="worker_allocated_count",requestStartedCount="request_started_count",requestCompletedCount="request_completed_count",canonicalAdvancedCount="canonical_advanced_count",queueCompletedCount="queue_completed_count",oldestQueueAgeAfter="oldest_queue_age_after",oldestReadyItemAgeSeconds="oldest_ready_item_age_seconds",activeWorkers="active_workers",providerBudgetRemaining="provider_budget_remaining",dispatchableCredits="dispatchable_credits",creditsConsumed="credits_consumed",creditsRemaining="credits_remaining",dispatchRatePerMinute="dispatch_rate_per_minute",workerUtilisation="worker_utilisation",databaseWaitMS="database_wait_ms",estateSnapshotDurationMS="estate_snapshot_duration_ms",publicationDurationMS="publication_duration_ms",lastDispatchAttemptAt="last_dispatch_attempt_at",lastSchedulerLockHolder="last_scheduler_lock_holder",noWorkerStartedReason="no_worker_started_reason",schedulerDispatchSlotsMissedDatabase="scheduler_dispatch_slots_missed_database",throughputLimitedBy="throughput_limited_by",requestsFailedByDomain="requests_failed_by_domain",traceSummaries="trace_summaries"}
    public init(from decoder:Decoder)throws{let c=try decoder.container(keyedBy:CodingKeys.self);cycleID=try c.decodeIfPresent(String.self,forKey:.cycleID);startedAt=try c.decodeIfPresent(String.self,forKey:.startedAt);completedAt=try c.decodeIfPresent(String.self,forKey:.completedAt);durationMS=try c.decodeIfPresent(Double.self,forKey:.durationMS);nextIntendedCycle=try c.decodeIfPresent(String.self,forKey:.nextIntendedCycle);cycleOverrun=try c.decodeIfPresent(Bool.self,forKey:.cycleOverrun);cycleOverrunMS=try c.decodeIfPresent(Double.self,forKey:.cycleOverrunMS);cycleOverrunReason=try c.decodeIfPresent(String.self,forKey:.cycleOverrunReason);queueDepthBefore=try c.decodeIfPresent(Int.self,forKey:.queueDepthBefore);queueDepthAfter=try c.decodeIfPresent(Int.self,forKey:.queueDepthAfter);eligibleCount=try c.decodeIfPresent(Int.self,forKey:.eligibleCount);selectedCount=try c.decodeIfPresent(Int.self,forKey:.selectedCount);dispatchAttemptedCount=try c.decodeIfPresent(Int.self,forKey:.dispatchAttemptedCount);workerAllocatedCount=try c.decodeIfPresent(Int.self,forKey:.workerAllocatedCount);requestStartedCount=try c.decodeIfPresent(Int.self,forKey:.requestStartedCount);requestCompletedCount=try c.decodeIfPresent(Int.self,forKey:.requestCompletedCount);canonicalAdvancedCount=try c.decodeIfPresent(Int.self,forKey:.canonicalAdvancedCount);queueCompletedCount=try c.decodeIfPresent(Int.self,forKey:.queueCompletedCount);oldestQueueAgeAfter=try c.decodeIfPresent(Double.self,forKey:.oldestQueueAgeAfter);oldestReadyItemAgeSeconds=try c.decodeIfPresent(Double.self,forKey:.oldestReadyItemAgeSeconds);activeWorkers=try c.decodeIfPresent(Int.self,forKey:.activeWorkers);providerBudgetRemaining=try c.decodeIfPresent(Int.self,forKey:.providerBudgetRemaining);dispatchableCredits=try c.decodeIfPresent(Int.self,forKey:.dispatchableCredits);creditsConsumed=try c.decodeIfPresent(Int.self,forKey:.creditsConsumed);creditsRemaining=try c.decodeIfPresent(Int.self,forKey:.creditsRemaining);dispatchRatePerMinute=try c.decodeIfPresent(Double.self,forKey:.dispatchRatePerMinute);workerUtilisation=try c.decodeIfPresent(Double.self,forKey:.workerUtilisation);databaseWaitMS=try c.decodeIfPresent(Double.self,forKey:.databaseWaitMS);estateSnapshotDurationMS=try c.decodeIfPresent(Double.self,forKey:.estateSnapshotDurationMS);publicationDurationMS=try c.decodeIfPresent(Double.self,forKey:.publicationDurationMS);lastDispatchAttemptAt=try c.decodeIfPresent(String.self,forKey:.lastDispatchAttemptAt);lastSchedulerLockHolder=try c.decodeIfPresent(String.self,forKey:.lastSchedulerLockHolder);noWorkerStartedReason=try c.decodeIfPresent(String.self,forKey:.noWorkerStartedReason);schedulerDispatchSlotsMissedDatabase=try c.decodeIfPresent(Int.self,forKey:.schedulerDispatchSlotsMissedDatabase);throughputLimitedBy=try c.decodeIfPresent(String.self,forKey:.throughputLimitedBy);requestsFailedByDomain=try c.decodeIfPresent([String:Int].self,forKey:.requestsFailedByDomain);traceSummaries=try c.decodeIfPresent([SchedulerTraceSummary].self,forKey:.traceSummaries) ?? []}
}

public enum SchedulerLifecycleStateResolver {
    public static func resolve(
        activeTrace:Bool,queueExists:Bool,queueState:String?,queueHasTrace:Bool,
        queueHasWorker:Bool,stopReason:String?,nextAttempt:String?,
        schedulerState:String?,fallback:String
    )->String {
        if activeTrace{return "Downloading"}
        if queueExists {
            if queueState=="Running",queueHasTrace,queueHasWorker{return "Downloading"}
            if stopReason != nil || nextAttempt != nil{return "Behind"}
            return "Queued"
        }
        if schedulerState=="Current"{return "Current"}
        if schedulerState=="Behind" || schedulerState=="Failed"{return "Behind"}
        return fallback
    }
}

public struct SchedulerEvent: Codable, Equatable, Sendable, Identifiable {
    public let id: String
    public let at: String
    public let symbol: String
    public let timeframe: String
    public let result: String
    public let observations: Int
    public let durationSeconds: Double
    public let reason: String?
    enum CodingKeys: String, CodingKey {
        case id, at, symbol, timeframe, result, observations, reason
        case durationSeconds = "duration_seconds"
    }
}

public struct SchedulerHealthComponent:Codable,Equatable,Sendable {
    public let state:String
    public let lastProgress:String?
    enum CodingKeys:String,CodingKey {case state;case lastProgress="last_progress"}
}
public struct SchedulerHealthHeartbeat:Codable,Equatable,Sendable {public let state:String;public let at:String?;public let ageSeconds:Double?;enum CodingKeys:String,CodingKey{case state,at;case ageSeconds="age_seconds"}}
public struct SchedulerHealthProcess:Codable,Equatable,Sendable {public let state:String}
public struct SchedulerHealthWorkers:Codable,Equatable,Sendable {public let state:String;public let activeWorkers:Int;public let availableWorkers:Int;enum CodingKeys:String,CodingKey{case state;case activeWorkers="active_workers",availableWorkers="available_workers"}}
public struct SchedulerMonitorTransport:Codable,Equatable,Sendable {public let state:String}
public struct SchedulerOperationalHealth:Codable,Equatable,Sendable {
    public let contract:String
    public let overallOperationalHealth:String
    public let process:SchedulerHealthProcess
    public let heartbeat:SchedulerHealthHeartbeat
    public let monitorTransport:SchedulerMonitorTransport
    public let selectionLoop:SchedulerHealthComponent
    public let workerPool:SchedulerHealthWorkers
    public let providerDispatch:SchedulerHealthComponent
    public let providerResponse:SchedulerHealthComponent
    public let evidenceAdmission:SchedulerHealthComponent
    public let publication:SchedulerHealthComponent
    public let queueProgress:SchedulerHealthComponent
    public let actionableQueueDepth:Int
    public let blockedQueueDepth:Int
    public let totalQueueDepth:Int
    public let oldestActionableAgeSeconds:Double?
    public let lastMeaningfulProgress:String?
    public let permittedProgressWindowSeconds:Double?
    public let currentTraceID:String?
    public let currentLane:String?
    public let currentStage:String?
    public let currentStopReason:String?
    enum CodingKeys:String,CodingKey {case contract,process,heartbeat,publication;case overallOperationalHealth="overall_operational_health",monitorTransport="monitor_transport",selectionLoop="selection_loop",workerPool="worker_pool",providerDispatch="provider_dispatch",providerResponse="provider_response",evidenceAdmission="evidence_admission",queueProgress="queue_progress",actionableQueueDepth="actionable_queue_depth",blockedQueueDepth="blocked_queue_depth",totalQueueDepth="total_queue_depth",oldestActionableAgeSeconds="oldest_actionable_age_seconds",lastMeaningfulProgress="last_meaningful_progress",permittedProgressWindowSeconds="permitted_progress_window_seconds",currentTraceID="current_trace_id",currentLane="current_lane",currentStage="current_stage",currentStopReason="current_stop_reason"}
}
public struct SchedulerEstateAudit:Codable,Equatable,Sendable {
    public let contract:String
    public let state:String
    public let auditRunID:String?
    public let trigger:String?
    public let startedAtUTC:String?
    public let completedAtUTC:String?
    public let overallResult:String?
    public let findingCounts:[String:Int]?
    public let repairPlanID:String?
    public let reportBytes:Int?
    public let nextWeeklyAuditAtUTC:String?
    enum CodingKeys:String,CodingKey {case contract,state,trigger;case auditRunID="audit_run_id",startedAtUTC="started_at_utc",completedAtUTC="completed_at_utc",overallResult="overall_result",findingCounts="finding_counts",repairPlanID="repair_plan_id",reportBytes="report_bytes",nextWeeklyAuditAtUTC="next_weekly_audit_at_utc"}
}

public struct SchedulerRequiredSetFailure:Codable,Equatable,Sendable,Identifiable {
    public var id:String{"\(timeframe):\(outcome):\(reason ?? "")"}
    public let timeframe:String
    public let outcome:String
    public let reason:String?
}
public struct SchedulerRequiredSetProgress:Codable,Equatable,Sendable,Identifiable { public var id:String{"\(at):\(stage)"};public let at:String;public let stage:String;public let currentLanes:[String];public let completedLanes:[String];public let blockedLanes:[String];public let failedLanes:[String];public let provider:String?;public let publicationState:String?;enum CodingKeys:String,CodingKey{case at,stage,provider;case currentLanes="current_lanes",completedLanes="completed_lanes",blockedLanes="blocked_lanes",failedLanes="failed_lanes",publicationState="publication_state"} }
public struct SchedulerRequiredSetJob:Codable,Equatable,Sendable,Identifiable {
    public let id:String
    public let symbol:String?
    public let assetClass:String?
    public let status:String?
    public let currentLane:String?
    public let completedLanes:[String]
    public let remainingLanes:[String]
    public let partialFailures:[SchedulerRequiredSetFailure]
    public let providerUsed:[String]
    public let lastPublishedEdge:[String:String]
    public let progressTimeline:[SchedulerRequiredSetProgress]
    enum CodingKeys:String,CodingKey {case id,symbol,status;case assetClass="asset_class",currentLane="current_lane",completedLanes="completed_lanes",remainingLanes="remaining_lanes",partialFailures="partial_failures",providerUsed="provider_used",lastPublishedEdge="last_published_edge",progressTimeline="progress_timeline"}
    public init(from decoder:Decoder)throws{let c=try decoder.container(keyedBy:CodingKeys.self);id=try c.decode(String.self,forKey:.id);symbol=try c.decodeIfPresent(String.self,forKey:.symbol);assetClass=try c.decodeIfPresent(String.self,forKey:.assetClass);status=try c.decodeIfPresent(String.self,forKey:.status);currentLane=try c.decodeIfPresent(String.self,forKey:.currentLane);completedLanes=try c.decodeIfPresent([String].self,forKey:.completedLanes) ?? [];remainingLanes=try c.decodeIfPresent([String].self,forKey:.remainingLanes) ?? [];partialFailures=try c.decodeIfPresent([SchedulerRequiredSetFailure].self,forKey:.partialFailures) ?? [];providerUsed=try c.decodeIfPresent([String].self,forKey:.providerUsed) ?? [];lastPublishedEdge=try c.decodeIfPresent([String:String].self,forKey:.lastPublishedEdge) ?? [:];progressTimeline=try c.decodeIfPresent([SchedulerRequiredSetProgress].self,forKey:.progressTimeline) ?? []}
}

public struct SchedulerSnapshot: Codable, Equatable, Sendable {
    public let contract: String
    public let generatedAt: String
    public let serviceState: String
    public let authorityHealth: SchedulerAuthorityHealth
    public let authorityRevision: String
    public let summary: SchedulerSummary
    public let nextRun: String?
    public let lastSuccessfulAcquisition: String?
    public let lastFailure: String?
    public let activeActivity: SchedulerActivity?
    public let lanes: [SchedulerLane]
    public let events: [SchedulerEvent]
    public let providers:[SchedulerProvider]
    public let rateBudgets:[SchedulerRateBudget]
    public let acquisitionQueue:[SchedulerQueueItem]
    public let routingDecisions:[SchedulerRoutingDecision]
    public let manualRequests:[SchedulerManualRequest]
    public let manualRequestHistory:[SchedulerManualRequest]
    public let schedulerPolicy:String
    public let schedulerPolicyKey:String
    public let throughput:SchedulerThroughput?
    public let queueSummary:SchedulerQueueSummary?
    public let dispatchState:SchedulerDispatchState?
    public let execution:SchedulerExecution?
    public let activeUniverseRevision:String?
    public let pauseRecords:[SchedulerPauseRecord]
    public let archivedOperationalWork:[SchedulerArchivedWork]
    public let unavailableLaneDetails:[SchedulerUnavailableLane]
    public let exceptionFilters:[String:[String]]
    public let manualRequestCount:Int
    public let manualRequestUniqueLanes:Int
    public let manualRequestUniqueSymbols:Int
    public let requestLifecycleCounts:[String:Int]
    public let operationalHealth:SchedulerOperationalHealth?
    public let requiredSetActiveJob:SchedulerRequiredSetJob?
    enum CodingKeys: String, CodingKey {
        case contract, summary, lanes, events, providers
        case generatedAt = "generated_at", serviceState = "service_state"
        case authorityHealth = "authority_health", authorityRevision = "authority_revision"
        case nextRun = "next_run", lastSuccessfulAcquisition = "last_successful_acquisition"
        case lastFailure = "last_failure", activeActivity = "active_activity"
        case rateBudgets="rate_budgets",acquisitionQueue="acquisition_queue",routingDecisions="routing_decisions",manualRequests="manual_requests",manualRequestHistory="manual_request_history",schedulerPolicy="scheduler_policy",schedulerPolicyKey="scheduler_policy_key",throughput,queueSummary="queue_summary",dispatchState="dispatch_state",execution
        case activeUniverseRevision="active_universe_revision",pauseRecords="pause_records",archivedOperationalWork="archived_operational_work",unavailableLaneDetails="unavailable_lane_details",exceptionFilters="exception_filters",manualRequestCount="manual_request_count",manualRequestUniqueLanes="manual_request_unique_lanes",manualRequestUniqueSymbols="manual_request_unique_symbols",requestLifecycleCounts="request_lifecycle_counts",operationalHealth="operational_health",requiredSetActiveJob="required_set_active_job"
    }
    public init(from decoder:Decoder)throws{let c=try decoder.container(keyedBy:CodingKeys.self);contract=try c.decode(String.self,forKey:.contract);generatedAt=try c.decode(String.self,forKey:.generatedAt);serviceState=try c.decode(String.self,forKey:.serviceState);authorityHealth=try c.decode(SchedulerAuthorityHealth.self,forKey:.authorityHealth);authorityRevision=try c.decode(String.self,forKey:.authorityRevision);summary=try c.decode(SchedulerSummary.self,forKey:.summary);nextRun=try c.decodeIfPresent(String.self,forKey:.nextRun);lastSuccessfulAcquisition=try c.decodeIfPresent(String.self,forKey:.lastSuccessfulAcquisition);lastFailure=try c.decodeIfPresent(String.self,forKey:.lastFailure);activeActivity=try c.decodeIfPresent(SchedulerActivity.self,forKey:.activeActivity);lanes=try c.decode([SchedulerLane].self,forKey:.lanes);events=try c.decodeIfPresent([SchedulerEvent].self,forKey:.events) ?? [];providers=try c.decodeIfPresent([SchedulerProvider].self,forKey:.providers) ?? [];rateBudgets=try c.decodeIfPresent([SchedulerRateBudget].self,forKey:.rateBudgets) ?? [];acquisitionQueue=try c.decodeIfPresent([SchedulerQueueItem].self,forKey:.acquisitionQueue) ?? [];routingDecisions=try c.decodeIfPresent([SchedulerRoutingDecision].self,forKey:.routingDecisions) ?? [];manualRequests=try c.decodeIfPresent([SchedulerManualRequest].self,forKey:.manualRequests) ?? [];manualRequestHistory=try c.decodeIfPresent([SchedulerManualRequest].self,forKey:.manualRequestHistory) ?? manualRequests;schedulerPolicy=try c.decodeIfPresent(String.self,forKey:.schedulerPolicy) ?? "Balanced";schedulerPolicyKey=try c.decodeIfPresent(String.self,forKey:.schedulerPolicyKey) ?? "BALANCED";throughput=try c.decodeIfPresent(SchedulerThroughput.self,forKey:.throughput);queueSummary=try c.decodeIfPresent(SchedulerQueueSummary.self,forKey:.queueSummary);dispatchState=try c.decodeIfPresent(SchedulerDispatchState.self,forKey:.dispatchState);execution=try c.decodeIfPresent(SchedulerExecution.self,forKey:.execution);activeUniverseRevision=try c.decodeIfPresent(String.self,forKey:.activeUniverseRevision);pauseRecords=try c.decodeIfPresent([SchedulerPauseRecord].self,forKey:.pauseRecords) ?? [];archivedOperationalWork=try c.decodeIfPresent([SchedulerArchivedWork].self,forKey:.archivedOperationalWork) ?? [];unavailableLaneDetails=try c.decodeIfPresent([SchedulerUnavailableLane].self,forKey:.unavailableLaneDetails) ?? [];exceptionFilters=try c.decodeIfPresent([String:[String]].self,forKey:.exceptionFilters) ?? [:];manualRequestCount=try c.decodeIfPresent(Int.self,forKey:.manualRequestCount) ?? manualRequests.count;manualRequestUniqueLanes=try c.decodeIfPresent(Int.self,forKey:.manualRequestUniqueLanes) ?? Set(manualRequests.map{"\($0.symbol):\($0.timeframe)"}).count;manualRequestUniqueSymbols=try c.decodeIfPresent(Int.self,forKey:.manualRequestUniqueSymbols) ?? Set(manualRequests.map(\.symbol)).count;requestLifecycleCounts=try c.decodeIfPresent([String:Int].self,forKey:.requestLifecycleCounts) ?? [:];operationalHealth=try c.decodeIfPresent(SchedulerOperationalHealth.self,forKey:.operationalHealth);requiredSetActiveJob=try c.decodeIfPresent(SchedulerRequiredSetJob.self,forKey:.requiredSetActiveJob)}
}

public struct SchedulerServiceMutation:Codable,Equatable,Sendable,Identifiable {
    public var id:String{operationID}
    public let operationID:String
    public let operationType:String
    public let status:String
    public let requestedAt:String?
    public let startedAt:String?
    public let lastProgressAt:String?
    public let completedAt:String?
    public let requestingAppBuild:String?
    public let requestingAppInstance:String?
    public let targetServiceGeneration:String?
    public let currentStage:String
    public let progressMessage:String
    public let failureCode:String?
    public let failureDetail:String?
    public let cancellable:Bool
    enum CodingKeys:String,CodingKey {
        case status,cancellable
        case operationID="operation_id",operationType="operation_type",requestedAt="requested_at",startedAt="started_at",lastProgressAt="last_progress_at",completedAt="completed_at",requestingAppBuild="requesting_app_build",requestingAppInstance="requesting_app_instance",targetServiceGeneration="target_service_generation",currentStage="current_stage",progressMessage="progress_message",failureCode="failure_code",failureDetail="failure_detail"
    }
}

public struct SchedulerMutationFailure:Codable,Equatable,Sendable {public let code:String?;public let detail:String?}

public struct SchedulerUpdateRegister:Codable,Equatable,Sendable {
    public let contract:String?
    public let nextDueCheck:String?
    public let readyCount:Int?
    public let retryingCount:Int?
    public let blockedCount:Int?
    public let pausedCount:Int?
    public let runningCount:Int?
    public let dueNowCount:Int?
    enum CodingKeys:String,CodingKey {case contract;case nextDueCheck="next_due_check",readyCount="ready_count",retryingCount="retrying_count",blockedCount="blocked_count",pausedCount="paused_count",runningCount="running_count",dueNowCount="due_now_count"}
}

public struct SchedulerUpdateRegisterLane:Codable,Equatable,Sendable,Identifiable {
    public var id:String{"\(asset):\(timeframe)"}
    public let asset:String
    public let timeframe:String
    public let state:String
    public let nextExpectedBoundaryUTC:String?
    public let nextCheckAtUTC:String?
    public let lastOutcome:String?
    public let retryCount:Int?
    public let retryNotBeforeUTC:String?
    enum CodingKeys:String,CodingKey {case asset,timeframe,state;case nextExpectedBoundaryUTC="next_expected_boundary_utc",nextCheckAtUTC="next_check_at_utc",lastOutcome="last_outcome",retryCount="retry_count",retryNotBeforeUTC="retry_not_before_utc"}
}

public struct SchedulerDiagnosticCheck:Codable,Equatable,Sendable,Identifiable {
    public var id:String{check}
    public let check:String
    public let passed:Bool
    public let failureCode:String?
    public let explanation:String?
    public let recommendedRepair:String?
    enum CodingKeys:String,CodingKey {case check,passed,explanation;case failureCode="failure_code",recommendedRepair="recommended_repair"}
}

public struct SchedulerServiceDiagnostics:Codable,Equatable,Sendable {
    public let contract:String
    public let generatedAt:String
    public let serviceGeneration:String?
    public let activeMutation:SchedulerServiceMutation?
    public let mutationAgeSeconds:Double?
    public let checks:[SchedulerDiagnosticCheck]
    public let credentialsIncluded:Bool
    enum CodingKeys:String,CodingKey {case contract,checks;case generatedAt="generated_at",serviceGeneration="service_generation",activeMutation="active_mutation",mutationAgeSeconds="mutation_age_seconds",credentialsIncluded="credentials_included"}
}

public struct SchedulerServiceStatus:Codable,Equatable,Sendable {
    public let contract:String
    public let serviceState:String
    public let installed:Bool
    public let live:Bool
    public let serviceBuild:String?
    public let runningBuild:String?
    public let serviceInstance:String?
    public let serviceGeneration:String?
    public let serviceStartTime:String?
    public let heartbeatTime:String?
    public let lastSuccessfulMonitorUpdate:String?
    public let compatibility:String
    public let restartCount:Int
    public let lastExitReason:String?
    public let serviceLocation:String?
    public let authorityDatabase:String?
    public let operationalJournal:String?
    public let automaticLoginStart:Bool
    public let credentialSource:String?
    public let activeMutation:SchedulerServiceMutation?
    public let lastMutation:SchedulerServiceMutation?
    public let mutationStatus:String?
    public let mutationStage:String?
    public let mutationStartedAt:String?
    public let mutationLastProgressAt:String?
    public let mutationCancellable:Bool
    public let mutationFailure:SchedulerMutationFailure?
    public let reconciliationStatus:String?
    public let recommendedActions:[String]
    public let acquisitionOwnerActive:Bool
    public let operationalHealth:SchedulerOperationalHealth?
    public let audit:SchedulerEstateAudit?
    public let schedulerMode:String?
    public let authorityRevision:String?
    public let authorityChangeToken:String?
    public let nextDueCheck:String?
    public let register:SchedulerUpdateRegister?
    public let scheduleDashboard:[SchedulerUpdateRegisterLane]
    public let schedulerPolicy:String?
    public let schedulerPolicyKey:String?
    enum CodingKeys:String,CodingKey {
        case contract,installed,live,compatibility
        case serviceState="service_state",serviceBuild="service_build",runningBuild="running_build",serviceInstance="service_instance",serviceGeneration="service_generation",serviceStartTime="service_start_time",heartbeatTime="heartbeat_time",lastSuccessfulMonitorUpdate="last_successful_monitor_update",restartCount="restart_count",lastExitReason="last_exit_reason",serviceLocation="service_location",authorityDatabase="authority_database",operationalJournal="operational_journal",automaticLoginStart="automatic_login_start",credentialSource="credential_source",activeMutation="active_mutation",lastMutation="last_mutation",mutationStatus="mutation_status",mutationStage="mutation_stage",mutationStartedAt="mutation_started_at",mutationLastProgressAt="mutation_last_progress_at",mutationCancellable="mutation_cancellable",mutationFailure="mutation_failure",reconciliationStatus="reconciliation_status",recommendedActions="recommended_actions",acquisitionOwnerActive="acquisition_owner_active",operationalHealth="operational_health",audit,schedulerMode="scheduler_mode",authorityRevision="authority_revision",authorityChangeToken="authority_change_token",nextDueCheck="next_due_check",register,scheduleDashboard="schedule_dashboard",schedulerPolicy="scheduler_policy",schedulerPolicyKey="scheduler_policy_key"
    }
    public init(from decoder:Decoder)throws {
        let c=try decoder.container(keyedBy:CodingKeys.self)
        contract=try c.decodeIfPresent(String.self,forKey:.contract) ?? "fragarach_ii.scheduler_service_status.v1"
        serviceState=try c.decodeIfPresent(String.self,forKey:.serviceState) ?? "UNREACHABLE"
        installed=try c.decodeIfPresent(Bool.self,forKey:.installed) ?? (serviceState != "NOT_INSTALLED")
        live=try c.decodeIfPresent(Bool.self,forKey:.live) ?? false
        serviceBuild=try c.decodeIfPresent(String.self,forKey:.serviceBuild)
        runningBuild=try c.decodeIfPresent(String.self,forKey:.runningBuild)
        serviceInstance=try c.decodeIfPresent(String.self,forKey:.serviceInstance)
        serviceGeneration=try c.decodeIfPresent(String.self,forKey:.serviceGeneration)
        serviceStartTime=try c.decodeIfPresent(String.self,forKey:.serviceStartTime)
        heartbeatTime=try c.decodeIfPresent(String.self,forKey:.heartbeatTime)
        lastSuccessfulMonitorUpdate=try c.decodeIfPresent(String.self,forKey:.lastSuccessfulMonitorUpdate)
        compatibility=try c.decodeIfPresent(String.self,forKey:.compatibility) ?? "Compatible"
        restartCount=try c.decodeIfPresent(Int.self,forKey:.restartCount) ?? 0
        lastExitReason=try c.decodeIfPresent(String.self,forKey:.lastExitReason)
        serviceLocation=try c.decodeIfPresent(String.self,forKey:.serviceLocation)
        authorityDatabase=try c.decodeIfPresent(String.self,forKey:.authorityDatabase)
        operationalJournal=try c.decodeIfPresent(String.self,forKey:.operationalJournal)
        automaticLoginStart=try c.decodeIfPresent(Bool.self,forKey:.automaticLoginStart) ?? false
        credentialSource=try c.decodeIfPresent(String.self,forKey:.credentialSource)
        activeMutation=try c.decodeIfPresent(SchedulerServiceMutation.self,forKey:.activeMutation)
        lastMutation=try c.decodeIfPresent(SchedulerServiceMutation.self,forKey:.lastMutation)
        mutationStatus=try c.decodeIfPresent(String.self,forKey:.mutationStatus)
        mutationStage=try c.decodeIfPresent(String.self,forKey:.mutationStage)
        mutationStartedAt=try c.decodeIfPresent(String.self,forKey:.mutationStartedAt)
        mutationLastProgressAt=try c.decodeIfPresent(String.self,forKey:.mutationLastProgressAt)
        mutationCancellable=try c.decodeIfPresent(Bool.self,forKey:.mutationCancellable) ?? false
        mutationFailure=try c.decodeIfPresent(SchedulerMutationFailure.self,forKey:.mutationFailure)
        reconciliationStatus=try c.decodeIfPresent(String.self,forKey:.reconciliationStatus)
        recommendedActions=try c.decodeIfPresent([String].self,forKey:.recommendedActions) ?? []
        acquisitionOwnerActive=try c.decodeIfPresent(Bool.self,forKey:.acquisitionOwnerActive) ?? false
        operationalHealth=try c.decodeIfPresent(SchedulerOperationalHealth.self,forKey:.operationalHealth)
        audit=try c.decodeIfPresent(SchedulerEstateAudit.self,forKey:.audit)
        schedulerMode=try c.decodeIfPresent(String.self,forKey:.schedulerMode)
        authorityRevision=try c.decodeIfPresent(String.self,forKey:.authorityRevision)
        authorityChangeToken=try c.decodeIfPresent(String.self,forKey:.authorityChangeToken)
        nextDueCheck=try c.decodeIfPresent(String.self,forKey:.nextDueCheck)
        register=try c.decodeIfPresent(SchedulerUpdateRegister.self,forKey:.register)
        scheduleDashboard=try c.decodeIfPresent([SchedulerUpdateRegisterLane].self,forKey:.scheduleDashboard) ?? []
        schedulerPolicy=try c.decodeIfPresent(String.self,forKey:.schedulerPolicy)
        schedulerPolicyKey=try c.decodeIfPresent(String.self,forKey:.schedulerPolicyKey)
    }
}

public struct ProviderFactProbeResult:Codable,Equatable,Sendable { public let outcome:String;public let requestedRows:Int;public let closedRows:Int;public let openRowsExcluded:Int;public let responseChecksum:String;public let apiCreditsUsed:Int?;public let apiCreditsLeft:Int?;public let canonicalPublication:String;public let samplePriceRange:[String:String]?;enum CodingKeys:String,CodingKey{case outcome;case requestedRows="requested_rows",closedRows="closed_rows",openRowsExcluded="open_rows_excluded",responseChecksum="response_checksum",apiCreditsUsed="api_credits_used",apiCreditsLeft="api_credits_left",canonicalPublication="canonical_publication",samplePriceRange="sample_price_range"} }
public struct ProviderTimeframeFact:Codable,Equatable,Sendable,Identifiable { public var id:String{timeframe};public let timeframe:String;public let providerInterval:String;public let supported:Bool;public let historyAvailability:String;public let maximumRows:Int;public let fragarachRequestCeiling:Int;public let entitlement:String;public let lastVerified:String;public let verificationMethod:String;public let reason:String;public let probeResult:ProviderFactProbeResult?;enum CodingKeys:String,CodingKey{case timeframe,supported,entitlement,reason;case providerInterval="provider_interval",historyAvailability="history_availability",maximumRows="maximum_rows",fragarachRequestCeiling="fragarach_request_ceiling",lastVerified="last_verified",verificationMethod="verification_method",probeResult="probe_result"} }
public struct ProviderFactCandidate:Codable,Equatable,Sendable,Identifiable { public var id:String{providerSymbol};public let providerSymbol:String;public let providerDescription:String;public let providerInstrumentType:String;public let providerAssetClass:String;public let providerBaseAsset:String?;public let providerQuoteAsset:String?;public let venueOrMarket:String;public let marketCategory:String;public let supportedIntervals:[String];public let samplePriceRange:[String:String]?;public let mappingClassification:String;enum CodingKeys:String,CodingKey{case providerSymbol="provider_symbol",providerDescription="provider_description",providerInstrumentType="provider_instrument_type",providerAssetClass="provider_asset_class",providerBaseAsset="provider_base_asset",providerQuoteAsset="provider_quote_asset",venueOrMarket="venue_or_market",marketCategory="market_category",supportedIntervals="supported_intervals",samplePriceRange="sample_price_range",mappingClassification="mapping_classification"} }
public struct ProviderResolutionEvidence:Codable,Equatable,Sendable { public let providerResponseTime:String?;public let responseChecksums:[String];public let apiCreditsUsed:Int?;public let apiUsageAccounting:String?;public let priorApprovedMapping:[String:String]?;enum CodingKeys:String,CodingKey{case providerResponseTime="provider_response_time",responseChecksums="response_checksums",apiCreditsUsed="api_credits_used",apiUsageAccounting="api_usage_accounting",priorApprovedMapping="prior_approved_mapping"} }
public struct ProviderFactMapping:Codable,Equatable,Sendable,Identifiable { public var id:String{"\(provider):\(canonicalSymbol)"};public let canonicalSymbol:String;public let canonicalBaseAsset:String?;public let canonicalQuoteAsset:String?;public let canonicalInstrumentType:String?;public let provider:String;public let providerSymbol:String?;public let providerDescription:String?;public let providerInstrumentType:String?;public let providerAssetClass:String?;public let providerBaseAsset:String?;public let providerQuoteAsset:String?;public let venueOrMarket:String?;public let mappingClass:String?;public let resolutionMethod:String;public let matchingRule:String?;public let status:String;public let reason:String?;public let effectiveTime:String;public let lastVerified:String;public let timeframeCapabilities:[String:ProviderTimeframeFact];public let capabilityProbeResult:ProviderFactProbeResult?;public let resolutionEvidence:ProviderResolutionEvidence;public let candidates:[ProviderFactCandidate];public let availableActions:[String]?;enum CodingKeys:String,CodingKey{case provider,status,reason,candidates;case canonicalSymbol="canonical_symbol",canonicalBaseAsset="canonical_base_asset",canonicalQuoteAsset="canonical_quote_asset",canonicalInstrumentType="canonical_instrument_type",providerSymbol="provider_symbol",providerDescription="provider_description",providerInstrumentType="provider_instrument_type",providerAssetClass="provider_asset_class",providerBaseAsset="provider_base_asset",providerQuoteAsset="provider_quote_asset",venueOrMarket="venue_or_market",mappingClass="mapping_class",resolutionMethod="resolution_method",matchingRule="matching_rule",effectiveTime="effective_time",lastVerified="last_verified",timeframeCapabilities="timeframe_capabilities",capabilityProbeResult="capability_probe_result",resolutionEvidence="resolution_evidence",availableActions="available_actions"} }
public struct ProviderFactIssue:Codable,Equatable,Sendable,Identifiable { public var id:String{"\(outcome):\(canonicalSymbol ?? provider ?? reason)"};public let canonicalSymbol:String?;public let provider:String?;public let outcome:String;public let reason:String;public let lastAttempt:String?;public let availableActions:[String];public let whatWasTried:[String]?;public let automaticNextAction:String?;public let operatorAction:String?;public let preservation:String?;enum CodingKeys:String,CodingKey{case provider,outcome,reason,preservation;case canonicalSymbol="canonical_symbol",lastAttempt="last_attempt",availableActions="available_actions",whatWasTried="what_was_tried",automaticNextAction="automatic_next_action",operatorAction="operator_action"} }
public struct ProviderFactsReconciliation:Codable,Equatable,Sendable { public let laneRowsOriginallyFlagged:Int;public let retiredRowsRemoved:Int;public let representationMappingsAutomaticallyResolved:Int;public let timeframeCapabilitiesVerified:Int;public let credentialAccessFailures:Int;public let providerLookupFailures:Int;public let genuineOperatorDecisionsRemaining:Int;public let decisionKeys:[String];enum CodingKeys:String,CodingKey{case laneRowsOriginallyFlagged="lane_rows_originally_flagged",retiredRowsRemoved="retired_rows_removed",representationMappingsAutomaticallyResolved="representation_mappings_automatically_resolved",timeframeCapabilitiesVerified="timeframe_capabilities_verified",credentialAccessFailures="credential_access_failures",providerLookupFailures="provider_lookup_failures",genuineOperatorDecisionsRemaining="genuine_operator_decisions_remaining",decisionKeys="decision_keys"} }
public struct ProviderFactsSnapshot:Codable,Equatable,Sendable { public let contract:String;public let resolverVersion:Int;public let revision:Int?;public let capabilityProjectionRevision:Int?;public let generatedAt:String;public let credentialState:String;public let resolvedAutomatically:[ProviderFactMapping];public let needsMaterialReview:[ProviderFactMapping];public let credentialOrAccessIssue:ProviderFactIssue?;public let providerLookupFailed:[ProviderFactIssue];public let retiredNonActionable:[ProviderFactIssue];public let reconciliation:ProviderFactsReconciliation?;enum CodingKeys:String,CodingKey{case contract,reconciliation,revision;case resolverVersion="resolver_version",capabilityProjectionRevision="capability_projection_revision",generatedAt="generated_at",credentialState="credential_state",resolvedAutomatically="resolved_automatically",needsMaterialReview="needs_material_review",credentialOrAccessIssue="credential_or_access_issue",providerLookupFailed="provider_lookup_failed",retiredNonActionable="retired_non_actionable"} }
public struct ProviderCapabilityProbe:Codable,Equatable,Sendable { public let contract:String;public let canonicalSymbol:String;public let provider:String;public let providerSymbol:String;public let timeframe:String;public let providerInterval:String;public let supported:Bool;public let historyAvailability:String;public let maximumRows:Int;public let fragarachRequestCeiling:Int;public let entitlement:String;public let lastVerified:String;public let verificationMethod:String;public let reason:String;public let probeResult:ProviderFactProbeResult;enum CodingKeys:String,CodingKey{case contract,provider,timeframe,supported,entitlement,reason;case canonicalSymbol="canonical_symbol",providerSymbol="provider_symbol",providerInterval="provider_interval",historyAvailability="history_availability",maximumRows="maximum_rows",fragarachRequestCeiling="fragarach_request_ceiling",lastVerified="last_verified",verificationMethod="verification_method",probeResult="probe_result"} }

public enum ConsoleSection: String, CaseIterable, Identifiable, Sendable {
    case overview = "Overview", estate = "Estate", scheduler = "Scheduler", history = "History", manageData = "Manage Data"
    public var id: String { rawValue }
    public var icon: String {
        switch self { case .overview: "gauge.with.dots.needle.50percent"; case .estate: "checkmark.seal"; case .scheduler: "calendar.badge.clock"; case .history: "clock.arrow.circlepath"; case .manageData: "externaldrive.badge.plus" }
    }
}

public enum DataOperationsMode: String, CaseIterable, Identifiable, Hashable, Sendable { case fetch="Fetch / Update",importFile="Import File",retire="Retire",history="History";public var id:String{rawValue} }
public enum SystemSection: String, CaseIterable, Identifiable, Hashable, Sendable { case status="Status",providerFacts="Provider Facts",backups="Backups",settings="Settings",audit="Audit";public var id:String{rawValue} }
public enum ManageDataSection: String, CaseIterable, Identifiable, Hashable, Sendable { case discover="Discover",operations="Acquire & Import",system="System";public var id:String{rawValue} }
public enum LegacyRoute: String, Sendable { case lanes,authorityLedger,operations,integrityBackup,settings,acquire,importEvidence }
public struct NavigationDestination:Equatable,Sendable { public let workspace:ConsoleSection;public let dataMode:DataOperationsMode?;public let systemSection:SystemSection?;public let manageDataSection:ManageDataSection?;public init(workspace:ConsoleSection,dataMode:DataOperationsMode?,systemSection:SystemSection?,manageDataSection:ManageDataSection?=nil){self.workspace=workspace;self.dataMode=dataMode;self.systemSection=systemSection;self.manageDataSection=manageDataSection} }
public enum NavigationRedirect {
    public static func destination(for route:LegacyRoute)->NavigationDestination { switch route {
    case .lanes:return .init(workspace:.estate,dataMode:nil,systemSection:nil)
    case .authorityLedger:return .init(workspace:.manageData,dataMode:nil,systemSection:.audit,manageDataSection:.system)
    case .operations:return .init(workspace:.manageData,dataMode:.history,systemSection:nil,manageDataSection:.operations)
    case .integrityBackup:return .init(workspace:.manageData,dataMode:nil,systemSection:.backups,manageDataSection:.system)
    case .settings:return .init(workspace:.manageData,dataMode:nil,systemSection:.settings,manageDataSection:.system)
    case .acquire:return .init(workspace:.manageData,dataMode:.fetch,systemSection:nil,manageDataSection:.operations)
    case .importEvidence:return .init(workspace:.manageData,dataMode:.importFile,systemSection:nil,manageDataSection:.operations)
    } }
}

public enum ConflictMode: String, CaseIterable, Sendable { case preserve, correct }
public enum AcquisitionIntent: String, Equatable, Sendable { case initial,update,force,custom }

public enum DataOperationState: String, Equatable, Sendable {
    case idle
    case preparing
    case reading
    case requestingHistory = "requesting"
    case planning
    case waitingForBudget = "waiting_for_budget"
    case contactingProvider = "contacting_provider"
    case responseReceived = "response_received"
    case failedOver = "failed_over"
    case publishing
    case manualEvidenceRequired = "manual_evidence_required"
    case acquiringEarlierHistory = "acquiring_earlier"
    case validating
    case ingesting
    case refreshingAuthority
    case completed
    case failed

    public var isActive: Bool {
        switch self {
        case .preparing, .reading, .requestingHistory, .planning, .waitingForBudget, .contactingProvider, .responseReceived, .failedOver, .publishing, .manualEvidenceRequired, .acquiringEarlierHistory, .validating, .ingesting, .refreshingAuthority: true
        case .idle, .completed, .failed: false
        }
    }

    public var stageLabel: String {
        switch self {
        case .idle: "Ready"
        case .preparing: "Preparing operation"
        case .reading: "Reading file"
        case .requestingHistory: "Requesting history"
        case .planning: "Planning provider fallback"
        case .waitingForBudget: "Waiting for provider budget"
        case .contactingProvider: "Contacting provider"
        case .responseReceived: "Provider response received"
        case .failedOver: "Trying the next eligible provider"
        case .publishing: "Publishing immutable evidence"
        case .manualEvidenceRequired: "Manual evidence required"
        case .acquiringEarlierHistory: "Acquiring earlier history"
        case .validating: "Validating observations"
        case .ingesting: "Writing history"
        case .refreshingAuthority: "Refreshing authority"
        case .completed: "Operation complete"
        case .failed: "Operation failed"
        }
    }
}

public struct ActiveDataOperation: Equatable, Sendable {
    public let id: UUID
    public let instrument: String
    public let timeframe: String
    public let actionLabel: String
    public init(id: UUID, instrument: String, timeframe: String, actionLabel: String) {
        self.id=id;self.instrument=instrument;self.timeframe=timeframe;self.actionLabel=actionLabel
    }
}

public enum OperationIntent: Equatable, Sendable {
    case readEstateTruth
    case readTruth(symbol: String, timeframe: String)
    case marketHistory(symbol: String, timeframe: String, tradingDays: Int)
    case resolveInstrument(query: String)
    case discoverMarket(query: String)
    case searchInstrument(query: String)
    case readProviderFacts
    case resolveProviderFacts(symbol:String?)
    case probeProviderCapability(symbol:String,timeframe:String)
    case recordProviderMappingDecision(symbol:String,decision:String,candidate:String)
    case registerInstrument(candidate: String)
    case retirementPlan(asset:String,scope:String,lanes:[String])
    case retireInstrument(asset:String,scope:String,lanes:[String],reason:String,note:String,confirmation:String)
    case reactivateInstrument(asset:String)
    case permanentRemovalPlan(asset:String)
    case permanentlyRemoveInstrument(asset:String,confirmation:String)
    case acquire(asset: String,timeframe:String,from: String, through: String, mode: ConflictMode)
    case acquireInitial(asset:String,timeframe:String,from:String,through:String,mode:ConflictMode)
    case acquireUpdate(asset:String,timeframe:String,from:String,through:String,mode:ConflictMode)
    case acquireForceHistory(asset:String,timeframe:String,from:String,through:String,mode:ConflictMode)
    case acquireRequiredSet(asset:String)
    case resumeRequiredSet(asset:String)
    case importCSV(file: String, symbol: String, timeframe: String, sourceTimezone: String?, d1DateFormat: String, mode: ConflictMode)
    case validate(symbol: String, timeframe: String, through: String, persist: Bool)
    case verify
    case backup(destination: String)
    case readScheduler
    case readSchedulerService(appBuild:String)
    case installSchedulerService
    case schedulerServiceAction(String)
    case repairSchedulerService
    case forceReconcileSchedulerService
    case readSchedulerDiagnostics(appBuild:String)
    case cancelSchedulerMutation(operationID:String?)
    case dismissManualRequest(id:String)
    case acknowledgeManualRequest(id:String)
    case retrySchedulerLane(id:String)
    case retryManualRequest(id:String)
    case queueLaneUpdate(id:String)
    case runSchedulerQueue
    case runEstateAudit
    case setSchedulerPolicy(String)
    case setM5Freshness(publicationDelaySeconds:Int,criticalAfterClosedBoundaries:Int)
    case pauseAcquisition(scopeType:String,scopeIdentifier:String?,reason:String,temporary:Bool,ingestionSession:String?)
    case resumeAcquisition(pauseIdentifier:String?,scopeType:String?,scopeIdentifier:String?,ingestionSession:String?)
    case readSyntheticProducts
    case regenerateSyntheticProduct(id:String?)
    case rebuildSyntheticRepository
}

public extension OperationIntent {
    var isAuthorityMutation: Bool {
        switch self {
        case .registerInstrument,.retireInstrument,.reactivateInstrument,
             .permanentlyRemoveInstrument,.acquire,.acquireInitial,.acquireUpdate,.acquireForceHistory,.acquireRequiredSet,.resumeRequiredSet,
             .importCSV,.validate:
            true
        default:
            false
        }
    }
    var dataOperationContext: (instrument:String,timeframe:String,actionLabel:String)? {
        switch self {
        case .importCSV(_,let symbol,let timeframe,_,_,_): (symbol,timeframe,"Importing…")
        case .acquire(let asset,let timeframe,_,_,_): (asset,timeframe,"Updating…")
        case .acquireInitial(let asset,let timeframe,_,_,_): (asset,timeframe,"Acquiring…")
        case .acquireUpdate(let asset,let timeframe,_,_,_): (asset,timeframe,"Updating…")
        case .acquireForceHistory(let asset,let timeframe,_,_,_): (asset,timeframe,"Refreshing history…")
        case .acquireRequiredSet(let asset): (asset,"Required Set","Fetching required set…")
        case .resumeRequiredSet(let asset): (asset,"Required Set","Resuming required set…")
        default: nil
        }
    }
}

public struct MarketRepresentation: Codable, Equatable, Sendable, Identifiable {
    public var id: String { "\(representationType):\(symbol)" }
    public let representationType: String;public let symbol:String;public let displayName:String;public let aliases:[String]
    public let exchange:String?;public let currency:String?;public let contractOrShareClass:String?;public let provider:String?;public let providerSymbol:String?;public let registrationStatus:String;public let providerMappingStatus:String;public let acquisitionReadiness:String;public let warnings:[String];public let registrationPlan:MarketRegistrationPlan?;public let timeframeLanes:[MarketTimeframeLane];public let retirement:RetiredInstrumentState?
    enum CodingKeys:String,CodingKey{case symbol,aliases,exchange,currency,provider,warnings,retirement;case representationType="representation_type",displayName="display_name",contractOrShareClass="contract_or_share_class",providerSymbol="provider_symbol",registrationStatus="registration_status",providerMappingStatus="provider_mapping_status",acquisitionReadiness="acquisition_readiness",registrationPlan="registration_plan",timeframeLanes="timeframe_lanes"}
}
public struct RetiredInstrumentState:Codable,Equatable,Sendable{public let retirementID:String;public let lifecycleState:String;public let reason:String;public let operatorNote:String;public let completedAt:String;public let selectedLanes:[String];enum CodingKeys:String,CodingKey{case reason;case retirementID="retirement_id",lifecycleState="lifecycle_state",operatorNote="operator_note",completedAt="completed_at",selectedLanes="selected_lanes"}}
public struct RetirementImpact:Codable,Equatable,Sendable,Identifiable{public var id:String{canonicalInstrument};public let canonicalInstrument:String;public let scope:String;public let selectedLanes:[String];public let activeTimeframeLanes:[String];public let alreadyRetiredLanes:[String];public let completedAcquisitionRuns:Int;public let rawEvidenceBlocks:Int;public let canonicalBars:Int;public let provenanceRecords:Int;public let currentTruthScore:Int?;public let currentCAODT:String?;public let currentServingState:String;public let typedConfirmationRequired:Bool;public let requiredConfirmation:String?;enum CodingKeys:String,CodingKey{case scope;case canonicalInstrument="canonical_instrument",selectedLanes="selected_lanes",activeTimeframeLanes="active_timeframe_lanes",alreadyRetiredLanes="already_retired_lanes",completedAcquisitionRuns="completed_acquisition_runs",rawEvidenceBlocks="raw_evidence_blocks",canonicalBars="canonical_bars",provenanceRecords="provenance_records",currentTruthScore="current_truth_score",currentCAODT="current_caodt",currentServingState="current_serving_state",typedConfirmationRequired="typed_confirmation_required",requiredConfirmation="required_confirmation"}}
public struct RetirementLaneOutcome:Codable,Equatable,Sendable,Identifiable{public var id:String{timeframe};public let timeframe:String;public let outcome:String}
public struct RetirementReceipt:Codable,Equatable,Sendable,Identifiable{public var id:String{retirementID};public let outcome:String;public let retirementID:String;public let canonicalInstrument:String;public let scope:String;public let selectedLanes:[String];public let reason:String;public let operatorNote:String;public let newAuthorityState:String;public let acquisitionShutdownState:String;public let evidenceQuarantineState:String;public let truthServingState:String;public let affectedAcquisitionRuns:Int;public let affectedRawBlocks:Int;public let affectedCanonicalBars:Int;public let completedTimestamp:String;public let perLaneOutcomes:[RetirementLaneOutcome];enum CodingKeys:String,CodingKey{case outcome,scope,reason;case retirementID="retirement_id",canonicalInstrument="canonical_instrument",selectedLanes="selected_lanes",operatorNote="operator_note",newAuthorityState="new_authority_state",acquisitionShutdownState="acquisition_shutdown_state",evidenceQuarantineState="evidence_quarantine_state",truthServingState="truth_serving_state",affectedAcquisitionRuns="affected_acquisition_runs",affectedRawBlocks="affected_raw_blocks",affectedCanonicalBars="affected_canonical_bars",completedTimestamp="completed_timestamp",perLaneOutcomes="per_lane_outcomes"}}
public struct ReactivationReceipt:Codable,Equatable,Sendable,Identifiable{public var id:String{reactivationID};public let outcome:String;public let canonicalInstrument:String;public let reactivationID:String;public let reactivatesRetirementID:String;public let selectedLanes:[String];public let newAuthorityState:String;public let evidenceState:String;public let providerMappingState:String;public let completedTimestamp:String;enum CodingKeys:String,CodingKey{case outcome;case canonicalInstrument="canonical_instrument",reactivationID="reactivation_id",reactivatesRetirementID="reactivates_retirement_id",selectedLanes="selected_lanes",newAuthorityState="new_authority_state",evidenceState="evidence_state",providerMappingState="provider_mapping_state",completedTimestamp="completed_timestamp"}}
public struct PermanentRemovalImpact:Codable,Equatable,Sendable,Identifiable{public var id:String{canonicalInstrument};public let canonicalInstrument:String;public let retirementID:String;public let retiredAt:String;public let reason:String;public let selectedLanes:[String];public let canonicalBars:Int;public let provenanceRecords:Int;public let rawEvidenceBlocks:Int;public let removable:Bool;public let blockingReason:String?;public let recommendedAction:String?;public let requiredConfirmation:String;enum CodingKeys:String,CodingKey{case reason,removable;case canonicalInstrument="canonical_instrument",retirementID="retirement_id",retiredAt="retired_at",selectedLanes="selected_lanes",canonicalBars="canonical_bars",provenanceRecords="provenance_records",rawEvidenceBlocks="raw_evidence_blocks",blockingReason="blocking_reason",recommendedAction="recommended_action",requiredConfirmation="required_confirmation"}}
public struct PermanentRemovalReceipt:Codable,Equatable,Sendable,Identifiable{public var id:String{removalID};public let outcome:String;public let canonicalInstrument:String;public let removalID:String;public let removedRetirementID:String;public let selectedLanes:[String];public let newAuthorityState:String;public let completedTimestamp:String;public let auditHistoryPreserved:Bool;enum CodingKeys:String,CodingKey{case outcome;case canonicalInstrument="canonical_instrument",removalID="removal_id",removedRetirementID="removed_retirement_id",selectedLanes="selected_lanes",newAuthorityState="new_authority_state",completedTimestamp="completed_timestamp",auditHistoryPreserved="audit_history_preserved"}}
public struct MarketTimeframeLane:Codable,Equatable,Sendable,Identifiable{public var id:String{timeframe};public let timeframe:String;public let registrationState:String;public let providerCapability:String;public let providerMapping:String;public let authorityState:String;public let acquisitionReadiness:String;public let reason:String;public let selectable:Bool;public let providerCapabilities:[AcquisitionCapabilityRow]?;public let lastSuccessfulProvider:AcquisitionCapabilityLastSuccess?;enum CodingKeys:String,CodingKey{case timeframe,reason,selectable;case registrationState="registration_state",providerCapability="provider_capability",providerMapping="provider_mapping",authorityState="authority_state",acquisitionReadiness="acquisition_readiness",providerCapabilities="provider_capabilities",lastSuccessfulProvider="last_successful_provider"}}
public struct MarketRegistrationProvider:Codable,Equatable,Sendable{public let provider:String;public let symbol:String;public let state:String}
extension MarketRegistrationPlan: Identifiable { public var id: String { candidate } }
public struct MarketRegistrationPlan:Codable,Equatable,Sendable{public let underlyingMarket:String;public let selectedRepresentation:String;public let canonicalRegistrationSymbol:String;public let displayName:String;public let assetClass:String;public let instrumentType:String;public let exchangeOrVenue:String?;public let timezone:String?;public let sessionAuthority:String;public let baseCurrency:String?;public let quoteCurrency:String?;public let providerMappings:[MarketRegistrationProvider];public let knownUnknowns:[String];public let registrationWarnings:[String];public let candidate:String;enum CodingKeys:String,CodingKey{case timezone,candidate;case underlyingMarket="underlying_market",selectedRepresentation="selected_representation",canonicalRegistrationSymbol="canonical_registration_symbol",displayName="display_name",assetClass="asset_class",instrumentType="instrument_type",exchangeOrVenue="exchange_or_venue",sessionAuthority="session_authority",baseCurrency="base_currency",quoteCurrency="quote_currency",providerMappings="provider_mappings",knownUnknowns="known_unknowns",registrationWarnings="registration_warnings"}}
public struct MarketProviderDiscovery: Codable, Equatable, Sendable, Identifiable {
    public var id:String{"\(representationSymbol):\(provider ?? "unmapped")"};public let representationSymbol:String;public let provider:String?;public let availability:String;public let supportedTimeframes:[String];public let entitlement:String;public let confidence:Int?;public let knownSymbol:String?;public let registrationStatus:String
    enum CodingKeys:String,CodingKey{case provider,availability,entitlement,confidence;case representationSymbol="representation_symbol",supportedTimeframes="supported_timeframes",knownSymbol="known_symbol",registrationStatus="registration_status"}
}
public struct MarketRecommendation:Codable,Equatable,Sendable{public let representationType:String;public let symbol:String;public let displayName:String;public let reason:String;public let alternatives:[String];enum CodingKeys:String,CodingKey{case symbol,reason,alternatives;case representationType="representation_type",displayName="display_name"}}
public struct MarketMetadata:Codable,Equatable,Sendable{public let market:String;public let assetClass:String;public let exchange:String?;public let timezone:String?;public let sessions:[String];public let currencies:[String];public let aliases:[String];public let providerMappings:[String];public let registrationState:String;enum CodingKeys:String,CodingKey{case market,exchange,timezone,sessions,currencies,aliases;case assetClass="asset_class",providerMappings="provider_mappings",registrationState="registration_state"}}
public struct ExistingMarketRegistration:Codable,Equatable,Sendable,Identifiable{public var id:String{canonicalSymbol};public let canonicalSymbol:String;public let registrationStatus:String;public let registrationVersion:Int;public let authorityState:String;public let truthScore:Int?;public let caodt:String?;enum CodingKeys:String,CodingKey{case caodt;case canonicalSymbol="canonical_symbol",registrationStatus="registration_status",registrationVersion="registration_version",authorityState="authority_state",truthScore="truth_score"}}
public struct FXOrientation:Codable,Equatable,Sendable{public let canonicalIdentity:String;public let orderedPair:String;public let baseCurrency:String;public let quoteCurrency:String;public let orientationState:String;public let provider:String;public let requestedProviderSymbol:String?;public let exactMappingState:String;public let inversePair:String;public let inverseProviderSymbol:String?;public let inverseMappingState:String;public let evidenceSource:String?;public let mappingVersion:String;public let evidenceTimestamp:String;public let supportedTimeframes:[String];public let entitlementState:String;public let acquisitionReadiness:String;enum CodingKeys:String,CodingKey{case provider;case canonicalIdentity="canonical_identity",orderedPair="ordered_pair",baseCurrency="base_currency",quoteCurrency="quote_currency",orientationState="orientation_state",requestedProviderSymbol="requested_provider_symbol",exactMappingState="exact_mapping_state",inversePair="inverse_pair",inverseProviderSymbol="inverse_provider_symbol",inverseMappingState="inverse_mapping_state",evidenceSource="evidence_source",mappingVersion="mapping_version",evidenceTimestamp="evidence_timestamp",supportedTimeframes="supported_timeframes",entitlementState="entitlement_state",acquisitionReadiness="acquisition_readiness"}}
public struct DiscoveredMarket:Codable,Equatable,Sendable,Identifiable{public var id:String{canonicalIdentity};public let underlyingMarket:String;public let canonicalIdentity:String;public let confidence:Int;public let marketType:String;public let assetClass:String;public let description:String;public let knownAliases:[String];public let representations:[MarketRepresentation];public let providerDiscovery:[MarketProviderDiscovery];public let recommendation:MarketRecommendation;public let metadata:MarketMetadata;public let existingRegistrations:[ExistingMarketRegistration];public let acquisitionReadiness:String;public let resolutionReason:String;public let requiredOperatorDecisions:[String];public let availableActions:[String];public let fxOrientation:FXOrientation?;enum CodingKeys:String,CodingKey{case confidence,description,representations,recommendation,metadata;case underlyingMarket="underlying_market",canonicalIdentity="canonical_identity",marketType="market_type",assetClass="asset_class",knownAliases="known_aliases",providerDiscovery="provider_discovery",existingRegistrations="existing_registrations",acquisitionReadiness="acquisition_readiness",resolutionReason="resolution_reason",requiredOperatorDecisions="required_operator_decisions",availableActions="available_actions",fxOrientation="fx_orientation"}}
public struct MarketDiscoveryResult:Codable,Equatable,Sendable{public let contract:String;public let query:String;public let discoveryStatus:String;public let confidence:Int;public let markets:[DiscoveredMarket];public let explanation:String;public let suggestedSearches:[String];public let similarMarkets:[String];public let operatorGuidance:String;enum CodingKeys:String,CodingKey{case contract,query,confidence,markets,explanation;case discoveryStatus="discovery_status",suggestedSearches="suggested_searches",similarMarkets="similar_markets",operatorGuidance="operator_guidance"}}

public struct ResolvedInstrumentIdentity: Codable, Equatable, Sendable, Identifiable {
    public var id: String { canonicalSymbol }
    public let canonicalName: String
    public let canonicalSymbol: String
    public let instrumentType: String
    public let market: String
    public let assetClass: String
    public let confidence: Int
    public let knownAliases: [String]
    public let knownExchange: String?
    public let knownCurrency: String?
    public let baseCurrency: String?
    public let quoteCurrency: String?
    public let timezone: String?
    public let sessions: [String]
    public let resolutionReason: String
    public let identityStatus: String
    public let registrationState: String
    public let authorityState: String?
    public let currentTruthScore: Int?
    public let currentCAODT: String?
    enum CodingKeys: String, CodingKey {
        case confidence, market, timezone, sessions
        case canonicalName = "canonical_name", canonicalSymbol = "canonical_symbol"
        case instrumentType = "instrument_type", assetClass = "asset_class", knownAliases = "known_aliases"
        case knownExchange = "known_exchange", knownCurrency = "known_currency", baseCurrency = "base_currency"
        case quoteCurrency = "quote_currency", resolutionReason = "resolution_reason", identityStatus = "identity_status"
        case registrationState = "registration_state", authorityState = "authority_state"
        case currentTruthScore = "current_truth_score", currentCAODT = "current_caodt"
    }
}

public struct InstrumentIdentityResolution: Codable, Equatable, Sendable {
    public let contract: String
    public let query: String
    public let identityStatus: String
    public let confidence: Int
    public let matches: [ResolvedInstrumentIdentity]
    public let explanation: String
    public let suggestedSearches: [String]
    public let suggestedProviders: [String]
    public let suggestedAliases: [String]
    enum CodingKeys: String, CodingKey {
        case contract, query, confidence, matches, explanation
        case identityStatus = "identity_status", suggestedSearches = "suggested_searches"
        case suggestedProviders = "suggested_providers", suggestedAliases = "suggested_aliases"
    }
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
    public init(operationID:UUID,exitCode:Int32,stdout:String,stderr:String){self.operationID=operationID;self.exitCode=exitCode;self.stdout=stdout;self.stderr=stderr}
    public var JSON: [String: Any]? { (try? JSONSerialization.jsonObject(with: Data(stdout.utf8))) as? [String: Any] }
    public static func == (lhs: Self, rhs: Self) -> Bool { lhs.operationID == rhs.operationID && lhs.exitCode == rhs.exitCode && lhs.stdout == rhs.stdout && lhs.stderr == rhs.stderr }
}
