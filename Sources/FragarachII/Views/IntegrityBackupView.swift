import OperationsCore
import SwiftUI

struct IntegrityBackupView:View {
    @EnvironmentObject var store:ConsoleStore;@State private var backupURL:URL?;@State private var reviewBackup=false
    var body:some View{ScrollView{VStack(alignment:.leading,spacing:18){Text("Integrity & Backup").font(.largeTitle);Text(store.databasePath).font(.caption.monospaced()).textSelection(.enabled);HStack{Button("Run Verification"){Task{await store.run(.verify)}}.buttonStyle(.borderedProminent).disabled(store.activeOperationID != nil);Button("Choose Backup Destination…"){backupURL=PanelService.chooseBackup();reviewBackup=backupURL != nil}.disabled(store.activeOperationID != nil)};Text("Verification and backup are explicit CLI operations and never run on launch or refresh.").foregroundStyle(.secondary);ResultPanel()}.padding().frame(maxWidth:800,alignment:.leading)}.confirmationDialog("Create Verified Backup",isPresented:$reviewBackup,titleVisibility:.visible){Button("Create Backup"){if let backupURL{Task{await store.run(.backup(destination:backupURL.path))}}};Button("Cancel",role:.cancel){}}message:{Text("Source: \(store.databasePath)\nDestination: \(backupURL?.path ?? "")\nExisting files are never overwritten.")}}
}
