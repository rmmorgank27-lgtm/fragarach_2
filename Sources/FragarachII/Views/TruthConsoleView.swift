import OperationsCore
import SwiftUI

struct TruthConsoleView: View {
    @EnvironmentObject var store: ConsoleStore
    @State private var search = ""
    @State private var selection: TruthHierarchySelection = .estate
    @State private var showInspector = true

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
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Estate Truth").font(.largeTitle).fontWeight(.semibold)
                    TruthBreadcrumbView(segments: breadcrumbSegments(hierarchy: hierarchy), selection: selection, onSelect: navigate)
                    if let condition=store.estateConditionFilter {
                        EstateFindingsView(condition:condition,lanes:estate.truthMatrix,commissioning:estate.commissioningMatrix,onSelect:{ id in store.selectedTruthLaneID = id; selection = .symbol(id) },onClose:{store.estateConditionFilter = nil})
                    } else if search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        browseContent(estate: estate, hierarchy: hierarchy)
                    } else {
                        searchContent
                    }
                }.padding().frame(maxWidth:.infinity,alignment:.leading)
            }
            .inspector(isPresented:$showInspector) {
                ScrollView { contextDetail(estate: estate, hierarchy: hierarchy).padding() }
                    .inspectorColumnWidth(min:300,ideal:380,max:480)
            }
            .searchable(text: $search, prompt: "Search symbol, alias, or market")
            .toolbar { ToolbarItem { Button { showInspector.toggle() } label:{Label("Estate Inspector",systemImage:"sidebar.trailing")}.help(showInspector ? "Hide Estate inspector":"Show Estate inspector") } }
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
            TruthEstateSummaryView(summary: estate.estateSummary,onSelect:store.showEstateFindings)
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
            TruthMatrixView(lanes: filtered, commissioning: commissioning(for:filtered), scheduler:store.schedulerSnapshot, selection: symbolSelection,queueUpdate:{id in Task{await store.queueLaneUpdate(id)}})
        }
    }

    private func marketContent(_ market: EstateMarketGroup) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack { Label(market.name, systemImage: market.systemImage).font(.title2.bold());Spacer();Text("\(market.summary.symbolCount) symbols").foregroundStyle(.secondary) }
            EstateScorecard(title: market.name, systemImage: market.systemImage, summary: market.summary)
            if market.subgroups.isEmpty {
                TruthMatrixView(lanes: market.lanes, commissioning: commissioning(for:market.lanes), scheduler:store.schedulerSnapshot, selection: symbolSelection,queueUpdate:{id in Task{await store.queueLaneUpdate(id)}})
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
            TruthMatrixView(lanes: subgroup.lanes, commissioning: commissioning(for:subgroup.lanes), scheduler:store.schedulerSnapshot, selection: symbolSelection,queueUpdate:{id in Task{await store.queueLaneUpdate(id)}})
        }
    }

    @ViewBuilder private func contextDetail(estate: EstateTruthState, hierarchy: EstateHierarchy) -> some View {
        switch selection {
        case .estate:
            EstateContextDetailView(estate: estate, hierarchy: hierarchy, scheduler: store.schedulerSnapshot)
        case .market(let name):
            if let market = hierarchy.market(named: name) { GroupContextDetailView(title: market.name, subtitle: "Market authority", summary: market.summary) }
        case .subgroup(let marketName, let subgroupName):
            if let subgroup = hierarchy.market(named: marketName)?.subgroups.first(where: { $0.name == subgroupName }) { GroupContextDetailView(title: subgroup.name, subtitle: "\(marketName) subgroup", summary: subgroup.summary) }
        case .symbol:
            if let selectedLane { TruthDetailView(lane: selectedLane,commissioning:estate.commissioningMatrix.first{$0.id==selectedLane.id}) }
            else { ContentUnavailableView("Authority unavailable", systemImage: "exclamationmark.triangle") }
        }
    }

    private var symbolSelection: Binding<String?> {
        Binding(get: { store.selectedTruthLaneID }, set: { id in
            store.selectedTruthLaneID = id
            if let id { selection = .symbol(id) }
        })
    }

    private func commissioning(for lanes:[EstateTruthLane])->[CommissionedLaneState] {
        let symbols=Set(lanes.map(\.symbol))
        return store.estateTruth?.commissioningMatrix.filter{symbols.contains($0.symbol)} ?? []
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

private struct EstateFindingsView: View {
    let condition:String
    let lanes:[EstateTruthLane]
    let commissioning:[CommissionedLaneState]
    let onSelect:(String)->Void
    let onClose:()->Void

    private var matchingCommissioning:[CommissionedLaneState] {
        switch condition {
        case "Required lanes": return commissioning.filter(\.required)
        case "Commissioned lanes": return commissioning.filter(\.commissioned)
        case "Operational lanes": return commissioning.filter(\.operational)
        case "Missing commissions": return commissioning.filter(\.missingCommission)
        case "Not enabled": return commissioning.filter { $0.enabled == false || $0.nonBlocking == true }
        case "Coverage": return commissioning.filter { $0.required && !$0.operational }
        default: return []
        }
    }
    private var matchingLanes:[EstateTruthLane] {
        switch condition {
        case "Healthy": return lanes.filter{$0.truthState.authorityState == "GREEN"}
        case "Attention": return lanes.filter{$0.truthState.authorityState == "AMBER"}
        case "Critical": return lanes.filter{$0.truthState.authorityState == "RED"}
        case "Coverage": return lanes.filter{$0.truthState.coverageScore != 100}
        default: return lanes.filter { lane in matchingCommissioning.contains(where:{$0.id == lane.id}) }
        }
    }
    var body: some View {
        VStack(alignment:.leading,spacing:12) {
            HStack { Text(condition).font(.title2.bold());Spacer();Text("\(matchingLanes.count + max(0, matchingCommissioning.count - matchingLanes.count)) findings").foregroundStyle(.secondary);Button("Done",action:onClose) }
            if matchingLanes.isEmpty && matchingCommissioning.isEmpty {
                ContentUnavailableView("No matching lanes",systemImage:"checkmark.circle",description:Text("This scorecard currently has no underlying findings."))
            } else {
                ForEach(matchingLanes) { lane in
                    Button { onSelect(lane.id) } label: {
                        HStack(alignment:.firstTextBaseline,spacing:10) {
                            Circle().fill(TruthPresentation.color(lane.truthState.authorityState)).frame(width:8,height:8)
                            Text("\(lane.symbol) · \(lane.timeframe)").fontWeight(.semibold)
                            Text(reason(for:lane)).foregroundStyle(.secondary).lineLimit(2)
                            Spacer()
                            Text(lane.operationalStateLabel ?? lane.truthState.authorityState).font(.caption.weight(.semibold))
                        }.padding(10).frame(maxWidth:.infinity,alignment:.leading).background(.regularMaterial,in:RoundedRectangle(cornerRadius:8))
                    }.buttonStyle(.plain)
                }
                ForEach(matchingCommissioning.filter { state in !matchingLanes.contains(where:{$0.id == state.id}) }) { state in
                    HStack { Circle().fill(.red).frame(width:8,height:8);Text("\(state.symbol) · \(state.timeframe)").fontWeight(.semibold);Text(state.missingCommission ? "Required lane is not commissioned" : state.operationalState).foregroundStyle(.secondary);Spacer() }
                        .padding(10).frame(maxWidth:.infinity,alignment:.leading).background(.regularMaterial,in:RoundedRectangle(cornerRadius:8))
                }
            }
        }
    }
    private func reason(for lane:EstateTruthLane)->String {
        if let detail=lane.freshnessDimension?.label,detail != "Current" { return detail }
        if lane.truthState.authorityState == "GREEN" { return "Healthy canonical authority" }
        return lane.gapSummary.operationalImpact == "NOT_MEASURED" ? lane.truthState.validationState : lane.gapSummary.operationalImpact
    }
}
