import Foundation
import OperationsCore
import SwiftUI

struct OperationsView:View {
    @EnvironmentObject private var store:ConsoleStore
    var filterAsset:String?=nil
    @State private var scopeAll=true
    private var operations:[OperationRecord]{(store.snapshot?.operations ?? []).filter{scopeAll || filterAsset==nil || $0.receiptFacts.instrument==filterAsset}}
    private var selected:OperationRecord?{operations.first{$0.id==store.selectedOperationID}}
    var body:some View{VStack(alignment:.leading,spacing:12){
        HStack{VStack(alignment:.leading,spacing:3){Text("History").font(.largeTitle.bold());Text("Immutable operation receipts").foregroundStyle(.secondary)};Spacer();if let filterAsset{Picker("Instrument scope",selection:$scopeAll){Text("All Instruments").tag(true);Text(filterAsset).tag(false)}.pickerStyle(.segmented).frame(width:300)}}.padding([.horizontal,.top])
        if operations.isEmpty{ContentUnavailableView(scopeAll ? "No operation receipts":"No receipts for \(filterAsset ?? "instrument")",systemImage:"doc.text.magnifyingglass",description:Text("Completed acquisition and import receipts will appear here without obscuring the controls."))}
        else{VStack(spacing:4){Grid(alignment:.leading,horizontalSpacing:14){GridRow{ForEach(["Timestamp","Instrument","Lane","Operation","Source","Result","Inserted","Warnings"],id:\.self){Text($0).font(.caption.bold()).foregroundStyle(.secondary)}}}.padding(.horizontal);HSplitView{List(operations,selection:$store.selectedOperationID){op in ReceiptRow(operation:op).tag(op.id)}.frame(minWidth:760);ScrollView{if let selected{ReceiptDetail(operation:selected)}else{VStack(spacing:10){Image(systemName:"doc.text").font(.largeTitle).foregroundStyle(.secondary);Text("Select a receipt").font(.title2);Text("Choose one operation to inspect its recorded result.").foregroundStyle(.secondary)}.frame(maxWidth:.infinity,minHeight:360)}}.frame(minWidth:430)}}}
    }.onChange(of:operations.map(\.id)){_,ids in if let id=store.selectedOperationID,!ids.contains(id){store.selectedOperationID=nil}}
    }
}

private struct ReceiptRow:View{let operation:OperationRecord;var body:some View{let f=operation.receiptFacts;Grid(alignment:.leading,horizontalSpacing:14){GridRow{Text(operation.startedAt).font(.caption.monospaced());Text(f.instrument).fontWeight(.semibold);Text(f.timeframe);Text(operation.kind);Text(f.source);Text(operation.status).foregroundStyle(operation.status=="committed" ? .green:.orange);Text("\(operation.inserted)");Text(f.warnings)}}.accessibilityLabel("\(operation.startedAt), \(f.instrument), \(f.timeframe), \(operation.kind), \(f.source), \(operation.status), \(operation.inserted) inserted, \(f.warnings)")}}

private struct ReceiptDetail:View{@EnvironmentObject var store:ConsoleStore;let operation:OperationRecord;var body:some View{let f=operation.receiptFacts;VStack(alignment:.leading,spacing:16){Text("Readable Receipt").font(.title2.bold());Facts([("Timestamp",operation.startedAt),("Instrument",f.instrument),("Timeframe",f.timeframe),("Operation type",operation.kind),("Source",f.source),("Result",operation.status),("Rows inserted","\(operation.inserted)"),("Rows unchanged","\(operation.unchanged)"),("Conflicts preserved","\(operation.conflicts)"),("Warnings",f.warnings),("Raw block",operation.rawBlockID ?? "—")]);if let detail=operation.detailJSON{DisclosureGroup("Technical Details"){Text(detail).font(.caption.monospaced()).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)}};Button("View Ledger Evidence"){store.auditFilter=operation.id;store.systemSection = .audit;store.section = .system}}.padding()}}

private struct ReceiptFacts{let instrument:String;let timeframe:String;let source:String;let warnings:String}
private extension OperationRecord{
    var receiptFacts:ReceiptFacts{let warnings=((try? JSONSerialization.jsonObject(with:Data(warningsJSON.utf8))) as? [String])?.joined(separator:", ");return .init(instrument:instrument,timeframe:timeframe,source:source,warnings:(warnings?.isEmpty==false ? warnings!:"None"))}
}
