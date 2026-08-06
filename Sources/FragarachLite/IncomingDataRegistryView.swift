import SwiftUI

struct IncomingDataRegistryView:View {
    let catalogue:LiteCatalogue
    private var records:[LiteIncomingData]{catalogue.incomingData ?? []}
    private var active:[LiteIncomingData]{records.filter{!["ACTIVE","CANCELLED","REMOVED","FAILED","PAUSED"].contains($0.state)}}

    var body:some View {
        GroupBox("Incoming Data") {
            VStack(alignment:.leading,spacing:10) {
                HStack {
                    Label(syncLabel,systemImage:syncIcon).font(.headline).foregroundStyle(syncColor)
                    Spacer()
                    Text(byteSummary).font(.caption.monospaced()).foregroundStyle(.secondary)
                }
                ProgressView(value:overallProgress).progressViewStyle(.linear).tint(syncColor)
                HStack {
                    Text(active.isEmpty ? "No incoming request is waiting" : "\(active.count) incoming request\(active.count == 1 ? "":"s")")
                    Spacer()
                    Text(catalogue.service?.lastSyncOutcome ?? "WAITING")
                }.font(.caption).foregroundStyle(.secondary)

                if records.isEmpty {
                    Text("Requests and completed arrivals will appear here.").font(.caption).foregroundStyle(.secondary).padding(.vertical,4)
                } else {
                    Divider()
                    ForEach(records.prefix(8)) { item in
                        HStack(spacing:10) {
                            VStack(alignment:.leading,spacing:2) {
                                Text("\(item.symbol) · \(item.timeframe)").font(.caption.bold())
                                Text(item.requestedAtUTC).font(.caption2.monospaced()).foregroundStyle(.secondary)
                            }.frame(width:190,alignment:.leading)
                            VStack(alignment:.trailing,spacing:2) {
                                ProgressView(value:item.actualProgress).progressViewStyle(.linear).tint(color(item.state))
                                Text("\(bytes(item.transferredBytes)) / \(bytes(item.expectedBytes)) · verified \(bytes(item.verifiedBytes))")
                                    .font(.system(size:9,design:.monospaced)).foregroundStyle(.secondary)
                            }
                            Text(item.state.replacingOccurrences(of:"_",with:" "))
                                .font(.caption.bold()).foregroundStyle(color(item.state)).frame(width:110,alignment:.trailing)
                        }
                    }
                }
            }.padding(8)
        }
    }

    private var overallProgress:Double {
        let expected=active.reduce(0){$0+($1.expectedBytes ?? 0)}
        guard expected>0 else{return 0}
        return min(max(Double(active.reduce(0){$0+($1.transferredBytes ?? 0)})/Double(expected),0),1)
    }
    private var syncLabel:String {
        if let first=active.first{return "\(first.symbol) \(first.timeframe) · \(first.state.replacingOccurrences(of:"_",with:" "))"}
        return catalogue.service?.syncPhase == "FAILED" ? "Sync failed":"Replica current"
    }
    private var syncIcon:String {active.isEmpty ? "checkmark.circle.fill":"arrow.down.circle.fill"}
    private var syncColor:Color {active.isEmpty ? (catalogue.service?.syncPhase == "FAILED" ? .red:.green):.cyan}
    private var byteSummary:String {"Transferred \(bytes(records.reduce(0){$0+($1.transferredBytes ?? 0)})) · verified \(bytes(records.reduce(0){$0+($1.verifiedBytes ?? 0)}))"}
    private func bytes(_ value:Int?)->String {ByteCountFormatter.string(fromByteCount:Int64(value ?? 0),countStyle:.file)}
    private func color(_ state:String)->Color {switch state{case "ACTIVE":.green;case "FAILED","CANCELLED","REMOVED":.red;case "TRANSFERRING","VERIFYING":.cyan;case "PAUSED":.gray;default:.orange}}
}
