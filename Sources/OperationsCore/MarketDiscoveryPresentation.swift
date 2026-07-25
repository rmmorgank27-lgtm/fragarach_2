import Foundation

public enum MarketAvailabilityState: String, CaseIterable, Sendable {
    case available = "Available"
    case active = "Active"
    case activePublished = "Active Published"
    case registeredNoEvidence = "Registered · No Evidence"
    case acquiringHistory = "Registered · Acquiring History"
    case recoverableFailure = "Registered · Recoverable Failure"
    case registeredWithEvidence = "Registered · Evidence Pending Publication"
    case retired = "Retired"
    case unsupported = "Unsupported"
    case providerMappingRequired = "Provider Mapping Required"
    case entitlementRequired = "Entitlement Required"
    case unavailable = "Unavailable"
}

public enum MarketPrimaryAction: String, Sendable {
    case approveMappingAndAdd = "Approve Mapping and Add"
    case addToEstate = "Add to Estate"
    case completeProviderSetup = "Complete Provider Setup"
    case openInEstate = "Open in Estate"
    case reactivate = "Reactivate"
    case registerCorrectInstrument = "Register Correct Instrument"
    case openManageData = "Open Manage Data"
    case resumeInitialHistory = "Resume Initial History"
    case repairPublication = "Repair Publication"
    case unavailable = "Unavailable"
    case selectRepresentation = "Select a representation"
}

public enum MarketAssetFilter: String, CaseIterable, Identifiable, Sendable {
    case all = "All"
    case forex = "Forex"
    case stocks = "Stocks"
    case indices = "Indices"
    case metals = "Metals"
    case energy = "Energy"
    case crypto = "Crypto"

    public var id: String { rawValue }

    public func includes(assetClass: String) -> Bool {
        let value = assetClass.uppercased()
        switch self {
        case .all: return true
        case .forex: return value == "FX" || value.contains("FOREX")
        case .stocks: return value.contains("EQUITIES") || value.contains("EQUITY")
        case .indices: return value.contains("INDICES") || value.contains("INDEX")
        case .metals: return value.contains("METALS") || value.contains("METAL")
        case .energy: return value.contains("ENERGY")
        case .crypto: return value.contains("CRYPTO")
        }
    }
}

public enum MarketDiscoveryPresentation {
    public static func usesNarrowLayout(availableWidth: CGFloat) -> Bool {
        availableWidth < 860
    }

    public static func availability(
        for representation: MarketRepresentation,
        providerDiscovery: MarketProviderDiscovery?
    ) -> MarketAvailabilityState {
        if representation.retirement != nil { return .retired }
        if representation.acquisitionReadiness.uppercased() == "PROVIDER_SETUP_INCOMPLETE" {
            return .providerMappingRequired
        }
        switch representation.registrationStatus.uppercased() {
        case "ACTIVE_PUBLISHED":
            return .activePublished
        case "REGISTERED_NO_EVIDENCE":
            return .registeredNoEvidence
        case "REGISTERED_ACQUIRING_HISTORY":
            return .acquiringHistory
        case "REGISTERED_FAILED_RECOVERABLE":
            return .recoverableFailure
        case "REGISTERED_WITH_EVIDENCE":
            return .registeredWithEvidence
        default:
            break
        }
        if representation.representationType.uppercased() == "FUTURES" {
            return .unsupported
        }
        let mapping = representation.providerMappingStatus.uppercased()
        let providerAvailability = providerDiscovery?.availability.uppercased() ?? ""
        if mapping == "REVIEW_REQUIRED"
            || mapping == "DISCOVERY_REQUIRED"
            || mapping.contains("MAPPING_REQUIRED")
            || providerAvailability == "REVIEW_REQUIRED"
            || providerAvailability.contains("MAPPING_REQUIRED") {
            return .providerMappingRequired
        }
        if isActive(representation) { return .active }

        let entitlement = providerDiscovery?.entitlement.uppercased() ?? ""
        if entitlement.contains("REQUIRED") || entitlement.contains("DENIED") {
            return .entitlementRequired
        }
        if representation.registrationPlan != nil {
            return representation.providerMappingStatus.uppercased().contains("REQUIRED")
                || representation.providerSymbol == nil
                ? .providerMappingRequired
                : .available
        }
        return .unavailable
    }

    public static func isActive(_ representation: MarketRepresentation) -> Bool {
        let status = representation.registrationStatus.uppercased()
        return representation.retirement == nil
            && status != "NOT_REGISTERED"
            && status != "PERMANENTLY_REMOVED"
    }

    public static func defaultRepresentationID(for market: DiscoveredMarket) -> String? {
        let active = market.representations.filter(isActive)
        if active.count == 1 { return active[0].id }

        let eligible = market.representations.filter { representation in
            let provider = market.providerDiscovery.first {
                $0.representationSymbol == representation.symbol
            }
            switch availability(for: representation, providerDiscovery: provider) {
            case .available, .active, .activePublished, .registeredNoEvidence,
                 .acquiringHistory, .recoverableFailure, .registeredWithEvidence,
                 .retired, .providerMappingRequired:
                return true
            case .unsupported, .entitlementRequired, .unavailable:
                return false
            }
        }
        return eligible.count == 1 ? eligible[0].id : nil
    }

