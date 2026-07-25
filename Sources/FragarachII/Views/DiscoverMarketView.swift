import OperationsCore
import SwiftUI

private struct MarketSearchFocusActionKey: FocusedValueKey {
    typealias Value = () -> Void
}

extension FocusedValues {
    var focusMarketSearch: (() -> Void)? {
        get { self[MarketSearchFocusActionKey.self] }
        set { self[MarketSearchFocusActionKey.self] = newValue }
    }
}

struct MarketSearchCommands: Commands {
    @FocusedValue(\.focusMarketSearch) private var focusMarketSearch

    var body: some Commands {
        CommandMenu("Market") {
            Button("Find Market") { focusMarketSearch?() }
                .keyboardShortcut("f", modifiers: .command)
                .disabled(focusMarketSearch == nil)
        }
    }
}

struct DiscoverMarketView: View {
    @EnvironmentObject private var store: ConsoleStore
    @AppStorage("discoverRecentSearches") private var storedRecentSearches = ""
    @FocusState private var searchFocused: Bool

    @State private var query = ""
    @State private var discovery: MarketDiscoveryResult?
    @State private var selectedMarketID: String?
    @State private var selectedRepresentationID: String?
    @State private var highlightedResult: DiscoveryResultTarget?
    @State private var assetFilter: MarketAssetFilter = .all
    @State private var isSearching = false
    @State private var pendingQuery: String?
    @State private var lastSubmittedQuery = ""
    @State private var searchError: String?
    @State private var debounceTask: Task<Void, Never>?
    @State private var narrowDetailVisible = false

    @State private var reviewContext: RegistrationReviewContext?
    @State private var registeredSymbol: String?
    @State private var registeredStatus: String?
    @State private var retirementImpact: RetirementImpact?
    @State private var retirementReceipt: RetirementReceipt?
    @State private var removalImpact: PermanentRemovalImpact?
    @State private var reactivationReceipt: ReactivationReceipt?
    @State private var removalReceipt: PermanentRemovalReceipt?

    private var filteredMarkets: [DiscoveredMarket] {
        (discovery?.markets ?? []).filter { assetFilter.includes(assetClass: $0.assetClass) }
    }

    private var selectedMarket: DiscoveredMarket? {
        filteredMarkets.first { $0.id == selectedMarketID }
    }

    private var selectedRepresentation: MarketRepresentation? {
        selectedMarket?.representations.first { $0.id == selectedRepresentationID }
    }

    private var resultSections: [DiscoveryResultSection] {
        guard let discovery else { return [] }
        return DiscoveryResultBuilder.sections(
            for: discovery,
            markets: filteredMarkets,
            query: query
        )
    }

    private var recentSearches: [String] {
        storedRecentSearches
            .split(separator: "|")
            .map(String.init)
            .filter { !$0.isEmpty }
    }

    private var unresolvedManualRequests: [SchedulerManualRequest] {
        (store.schedulerSnapshot?.manualRequests ?? [])
            .filter { $0.status.uppercased() != "DISMISSED" }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Discover Market")
                    .font(.largeTitle.bold())
                Text("Find a market, then choose the representation Fragarach will track.")
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 20)
            .padding(.top, 16)
            .padding(.bottom, 12)

            Divider()

