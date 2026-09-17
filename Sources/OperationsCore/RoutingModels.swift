import Foundation

public struct RoutingSnapshot: Codable, Sendable {
    public let contract:String
    public let routingRevision:String
    public let generatedAtUTC:String
    public let estateDefaultOrder:[String]
    public let providers:[RoutingProvider]
    public let lanes:[RoutingLane]
    public let attention:[RoutingAttention]
    enum CodingKeys:String,CodingKey { case contract;case routingRevision="routing_revision";case generatedAtUTC="generated_at_utc";case estateDefaultOrder="estate_default_order";case providers,lanes,attention }
}

public struct RoutingAttention:Codable,Sendable,Identifiable {
    public var id:String { lane+":"+reason }
    public let lane:String
    public let reason:String
}

public struct RoutingLastUsed:Codable,Sendable {
    public let provider:String?
    public let providerSymbol:String?
    public let receiptTime:String?
    enum CodingKeys:String,CodingKey { case provider;case providerSymbol="provider_symbol";case receiptTime="receipt_time" }
}

public struct RoutingAttemptState:Codable,Sendable {
    public let boundary:String?
    public let count:Int
    public let cap:Int
    public let providers:[String]
    public let lastOutcome:String?
    public let nextAction:String?
    enum CodingKeys:String,CodingKey { case boundary,count,cap,providers;case lastOutcome="last_outcome";case nextAction="next_action" }
}

public struct RoutingCandidate:Codable,Sendable,Identifiable,Hashable {
    public var id:String { provider }
    public let provider:String
    public let providerSymbol:String?
    public let mappingClass:String?
    public let authoritySource:String?
    public let capabilityState:String
    public let credentialState:String
    public let entitlementState:String
    public let reviewed:Bool
    public let enabled:Bool
    public let order:Int
    public let nodeID:String?
    enum CodingKeys:String,CodingKey { case provider,reviewed,enabled,order;case providerSymbol="provider_symbol";case mappingClass="mapping_class";case authoritySource="authority_source";case capabilityState="capability_state";case credentialState="credential_state";case entitlementState="entitlement_state";case nodeID="node_id" }
}

public struct RoutingBridgeNode:Codable,Sendable,Identifiable {
    public var id:String { nodeID }
    public let nodeID:String
    public let displayName:String
    public let currentEstateSymbols:[String]
    public let reviewedLaneCount:Int
    public let availableLaneCount:Int
    enum CodingKeys:String,CodingKey { case nodeID="node_id";case displayName="display_name";case currentEstateSymbols="current_estate_symbols";case reviewedLaneCount="reviewed_lane_count";case availableLaneCount="available_lane_count" }
}

public struct RoutingLane:Codable,Sendable,Identifiable {
    public let id:String
    public let active:Bool
    public let lifecycleState:String?
    public let ineligibilityReason:String?
    public let symbol:String
    public let timeframe:String
    public let assetClass:String?
    public let market:String?
    public let derivationState:String
    public let inheritance:String
    public let operatorReason:String?
    public let candidates:[RoutingCandidate]
    public let disabledProviders:[String]
    public let effectiveProviderOrder:[String]
    public let primaryProvider:String?
    public let primaryProviderSymbol:String?
    public let routeState:String
    public let lastUsed:RoutingLastUsed?
    public let attemptState:RoutingAttemptState
    enum CodingKeys:String,CodingKey { case id,active,symbol,timeframe,market,candidates;case lifecycleState="lifecycle_state";case ineligibilityReason="ineligibility_reason";case assetClass="asset_class";case derivationState="derivation_state";case inheritance;case operatorReason="operator_reason";case disabledProviders="disabled_providers";case effectiveProviderOrder="effective_provider_order";case primaryProvider="primary_provider";case primaryProviderSymbol="primary_provider_symbol";case routeState="route_state";case lastUsed="last_used";case attemptState="attempt_state" }
}

public struct RoutingProvider:Codable,Sendable,Identifiable {
    public var id:String { provider }
    public let provider:String
    public let enabled:Bool
    public let credentialState:String
    public let entitlementState:String
    public let supportedAssetClasses:[String]
    public let supportedTimeframes:[String]
    public let currentEstateSymbols:[String]
    public let activePrimaryLaneCount:Int
    public let activeFallbackLaneCount:Int
    public let reviewedCandidateLaneCount:Int
    public let operationalLimit:Int?
    public let concurrencyLimit:Int?
    public let additionalSymbolsAvailable:Bool
    public let bridgeNodes:[RoutingBridgeNode]
    enum CodingKeys:String,CodingKey { case provider,enabled;case credentialState="credential_state";case entitlementState="entitlement_state";case supportedAssetClasses="supported_asset_classes";case supportedTimeframes="supported_timeframes";case currentEstateSymbols="current_estate_symbols";case activePrimaryLaneCount="active_primary_lane_count";case activeFallbackLaneCount="active_fallback_lane_count";case reviewedCandidateLaneCount="reviewed_candidate_lane_count";case operationalLimit="operational_limit";case concurrencyLimit="concurrency_limit";case additionalSymbolsAvailable="additional_symbols_available";case bridgeNodes="bridge_nodes" }
}

public struct RoutingDraft:Codable,Sendable {
    public let draftID:String
    public let symbol:String
    public let timeframe:String
    public let providerOrder:[String]
    public let disabledProviders:[String]
    public let operatorReason:String
    enum CodingKeys:String,CodingKey { case symbol,timeframe;case draftID="draft_id";case providerOrder="provider_order";case disabledProviders="disabled_providers";case operatorReason="operator_reason" }
}

public struct RoutingDraftValidation:Codable,Sendable {
    public let draftID:String
    public let valid:Bool
    public let activationGate:String?
    public let issues:[String]
    public let warnings:[String]
    public let lane:String
    public let beforeOrder:[String]
    public let afterOrder:[String]
    enum CodingKeys:String,CodingKey { case valid,issues,warnings,lane;case draftID="draft_id";case activationGate="activation_gate";case beforeOrder="before_order";case afterOrder="after_order" }
}

public struct RoutingActivationReceipt:Codable,Sendable {
    public let activationID:String
    public let routingRevision:String
    public let parentRevision:String
    public let activatedAtUTC:String
    public let affectedLanes:[String]
    public let restoreDefault:Bool
    enum CodingKeys:String,CodingKey { case activationID="activation_id";case routingRevision="routing_revision";case parentRevision="parent_revision";case activatedAtUTC="activated_at_utc";case affectedLanes="affected_lanes";case restoreDefault="restore_default" }
}
