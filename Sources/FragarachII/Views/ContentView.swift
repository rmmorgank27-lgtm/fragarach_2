import OperationsCore
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store:ConsoleStore
    var body: some View {
        NavigationSplitView {
            List(selection:$store.section) { ForEach(ConsoleSection.allCases) { section in Label(section.rawValue,systemImage:section.icon).tag(section) } }.listStyle(.sidebar).navigationSplitViewColumnWidth(min:180,ideal:210,max:240)
        } detail: {
            Group { switch store.section { case .truth: TruthConsoleView(); case .discoverMarket: DiscoverMarketView(); case .dataOperations: DataOperationsView(); case .system: SystemWorkspaceView() } }
                .toolbar { ToolbarItem { Button { Task{await store.refresh()} } label:{Label("Refresh",systemImage:"arrow.clockwise")}.keyboardShortcut("r",modifiers:.command).disabled(store.isRefreshing || store.activeOperationID != nil) } }
        }
        .overlay(alignment:.bottom){ if store.activeOperationID != nil { ActiveOperationBar() } }
    }
}

struct ActiveOperationBar:View { @EnvironmentObject var store:ConsoleStore;var body:some View{HStack{ProgressView();Text("Operation \(store.activeOperationID?.uuidString ?? "")").font(.caption.monospaced());Spacer();Button("Cancel",role:.destructive){store.cancel()}}.padding(10).background(.regularMaterial)} }