            GeometryReader { proxy in
                let isNarrow = MarketDiscoveryPresentation.usesNarrowLayout(
                    availableWidth: proxy.size.width
                )
                Group {
                    if isNarrow, narrowDetailVisible, let selectedMarket {
                        detailPane(for: selectedMarket, showsBack: true)
                    } else if isNarrow {
                        searchPane(isNarrow: true)
                    } else {
                        HStack(spacing: 0) {
                            searchPane(isNarrow: false)
                                .frame(width: proxy.size.width * 0.39)
                            Divider()
                            detailPane(for: selectedMarket, showsBack: false)
                                .frame(maxWidth: .infinity)
                        }
                    }
                }
                .onExitCommand { handleEscape(isNarrow: isNarrow) }
            }
        }
        .focusedSceneValue(\.focusMarketSearch, { searchFocused = true })
        .onAppear { searchFocused = true; consumeProviderSetupRequest() }
        .onChange(of: store.marketDiscoveryRequest) { _, _ in consumeProviderSetupRequest() }
        .onDisappear { debounceTask?.cancel() }
        .onChange(of: query) { _, value in scheduleDebouncedSearch(for: value) }
        .onChange(of: assetFilter) { reconcileFilteredSelection() }
        .sheet(item: $reviewContext) { context in
            MarketRegistrationReview(
                context: context,
                onConfirm: { confirmRegistration(context.plan) }
            )
        }
        .sheet(item: $retirementImpact) { impact in
            MarketRetirementReview(impact: impact, onConfirm: confirmRetirement)
        }
        .sheet(item: $retirementReceipt) { receipt in
            MarketRetirementSuccess(receipt: receipt) {
                retirementReceipt = nil
                searchImmediately(receipt.canonicalInstrument)
            }
        }
        .sheet(item: $removalImpact) { impact in
            MarketPermanentRemovalReview(impact: impact, onConfirm: confirmPermanentRemoval)
        }
        .sheet(item: $reactivationReceipt) { receipt in
            MarketReactivationSuccess(receipt: receipt) {
                reactivationReceipt = nil
                continueToAcquire(receipt.canonicalInstrument)
            }
        }
        .sheet(item: $removalReceipt) { receipt in
            MarketPermanentRemovalSuccess(receipt: receipt) {
                removalReceipt = nil
                searchImmediately(receipt.canonicalInstrument)
            }
        }
    }

    private func searchPane(isNarrow: Bool) -> some View {
        DiscoverySearchPane(
            query: $query,
            searchFocused: $searchFocused,
            assetFilter: $assetFilter,
            highlightedResult: Binding(
                get: { highlightedResult },
                set: { target in
                    guard let target else { return }
                    selectResult(target, openNarrowDetail: isNarrow)
                }
            ),
            sections: resultSections,
            discovery: discovery,
            isSearching: isSearching,
            error: searchError,
            recentSearches: recentSearches,
            manualRequests: unresolvedManualRequests,
            onSubmit: submitFromKeyboard,
            onSearchSuggestion: searchImmediately,
            onMove: moveHighlight,
            onOpenControlledWorkflow: openControlledWorkflow
        )
    }

    @ViewBuilder
    private func detailPane(for market: DiscoveredMarket?, showsBack: Bool) -> some View {
        if let market {
            DiscoveryMarketDetailPane(
                market: market,
                selection: $selectedRepresentationID,
                registeredSymbol: registeredSymbol,
                registeredStatus: registeredStatus,
                showsBack: showsBack,
                onBack: { narrowDetailVisible = false },
                onReviewRegistration: { plan, representation in
                    reviewContext = RegistrationReviewContext(
                        plan: plan,
                        representation: representation
                    )
                },
                onOpenEstate: openExisting,
                onOpenManageData: continueToAcquire,
                onOpenInverse: searchImmediately,
                onRetire: planRetirement,
                onReactivate: reactivate,
                onRegisterCorrectInstrument: { query="";discovery=nil;selectedMarketID=nil;selectedRepresentationID=nil;searchFocused=true },
                onPermanentRemove: planPermanentRemoval,
                onHistory: openHistory
            )
        } else {
            DiscoveryDetailEmptyState()
        }
    }

    private func scheduleDebouncedSearch(for value: String) {
        debounceTask?.cancel()
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            discovery = nil
            selectedMarketID = nil
            selectedRepresentationID = nil
            highlightedResult = nil
            searchError = nil
            narrowDetailVisible = false
            pendingQuery = nil
            return
        }
        debounceTask = Task {
            try? await Task.sleep(for: .milliseconds(320))
            guard !Task.isCancelled else { return }
            await executeSearch(trimmed)
        }
    }

    private func submitFromKeyboard() {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        debounceTask?.cancel()
        if lastSubmittedQuery.caseInsensitiveCompare(trimmed) == .orderedSame,
           let highlightedResult {
            selectResult(highlightedResult, openNarrowDetail: true)
        } else {
            Task { await executeSearch(trimmed) }
        }
    }

    private func searchImmediately(_ value: String) {
        query = value
        debounceTask?.cancel()
        Task { await executeSearch(value.trimmingCharacters(in: .whitespacesAndNewlines)) }
    }

    private func consumeProviderSetupRequest() {
        guard let symbol=store.marketDiscoveryRequest else { return }
        store.marketDiscoveryRequest=nil
        searchImmediately(symbol)
    }

    @MainActor
    private func executeSearch(_ requestedQuery: String) async {
        guard !requestedQuery.isEmpty else { return }
        if isSearching {
            pendingQuery = requestedQuery
            return
        }

        isSearching = true
        searchError = nil
        lastSubmittedQuery = requestedQuery
        let response: MarketDiscoveryResult?
        do {
            response = try await store.discoverMarket(requestedQuery)
        } catch {
            response = nil
            searchError = readableSearchError(error)
        }

        if let response,
           response.query.caseInsensitiveCompare(requestedQuery) == .orderedSame,
           query.trimmingCharacters(in: .whitespacesAndNewlines)
            .caseInsensitiveCompare(requestedQuery) == .orderedSame {
            apply(response)
            rememberSearch(requestedQuery)
        }

        isSearching = false
        let next = pendingQuery
        pendingQuery = nil
        if let next,
           next.caseInsensitiveCompare(requestedQuery) != .orderedSame {
            await executeSearch(next)
        }
    }

    private func apply(_ response: MarketDiscoveryResult) {
        discovery = response
        registeredSymbol = nil
        registeredStatus = nil
        searchError = nil
        narrowDetailVisible = false

        if response.markets.count == 1, let market = response.markets.first {
            selectedMarketID = market.id
            selectedRepresentationID = MarketDiscoveryPresentation.initialRepresentationID(for: market)
            highlightedResult = .market(market.id)
        } else {
            selectedMarketID = nil
            selectedRepresentationID = nil
            highlightedResult = resultSections.first?.items.first?.target
        }
        reconcileFilteredSelection()
    }

    private func selectResult(_ target: DiscoveryResultTarget, openNarrowDetail: Bool) {
        highlightedResult = target
        switch target {
        case .market(let marketID), .alias(let marketID, nil):
            selectedMarketID = marketID
            selectedRepresentationID = filteredMarkets
                .first { $0.id == marketID }
                .flatMap(MarketDiscoveryPresentation.initialRepresentationID)
        case .representation(let marketID, let representationID),
             .existing(let marketID, let representationID),
             .alias(let marketID, .some(let representationID)):
            selectedMarketID = marketID
            selectedRepresentationID = representationID
        }
        if openNarrowDetail { narrowDetailVisible = true }
    }

    private func moveHighlight(_ direction: MoveCommandDirection) {
        let items = resultSections.flatMap(\.items)
        guard !items.isEmpty else { return }
        let current = highlightedResult.flatMap { selected in
            items.firstIndex { $0.target == selected }
        }
        let index: Int
        switch direction {
        case .down:
            index = min((current ?? -1) + 1, items.count - 1)
        case .up:
            index = max((current ?? items.count) - 1, 0)
        default:
            return
        }
        selectResult(items[index].target, openNarrowDetail: false)
    }

    private func reconcileFilteredSelection() {
        guard let selectedMarketID,
              filteredMarkets.contains(where: { $0.id == selectedMarketID }) else {
            selectedMarketID = filteredMarkets.count == 1 ? filteredMarkets.first?.id : nil
            selectedRepresentationID = filteredMarkets.first.flatMap(
                MarketDiscoveryPresentation.initialRepresentationID
            )
            highlightedResult = resultSections.first?.items.first?.target
            narrowDetailVisible = false
            return
        }
    }

    private func handleEscape(isNarrow: Bool) {
        if isNarrow, narrowDetailVisible {
            narrowDetailVisible = false
        } else if !query.isEmpty {
            query = ""
            searchFocused = true
        }
    }

    private func rememberSearch(_ value: String) {
        var searches = recentSearches.filter {
            $0.caseInsensitiveCompare(value) != .orderedSame
        }
        searches.insert(value, at: 0)
        storedRecentSearches = searches.prefix(5).joined(separator: "|")
    }

    private func readableSearchError(_ error: Error) -> String {
        let detail = error.localizedDescription.trimmingCharacters(in: .whitespacesAndNewlines)
        return !detail.isEmpty
            ? "Search is temporarily unavailable. \(detail)"
            : "Search is temporarily unavailable. Your query and prior results have been preserved."
    }

    private func confirmRegistration(_ plan: MarketRegistrationPlan) {
        reviewContext = nil
        Task {
            await store.run(.registerInstrument(candidate: plan.candidate))
            guard store.lastProcessResult?.exitCode == 0 else {
                searchError = readableRegistrationError()
                return
            }
            registeredSymbol = plan.canonicalRegistrationSymbol
            registeredStatus = store.lastProcessResult?.JSON?["provider_setup_status"] as? String
                ?? store.lastProcessResult?.JSON?["registration_status"] as? String
            let reconciliation=store.lastProcessResult?.JSON?["scheduler_reconciliation"] as? [String:Any]
            let timeframes=reconciliation?["queued_timeframes"] as? [String] ?? []
            if !timeframes.isEmpty {
                store.beginEstateAdmission(symbol:plan.canonicalRegistrationSymbol,timeframes:timeframes)
            }
            continueToAcquire(plan.canonicalRegistrationSymbol)
            Task { await store.refreshProviderFacts() }
        }
    }

    private func readableRegistrationError() -> String {
        guard let payload = store.lastProcessResult?.JSON else {
            return "Registration could not be completed. "
                + (store.operationError ?? "Check the configured authority database and try again.")
        }
        let code = (payload["code"] as? String ?? "REGISTRATION_REJECTED")
            .replacingOccurrences(of: "_", with: " ").lowercased()
        if payload["code"] as? String == "WRITER_BUSY" {
            return "The Scheduler was briefly committing authority data. GBPCHF was not changed; please press Add to Estate again in a few seconds."
        }
        let detail = (payload["error"] as? String ?? "The registration was rejected.")
            .replacingOccurrences(of: "_", with: " ").lowercased()
        return "Registration could not be completed (\(code)): \(detail)."
    }

    private func openExisting(_ symbol: String) {
        let id = "\(symbol):D1"
        store.selectedTruthLaneID = id
        store.truthNavigationRequestID = id
        store.section = .estate
    }

    private func continueToAcquire(_ symbol: String) {
        store.acquisitionAsset = symbol
        store.dataOperationsMode = .fetch
        store.manageDataSection = .operations
        store.section = .manageData
    }

    private func openControlledWorkflow() {
        store.dataOperationsMode = .importFile
        store.manageDataSection = .operations
    }

    private func openHistory(_ symbol: String) {
        store.auditFilter = symbol
        store.navigate(.authorityLedger)
    }

    private func planRetirement(_ symbol: String) {
        Task {
            await store.run(.retirementPlan(asset: symbol, scope: "WHOLE_INSTRUMENT", lanes: ["D1"]))
            guard store.lastProcessResult?.exitCode == 0,
                  let data = store.lastProcessResult?.stdout.data(using: .utf8),
                  let impact = try? JSONDecoder().decode(RetirementImpact.self, from: data) else {
                searchError = store.operationError ?? "Retirement impact could not be loaded."
                return
            }
            retirementImpact = impact
        }
    }

    private func confirmRetirement(
        _ impact: RetirementImpact,
        _ reason: String,
        _ note: String,
        _ confirmation: String
    ) {
        retirementImpact = nil
        Task {
            await store.run(.retireInstrument(
                asset: impact.canonicalInstrument,
                scope: impact.scope,
                lanes: impact.selectedLanes,
                reason: reason,
                note: note,
                confirmation: confirmation
            ))
            guard store.lastProcessResult?.exitCode == 0,
                  let data = store.lastProcessResult?.stdout.data(using: .utf8),
                  let receipt = try? JSONDecoder().decode(RetirementReceipt.self, from: data) else {
                searchError = store.operationError ?? "Retirement failed."
                return
            }
            retirementReceipt = receipt
        }
    }

    private func reactivate(_ symbol: String) {
        Task {
            await store.run(.reactivateInstrument(asset: symbol))
            guard store.lastProcessResult?.exitCode == 0,
                  let data = store.lastProcessResult?.stdout.data(using: .utf8),
                  let receipt = try? JSONDecoder().decode(ReactivationReceipt.self, from: data) else {
                searchError = store.operationError ?? "Reactivation failed."
                return
            }
            reactivationReceipt = receipt
        }
    }

    private func planPermanentRemoval(_ symbol: String) {
        Task {
            await store.run(.permanentRemovalPlan(asset: symbol))
            guard store.lastProcessResult?.exitCode == 0,
                  let data = store.lastProcessResult?.stdout.data(using: .utf8),
                  let impact = try? JSONDecoder().decode(PermanentRemovalImpact.self, from: data) else {
                searchError = store.operationError ?? "Removal impact could not be loaded."
                return
            }
            removalImpact = impact
        }
    }

    private func confirmPermanentRemoval(
        _ impact: PermanentRemovalImpact,
        _ confirmation: String
    ) {
        removalImpact = nil
        Task {
            await store.run(.permanentlyRemoveInstrument(
                asset: impact.canonicalInstrument,
                confirmation: confirmation
            ))
            guard store.lastProcessResult?.exitCode == 0,
                  let data = store.lastProcessResult?.stdout.data(using: .utf8),
                  let receipt = try? JSONDecoder().decode(PermanentRemovalReceipt.self, from: data) else {
                searchError = store.operationError ?? "Permanent removal failed."
                return
            }
            removalReceipt = receipt
        }
    }
}
