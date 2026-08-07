import SwiftUI

private enum LitePage:String,CaseIterable,Identifiable {
    case estate
    case replication
    var id:String{rawValue}
    var title:String{self == .estate ? "Markets":"Replication"}
    var icon:String{self == .estate ? "square.grid.2x2":"arrow.triangle.2.circlepath"}
}

struct LiteRootView:View {
    @EnvironmentObject private var store:LiteEstateStore
    @SceneStorage("lite.page") private var page=LitePage.estate

    var body:some View {
        NavigationSplitView {
            List(LitePage.allCases,selection:$page) { item in
                Label(item.title,systemImage:item.icon).tag(item)
            }
            .listStyle(.sidebar)
            .navigationTitle("Fragarach Lite")
        } detail: {
            switch page {
            case .estate:LiteEstateView()
            case .replication:LiteReplicationView()
            }
        }
        .task{await store.start()}
        .onChange(of:store.focusedSymbol){_,symbol in if symbol != nil{page = .estate}}
    }
}

private struct LiteReplicationView:View {
    @EnvironmentObject private var store:LiteEstateStore

    var body:some View {
        ScrollView {
            VStack(alignment:.leading,spacing:16) {
                HStack {
                    VStack(alignment:.leading) {
                        Text("Replication").font(.largeTitle.bold())
                        Text("MacBook lane storage, arrivals, and update checks").foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Refresh"){Task{await store.refresh()}}.keyboardShortcut("r")
                }
                if let error=store.error {Label(error,systemImage:"exclamationmark.triangle.fill").foregroundStyle(.red)}
                if let notice=store.notice {Label(notice,systemImage:"info.circle.fill").foregroundStyle(.orange)}
                NewSymbolRequestView()
                RecentActivityView()
                IncomingDataRegistryView(catalogue:store.catalogue)
                Label("Only requested and verified lane artifacts are stored on this MacBook.",systemImage:"checkmark.shield.fill")
                    .font(.caption).foregroundStyle(.green)
            }.padding(24)
        }
    }
}

private struct NewSymbolRequestView:View {
    @EnvironmentObject private var store:LiteEstateStore
    @State private var timeframes:Set<String>=["D1"]
    @State private var submitting=false
    private let choices=["D1","H1","M30","M5"]

    var body:some View {
        GroupBox("Request a New Symbol") {
            VStack(alignment:.leading,spacing:10) {
                Text("Search Studio first, select the canonical market, then add its lanes to Fragarach and this MacBook.")
                    .font(.caption).foregroundStyle(.secondary)
                HStack(spacing:12) {
                    TextField("Name or symbol, for example PEPE",text:$store.searchDraft)
                        .textFieldStyle(.roundedBorder).frame(width:320)
                        .onSubmit{Task{await store.discover(store.searchDraft)}}
                    Spacer()
                    Button(store.discoveryLoading ? "Searching…":"Search Studio") {
                        Task{await store.discover(store.searchDraft)}
                    }.disabled(store.discoveryLoading || store.searchDraft.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)
                }
                if let discovery=store.discovery {
                    Divider()
                    Text(discovery.explanation).font(.caption).foregroundStyle(.secondary)
                    if discovery.markets.isEmpty {
                        ContentUnavailableView("No matching market",systemImage:"magnifyingglass",description:Text("Try a company name, canonical symbol, currency pair, commodity, or cryptocurrency name."))
                            .frame(maxWidth:.infinity,minHeight:100)
                        suggestionButtons(discovery.suggestedSearches + discovery.similarMarkets)
                    } else {
                        ForEach(discovery.markets){market in
                            ForEach(market.representations){representation in
                                let selectable=Set(representation.timeframeLanes.filter(\.selectable).map(\.timeframe))
                                VStack(alignment:.leading,spacing:8) {
                                    HStack {
                                        VStack(alignment:.leading,spacing:2) {
                                            Text(representation.displayName).font(.headline)
                                            Text("\(representation.symbol) · \(market.assetClass) · \(representation.registrationStatus.replacingOccurrences(of:"_",with:" "))")
                                                .font(.caption).foregroundStyle(.secondary)
                                        }
                                        Spacer()
                                        Text(representation.acquisitionReadiness.replacingOccurrences(of:"_",with:" "))
                                            .font(.caption.bold()).foregroundStyle(.green)
                                    }
                                    HStack(spacing:12) {
                                        ForEach(choices,id:\.self){timeframe in
                                            let available=selectable.contains(timeframe)
                                            Toggle(timeframe,isOn:Binding(
                                                get:{timeframes.contains(timeframe)},
                                                set:{enabled in
                                                    if enabled {timeframes.insert(timeframe)}
                                                    else {timeframes.remove(timeframe)}
                                                }
                                            )).toggleStyle(.checkbox).disabled(!available)
                                        }
                                        Spacer()
                                        Button(submitting ? "Adding…":(representation.registrationPlan == nil ? "Request Lanes":"Add to Fragarach & Replica")) {
                                            submitting=true
                                            let selected=choices.filter{timeframes.contains($0) && selectable.contains($0)}
                                            Task {
                                                await store.onboard(query:store.searchDraft,representation:representation,timeframes:selected)
                                                if store.error == nil {store.searchDraft=""}
                                                submitting=false
                                            }
                                        }.buttonStyle(.borderedProminent).disabled(submitting || timeframes.intersection(selectable).isEmpty)
                                    }
                                }
                                .padding(10)
                                .background(.quaternary.opacity(0.25),in:RoundedRectangle(cornerRadius:8))
                            }
                        }
                    }
                }
            }.padding(8)
        }
    }

