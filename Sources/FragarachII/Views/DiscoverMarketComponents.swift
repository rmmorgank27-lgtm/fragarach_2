import OperationsCore
import SwiftUI

enum DiscoveryResultTarget: Hashable {
    case market(String)
    case representation(String, String)
    case existing(String, String)
    case alias(String, String?)
}

struct DiscoveryResultItem: Identifiable {
    let id: String
    let target: DiscoveryResultTarget
    let displayName: String
    let primarySymbol: String
    let instrumentType: String
    let representationSummary: String
    let estateStatus: String
}

struct DiscoveryResultSection: Identifiable {
    let id: String
    let title: String
    let items: [DiscoveryResultItem]
}

enum DiscoveryResultBuilder {
    static func sections(
        for discovery: MarketDiscoveryResult,
        markets: [DiscoveredMarket],
        query: String
    ) -> [DiscoveryResultSection] {
        guard !markets.isEmpty else { return [] }

        let identities = markets.map { market in
            DiscoveryResultItem(
                id: "market:\(market.id)",
                target: .market(market.id),
                displayName: market.underlyingMarket,
                primarySymbol: market.recommendation.symbol.isEmpty
                    ? market.canonicalIdentity
                    : market.recommendation.symbol,
                instrumentType: market.marketType.displayStatus,
                representationSummary: "\(market.representations.count) representation\(market.representations.count == 1 ? "" : "s")",
                estateStatus: market.existingRegistrations.isEmpty
                    ? "Not in Estate"
                    : "Active in Estate"
            )
        }

        let representations = markets.flatMap { market in
            market.representations.map { representation in
                let provider = market.providerDiscovery.first {
                    $0.representationSymbol == representation.symbol
                }
                return DiscoveryResultItem(
                    id: "representation:\(market.id):\(representation.id)",
                    target: .representation(market.id, representation.id),
                    displayName: representation.displayName,
                    primarySymbol: representation.symbol,
                    instrumentType: representation.representationType.displayStatus,
                    representationSummary: representation.exchange
                        ?? representation.contractOrShareClass
                        ?? "Venue not established",
                    estateStatus: MarketDiscoveryPresentation.availability(
                        for: representation,
                        providerDiscovery: provider
                    ).rawValue
                )
            }
        }

        let existing = markets.flatMap { market in
            market.representations.compactMap { representation -> DiscoveryResultItem? in
                guard MarketDiscoveryPresentation.isActive(representation)
                        || representation.retirement != nil else { return nil }
                let provider = market.providerDiscovery.first {
                    $0.representationSymbol == representation.symbol
                }
                return DiscoveryResultItem(
                    id: "existing:\(market.id):\(representation.id)",
                    target: .existing(market.id, representation.id),
                    displayName: representation.displayName,
                    primarySymbol: representation.symbol,
                    instrumentType: representation.representationType.displayStatus,
                    representationSummary: "Existing Estate registration",
                    estateStatus: MarketDiscoveryPresentation.availability(
                        for: representation,
                        providerDiscovery: provider
                    ).rawValue
                )
            }
        }

        var seenAliases = Set<String>()
        let normalizedQuery = query.normalizedMarketSearch
        let aliases = markets.flatMap { market -> [DiscoveryResultItem] in
            var values = market.knownAliases.map { ($0, nil as String?) }
            values += market.representations.flatMap { representation in
                representation.aliases.map { ($0, Optional(representation.id)) }
            }
            return values.compactMap { alias, representationID in
                let key = "\(market.id):\(alias.normalizedMarketSearch)"
                guard !alias.isEmpty, seenAliases.insert(key).inserted else { return nil }
                let match = alias.normalizedMarketSearch == normalizedQuery
                    ? "Exact alias match"
                    : "Approved alias"
                return DiscoveryResultItem(
                    id: "alias:\(key)",
                    target: .alias(market.id, representationID),
                    displayName: alias,
                    primarySymbol: market.underlyingMarket,
                    instrumentType: representationID == nil
                        ? "Market alias"
                        : "Representation alias",
                    representationSummary: match,
                    estateStatus: market.existingRegistrations.isEmpty
                        ? "Resolves to market identity"
                        : "Resolves to Estate market"
                )
            }
        }

        return [
            DiscoveryResultSection(id: "identities", title: "Market Identities", items: identities),
            DiscoveryResultSection(id: "representations", title: "Tradable Representations", items: representations),
            DiscoveryResultSection(id: "existing", title: "Existing Estate Markets", items: existing),
            DiscoveryResultSection(id: "aliases", title: "Aliases", items: aliases),
        ].filter { !$0.items.isEmpty }
    }
}

