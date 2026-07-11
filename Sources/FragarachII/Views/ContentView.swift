import OperationsCore
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store:ConsoleStore
    var body: some View {
        NavigationSplitView {
            List(selection:$store.section) { ForEach(ConsoleSection.allCases) { section in Label(section.rawValue,systemImage:section.icon).tag(section) } }.listStyle(.sidebar)
        } detail: {
            Group { switch store.section { case .lanes: LanesView(); case .acquire: AcquireView(); case .importEvidence: ImportView(); case .addInstrument: AddInstrumentView(); case .operations: OperationsView(); case .integrity: IntegrityBackupView(); case .settings: DiagnosticsSettingsView() } }
                .toolbar { ToolbarItem { Button { Task{await store.refresh()} } label:{Label("Refresh",systemImage:"arrow.clockwise")}.disabled(store.isRefreshing) } }
        }
        .overlay(alignment:.bottom){ if store.activeOperationID != nil { ActiveOperationBar() } }
    }
}

struct ActiveOperationBar:View { @EnvironmentObject var store:ConsoleStore;var body:some View{HStack{ProgressView();Text("Operation \(store.activeOperationID?.uuidString ?? "")").font(.caption.monospaced());Spacer();Button("Cancel",role:.destructive){store.cancel()}}.padding(10).background(.regularMaterial)} }