    @ViewBuilder private func suggestionButtons(_ values:[String])->some View {
        let suggestions=Array(NSOrderedSet(array:values).array.compactMap{$0 as? String})
        if !suggestions.isEmpty {
            HStack(spacing:8) {
                Text("Suggestions").font(.caption.bold()).foregroundStyle(.secondary)
                ForEach(suggestions,id:\.self){suggestion in
                    Button(suggestion){
                        store.searchDraft=suggestion
                        Task{await store.discover(suggestion)}
                    }.buttonStyle(.bordered)
                }
                Spacer()
            }
        }
    }
}

private struct RecentActivityView:View {
    @EnvironmentObject private var store:LiteEstateStore
    @SceneStorage("replication.recentActivity.expanded") private var isExpanded=false
    private var requests:[LiteIncomingData] {
        Array((store.catalogue.incomingData ?? []).sorted{$0.requestedAtUTC > $1.requestedAtUTC}.prefix(10))
    }
    private var recentSearches:[LiteSearchHistoryItem]{Array(store.searchHistory.prefix(5))}
    private var failedSearches:[LiteSearchHistoryItem]{Array(store.searchHistory.filter(\.failed).prefix(5))}

    var body:some View {
        GroupBox {
            DisclosureGroup(isExpanded:$isExpanded) {
                HStack(alignment:.top,spacing:12) {
                    activityColumn("Last 10 requests",icon:"arrow.down.circle") {
                        if requests.isEmpty {empty("No requests yet")}
                        ForEach(requests){request in
                            activityRow("\(request.symbol) · \(request.timeframe)",detail:request.state.replacingOccurrences(of:"_",with:" ").capitalized,date:request.requestedAtUTC)
                        }
                    }
                    Divider()
                    activityColumn("Last 5 searches",icon:"magnifyingglass") {
                        if recentSearches.isEmpty {empty("Search history starts here")}
                        ForEach(recentSearches){item in
                            activityRow(item.query,detail:item.resultSymbols.isEmpty ? "No match":item.resultSymbols.joined(separator:", "),date:item.searchedAtUTC)
                        }
                    }
                    Divider()
                    activityColumn("Failed searches",icon:"exclamationmark.magnifyingglass") {
                        if failedSearches.isEmpty {empty("No failed searches")}
                        ForEach(failedSearches){item in
                            VStack(alignment:.leading,spacing:4) {
                                activityRow(item.query,detail:item.discoveryStatus.replacingOccurrences(of:"_",with:" ").capitalized,date:item.searchedAtUTC)
                                if !item.suggestions.isEmpty {
                                    HStack(spacing:5) {
                                        ForEach(item.suggestions.prefix(3),id:\.self){suggestion in
                                            Button(suggestion){
                                                store.searchDraft=suggestion
                                                Task{await store.discover(suggestion)}
                                            }.buttonStyle(.link).font(.caption2)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(.top,10)
                .fixedSize(horizontal:false,vertical:true)
            } label: {
                Label("Recent Activity",systemImage:"clock.arrow.circlepath").font(.headline)
            }
            .padding(8)
        }
    }

    private func activityColumn<Content:View>(_ title:String,icon:String,@ViewBuilder content:()->Content)->some View {
        VStack(alignment:.leading,spacing:8) {
            Label(title,systemImage:icon).font(.caption.bold())
            Divider()
            content()
        }.frame(maxWidth:.infinity,alignment:.topLeading)
    }

    private func activityRow(_ title:String,detail:String,date:String)->some View {
        HStack(alignment:.firstTextBaseline,spacing:6) {
            VStack(alignment:.leading,spacing:1) {
                Text(title).font(.caption.bold()).lineLimit(1)
                Text(detail).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer(minLength:4)
            Text(shortDate(date)).font(.caption2.monospaced()).foregroundStyle(.tertiary).lineLimit(1)
        }
    }

    private func empty(_ text:String)->some View {Text(text).font(.caption2).foregroundStyle(.secondary)}
    private func shortDate(_ value:String)->String {
        let display=value.replacingOccurrences(of:"T",with:" ").replacingOccurrences(of:"+00:00",with:"Z")
        return display.count > 16 ? String(display.prefix(16)):display
    }
}
