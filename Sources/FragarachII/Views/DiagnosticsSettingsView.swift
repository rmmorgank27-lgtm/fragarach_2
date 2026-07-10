import SwiftUI

struct DiagnosticsSettingsView:View {
    @EnvironmentObject var store:ConsoleStore
    var body:some View{ScrollView{Form{Section("Authority database"){TextField("Database path",text:$store.databasePath);Button("Choose…"){if let url=PanelService.chooseDatabase(){store.databasePath=url.path;Task{await store.refresh()}}}};Section("Development CLI"){TextField("Repository",text:$store.repositoryPath);TextField("Python executable",text:$store.pythonPath);LabeledContent("CLI identity",value:"fragarach_ii.operations_cli.v1");LabeledContent("Source commit",value:"c77aec4 + SPEC-005 working tree")};Section("Application"){LabeledContent("Product",value:"Fragarach II");LabeledContent("Authority status",value:"Candidate Authority");LabeledContent("Minimum macOS",value:"14.0");Text("Preferences store paths and presentation choices only. Credentials and authority facts are never persisted here.").foregroundStyle(.secondary)}}.padding()}}
}
