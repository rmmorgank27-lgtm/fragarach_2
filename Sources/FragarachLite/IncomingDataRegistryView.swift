import SwiftUI

struct IncomingDataRegistryView:View {
    @EnvironmentObject private var store:LiteEstateStore
    let catalogue:LiteCatalogue
    @State private var requestToRemove:LiteIncomingData?
    @State private var search=""
    @State private var order=ReplicaOrder.symbol
    @State private var selectedMarket="All"
    private var records:[LiteIncomingData]{(catalogue.incomingData ?? []).filter{!["CANCELLED","REMOVED"].contains($0.state)}}
    private var incoming:[LiteIncomingData]{records.filter{["REQUESTED","ACCEPTED","TRANSFERRING","VERIFYING"].contains($0.state)} }
    private var waiting:[LiteIncomingData]{records.filter{$0.state == "WAITING_FOR_STUDIO"}}
    private var displayed:[LiteIncomingData] {
        let filtered=records.filter{
            (selectedMarket == "All" || marketName($0) == selectedMarket)
                && (search.isEmpty || $0.symbol.localizedCaseInsensitiveContains(search))
        }
        return filtered.sorted{lhs,rhs in
            switch order {
            case .symbol:return lhs.symbol == rhs.symbol ? timeframeRank(lhs.timeframe)<timeframeRank(rhs.timeframe):lhs.symbol<rhs.symbol
            case .recent:return (lhs.activeAtUTC ?? lhs.requestedAtUTC) > (rhs.activeAtUTC ?? rhs.requestedAtUTC)
            case .largest:return (lhs.databaseBytes ?? 0) == (rhs.databaseBytes ?? 0) ? lhs.symbol<rhs.symbol:(lhs.databaseBytes ?? 0) > (rhs.databaseBytes ?? 0)
            }
        }
    }
    private var grouped:[(String,[LiteIncomingData])] {
        let values=Dictionary(grouping:displayed,by:\.symbol).map{($0.key,$0.value)}
        return values.sorted{lhs,rhs in
            switch order {
            case .symbol:return lhs.0<rhs.0
            case .recent:return (lhs.1.compactMap(\.activeAtUTC).max() ?? "") > (rhs.1.compactMap(\.activeAtUTC).max() ?? "")
            case .largest:return lhs.1.reduce(0){$0+($1.databaseBytes ?? 0)} > rhs.1.reduce(0){$0+($1.databaseBytes ?? 0)}
            }
        }
    }
    private let markets=["Crypto","Energy","Forex","Indices","Metals","Other","Stocks"]

    var body:some View {
        GroupBox("Replication Activity") {
            VStack(alignment:.leading,spacing:10) {
                HStack {
                    Label(syncLabel,systemImage:syncIcon).font(.headline).foregroundStyle(syncColor)
                    Spacer()
                    VStack(alignment:.trailing,spacing:2) {
                        Text(byteSummary).font(.caption.monospaced()).foregroundStyle(.secondary)
                        Text("Last checked \(date(catalogue.service?.lastSyncAtUTC)) · \(outcome(catalogue.service?.lastSyncOutcome))")
                            .font(.caption2.monospaced()).foregroundStyle(.secondary)
                    }
                }
                ProgressView(value:overallProgress).progressViewStyle(.linear).tint(syncColor)
                HStack {
                    Text(incoming.isEmpty ? "No transfer is waiting" : "\(incoming.count) transfer\(incoming.count == 1 ? "":"s") in progress")
                    Spacer()
                    Text(waiting.isEmpty ? (incoming.isEmpty ? "Subscriptions are checked automatically":"Receiving updated lane data") : "\(waiting.count) lane\(waiting.count == 1 ? "":"s") waiting for Studio onboarding")
                }.font(.caption).foregroundStyle(.secondary)

                LazyVGrid(columns:Array(repeating:GridItem(.flexible(),spacing:10),count:4),spacing:10) {
                    marketCard("All",items:records)
                    ForEach(markets,id:\.self){name in marketCard(name,items:records.filter{marketName($0)==name})}
                }

                HStack(spacing:10) {
                    TextField("Search symbols",text:$search).textFieldStyle(.roundedBorder).frame(width:220)
                    Picker("Order",selection:$order) {
                        ForEach(ReplicaOrder.allCases){value in Text(value.title).tag(value)}
                    }.frame(width:190)
                    Spacer()
                    Text("\(Set(displayed.map(\.symbol)).count) symbols · \(displayed.count) lanes").font(.caption).foregroundStyle(.secondary)
                }

                if records.isEmpty {
                    Text("Requested lanes and their update history will appear here.").font(.caption).foregroundStyle(.secondary).padding(.vertical,4)
                } else {
                    Divider()
                    HStack(spacing:10) {
                        Text("Lane").frame(width:110,alignment:.leading)
                        Text("Local data").frame(width:150,alignment:.leading)
                        Text("Bar range (UTC)").frame(maxWidth:.infinity,alignment:.leading)
                        Text("Received / checked").frame(width:210,alignment:.leading)
                        Text("Status").frame(width:125,alignment:.trailing)
                        Text("Actions").frame(width:170,alignment:.trailing)
                    }.font(.caption2.bold()).foregroundStyle(.secondary)
                    LazyVStack(spacing:0) {
                        ForEach(grouped,id:\.0){symbol,items in
                            HStack {
                                Text(symbol).font(.headline)
                                Text("\(marketName(items[0])) · \(items.count) lane\(items.count == 1 ? "":"s") · \(bytes(items.reduce(0){$0+($1.databaseBytes ?? 0)}))")
                                    .font(.caption).foregroundStyle(.secondary)
                                Spacer()
                            }
                            .padding(.horizontal,8).frame(height:34).background(.quaternary.opacity(0.4))
                            ForEach(items){item in
                                laneRow(item,showSymbol:false)
                                if item.id != items.last?.id {Divider()}
                            }
                        }
                    }
                }
            }.padding(8).fixedSize(horizontal:false,vertical:true)
        }
        .confirmationDialog(
            "Remove \(requestToRemove?.symbol ?? "") \(requestToRemove?.timeframe ?? "") from this MacBook?",
            isPresented:Binding(get:{requestToRemove != nil},set:{if !$0{requestToRemove=nil}}),
            titleVisibility:.visible
        ) {
            if let item=requestToRemove {
                Button("Remove from MacBook",role:.destructive){Task{await store.act(symbol:item.symbol,timeframe:item.timeframe,"REMOVE")};requestToRemove=nil}
            }
            Button("Cancel",role:.cancel){requestToRemove=nil}
        } message: {
            Text("The local lane file will be deleted. The Studio source is not changed, and the lane can be requested again later.")
        }
    }