struct DiscoverySearchPane: View {
    @Binding var query: String
    var searchFocused: FocusState<Bool>.Binding
    @Binding var assetFilter: MarketAssetFilter
    @Binding var highlightedResult: DiscoveryResultTarget?
    let sections: [DiscoveryResultSection]
    let discovery: MarketDiscoveryResult?
    let isSearching: Bool
    let error: String?
    let recentSearches: [String]
    let manualRequests: [SchedulerManualRequest]
    let onSubmit: () -> Void
    let onSearchSuggestion: (String) -> Void
    let onMove: (MoveCommandDirection) -> Void
    let onOpenControlledWorkflow: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 10) {
                Text("Search and Results")
                    .font(.headline)
                HStack(spacing: 8) {
                    TextField(
                        "Search symbol, market, company, alias, index, commodity, FX or crypto",
                        text: $query
                    )
                    .textFieldStyle(.roundedBorder)
                    .focused(searchFocused)
                    .onSubmit(onSubmit)
                    .accessibilityLabel("Market search")

                    Button(action: onSubmit) {
                        Image(systemName: "arrow.right.circle.fill")
                    }
                    .buttonStyle(.borderless)
                    .help("Search now")
                    .disabled(query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(MarketAssetFilter.allCases) { filter in
                            Button(filter.rawValue) { assetFilter = filter }
                                .buttonStyle(.bordered)
                                .controlSize(.small)
                                .tint(assetFilter == filter ? .accentColor : nil)
                                .accessibilityAddTraits(assetFilter == filter ? .isSelected : [])
                        }
                    }
                }

                if isSearching {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small)
                        Text("Searching…")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .accessibilityLabel("Searching for markets")
                }

                if let error {
                    CompactMessage(
                        title: "Search unavailable",
                        message: error,
                        systemImage: "exclamationmark.triangle",
                        tint: .orange
                    )
                }
            }
            .padding(16)

            Divider()

            if query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                DiscoveryEmptyState(
                    recentSearches: recentSearches,
                    manualRequests: manualRequests,
                    onSearchSuggestion: onSearchSuggestion
                )
            } else if let discovery, discovery.markets.isEmpty {
                DiscoveryNoMatchState(
                    discovery: discovery,
                    onSearchSuggestion: onSearchSuggestion,
                    onOpenControlledWorkflow: onOpenControlledWorkflow
                )
            } else if sections.isEmpty, discovery != nil {
                ContentUnavailableView(
                    "No results in \(assetFilter.rawValue)",
                    systemImage: "line.3.horizontal.decrease.circle",
                    description: Text("Choose All or another asset filter.")
                )
            } else {
                List(selection: $highlightedResult) {
                    ForEach(sections) { section in
                        Section(section.title) {
                            ForEach(section.items) { item in
                                DiscoveryResultRow(
                                    item: item,
                                    isSelected: highlightedResult == item.target
                                )
                                .contentShape(Rectangle())
                                .onTapGesture { highlightedResult = item.target }
                                .listRowBackground(
                                    highlightedResult == item.target
                                        ? Color.accentColor.opacity(0.14)
                                        : Color.clear
                                )
                                    .tag(Optional(item.target))
                            }
                        }
                    }
                }
                .listStyle(.inset)
                .accessibilityLabel("Market search results")
            }
        }
        .onMoveCommand(perform: onMove)
    }
}

private struct DiscoveryEmptyState: View {
    let recentSearches: [String]
    let manualRequests: [SchedulerManualRequest]
    let onSearchSuggestion: (String) -> Void