    public static func initialRepresentationID(for market: DiscoveredMarket) -> String? {
        defaultRepresentationID(for: market)
            ?? market.representations.first { $0.symbol == market.recommendation.symbol }?.id
            ?? (market.representations.count == 1 ? market.representations[0].id : nil)
    }

    public static func estateStatus(for representation: MarketRepresentation) -> String {
        let status = representation.registrationStatus.uppercased()
        if status == "NOT_REGISTERED" { return "Not in Estate" }
        if status == "PERMANENTLY_REMOVED" { return "Permanently Removed" }
        if representation.retirement != nil { return "Retired" }
        if status == "REGISTERED_NO_EVIDENCE" { return "Registered · No Evidence" }
        if status == "REGISTERED_ACQUIRING_HISTORY" { return "Registered · Acquiring History" }
        if status == "REGISTERED_FAILED_RECOVERABLE" { return "Registered · Recoverable Failure" }
        if status == "REGISTERED_WITH_EVIDENCE" { return "Registered · Evidence Pending Publication" }
        if status == "ACTIVE_PUBLISHED" { return "Active Published" }
        return "Active in Estate"
    }

    public static func primaryAction(
        for representation: MarketRepresentation?,
        newlyRegisteredSymbol: String? = nil
    ) -> MarketPrimaryAction {
        guard let representation else { return .selectRepresentation }
        if newlyRegisteredSymbol == representation.symbol { return .openManageData }
        if let retirement=representation.retirement {
            return retirement.reason == "INCORRECT_INSTRUMENT_IDENTITY" ? .registerCorrectInstrument:.reactivate
        }
        if representation.acquisitionReadiness.uppercased() == "PROVIDER_SETUP_INCOMPLETE",
           representation.registrationPlan != nil { return .completeProviderSetup }
        switch representation.registrationStatus.uppercased() {
        case "REGISTERED_NO_EVIDENCE", "REGISTERED_FAILED_RECOVERABLE":
            return .resumeInitialHistory
        case "REGISTERED_WITH_EVIDENCE":
            return .repairPublication
        case "REGISTERED_ACQUIRING_HISTORY":
            return .openManageData
        default:
            break
        }
        if isActive(representation) { return .openInEstate }
        if representation.registrationPlan != nil,
           representation.providerMappingStatus.uppercased() == "REVIEW_REQUIRED" {
            return .approveMappingAndAdd
        }
        if representation.registrationPlan != nil { return .addToEstate }
        return .unavailable
    }

    public static func supportedTimeframes(
        for representation: MarketRepresentation,
        providerDiscovery: MarketProviderDiscovery?
    ) -> [String] {
        let explicit = providerDiscovery?.supportedTimeframes ?? []
        if !explicit.isEmpty { return explicit }
        return representation.timeframeLanes
            .filter { $0.providerCapability == "SUPPORTED" }
            .map(\.timeframe)
    }

    public static func availabilityReason(
        for representation: MarketRepresentation,
        providerDiscovery: MarketProviderDiscovery?
    ) -> String {
        switch availability(for: representation, providerDiscovery: providerDiscovery) {
        case .active, .activePublished:
            return "Already active in Estate."
        case .registeredNoEvidence:
            return "Registration exists, but no published canonical evidence is available yet."
        case .acquiringHistory:
            return "Initial history acquisition is in progress."
        case .recoverableFailure:
            return "Registration exists, but acquisition or publication needs recovery."
        case .registeredWithEvidence:
            return "Canonical evidence exists, but Estate Truth publication needs repair."
        case .retired:
            return representation.retirement?.reason == "INCORRECT_INSTRUMENT_IDENTITY"
                ? "Immutable evidence remains under the retired identity. Register the correct instrument separately."
                : "Retired authority and evidence are preserved for reactivation."
        case .unsupported:
            return representation.warnings.first
                ?? "This representation is not currently supported."
        case .providerMappingRequired:
            if let symbol = providerDiscovery?.knownSymbol,
               let provider = providerDiscovery?.provider {
                return "Provider mapping required. \(provider.replacingOccurrences(of: "_", with: " ").capitalized) candidate: \(symbol)."
            }
            return "Provider mapping required before provider acquisition."
        case .entitlementRequired:
            return "Provider entitlement is required before acquisition."
        case .available:
            let timeframes = supportedTimeframes(
                for: representation,
                providerDiscovery: providerDiscovery
            )
            return timeframes.isEmpty
                ? "Registration is available; provider capability is not yet measured."
                : "Provider supports \(timeframes.joined(separator: ", "))."
        case .unavailable:
            return representation.warnings.first
                ?? representation.acquisitionReadiness.replacingOccurrences(of: "_", with: " ").capitalized + "."
        }
    }
}
