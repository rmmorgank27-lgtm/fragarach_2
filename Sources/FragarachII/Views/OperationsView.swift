import OperationsCore
import SwiftUI

struct OperationsView:View {
    @EnvironmentObject var store:ConsoleStore
    var selected:OperationRecord?{store.snapshot?.operations.first{$0.id==store.selectedOperationID}}
    var body:some View{HSplitView{VStack(alignment:.leading){Text("Operations").font(.largeTitle);List(store.snapshot?.operations ?? [],selection:$store.selectedOperationID){op in VStack(alignment:.leading){HStack{Text(op.kind).font(.headline);Spacer();Text(op.status)};Text(op.id).font(.caption.monospaced()).foregroundStyle(.secondary);Text("\(op.startedAt) · provenance \(op.provenanceTotal)").font(.caption).foregroundStyle(.secondary)}.tag(op.id)};Text("Bounded to the latest 100 operations").font(.caption).foregroundStyle(.secondary)}.padding().frame(minWidth:430);ScrollView{if let op=selected{VStack(alignment:.leading,spacing:16){Text("Operation detail").font(.largeTitle);Facts([("Run",op.id),("Kind",op.kind),("Status",op.status),("Started",op.startedAt),("Finished",op.finishedAt ?? "—"),("Raw block",op.rawBlockID ?? "—"),("Provenance","\(op.provenanceTotal)"),("Inserted","\(op.inserted)"),("Unchanged","\(op.unchanged)"),("Conflicts","\(op.conflicts)"),("Corrected","\(op.corrected)")]);if let detail=op.detailJSON{GroupBox("Structured detail"){Text(detail).font(.caption.monospaced()).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}}}.padding()}else{ContentUnavailableView("Select an operation",systemImage:"clock")}}.frame(minWidth:440)}}
}