    private var overallProgress:Double {
        let expected=incoming.reduce(0){$0+($1.expectedBytes ?? 0)}
        guard expected>0 else{return incoming.isEmpty ? 1:0}
        return min(max(Double(incoming.reduce(0){$0+($1.transferredBytes ?? 0)})/Double(expected),0),1)
    }
    private var syncLabel:String {
        if let first=incoming.first{return "\(first.symbol) \(first.timeframe) · \(first.state.replacingOccurrences(of:"_",with:" "))"}
        if !waiting.isEmpty{return "Waiting for Studio"}
        return catalogue.service?.syncPhase == "FAILED" ? "Update check failed":"Replica current"
    }
    private var syncIcon:String {!incoming.isEmpty ? "arrow.down.circle.fill":!waiting.isEmpty ? "clock.badge":"checkmark.circle.fill"}
    private var syncColor:Color {!incoming.isEmpty ? .cyan:!waiting.isEmpty ? .orange:(catalogue.service?.syncPhase == "FAILED" ? .red:.green)}
    private var byteSummary:String {"Stored \(bytes(records.filter{$0.state == "ACTIVE"}.reduce(0){$0+($1.databaseBytes ?? 0)})) · last transfer \(bytes(records.reduce(0){$0+($1.verifiedBytes ?? 0)}))"}
    private func bytes(_ value:Int?)->String {ByteCountFormatter.string(fromByteCount:Int64(value ?? 0),countStyle:.file)}
    private func date(_ value:String?)->String {
        guard let value,!value.isEmpty else{return "—"}
        return value.replacingOccurrences(of:"T",with:" ").replacingOccurrences(of:"+00:00",with:"Z")
    }
    private func outcome(_ value:String?)->String {
        switch value {case "ALREADY_CURRENT","NO_CHANGE":return "No changes";case "SELECTIVE_ADMITTED","ADMITTED":return "Updated";case "FAILED":return "Failed";default:return value?.replacingOccurrences(of:"_",with:" ").capitalized ?? "Waiting"}
    }
    private func status(_ item:LiteIncomingData)->String {
        if item.state == "ACTIVE" {return item.lastUpdateOutcome == "NO_CHANGE" ? "CURRENT":"ACTIVE"}
        if item.state == "WAITING_FOR_STUDIO" {return "WAITING FOR STUDIO"}
        return item.state.replacingOccurrences(of:"_",with:" ")
    }
    @ViewBuilder private func laneRow(_ item:LiteIncomingData,showSymbol:Bool)->some View {
        HStack(spacing:10) {
            Text(showSymbol ? "\(item.symbol) · \(item.timeframe)":item.timeframe).font(.caption.bold()).frame(width:110,alignment:.leading)
            VStack(alignment:.leading,spacing:2) {
                Text("\(item.barCount ?? 0) bars · \(bytes(item.databaseBytes ?? item.expectedBytes))")
                if item.state != "ACTIVE" && item.state != "WAITING_FOR_STUDIO" {ProgressView(value:item.actualProgress).progressViewStyle(.linear).tint(color(item.state))}
            }.font(.caption2).frame(width:150,alignment:.leading)
            Text("\(date(item.firstBarUTC))  →  \(date(item.caodt))").font(.caption2.monospaced()).frame(maxWidth:.infinity,alignment:.leading)
            VStack(alignment:.leading,spacing:2) {Text("Received  \(date(item.activeAtUTC))");Text("Checked   \(date(item.lastUpdateCheckAtUTC))")}
                .font(.caption2.monospaced()).foregroundStyle(.secondary).frame(width:210,alignment:.leading)
            Text(status(item)).font(.caption.bold()).foregroundStyle(color(item.state)).frame(width:125,alignment:.trailing).minimumScaleFactor(0.7)
            HStack(spacing:6) {
                if let lane=lane(item) {
                    Button("Re-request"){Task{await store.rerequest(lane)}}.disabled(store.pendingLaneIDs.contains(lane.id) || item.state == "WAITING_FOR_STUDIO")
                }
                Button("Remove",role:.destructive){requestToRemove=item}.help("Remove this request and any local lane data")
            }.frame(width:170,alignment:.trailing)
        }.frame(height:52)
    }
    private func lane(_ item:LiteIncomingData)->LiteLane? {
        catalogue.lanes.first{$0.symbol == item.symbol && $0.timeframe == item.timeframe}
            ?? catalogue.availableLanes.first{$0.symbol == item.symbol && $0.timeframe == item.timeframe}
    }
    private func marketName(_ item:LiteIncomingData)->String {
        let value=(lane(item)?.assetClass ?? "").uppercased()
        if item.state == "WAITING_FOR_STUDIO" && value.isEmpty{return "Pending"}
        if value.contains("CRYPTO") || value.contains("DIGITAL"){return "Crypto"}
        if value.contains("FOREX") || value.contains("FX"){return "Forex"}
        if value.contains("METAL"){return "Metals"}
        if value.contains("ENERGY"){return "Energy"}
        if value.contains("INDEX") || value.contains("INDIC"){return "Indices"}
        if value.contains("EQUIT") || value.contains("STOCK"){return "Stocks"}
        return "Other"
    }
    private func marketCard(_ name:String,items:[LiteIncomingData])->some View {
        let active=items.filter{$0.state == "ACTIVE"}
        let waitingCount=items.filter{$0.state == "WAITING_FOR_STUDIO"}.count
        let stored=active.reduce(0){$0+($1.databaseBytes ?? 0)}
        let symbols=Set(items.map(\.symbol)).count
        let current=active.filter{$0.lastUpdateOutcome == "NO_CHANGE"}.count
        let color:Color=waitingCount>0 ? .orange:.green
        return Button{selectedMarket=name}label:{
            VStack(alignment:.leading,spacing:6) {
                HStack{Text(name).font(.headline);Spacer();Text("\(symbols)").font(.title2.bold())}
                HStack{Text("Current \(current)");Spacer();Text("Lanes \(items.count)")}.font(.caption)
                HStack{Text("Stored \(bytes(stored))");Spacer();Text(waitingCount>0 ? "Waiting \(waitingCount)":"Ready")}.font(.caption2)
            }
            .padding(12).frame(maxWidth:.infinity,alignment:.leading)
            .background((selectedMarket==name ? Color.accentColor:color).opacity(0.12),in:RoundedRectangle(cornerRadius:10))
            .overlay{RoundedRectangle(cornerRadius:10).stroke(selectedMarket==name ? Color.accentColor:color.opacity(0.4))}
        }.buttonStyle(.plain)
    }
    private func timeframeRank(_ value:String)->Int {["D1","H1","M30","M15","M5"].firstIndex(of:value) ?? 99}
    private func color(_ state:String)->Color {switch state{case "ACTIVE":.green;case "FAILED","CANCELLED","REMOVED":.red;case "TRANSFERRING","VERIFYING":.cyan;case "PAUSED":.gray;default:.orange}}
}

private enum ReplicaOrder:String,CaseIterable,Identifiable {
    case symbol,recent,largest
    var id:String{rawValue}
    var title:String{switch self{case .symbol:"Symbol";case .recent:"Most recently received";case .largest:"Largest first"}}
}
