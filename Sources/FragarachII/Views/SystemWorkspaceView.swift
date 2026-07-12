import OperationsCore
import SwiftUI

struct SystemWorkspaceView:View {
    @EnvironmentObject private var store:ConsoleStore
    var body:some View { VStack(alignment:.leading,spacing:14) {
        WorkspaceHeader(title:"System",purpose:"Health, protection, configuration, and audit evidence.")
        Picker("Section",selection:$store.systemSection){ForEach(SystemSection.allCases){Text($0.rawValue).tag($0)}}.pickerStyle(.segmented).frame(maxWidth:620)
        Group { switch store.systemSection { case .status:SystemStatusView();case .backups:IntegrityBackupView();case .settings:DiagnosticsSettingsView();case .audit:AuditWorkspaceView() } }.frame(maxWidth:.infinity,maxHeight:.infinity)
    }.padding() }
}

struct WorkspaceHeader:View { let title:String;let purpose:String;var body:some View{VStack(alignment:.leading,spacing:4){Text(title).font(.largeTitle).fontWeight(.semibold);Text(purpose).foregroundStyle(.secondary)}} }

private struct SystemStatusView:View { @EnvironmentObject var store:ConsoleStore;var body:some View{ScrollView{VStack(alignment:.leading,spacing:16){GroupBox("Overall Status"){Label(store.readError==nil ? "GREEN — Operational":"AMBER — Review required",systemImage:"circle.fill").foregroundStyle(store.readError==nil ? .green:.orange)};GroupBox("Runtime Health"){Facts([("Database Integrity",store.readError==nil ? "Readable":"Review required"),("Writer State",store.activeOperationID==nil ? "Idle":"Operation active"),("Runtime Database",store.databasePath),("Authority Manifest","RATIFIED"),("Constitutional Documents","50 controlled"),("Provider Credential",store.credentialAvailable ? "Available (redacted)":"Unavailable"),("Application Build",Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "Development")])};Button("Run Database Verification"){Task{await store.run(.verify)}}.buttonStyle(.borderedProminent).disabled(store.activeOperationID != nil);ResultPanel()}.frame(maxWidth:850,alignment:.leading)}} }