    private let examples = [
        ("Symbol", "XAGUSD, GOOGL, NZDJPY"),
        ("Market", "Silver, Bitcoin, S&P 500"),
        ("Alias", "US30, SPX500"),
        ("Company", "Alphabet, BHP"),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 4) {
                    Label("Search by the name you know", systemImage: "magnifyingglass")
                        .font(.headline)
                    Text("Fragarach resolves the market identity before you choose a tradable representation.")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }

                GroupBox("Examples") {
                    Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 9) {
                        ForEach(examples, id: \.0) { label, values in
                            GridRow {
                                Text(label).foregroundStyle(.secondary)
                                Text(values)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 4)
                }

                if !recentSearches.isEmpty {
                    CompactSearchLinks(
                        title: "Recent Searches",
                        values: recentSearches,
                        action: onSearchSuggestion
                    )
                }

                if !manualRequests.isEmpty {
                    GroupBox("Manual Requests Requiring Selection") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(manualRequests.prefix(4)) { request in
                                Button {
                                    onSearchSuggestion(request.symbol)
                                } label: {
                                    HStack {
                                        Text(request.symbol).font(.body.monospaced().bold())
                                        Text(request.timeframe).foregroundStyle(.secondary)
                                        Spacer()
                                        Text(request.reason.displayStatus)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct CompactSearchLinks: View {
    let title: String
    let values: [String]
    let action: (String) -> Void

    var body: some View {
        GroupBox(title) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(values, id: \.self) { value in
                        Button(value) { action(value) }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                    }
                }
            }
            .padding(.vertical, 4)
        }
    }
}

private struct DiscoveryNoMatchState: View {
    let discovery: MarketDiscoveryResult
    let onSearchSuggestion: (String) -> Void
    let onOpenControlledWorkflow: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ContentUnavailableView(
                    "No matching market found.",
                    systemImage: "magnifyingglass",
                    description: Text("Try another symbol, company name, market name, or alias.")
                )

                if !discovery.suggestedSearches.isEmpty {
                    CompactSearchLinks(
                        title: "Search Suggestions",
                        values: discovery.suggestedSearches,
                        action: onSearchSuggestion
                    )
                }

                Button("Open Acquire & Import", action: onOpenControlledWorkflow)
                    .help("Continue to the controlled manual acquisition workflow")
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct DiscoveryResultRow: View {
    let item: DiscoveryResultItem
    let isSelected: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(item.displayName)
                    .fontWeight(.semibold)
                    .lineLimit(1)
                Spacer()
                Text(item.estateStatus)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            HStack(spacing: 7) {
                Text(item.primarySymbol)
                    .font(.caption.monospaced().bold())
                Text(item.instrumentType)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text(item.representationSummary)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .padding(.vertical, 4)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            "\(item.displayName), \(item.primarySymbol), \(item.instrumentType), \(item.representationSummary), \(item.estateStatus)"
        )
    }
}

struct DiscoveryDetailEmptyState: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Selected Market")
                .font(.headline)
                .padding(16)
            Divider()
            ContentUnavailableView(
                "Select a market result",
                systemImage: "chart.line.uptrend.xyaxis",
                description: Text("Market identity, representations, provider support, and Estate status will appear here.")
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

struct DiscoveryMarketDetailPane: View {
    let market: DiscoveredMarket
    @Binding var selection: String?
    let registeredSymbol: String?
    let registeredStatus: String?
    let showsBack: Bool
    let onBack: () -> Void
    let onReviewRegistration: (MarketRegistrationPlan, MarketRepresentation) -> Void
    let onOpenEstate: (String) -> Void
    let onOpenManageData: (String) -> Void
    let onOpenInverse: (String) -> Void
    let onRetire: (String) -> Void
    let onReactivate: (String) -> Void
    let onRegisterCorrectInstrument: () -> Void
    let onPermanentRemove: (String) -> Void
    let onHistory: (String) -> Void

    private var selected: MarketRepresentation? {
        market.representations.first { $0.id == selection }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                if showsBack {
                    Button(action: onBack) {
                        Label("Back", systemImage: "chevron.left")
                    }
                }
                Text("Selected Market")
                    .font(.headline)
                Spacer()
            }
            .padding(16)

            Divider()

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    marketIdentity
                    representationSelection
                    if let selected { representationDetail(selected) }
                    if registeredSymbol != nil { registrationComplete }
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            Divider()
            primaryActionBar
        }
    }

    private var marketIdentity: some View {
        DiscoveryPanel("Market Identity") {
            VStack(alignment: .leading, spacing: 10) {
                Text(market.underlyingMarket)
                    .font(.title2.bold())
                Text(market.description)
                    .foregroundStyle(.secondary)
                DiscoveryFactsGrid([
                    ("Canonical identity", market.canonicalIdentity),
                    ("Asset class", market.assetClass.displayStatus),
                    ("Market or benchmark", market.marketType.displayStatus),
                    ("Resolution", market.resolutionReason),
                ])
            }
        }
    }

    private var representationSelection: some View {
        DiscoveryPanel("Tradable Representations") {
            VStack(alignment: .leading, spacing: 8) {
                if market.representations.count > 1, selection == nil {
                    Label(
                        "Choose the materially correct representation before continuing.",
                        systemImage: "cursorarrow.click"
                    )
                    .font(.callout)
                    .foregroundStyle(.secondary)
                }

                Picker("Representation", selection: $selection) {
                    ForEach(market.representations) { representation in
                        RepresentationChoiceRow(
                            representation: representation,
                            providerDiscovery: provider(for: representation)
                        )
                        .tag(Optional(representation.id))
                    }
                }
                .labelsHidden()
                .pickerStyle(.radioGroup)
                .accessibilityLabel("Select one tradable representation")
            }
        }
    }

    private func representationDetail(_ representation: MarketRepresentation) -> some View {
        let provider = provider(for: representation)
        let timeframes = MarketDiscoveryPresentation.supportedTimeframes(
            for: representation,
            providerDiscovery: provider
        )
        let availability = MarketDiscoveryPresentation.availability(
            for: representation,
            providerDiscovery: provider
        )

        return VStack(alignment: .leading, spacing: 16) {
            DiscoveryPanel("Representation Status") {
                DiscoveryFactsGrid([
                    ("Symbol", representation.symbol),
                    ("Identity", market.underlyingMarket),
                    ("Representation", representation.symbol),
                    ("Instrument type", representation.representationType.displayStatus),
                    ("Venue", representation.exchange ?? representation.contractOrShareClass ?? "Not established"),
                    ("Country/market", countryOrMarket(for: representation)),
                    ("Provider support", providerSupport(provider, representation: representation)),
                    ("Supported timeframes", timeframes.isEmpty ? "Not established" : timeframes.joined(separator: ", ")),
                    ("Estate status", MarketDiscoveryPresentation.estateStatus(for: representation)),
                    ("Acquisition status", availability.rawValue),
                    ("Availability reason", MarketDiscoveryPresentation.availabilityReason(for: representation, providerDiscovery: provider)),
                ])
            }

            if let retirement = representation.retirement {
                DiscoveryPanel("Lifecycle") {
                    DiscoveryFactsGrid([
                        ("State", retirement.lifecycleState.displayStatus),
                        ("Retired on", retirement.completedAt),
                        ("Reason", retirement.reason.displayStatus),
                        ("Commissioned timeframes", retirement.selectedLanes.joined(separator: ", ")),
                    ])
                }
            } else {
                TimeframeAvailabilityView(lanes: representation.timeframeLanes)
            }

            if let fx = market.fxOrientation,
               fx.orientationState != "DIRECT_PROVIDER_SUPPORTED" {
                DiscoveryPanel("FX Pair Orientation") {
                    VStack(alignment: .leading, spacing: 8) {
                        DiscoveryFactsGrid([
                            ("Ordered identity", fx.orderedPair),
                            ("Orientation", fx.orientationState.displayStatus),
                            ("Direct provider symbol", fx.requestedProviderSymbol ?? "Not confirmed"),
                            ("Authoritative inverse", fx.inversePair),
                        ])
                        if fx.orientationState == "INVERSE_ONLY" {
                            Button("Open \(fx.inversePair)") { onOpenInverse(fx.inversePair) }
                        }
                    }
                }
            }
        }
    }

    private var registrationComplete: some View {
        DiscoveryPanel("Registration Complete") {
            DiscoveryFactsGrid([
                ("Registration identifier", registeredSymbol ?? "Unknown"),
                ("Authority state", registeredStatus ?? "REGISTERED_NO_EVIDENCE"),
                ("Provider mapping", selected?.providerMappingStatus.displayStatus ?? "Unknown"),
            ])
        }
    }

    private var primaryActionBar: some View {
        let action = MarketDiscoveryPresentation.primaryAction(
            for: selected,
            newlyRegisteredSymbol: registeredSymbol
        )
        return HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(primaryActionTitle(action))
                    .font(.caption.bold())
                Text(primaryActionReason(action))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer(minLength: 12)

            if let selected,
               MarketDiscoveryPresentation.isActive(selected) {
                Menu {
                    Button("Open Manage Data") { onOpenManageData(selected.symbol) }
                    Button("Authority History") { onHistory(selected.symbol) }
                    Divider()
                    Button("Retire Instrument", role: .destructive) { onRetire(selected.symbol) }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
                .menuStyle(.borderlessButton)
                .help("More actions")
            } else if let selected, selected.retirement != nil {
                Menu {
                    if selected.retirement?.reason == "INCORRECT_INSTRUMENT_IDENTITY" {
                        Button("Keep Retired") { }
                    }
                    Button("Permanently Remove", role: .destructive) {
                        onPermanentRemove(selected.symbol)
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
                .menuStyle(.borderlessButton)
                .help("More actions")
            }

            Button(primaryActionTitle(action)) { perform(action) }
                .buttonStyle(.borderedProminent)
                .disabled(action == .selectRepresentation || action == .unavailable)
                .accessibilityHint(primaryActionReason(action))
        }
        .padding(14)
        .background(.regularMaterial)
    }

    private func perform(_ action: MarketPrimaryAction) {
        guard let selected else { return }
        switch action {
        case .approveMappingAndAdd:
            if let plan = selected.registrationPlan { onReviewRegistration(plan, selected) }
        case .addToEstate:
            if let plan = selected.registrationPlan { onReviewRegistration(plan, selected) }
        case .completeProviderSetup:
            if let plan = selected.registrationPlan { onReviewRegistration(plan, selected) }
        case .openInEstate:
            onOpenEstate(selected.symbol)
        case .reactivate:
            onReactivate(selected.symbol)
        case .registerCorrectInstrument:
            onRegisterCorrectInstrument()
        case .openManageData:
            onOpenManageData(selected.symbol)
        case .resumeInitialHistory:
            onOpenManageData(selected.symbol)
        case .repairPublication:
            onOpenManageData(selected.symbol)
        case .selectRepresentation, .unavailable:
            break
        }
    }

    private func primaryActionReason(_ action: MarketPrimaryAction) -> String {
        guard let selected else {
            return "Choose one representation from the list above."
        }
        switch action {
        case .approveMappingAndAdd:
            return "Approve the selected provider mapping, add the registration, and commission D1."
        case .addToEstate:
            return MarketDiscoveryPresentation.availabilityReason(
                for: selected,
                providerDiscovery: provider(for: selected)
            )
        case .completeProviderSetup:
            return "Approve the selected provider representation without recreating the canonical instrument."
        case .openInEstate:
            return "This representation is already active; a duplicate will not be created."
        case .reactivate:
            return "Existing authority and evidence will be preserved."
        case .registerCorrectInstrument:
            return "Keep the incorrect identity retired and start a separately reviewed registration. Evidence will not be reassigned."
        case .openManageData:
            return "Registration completed; continue to controlled acquisition."
        case .resumeInitialHistory:
            return "Continue to governed initial history acquisition for this registered symbol."
        case .repairPublication:
            return "Open controlled acquisition and refresh the Estate Truth publication."
        case .unavailable:
            return MarketDiscoveryPresentation.availabilityReason(
                for: selected,
                providerDiscovery: provider(for: selected)
            )
        case .selectRepresentation:
            return "Choose one representation from the list above."
        }
    }

    private func primaryActionTitle(_ action: MarketPrimaryAction) -> String {
        guard let selected else { return action.rawValue }
        switch action {
        case .approveMappingAndAdd, .addToEstate:
            return "\(action.rawValue) \(selected.symbol)"
        default:
            return action.rawValue
        }
    }

    private func provider(for representation: MarketRepresentation) -> MarketProviderDiscovery? {
        market.providerDiscovery.first { $0.representationSymbol == representation.symbol }
    }

    private func countryOrMarket(for representation: MarketRepresentation) -> String {
        switch market.assetClass.uppercased() {
        case "AUSTRALIAN_EQUITIES":
            return "Australia"
        case "US_EQUITIES":
            return "United States"
        case "UK_EQUITIES":
            return "United Kingdom"
        case "GERMAN_EQUITIES":
            return "Germany"
        default:
            return representation.exchange ?? market.metadata.market
        }
    }

    private func providerSupport(
        _ provider: MarketProviderDiscovery?,
        representation: MarketRepresentation
    ) -> String {
        guard let provider else { return "Not established" }
        if let name = provider.provider {
            return "\(name.displayStatus) · \(provider.availability.displayStatus)"
        }
        return representation.providerMappingStatus.displayStatus
    }
}

private struct RepresentationChoiceRow: View {
    let representation: MarketRepresentation
    let providerDiscovery: MarketProviderDiscovery?

    var body: some View {
        let status = MarketDiscoveryPresentation.availability(
            for: representation,
            providerDiscovery: providerDiscovery
        )
        let timeframes = MarketDiscoveryPresentation.supportedTimeframes(
            for: representation,
            providerDiscovery: providerDiscovery
        )

        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(representation.symbol)
                    .font(.body.monospaced().bold())
                Text(representation.representationType.displayStatus)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Text(status.rawValue)
                    .font(.caption.bold())
            }
            HStack {
                Text(representation.displayName).lineLimit(1)
                Spacer()
                Text(timeframes.isEmpty ? "No timeframes" : timeframes.joined(separator: ", "))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Text(MarketDiscoveryPresentation.availabilityReason(
                for: representation,
                providerDiscovery: providerDiscovery
            ))
            .font(.caption)
            .foregroundStyle(.secondary)
            .lineLimit(1)
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            "\(representation.symbol), \(representation.representationType.displayStatus), \(status.rawValue), \(MarketDiscoveryPresentation.availabilityReason(for: representation, providerDiscovery: providerDiscovery))"
        )
    }
}

struct RegistrationReviewContext: Identifiable {
    let plan: MarketRegistrationPlan
    let representation: MarketRepresentation

    var id: String { plan.candidate }
    var isProviderCompletion:Bool { representation.acquisitionReadiness.uppercased()=="PROVIDER_SETUP_INCOMPLETE" }
    var isMappingApprovalAdd:Bool { !isProviderCompletion && representation.providerMappingStatus.uppercased()=="REVIEW_REQUIRED" }
    var isUnmappedRegistration: Bool { plan.providerMappings.isEmpty }
    var canConfirm:Bool { true }
    var initialCommissionedTimeframes: [String] { ["D1"] }
    var eligibleProviders: String {
        plan.providerMappings.isEmpty
            ? "Provider discovery will run after registration"
            : plan.providerMappings.map { "\($0.provider.displayStatus) (\($0.symbol))" }.joined(separator: ", ")
    }
    var limitations: [String] {
        Array(Set(plan.knownUnknowns + plan.registrationWarnings + representation.warnings)).sorted()
    }
}

struct MarketRegistrationReview: View {
    let context: RegistrationReviewContext
    let onConfirm: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(context.isProviderCompletion ? "Review Provider Setup":context.isMappingApprovalAdd ? "Review Mapping and Add":context.isUnmappedRegistration ? "Register and Discover Provider":"Review Add to Estate")
                .font(.title.bold())
            Text(context.isProviderCompletion ? "The canonical instrument is preserved; provider authority changes only after confirmation and readback.":context.isMappingApprovalAdd ? "Provider mapping approval and Estate registration are committed together after confirmation and readback.":context.isUnmappedRegistration ? "The canonical FX instrument will be added now. Provider discovery starts automatically; acquisition remains pending until a provider representation is verified.":"No registration occurs until you confirm.")
                .foregroundStyle(.secondary)

            DiscoveryFactsGrid([
                ("Canonical market", context.plan.underlyingMarket),
                ("Selected representation", context.plan.selectedRepresentation),
                ("Symbol", context.plan.canonicalRegistrationSymbol),
                ("Asset class", context.plan.assetClass.displayStatus),
                ("Instrument type", context.plan.instrumentType.displayStatus),
                ("Initial commissioned timeframes", context.initialCommissionedTimeframes.joined(separator: ", ")),
                ("Selected provider representation", context.eligibleProviders),
                ("Known limitations", context.limitations.isEmpty ? "None known" : context.limitations.joined(separator: " · ")),
            ])

            HStack {
                Button("Cancel", role: .cancel) { dismiss() }
                Spacer()
                Button(context.isProviderCompletion ? "Approve and Complete Setup":context.isMappingApprovalAdd ? "Approve Mapping and Add":context.isUnmappedRegistration ? "Add and Discover Provider":"Confirm Add to Estate") {
                    dismiss()
                    onConfirm()
                }
                .buttonStyle(.borderedProminent)
                .disabled(!context.canConfirm)
            }
        }
        .padding(24)
        .frame(minWidth: 620, idealWidth: 700)
    }
}

private struct TimeframeAvailabilityView: View {
    let lanes: [MarketTimeframeLane]

