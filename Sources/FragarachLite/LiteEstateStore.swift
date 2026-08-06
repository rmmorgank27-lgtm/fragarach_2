import Foundation

struct LiteLane:Codable,Identifiable,Hashable,Sendable {
    var id:String{"\(symbol):\(timeframe)"}
    let symbol:String
    let timeframe:String
    let firstBarUTC:String?
    let caodt:String?
    let barCount:Int
    let dataFingerprint:String
    let state:String?
    let assetClass:String?
    enum CodingKeys:String,CodingKey {case symbol,timeframe,caodt,state;case firstBarUTC="first_bar_utc",barCount="bar_count",dataFingerprint="data_fingerprint",assetClass="asset_class"}
}

struct LiteIncomingData:Codable,Identifiable,Hashable,Sendable {
    var id:String{requestID ?? "\(symbol):\(timeframe):\(requestedAtUTC)"}
    let requestID:String?
    let symbol:String
    let timeframe:String
    let state:String
    let progress:Double?
    let expectedBytes:Int?
    let transferredBytes:Int?
    let verifiedBytes:Int?
    let sourceRevision:String?
    let caodt:String?
    let requestedAtUTC:String
    let updatedAtUTC:String?
    let completedAtUTC:String?
    let expectedGeneration:Int?
    var actualProgress:Double {guard let expectedBytes,expectedBytes>0 else{return 0};return min(max(Double(transferredBytes ?? 0)/Double(expectedBytes),0),1)}
    enum CodingKeys:String,CodingKey {case symbol,timeframe,state,progress,caodt;case requestID="request_id",expectedBytes="expected_bytes",transferredBytes="transferred_bytes",verifiedBytes="verified_bytes",sourceRevision="source_revision",requestedAtUTC="requested_at_utc",updatedAtUTC="updated_at_utc",completedAtUTC="completed_at_utc",expectedGeneration="expected_generation"}
}

struct LiteServiceProgress:Codable,Equatable,Sendable {
    let syncPhase:String?
    let lastSyncAtUTC:String?
    let lastSyncOutcome:String?
    let refreshGenerationReceived:Int?
    let refreshGenerationCompleted:Int?
    enum CodingKeys:String,CodingKey {case syncPhase="sync_phase",lastSyncAtUTC="last_sync_at_utc",lastSyncOutcome="last_sync_outcome",refreshGenerationReceived="refresh_generation_received",refreshGenerationCompleted="refresh_generation_completed"}
}

struct LiteCatalogue:Codable,Equatable,Sendable {
    let state:String
    let lanes:[LiteLane]
    let availableLanes:[LiteLane]
    let incomingData:[LiteIncomingData]?
    let service:LiteServiceProgress?
    enum CodingKeys:String,CodingKey {case state,lanes,service;case availableLanes="available_lanes",incomingData="incoming_data"}
}

@MainActor final class LiteEstateStore:ObservableObject {
    @Published var catalogue=LiteCatalogue(state:"LOADING",lanes:[],availableLanes:[],incomingData:[],service:nil)
    @Published var error:String?
    @Published private(set) var pendingLaneIDs:Set<String>=[]
    @Published var notice:String?
    private let base=URL(string:"http://127.0.0.1:9463")!
    private var refreshing=false

    func start() async {
        while !Task.isCancelled {
            await refresh()
            let active=(catalogue.incomingData ?? []).contains{!["ACTIVE","CANCELLED","REMOVED","FAILED","PAUSED"].contains($0.state)}
            try? await Task.sleep(for:active ? .milliseconds(500):.seconds(5))
        }
    }

    func refresh() async {
        guard !refreshing else{return}
        refreshing=true
        defer{refreshing=false}
        do {
            let (data,response)=try await URLSession.shared.data(from:base.appending(path:"v1/catalogue"))
            guard (response as? HTTPURLResponse)?.statusCode==200 else{throw URLError(.badServerResponse)}
            let decoded=try await Task.detached(priority:.utility){try JSONDecoder().decode(LiteCatalogue.self,from:data)}.value
            if decoded != catalogue {catalogue=decoded}
            if error != nil {error=nil}
        } catch {
            let message=error.localizedDescription
            if self.error != message {self.error=message}
        }
    }

    func request(_ lane:LiteLane) async {
        guard pendingLaneIDs.insert(lane.id).inserted else{return}
        notice="Requesting \(lane.symbol) \(lane.timeframe)…"
        defer{pendingLaneIDs.remove(lane.id)}
        do {
            var request=URLRequest(url:base.appending(path:"v1/request-lane"));request.httpMethod="POST";request.setValue("application/json",forHTTPHeaderField:"Content-Type")
            request.httpBody=try JSONSerialization.data(withJSONObject:["symbol":lane.symbol,"timeframe":lane.timeframe])
            let (_,response)=try await URLSession.shared.data(for:request)
            guard (response as? HTTPURLResponse)?.statusCode==200 else{throw URLError(.badServerResponse)}
            error=nil
            await refresh()
            notice="\(lane.symbol) \(lane.timeframe) requested · sync starting"
        } catch {self.error=error.localizedDescription}
    }

    func act(_ lane:LiteLane,_ action:String) async {
        do {
            var request=URLRequest(url:base.appending(path:"v1/request-action"));request.httpMethod="POST";request.setValue("application/json",forHTTPHeaderField:"Content-Type")
            request.httpBody=try JSONSerialization.data(withJSONObject:["symbol":lane.symbol,"timeframe":lane.timeframe,"action":action])
            let (_,response)=try await URLSession.shared.data(for:request)
            guard (response as? HTTPURLResponse)?.statusCode==200 else{throw URLError(.badServerResponse)}
            error=nil
            await refresh()
        } catch {self.error=error.localizedDescription}
    }
}
