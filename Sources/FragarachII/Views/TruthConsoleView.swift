import OperationsCore
import SwiftUI

struct TruthConsoleView:View {
    @EnvironmentObject var store:ConsoleStore
    @State private var search=""
    private var filtered:[EstateTruthLane] {
        guard let lanes=store.estateTruth?.truthMatrix else{return []}
        guard !search.isEmpty else{return lanes}
        return lanes.filter { lane in
            lane.symbol.localizedCaseInsensitiveContains(search)
            || lane.searchMetadata.market.localizedCaseInsensitiveContains(search)
            || lane.searchMetadata.aliases.contains { $0.alias.localizedCaseInsensitiveContains(search) || $0.normalizedAlias.localizedCaseInsensitiveContains(search) }
        }
    }
    private var selected:EstateTruthLane? { store.estateTruth?.truthMatrix.first{$0.id==store.selectedTruthLaneID} }
    var body:some View {
        if let estate=store.estateTruth {
            HSplitView {
                ScrollView {
                    VStack(alignment:.leading,spacing:18) {
                        Text("Truth").font(.largeTitle).fontWeight(.semibold)
                        TruthEstateSummaryView(summary:estate.estateSummary)
                        TruthMatrixView(lanes:filtered,selection:$store.selectedTruthLaneID)
                    }.padding()
                }.frame(minWidth:620,idealWidth:760)
                ScrollView {
                    if let selected { TruthDetailView(lane:selected) }
                    else { ContentUnavailableView("Select authority",systemImage:"checkmark.seal",description:Text("Select a Symbol × Timeframe cell to inspect its TruthState.")) }
                }.frame(minWidth:400,idealWidth:500)
            }.searchable(text:$search,prompt:"Search symbol, alias, or market")
        } else if let error=store.estateTruthError {
            ContentUnavailableView("Estate truth unavailable",systemImage:"exclamationmark.triangle",description:Text(error))
        } else {
            VStack(spacing:12){ProgressView();Text("Loading EstateTruthState…").foregroundStyle(.secondary)}
        }
    }
}
