import OperationsCore
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store:ConsoleStore
    var body: some View {
        NavigationSplitView {
            List(selection:$store.section) { ForEach(ConsoleSection.allCases) { section in Label(section.rawValue,systemImage:section.icon).tag(section) } }.listStyle(.sidebar).navigationSplitViewColumnWidth(min:180,ideal:210,max:240)
        } detail: {
            Group { switch store.section { case .overview: OverviewView(); case .estate: TruthConsoleView(); case .scheduler: SchedulerMonitorView(); case .history: MarketHistoryView(); case .readOnlyClients: ReadOnlyClientsView(); case .manageData: ManageDataWorkspaceView() } }
                .toolbar { ToolbarItem { Button { Task{await store.refresh()} } label:{Label("Refresh",systemImage:"arrow.clockwise")}.keyboardShortcut("r",modifiers:.command).disabled(store.isRefreshing || store.activeOperationID != nil) } }
        }
        .navigationSplitViewStyle(.balanced)
        .overlay(alignment:.bottom){
            if let progress=store.estateAdmissionProgress { EstateAdmissionBar(progress:progress) }
            else if store.activeOperationID != nil { ActiveOperationBar() }
        }
    }
}

struct EstateAdmissionBar:View {
    let progress:EstateAdmissionProgress
    var body:some View {
        HStack(spacing:10) {
            ProgressView().controlSize(.small)
            Text("\(progress.symbol) · Initial history").font(.caption.bold())
            Text(progress.stage).font(.caption).foregroundStyle(.secondary)
            Spacer()
            Text("Automatic onboarding").font(.caption).foregroundStyle(.secondary)
        }.padding(10).background(.regularMaterial)
    }
}

struct ActiveOperationBar:View {
    @EnvironmentObject var store:ConsoleStore
    var body:some View {
        HStack(spacing:10) {
            if store.activeOperationIsStale { Image(systemName:"lock.open.trianglebadge.exclamationmark").foregroundStyle(.orange) }
            else { ProgressView().controlSize(.small) }
            if let operation=store.activeDataOperation {
                Text("\(operation.instrument) · \(operation.timeframe)").font(.caption.bold())
            } else {
                Text(store.activeOperationOwner ?? "Operation").font(.caption.bold())
            }
            Text(store.activeOperationState ?? store.dataOperationState.stageLabel).font(.caption).foregroundStyle(.secondary)
            Text("Age \(ageLabel)").font(.caption.monospaced()).foregroundStyle(.secondary)
            Spacer()
            if store.activeOperationIsStale {
                Button("Clear Stale Lock"){store.releaseStaleOperationLockIfSafe()}
            } else {
                Button("Cancel",role:.destructive){store.cancel()}
            }
        }.padding(10).background(.regularMaterial)
    }
    private var ageLabel:String {
        guard let seconds=store.activeOperationAgeSeconds else { return "—" }
        if seconds < 60 { return "\(Int(max(0,seconds)))s" }
        let minutes=Int(seconds/60)
        if minutes < 60 { return "\(minutes)m \(Int(seconds) % 60)s" }
        return "\(minutes/60)h \(minutes % 60)m"
    }
}
