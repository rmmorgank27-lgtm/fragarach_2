import OperationsCore
import SwiftUI

struct TruthConsoleView: View {
    @EnvironmentObject var store: ConsoleStore
    @State private var search = ""
    @State private var selection: TruthHierarchySelection = .estate

    private var filtered: [EstateTruthLane] {
        guard let lanes = store.estateTruth?.truthMatrix else { return [] }
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return lanes }
        return lanes.filter { lane in
            lane.symbol.localizedCaseInsensitiveContains(query)
            || lane.searchMetadata.displayName.localizedCaseInsensitiveContains(query)
            || lane.searchMetadata.market.localizedCaseInsensitiveContains(query)
            || lane.searchMetadata.assetClass.localizedCaseInsensitiveContains(query)
            || lane.searchMetadata.aliases.contains { $0.alias.localizedCaseInsensitiveContains(query) || $0.normalizedAlias.localizedCaseInsensitiveContains(query) }
        }
    }

    private var selectedLane: EstateTruthLane? {
        guard case .symbol(let id) = selection else { return nil }
        return store.estateTruth?.truthMatrix.first { $0.id == id }
    }

    var body: some View {
        if let estate = store.estateTruth, let hierarchy = store.estateHierarchy {
            HSplitView {
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        Text("Estate Truth").font(.largeTitle).fontWeight(.semibold)
                        TruthBreadcrumbView(segments: breadcrumbSegments(hierarchy: hierarchy), selection: selection, onSelect: navigate)
                        if search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            browseContent(estate: estate, hierarchy: hierarchy)
                        } else {
                            searchContent
                        }
                    }.padding()
                }.frame(minWidth: 620, idealWidth: 820)
                ScrollView { contextDetail(estate: estate, hierarchy: hierarchy) }
                    .frame(minWidth: 400, idealWidth: 500)
            }
            .searchable(text: $search, prompt: "Search symbol, alias, or market")
            .onChange(of: search) { locateExactSearch(in: estate.truthMatrix) }
            .onChange(of: store.truthNavigationRequestID) { consumeNavigationRequest() }
            .onAppear { consumeNavigationRequest() }
        } else if let error = store.estateTruthError {
            ContentUnavailableView("Estate truth unavailable", systemImage: "exclamationmark.triangle", description: Text(error))
        } else {
            VStack(spacing: 12) { ProgressView();Text("Loading EstateTruthState…").foregroundStyle(.secondary) }
        }
    }

    @ViewBuilder private func browseContent(estate: EstateTruthState, hierarchy: EstateHierarchy) -> some View {
        switch selection {
        case .estate:
            TruthEstateSummaryView(summary: estate.estateSummary)
            Text("Markets").font(.title2.bold())
            EstateMarketCardsView(markets: hierarchy.markets) { navigate(.market($0.name)) }
        case .market(let name):
            if let market = hierarchy.market(named: name) { marketContent(market) }
        case .subgroup(let marketName, let subgroupName):
            if let market = hierarchy.market(named: marketName), let subgroup = market.subgroups.first(where: { $0.name == subgroupName }) { subgroupContent(market: market, subgroup: subgroup) }
        case .symbol:
            if let lane = selectedLane, let market = market(for: lane, hierarchy: hierarchy) {
                if let subgroup = subgroup(for: lane, market: market) { subgroupContent(market: market, subgroup: subgroup) }
                else { marketContent(market) }
            }
        }
    }

    private var searchContent: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack { Text("Search Results").font(.title2.bold());Spacer();Text("\(Set(filtered.map(\.symbol)).count) symbols").foregroundStyle(.secondary) }
            TruthMatrixView(lanes: filtered, selection: symbolSelection)
        }
    }

    private func marketContent(_ market: EstateMarketGroup) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack { Label(market.name, systemImage: market.systemImage).font(.title2.bold());Spacer();Text("\(market.summary.symbolCount) symbols").foregroundStyle(.secondary) }
            EstateScorecard(title: market.name, systemImage: market.systemImage, summary: market.summary)
            if market.subgroups.isEmpty {
                TruthMatrixView(lanes: market.lanes, selection: symbolSelection)
            } else {
                Text("Subgroups").font(.headline)
                EstateSubgroupCardsView(subgroups: market.subgroups) { navigate(.subgroup(market: market.name, subgroup: $0.name)) }
            }
        }
    }

    private func subgroupContent(market: EstateMarketGroup, subgroup: EstateSubgroup) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack { Text(subgroup.name).font(.title2.bold());Spacer();Text("\(subgroup.summary.symbolCount) symbols").foregroundStyle(.secondary) }
            EstateScorecard(title: subgroup.name, systemImage: market.systemImage, summary: subgroup.summary)
            TruthMatrixView(lanes: subgroup.lanes, selection: symbolSelection)
        }
    }

    @ViewBuilder private func contextDetail(estate: EstateTruthState, hierarchy: EstateHierarchy) -> some View {
        switch selection {
        case .estate:
            EstateContextDetailView(estate: estate, hierarchy: hierarchy)
        case .market(let name):
            if let market = hierarchy.market(named: name) { GroupContextDetailView(title: market.name, subtitle: "Market authority", summary: market.summary) }
        case .subgroup(let marketName, let subgroupName):
            if let subgroup = hierarchy.market(named: marketName)?.subgroups.first(where: { $0.name == subgroupName }) { GroupContextDetailView(title: subgroup.name, subtitle: "\(marketName) subgroup", summary: subgroup.summary) }
        case .symbol:
            if let selectedLane { TruthDetailView(lane: selectedLane) }
            else { ContentUnavailableView("Authority unavailable", systemImage: "exclamationmark.triangle") }
        }
    }

    private var symbolSelection: Binding<String?> {
        Binding(get: { store.selectedTruthLaneID }, set: { id in
            store.selectedTruthLaneID = id
            if let id { selection = .symbol(id) }
        })
    }

    private func navigate(_ destination: TruthHierarchySelection) { selection = destination }

    private func locateExactSearch(in lanes: [EstateTruthLane]) {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let lane = lanes.first(where: { $0.symbol.caseInsensitiveCompare(query) == .orderedSame }) else { return }
        store.selectedTruthLaneID = lane.id
        selection = .symbol(lane.id)
    }

    private func consumeNavigationRequest() {
        guard let id = store.truthNavigationRequestID else { return }
        store.selectedTruthLaneID = id
        selection = .symbol(id)
        store.truthNavigationRequestID = nil
    }

    private func breadcrumbSegments(hierarchy: EstateHierarchy) -> [(String, TruthHierarchySelection)] {
        var segments: [(String, TruthHierarchySelection)] = [("Estate", .estate)]
        switch selection {
        case .estate: break
        case .market(let market): segments.append((market, .market(market)))
        case .subgroup(let market, let subgroup):
            segments.append((market, .market(market)));segments.append((subgroup, .subgroup(market: market, subgroup: subgroup)))
        case .symbol:
            if let lane = selectedLane, let market = market(for: lane, hierarchy: hierarchy) {
                segments.append((market.name, .market(market.name)))
                if let subgroup = subgroup(for: lane, market: market) { segments.append((subgroup.name, .subgroup(market: market.name, subgroup: subgroup.name))) }
                segments.append((lane.symbol, .symbol(lane.id)))
            }
        }
        return segments
    }

    private func market(for lane: EstateTruthLane, hierarchy: EstateHierarchy) -> EstateMarketGroup? {
        hierarchy.market(named: EstateHierarchyClassifier.marketName(assetClass: lane.searchMetadata.assetClass))
    }

    private func subgroup(for lane: EstateTruthLane, market: EstateMarketGroup) -> EstateSubgroup? {
        guard let name = EstateHierarchyClassifier.subgroupName(market: market.name, symbol: lane.symbol, assetClass: lane.searchMetadata.assetClass, exchange: lane.searchMetadata.exchange) else { return nil }
        return market.subgroups.first { $0.name == name }
    }
}