    var body: some View {
        DiscoveryPanel("Timeframe Availability") {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(lanes) { lane in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack {
                            Text(lane.timeframe).font(.body.monospaced().bold())
                            Text(lane.providerCapability.displayStatus)
                            Spacer()
                            Text(lane.registrationState.displayStatus)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Text(lane.reason)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        if let providers=lane.providerCapabilities {
                            ForEach(providers) { provider in
                                HStack(spacing:8) {
                                    Text(provider.provider).fontWeight(.semibold).frame(width:110,alignment:.leading)
                                    Text(provider.providerSymbol ?? "No mapping").monospaced().frame(width:100,alignment:.leading)
                                    Text(provider.eligibility == "ELIGIBLE" ? "Eligible through \(provider.mappingStatus.displayStatus)":(provider.rejectionReason ?? provider.capabilityState).displayStatus)
                                        .foregroundStyle(provider.eligibility == "ELIGIBLE" ? .green:.secondary)
                                }.font(.caption2)
                            }
                        }
                        if let last=lane.lastSuccessfulProvider {
                            Text("Last successful provider: \(last.provider ?? "—") · \(last.providerSymbol ?? "—")")
                                .font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                    if lane.id != lanes.last?.id { Divider() }
                }
            }
        }
    }
}

struct DiscoveryPanel<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    init(_ title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        GroupBox(title) {
            content
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 4)
        }
    }
}

struct DiscoveryFactsGrid: View {
    let rows: [(String, String)]

    init(_ rows: [(String, String)]) { self.rows = rows }

    var body: some View {
        Grid(alignment: .leading, horizontalSpacing: 20, verticalSpacing: 7) {
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                GridRow {
                    Text(row.0).foregroundStyle(.secondary)
                    Text(row.1)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }
}

private struct CompactMessage: View {
    let title: String
    let message: String
    let systemImage: String
    let tint: Color

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: systemImage).foregroundStyle(tint)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.caption.bold())
                Text(message).font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(9)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(tint.opacity(0.09), in: RoundedRectangle(cornerRadius: 8))
    }
}

extension String {
    var displayStatus: String {
        replacingOccurrences(of: "_", with: " ").capitalized
    }

    var normalizedMarketSearch: String {
        uppercased().filter { $0.isLetter || $0.isNumber || $0 == "^" || $0 == "&" }
    }
}
