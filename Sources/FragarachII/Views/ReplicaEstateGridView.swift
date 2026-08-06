import OperationsCore
import SwiftUI

enum ReplicaLaneSyncState:String {
    case macbookLocal="MACBOOK CACHE", stale="STALE CACHE", paused="PAUSED", studioOnly="STUDIO ONLY", requested="REQUESTED", incoming="INCOMING", error="FAILED"
    var color:Color {switch self{case .macbookLocal:.green;case .stale:.yellow;case .paused:.gray;case .studioOnly:.indigo;case .requested:.orange;case .incoming:.cyan;case .error:.red}}
}

private struct ReplicaStudioLane:Identifiable {
    var id:String{"\(symbol):\(timeframe)"}
    let symbol:String
    let timeframe:String
    let caodt:String?
    let assetClass:String
}

struct ReplicaEstateGridView:View {
    let authority:[EstateTruthLane]
    let available:[ReplicaLiteLaneReport]
    let actual:[ReplicaLiteLaneReport]
    let paused:[ReplicaPausedLane]
    let requests:[ReplicaLiteRequestReport]
    let onSelect:(String,String,ReplicaLaneSyncState)->Void
    @State private var market="All"
    @State private var filter=""
    private let timeframes=["D1","H1","M30","M5"]

    private var source:[ReplicaStudioLane] {
        if !available.isEmpty {
            return available.map{.init(symbol:$0.symbol,timeframe:$0.timeframe,caodt:$0.caodt,assetClass:$0.assetClass ?? "UNKNOWN")}
        }
        return authority.map{.init(symbol:$0.symbol,timeframe:$0.timeframe,caodt:$0.latestCanonicalObservation,assetClass:$0.searchMetadata.assetClass)}
    }
    private var markets:[String] {Array(Set(source.map{marketName($0.assetClass)})).sorted()}
    private var filtered:[ReplicaStudioLane] {source.filter{(market=="All" || marketName($0.assetClass)==market) && (filter.isEmpty || $0.symbol.localizedCaseInsensitiveContains(filter))}}
    private var symbols:[String] {Array(Set(filtered.map(\.symbol))).sorted()}
    private func sourceLane(_ symbol:String,_ timeframe:String)->ReplicaStudioLane?{filtered.first{$0.symbol==symbol && $0.timeframe==timeframe}}
    private func actualLane(_ symbol:String,_ timeframe:String)->ReplicaLiteLaneReport?{actual.first{$0.symbol==symbol && $0.timeframe==timeframe}}
    private func contains(_ values:[ReplicaPausedLane],_ symbol:String,_ timeframe:String)->Bool{values.contains{$0.symbol==symbol && $0.timeframe==timeframe}}
    private func request(_ symbol:String,_ timeframe:String)->ReplicaLiteRequestReport?{requests.first{$0.symbol==symbol && $0.timeframe==timeframe}}
    private func state(_ symbol:String,_ timeframe:String)->ReplicaLaneSyncState {
        if contains(paused,symbol,timeframe){return .paused}
        if let request=request(symbol,timeframe){switch request.state{case "ACTIVE":break;case "PAUSED":return .paused;case "TRANSFERRING","VERIFYING":return .incoming;case "FAILED","CANCELLED","REMOVED":return .error;default:return .requested}}
        guard let source=sourceLane(symbol,timeframe) else{return .studioOnly}
        guard let local=actualLane(symbol,timeframe) else{return .studioOnly}
        if local.state=="PAUSED"{return .paused}
        guard let localDate=ISO8601DateFormatter().date(from:local.caodt ?? ""),let studioDate=ISO8601DateFormatter().date(from:source.caodt ?? "") else{return .macbookLocal}
        return localDate >= studioDate ? .macbookLocal:.stale
    }

