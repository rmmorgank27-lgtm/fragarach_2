import SwiftUI

struct LiteEstateView:View {
    @EnvironmentObject var store:LiteEstateStore
    @State private var market="All"
    @State private var filter=""
    private let timeframes=["D1","H1","M30","M5"]
    private var all:[LiteLane] {
        var values:[String:LiteLane]=[:]
        for lane in store.catalogue.availableLanes {values[lane.id]=lane}
        for lane in store.catalogue.lanes {values[lane.id]=lane}
        return values.values.sorted{$0.id<$1.id}
    }
    private var local:Set<String>{Set(store.catalogue.lanes.map(\.id))}
    private var markets:[String]{Array(Set(all.map(marketName))).sorted()}
    private var visible:[LiteLane]{all.filter{(market=="All" || marketName($0)==market) && (filter.isEmpty || $0.symbol.localizedCaseInsensitiveContains(filter))}}
    private var symbols:[String]{Array(Set(visible.map(\.symbol))).sorted()}
    private var incomingByLane:[String:LiteIncomingData] {var result:[String:LiteIncomingData]=[:];for item in store.catalogue.incomingData ?? []{result["\(item.symbol):\(item.timeframe)"]=item};return result}

    var body:some View {
        let visibleLanes=visible
        let visibleSymbols=Array(Set(visibleLanes.map(\.symbol))).sorted()
        let laneByID=Dictionary(uniqueKeysWithValues:visibleLanes.map{($0.id,$0)})
        let localIDs=local
        let incoming=incomingByLane
        let pendingIDs=store.pendingLaneIDs
        ScrollView {
            VStack(alignment:.leading,spacing:16) {
                HStack {VStack(alignment:.leading){Text("Fragarach Lite Estate").font(.largeTitle.bold());Text("Local read-only market data from the Mac Studio").foregroundStyle(.secondary)};Spacer();Button("Refresh"){Task{await store.refresh()}}.keyboardShortcut("r")}
                if let error=store.error {Label(error,systemImage:"exclamationmark.triangle.fill").foregroundStyle(.red)}
                if let notice=store.notice {Label(notice,systemImage:"arrow.down.circle.fill").foregroundStyle(.orange)}
                IncomingDataRegistryView(catalogue:store.catalogue)
                Label("SELECTIVE V2 · only requested and verified lane artifacts are stored on this MacBook.",systemImage:"checkmark.shield.fill")
                    .font(.caption).foregroundStyle(.green)
                Text("Markets").font(.headline)
                LazyVGrid(columns:[GridItem(.adaptive(minimum:170),spacing:10)],spacing:10){marketCard("All",lanes:all);ForEach(markets,id:\.self){name in marketCard(name,lanes:all.filter{marketName($0)==name})}}
                HStack {TextField("Filter symbols",text:$filter).frame(width:220);Spacer();Text("Click STUDIO ONLY to request that lane.").font(.caption).foregroundStyle(.secondary)}
                LiteLaneLegend()
                ScrollView(.horizontal) {Grid(alignment:.leading,horizontalSpacing:8,verticalSpacing:8){GridRow{Text("Symbol").font(.caption).foregroundStyle(.secondary).frame(width:110,alignment:.leading);ForEach(timeframes,id:\.self){Text($0).font(.caption).foregroundStyle(.secondary).frame(width:118)}};Divider().gridCellUnsizedAxes(.horizontal);ForEach(visibleSymbols,id:\.self){symbol in GridRow{Text(symbol).font(.headline).frame(width:110,alignment:.leading);ForEach(timeframes,id:\.self){timeframe in if let lane=laneByID["\(symbol):\(timeframe)"]{cell(lane,localIDs:localIDs,incoming:incoming[lane.id],pendingIDs:pendingIDs)}else{Color.clear.frame(width:118,height:58)}}}}}}}
            .padding(24)
        }.task{await store.start()}
    }

    private func marketCard(_ name:String,lanes:[LiteLane])->some View {let count=lanes.filter{local.contains($0.id)}.count;let latest=lanes.filter{local.contains($0.id)}.compactMap(\.caodt).max() ?? "—";return Button{market=name}label:{VStack(alignment:.leading,spacing:6){HStack{Text(name).font(.headline);Spacer();Text("\(count)/\(lanes.count)").font(.title3.bold())};Text("Local \(count) · Studio available \(lanes.count-count)").font(.caption);Text("CAODT \(latest)").font(.caption2.monospaced()).foregroundStyle(.secondary)}.padding(12).frame(maxWidth:.infinity,alignment:.leading).background((market==name ? Color.accentColor:.green).opacity(0.12),in:RoundedRectangle(cornerRadius:10)).overlay{RoundedRectangle(cornerRadius:10).stroke(market==name ? Color.accentColor:.green.opacity(0.35))}}.buttonStyle(.plain)}
    private func cell(_ lane:LiteLane,localIDs:Set<String>,incoming:LiteIncomingData?,pendingIDs:Set<String>)->some View {
        let visual=visual(lane,localIDs:localIDs,incoming:incoming,pendingIDs:pendingIDs)
        return LiteLaneStatusCell(lane:lane,visual:visual) {
            Task {
                switch visual.state {
                case .studioOnly:await store.request(lane)
                case .local:await store.act(lane,"PAUSE")
                case .paused:await store.act(lane,"RESUME")
                case .failed:await store.act(lane,"RETRY")
                case .requested,.incoming:await store.act(lane,"PAUSE")
                }
            }
        }
    }
    private func visual(_ lane:LiteLane,localIDs:Set<String>,incoming:LiteIncomingData?,pendingIDs:Set<String>)->LiteLaneCellVisual {
        if localIDs.contains(lane.id) {return .init(state:lane.state=="PAUSED" ? .paused:.local,progress:1)}
        if pendingIDs.contains(lane.id) {return .init(state:.requested,progress:0)}
        if let incoming {
            switch incoming.state {
            case "REQUESTED","ACCEPTED":return .init(state:.requested,progress:incoming.actualProgress)
            case "TRANSFERRING","VERIFYING":return .init(state:.incoming,progress:incoming.actualProgress)
            case "FAILED","CANCELLED","REMOVED":return .init(state:.failed,progress:incoming.actualProgress)
            case "ACTIVE":return .init(state:.local,progress:1)
            case "PAUSED":return .init(state:.paused,progress:incoming.actualProgress)
            default:break
            }
        }
        return .init(state:.studioOnly,progress:0)
    }
    private func marketName(_ lane:LiteLane)->String {let value=(lane.assetClass ?? "").uppercased();if value.contains("CRYPTO") || value.contains("DIGITAL"){return "Crypto"};if value.contains("FOREX") || value.contains("FX"){return "Forex"};if value.contains("METAL"){return "Metals"};if value.contains("ENERGY"){return "Energy"};if value.contains("INDEX"){return "Indices"};if value.contains("EQUIT") || value.contains("STOCK"){return "Stocks"};return "Other"}
}
