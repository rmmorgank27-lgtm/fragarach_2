import OperationsCore
import SwiftUI

struct OperationsView:View {
    @EnvironmentObject var store:ConsoleStore
    var filterAsset:String?=nil
    var operations:[OperationRecord]{(store.snapshot?.operations ?? []).filter{filterAsset==nil || ($0.detailJSON?.localizedCaseInsensitiveContains(filterAsset!) == true)}}
    var selected:OperationRecord?{store.snapshot?.operations.first{$0.id==store.selectedOperationID}}
    var body:some View{HSplitView{VStack(alignment:.leading){Text("History").font(.title2.bold());List(operations,selection:$store.selectedOperationID){op in VStack(alignment:.leading){HStack{Text(op.kind).font(.headline);Spacer();Text(op.status)};Text(op.id).font(.caption.monospaced()).foregroundStyle(.secondary);Text("\(op.startedAt) · provenance \(op.provenanceTotal)").font(.caption).foregroundStyle(.secondary)}.tag(op.id)};Text("Latest 100 receipts · \(filterAsset ?? "all instruments")").font(.caption).foregroundStyle(.secondary)}.padding().frame(minWidth:360);ScrollView{if let op=selected{VStack(alignment:.leading,spacing:16){Text("Readable Receipt").font(.title2);Facts([("Run",op.id),("Kind",op.kind),("Status",op.status),("Started",op.startedAt),("Finished",op.finishedAt ?? "—"),("Raw block",op.rawBlockID ?? "—"),("Provenance","\(op.provenanceTotal)"),("Inserted","\(op.inserted)"),("Unchanged","\(op.unchanged)"),("Conflicts","\(op.conflicts)"),("Corrected","\(op.corrected)")]);if let detail=op.detailJSON{DisclosureGroup("Technical Details"){Text(detail).font(.caption.monospaced()).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}};Button("View Ledger Evidence"){store.auditFilter=op.id;store.systemSection = .audit;store.section = .system}}.padding()}else{ContentUnavailableView("Select an operation",systemImage:"clock")}}.frame(minWidth:400)}}
}