    var body:some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Markets").font(.headline)
            LazyVGrid(columns:[GridItem(.adaptive(minimum:170),spacing:10)],spacing:10) {
                marketCard("All",lanes:source)
                ForEach(markets,id:\.self){name in marketCard(name,lanes:source.filter{marketName($0.assetClass)==name})}
            }
            HStack {TextField("Filter symbols",text:$filter).frame(width:220);Spacer();Text("Ownership is explicit: Studio source versus MacBook local copy.").font(.caption).foregroundStyle(.secondary)}
            ownershipLegend
            ScrollView(.horizontal) {
                Grid(alignment:.leading,horizontalSpacing:8,verticalSpacing:8) {
                    GridRow {Text("Symbol").font(.caption).foregroundStyle(.secondary).frame(width:110,alignment:.leading);ForEach(timeframes,id:\.self){Text($0).font(.caption).foregroundStyle(.secondary).frame(width:118)}}
                    Divider().gridCellUnsizedAxes(.horizontal)
                    ForEach(symbols,id:\.self){symbol in
                        GridRow {
                            Text(symbol).font(.headline).frame(width:110,alignment:.leading)
                            ForEach(timeframes,id:\.self){timeframe in
                                if sourceLane(symbol,timeframe) != nil {
                                    laneCell(symbol,timeframe,state:state(symbol,timeframe))
                                } else {Color.clear.frame(width:118,height:58)}
                            }
                        }
                    }
                }.padding(.vertical,4)
            }
        }
    }

    private func marketCard(_ name:String,lanes:[ReplicaStudioLane])->some View {
        let local=lanes.filter{actualLane($0.symbol,$0.timeframe) != nil}
        let pausedCount=lanes.filter{contains(paused,$0.symbol,$0.timeframe)}.count
        let studioOnly=lanes.count-local.count
        let requested=lanes.filter{request($0.symbol,$0.timeframe) != nil}.count
        let latest=local.compactMap{actualLane($0.symbol,$0.timeframe)?.caodt}.max() ?? "—"
        return Button(action:{market=name}) {
            VStack(alignment:.leading,spacing:6) {
                HStack {Text(name).font(.headline);Spacer();Text("\(local.count)/\(lanes.count)").font(.title3.bold())}
                HStack {Label("MacBook cache \(local.count)",systemImage:"circle.fill").foregroundStyle(.green);Spacer();Text("Studio only \(studioOnly)").foregroundStyle(.indigo)}.font(.caption)
                HStack {Text("Requested \(requested)").foregroundStyle(.orange);Spacer();Text("Paused \(pausedCount)").foregroundStyle(.gray)}.font(.caption2)
                Text("CAODT \(latest)").font(.caption2.monospaced()).foregroundStyle(.secondary)
            }
            .padding(12).frame(maxWidth:.infinity,alignment:.leading)
            .background((market==name ? Color.accentColor:.green).opacity(0.12),in:RoundedRectangle(cornerRadius:10))
            .overlay{RoundedRectangle(cornerRadius:10).stroke(market==name ? Color.accentColor:.green.opacity(0.35))}
        }.buttonStyle(.plain)
    }

    private func laneCell(_ symbol:String,_ timeframe:String,state:ReplicaLaneSyncState)->some View {
        let local=actualLane(symbol,timeframe)
        let progress=request(symbol,timeframe)?.actualProgress ?? (state == .macbookLocal || state == .stale || state == .paused ? 1:0)
        return Button{if state != .studioOnly{onSelect(symbol,timeframe,state)}}label:{ZStack(alignment:.bottom){RoundedRectangle(cornerRadius:7).fill(state.color.opacity(0.07));Rectangle().fill(state.color.opacity(0.24)).frame(height:58 * min(max(progress,0),1)).clipShape(RoundedRectangle(cornerRadius:7));VStack(spacing:2){Text(local?.caodt.map(shortCAODT) ?? "—").font(.caption2.bold().monospacedDigit());Text(state.rawValue).font(.caption2.bold()).lineLimit(1).minimumScaleFactor(0.7)}}.foregroundStyle(.primary).frame(width:118,height:58).overlay{RoundedRectangle(cornerRadius:7).stroke(state.color.opacity(0.7))}.overlay(alignment:.topTrailing){if state == .requested || state == .incoming{ZStack{Circle().stroke(state.color.opacity(0.2),lineWidth:2);Circle().trim(from:0,to:min(max(progress,0),1)).stroke(state.color,style:StrokeStyle(lineWidth:2,lineCap:.round)).rotationEffect(.degrees(-90))}.frame(width:14,height:14).padding(4)}}.animation(.easeInOut(duration:0.35),value:progress)}.buttonStyle(.plain).help(state == .studioOnly ? "\(symbol) \(timeframe): request this lane on the MacBook":"\(symbol) \(timeframe): \(state.rawValue) · \(Int(progress * 100))%")
    }

    private var ownershipLegend:some View {HStack(spacing:14){legend(.studioOnly);legend(.requested);legend(.incoming);legend(.macbookLocal);legend(.paused);legend(.error)}.font(.caption2)}
    private func legend(_ state:ReplicaLaneSyncState)->some View {HStack(spacing:4){RoundedRectangle(cornerRadius:2).fill(state.color).frame(width:10,height:10);Text(state.rawValue)}}

    private func shortCAODT(_ value:String)->String {value.replacingOccurrences(of:"+00:00",with:"").replacingOccurrences(of:"T",with:" ")}
    private func marketName(_ assetClass:String)->String {let value=assetClass.uppercased();if value.contains("CRYPTO") || value.contains("DIGITAL"){return "Crypto"};if value.contains("FOREX") || value=="FX"{return "Forex"};if value.contains("METAL"){return "Metals"};if value.contains("ENERGY"){return "Energy"};if value.contains("INDEX"){return "Indices"};if value.contains("EQUIT") || value.contains("STOCK"){return "Stocks"};return "Other"}
}
