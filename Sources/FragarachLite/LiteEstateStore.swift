import Foundation

struct LiteMarketDiscovery:Codable,Sendable {
    let discoveryStatus:String
    let explanation:String
    let markets:[LiteDiscoveredMarket]
    let suggestedSearches:[String]
    let similarMarkets:[String]
    enum CodingKeys:String,CodingKey {case explanation,markets;case discoveryStatus="discovery_status",suggestedSearches="suggested_searches",similarMarkets="similar_markets"}
}

struct LiteSearchHistoryItem:Codable,Identifiable,Hashable,Sendable {
    let id:UUID
    let query:String
    let searchedAtUTC:String
    let discoveryStatus:String
    let resultSymbols:[String]
    let suggestions:[String]
    var failed:Bool{resultSymbols.isEmpty}
}
struct LiteDiscoveredMarket:Codable,Identifiable,Sendable {
    var id:String{canonicalIdentity}
    let underlyingMarket:String
    let canonicalIdentity:String
    let assetClass:String
    let representations:[LiteDiscoveredRepresentation]
    enum CodingKeys:String,CodingKey {case representations;case underlyingMarket="underlying_market",canonicalIdentity="canonical_identity",assetClass="asset_class"}
}
struct LiteDiscoveredRepresentation:Codable,Identifiable,Sendable {
    var id:String{symbol}
    let symbol:String
    let displayName:String
    let registrationStatus:String
    let acquisitionReadiness:String
    let registrationPlan:LiteRegistrationPlan?
    let timeframeLanes:[LiteDiscoveredTimeframe]
    enum CodingKeys:String,CodingKey {case symbol;case displayName="display_name",registrationStatus="registration_status",acquisitionReadiness="acquisition_readiness",registrationPlan="registration_plan",timeframeLanes="timeframe_lanes"}
}
struct LiteRegistrationPlan:Codable,Sendable {let candidate:String}
struct LiteDiscoveredTimeframe:Codable,Identifiable,Sendable {
    var id:String{timeframe}
    let timeframe:String
    let selectable:Bool
}

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
    let storedBytes:Int?
    let expectedBytes:Int?
    let receivedAtUTC:String?
    let lastUpdateCheckAtUTC:String?
    let lastUpdateOutcome:String?
    enum CodingKeys:String,CodingKey {case symbol,timeframe,caodt,state;case firstBarUTC="first_bar_utc",barCount="bar_count",dataFingerprint="data_fingerprint",assetClass="asset_class",storedBytes="stored_bytes",expectedBytes="expected_bytes",receivedAtUTC="received_at_utc",lastUpdateCheckAtUTC="last_update_check_at_utc",lastUpdateOutcome="last_update_outcome"}
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
    let firstBarUTC:String?
    let caodt:String?
    let barCount:Int?
    let requestedAtUTC:String
    let updatedAtUTC:String?
    let completedAtUTC:String?
    let activeAtUTC:String?
    let lastUpdateCheckAtUTC:String?
    let lastUpdateOutcome:String?
    let databaseBytes:Int?
    let expectedGeneration:Int?
    var actualProgress:Double {guard let expectedBytes,expectedBytes>0 else{return 0};return min(max(Double(transferredBytes ?? 0)/Double(expectedBytes),0),1)}
    enum CodingKeys:String,CodingKey {case symbol,timeframe,state,progress,caodt;case requestID="request_id",expectedBytes="expected_bytes",transferredBytes="transferred_bytes",verifiedBytes="verified_bytes",sourceRevision="source_revision",firstBarUTC="first_bar_utc",barCount="bar_count",requestedAtUTC="requested_at_utc",updatedAtUTC="updated_at_utc",completedAtUTC="completed_at_utc",activeAtUTC="active_at_utc",lastUpdateCheckAtUTC="last_update_check_at_utc",lastUpdateOutcome="last_update_outcome",databaseBytes="database_bytes",expectedGeneration="expected_generation"}
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
    @Published var discovery:LiteMarketDiscovery?
    @Published var discoveryLoading=false
    @Published var searchDraft=""
    @Published private(set) var searchHistory:[LiteSearchHistoryItem]=[]
    @Published private(set) var onboardingSymbol:String?
    @Published private(set) var focusedSymbol:String?
    private let base=URL(string:"http://127.0.0.1:9463")!
    private let searchHistoryKey="fragarach.lite.search-history.v1"
    private var refreshing=false

    init() {
        guard let data=UserDefaults.standard.data(forKey:searchHistoryKey),
              let history=try? JSONDecoder().decode([LiteSearchHistoryItem].self,from:data) else{return}
        searchHistory=history
    }

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
            if let symbol=onboardingSymbol {
                if let lane=decoded.lanes.first(where:{$0.symbol == symbol}) {
                    notice="\(symbol) ready on this MacBook · \(lane.barCount) bars received"
                    onboardingSymbol=nil
                    focusedSymbol=symbol
                } else if let request=decoded.incomingData?.first(where:{$0.symbol == symbol}) {
                    let stage=request.state.replacingOccurrences(of:"_",with:" ").lowercased()
                    notice="\(symbol) · \(stage) · this page updates automatically"
                }
            }
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

    func requestLanes(_ symbol:String,timeframes:[String]) async {
        let normalized=symbol.trimmingCharacters(in:.whitespacesAndNewlines).uppercased()
        guard !normalized.isEmpty,!timeframes.isEmpty else{return}
        notice="Sending \(normalized) to Studio…"
        do {
            for timeframe in timeframes {
                var request=URLRequest(url:base.appending(path:"v1/request-lane"));request.httpMethod="POST";request.setValue("application/json",forHTTPHeaderField:"Content-Type")
                request.httpBody=try JSONSerialization.data(withJSONObject:["symbol":normalized,"timeframe":timeframe])
                let (data,response)=try await URLSession.shared.data(for:request)
                guard (response as? HTTPURLResponse)?.statusCode==200 else {
                    let detail=(try? JSONSerialization.jsonObject(with:data) as? [String:Any])?["error"] as? String
                    throw NSError(domain:"FragarachLite",code:1,userInfo:[NSLocalizedDescriptionKey:detail ?? "Studio did not accept the request"])
                }
            }
            error=nil
            await refresh()
            notice="\(normalized) requested · Studio will return each lane when it is ready"
        } catch {self.error=error.localizedDescription}
    }

    func discover(_ query:String) async {
        let value=query.trimmingCharacters(in:.whitespacesAndNewlines)
        guard !value.isEmpty else{return}
        discoveryLoading=true
        defer{discoveryLoading=false}
        do {
            var components=URLComponents(url:base.appending(path:"v1/discover-symbol"),resolvingAgainstBaseURL:false)!
            components.queryItems=[URLQueryItem(name:"q",value:value)]
            let (data,response)=try await URLSession.shared.data(from:components.url!)
            guard (response as? HTTPURLResponse)?.statusCode==200 else {
                let detail=(try? JSONSerialization.jsonObject(with:data) as? [String:Any])?["error"] as? String
                throw NSError(domain:"FragarachLite",code:1,userInfo:[NSLocalizedDescriptionKey:detail ?? "Studio search failed"])
            }
            let result=try JSONDecoder().decode(LiteMarketDiscovery.self,from:data)
            discovery=result
            recordSearch(query:value,result:result)
            error=nil
        } catch {
            self.error=error.localizedDescription
            discovery=nil
            recordSearch(query:value,status:"ERROR",resultSymbols:[],suggestions:[])
        }
    }

    func onboard(query:String,representation:LiteDiscoveredRepresentation,timeframes:[String]) async {
        guard let candidate=representation.registrationPlan?.candidate else {
            await requestLanes(representation.symbol,timeframes:timeframes)
            return
        }
        notice="Adding \(representation.symbol) to Fragarach…"
        do {
            var request=URLRequest(url:base.appending(path:"v1/onboard-symbol"));request.httpMethod="POST";request.setValue("application/json",forHTTPHeaderField:"Content-Type")
            request.httpBody=try JSONSerialization.data(withJSONObject:["query":query,"candidate":candidate,"timeframes":timeframes])
            let (data,response)=try await URLSession.shared.data(for:request)
            guard (response as? HTTPURLResponse)?.statusCode==200 else {
                let detail=(try? JSONSerialization.jsonObject(with:data) as? [String:Any])?["error"] as? String
                throw NSError(domain:"FragarachLite",code:1,userInfo:[NSLocalizedDescriptionKey:detail ?? "Studio onboarding failed"])
            }
            error=nil
            discovery=nil
            onboardingSymbol=representation.symbol
            await refresh()
            notice="\(representation.symbol) registered · Studio is acquiring the selected lanes"
        } catch {self.error=error.localizedDescription}
    }

    func clearFocusedSymbol(){focusedSymbol=nil}

    func act(_ lane:LiteLane,_ action:String) async {
        await act(symbol:lane.symbol,timeframe:lane.timeframe,action)
    }

    func act(symbol:String,timeframe:String,_ action:String) async {
        do {
            try await sendAction(symbol:symbol,timeframe:timeframe,action:action)
            error=nil
            await refresh()
            if action == "REMOVE" {notice="Removed \(symbol) \(timeframe) from this MacBook"}
        } catch {self.error=error.localizedDescription}
    }

    func rerequest(_ lane:LiteLane) async {
        guard pendingLaneIDs.insert(lane.id).inserted else{return}
        notice="Replacing \(lane.symbol) \(lane.timeframe) from Studio…"
        defer{pendingLaneIDs.remove(lane.id)}
        do {
            try await sendAction(symbol:lane.symbol,timeframe:lane.timeframe,action:"REMOVE")
            var request=URLRequest(url:base.appending(path:"v1/request-lane"));request.httpMethod="POST";request.setValue("application/json",forHTTPHeaderField:"Content-Type")
            request.httpBody=try JSONSerialization.data(withJSONObject:["symbol":lane.symbol,"timeframe":lane.timeframe])
            let (_,response)=try await URLSession.shared.data(for:request)
            guard (response as? HTTPURLResponse)?.statusCode==200 else{throw URLError(.badServerResponse)}
            error=nil
            await refresh()
            notice="\(lane.symbol) \(lane.timeframe) re-requested · waiting for Studio"
        } catch {self.error=error.localizedDescription}
    }

    private func sendAction(symbol:String,timeframe:String,action:String) async throws {
        var request=URLRequest(url:base.appending(path:"v1/request-action"));request.httpMethod="POST";request.setValue("application/json",forHTTPHeaderField:"Content-Type")
        request.httpBody=try JSONSerialization.data(withJSONObject:["symbol":symbol,"timeframe":timeframe,"action":action])
        let (data,response)=try await URLSession.shared.data(for:request)
        guard (response as? HTTPURLResponse)?.statusCode==200 else {
            let detail=(try? JSONSerialization.jsonObject(with:data) as? [String:Any])?["error"] as? String
            throw NSError(domain:"FragarachLite",code:1,userInfo:[NSLocalizedDescriptionKey:detail ?? "The lane action was not accepted"])
        }
    }

    private func recordSearch(query:String,result:LiteMarketDiscovery) {
        let symbols=result.markets.flatMap(\.representations).map(\.symbol)
        let suggestions=Array(NSOrderedSet(array:result.suggestedSearches + result.similarMarkets).array.compactMap{$0 as? String})
        recordSearch(query:query,status:result.discoveryStatus,resultSymbols:symbols,suggestions:suggestions)
    }

    private func recordSearch(query:String,status:String,resultSymbols:[String],suggestions:[String]) {
        let normalized=query.trimmingCharacters(in:.whitespacesAndNewlines)
        searchHistory.removeAll{$0.query.caseInsensitiveCompare(normalized) == .orderedSame}
        searchHistory.insert(LiteSearchHistoryItem(
            id:UUID(),query:normalized,searchedAtUTC:Date().ISO8601Format(),discoveryStatus:status,
            resultSymbols:Array(NSOrderedSet(array:resultSymbols).array.compactMap{$0 as? String}),suggestions:suggestions
        ),at:0)
        searchHistory=Array(searchHistory.prefix(25))
        if let data=try? JSONEncoder().encode(searchHistory){UserDefaults.standard.set(data,forKey:searchHistoryKey)}
    }
}
