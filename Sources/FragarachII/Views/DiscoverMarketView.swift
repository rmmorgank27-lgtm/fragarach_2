import OperationsCore
import SwiftUI

struct DiscoverMarketView:View {
    @EnvironmentObject var store:ConsoleStore
    @State private var query="";@State private var discovery:MarketDiscoveryResult?;@State private var selectedID:String?;@State private var error:String?
    private var selected:DiscoveredMarket?{discovery?.markets.first{$0.id==selectedID}};private var busy:Bool{store.activeOperationID != nil}
    var body:some View { VStack(alignment:.leading,spacing:16){
        Text("Discover Market").font(.largeTitle);Text("Move from market intent to representations, provider mappings, and onboarding readiness.").foregroundStyle(.secondary)
        HStack{TextField("Market, CFD, ETF, futures, index, commodity, company, or alias",text:$query).textFieldStyle(.roundedBorder).onSubmit{discover()};Button("Discover"){discover()}.buttonStyle(.borderedProminent).disabled(query.trimmingCharacters(in:.whitespaces).isEmpty || busy);if busy{ProgressView().controlSize(.small)}}
        if let error{ContentUnavailableView("Discovery failed",systemImage:"exclamationmark.triangle",description:Text(error))}
        else if let discovery{HStack{Text("Discovery").foregroundStyle(.secondary);Text(discovery.discoveryStatus).fontWeight(.semibold);Text("Confidence \(discovery.confidence)").foregroundStyle(.secondary)};Text(discovery.explanation).foregroundStyle(.secondary)
            if discovery.markets.isEmpty{UnknownMarketView(discovery:discovery)}else{HSplitView{List(discovery.markets,selection:$selectedID){market in VStack(alignment:.leading,spacing:3){Text(market.underlyingMarket).font(.headline);Text(market.canonicalIdentity).font(.caption.monospaced()).foregroundStyle(.secondary);Text("\(market.confidence) · \(market.marketType)").font(.caption).foregroundStyle(.secondary)}.tag(market.id)}.frame(minWidth:280,idealWidth:340);ScrollView{if let selected{MarketOnboardingDetail(market:selected)}}.frame(minWidth:520)}}
        }else{ContentUnavailableView("Discover a market",systemImage:"map",description:Text("Examples: US30, DJI, DIA, YM, Gold, WTI, AUDJPY, Apple, Tesla, or BHP."))};Spacer(minLength:0)
    }.padding() }
    private func discover(){discovery=nil;selectedID=nil;error=nil;Task{await store.run(.discoverMarket(query:query));guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let data=text.data(using:.utf8),let decoded=try? JSONDecoder().decode(MarketDiscoveryResult.self,from:data)else{error=factualError();return};discovery=decoded;selectedID=decoded.markets.first?.id}}
    private func factualError()->String{guard let raw=store.operationError ?? store.lastProcessResult?.stdout,let data=raw.data(using:.utf8),let value=try? JSONSerialization.jsonObject(with:data) as? [String:Any]else{return store.operationError ?? "Market discovery failed"};return (value["error"] as? String) ?? (value["code"] as? String) ?? "Market discovery failed"}
}

private struct MarketOnboardingDetail:View {
    @EnvironmentObject var store:ConsoleStore;let market:DiscoveredMarket
    var body:some View{VStack(alignment:.leading,spacing:16){
        Text(market.underlyingMarket).font(.title2).fontWeight(.semibold);Text(market.description).foregroundStyle(.secondary)
        OnboardingStage(number:1,title:"Market Identity"){Facts([("Canonical",market.canonicalIdentity),("Confidence","\(market.confidence)"),("Type",market.marketType),("Asset Class",market.assetClass),("Reason",market.resolutionReason)])}
        OnboardingStage(number:2,title:"Tradable Representations"){VStack(spacing:0){ForEach(market.representations){r in HStack{VStack(alignment:.leading){Text(r.representationType).font(.caption).foregroundStyle(.secondary);Text(r.displayName)};Spacer();Text(r.symbol).font(.headline.monospaced());Text(r.registrationStatus).font(.caption).foregroundStyle(.secondary)}.padding(.vertical,7);Divider()}}}
        OnboardingStage(number:3,title:"Provider Discovery"){VStack(spacing:0){ForEach(market.providerDiscovery){p in HStack{VStack(alignment:.leading){Text(p.provider).fontWeight(.semibold);Text(p.representationSymbol).font(.caption.monospaced())};Spacer();VStack(alignment:.trailing){Text(p.availability);Text("Timeframes: \(p.supportedTimeframes.isEmpty ? "Unknown":p.supportedTimeframes.joined(separator:", "))").font(.caption);Text("Entitlement: \(p.entitlement)").font(.caption).foregroundStyle(.secondary)}}.padding(.vertical,7);Divider()}}}
        OnboardingStage(number:4,title:"Registration Recommendation"){Facts([("Recommended",market.recommendation.displayName),("Symbol",market.recommendation.symbol),("Representation",market.recommendation.representationType),("Reason",market.recommendation.reason),("Alternatives",market.recommendation.alternatives.joined(separator:", "))])}
        OnboardingStage(number:5,title:"Preliminary Metadata"){Facts([("Market",market.metadata.market),("Asset Class",market.metadata.assetClass),("Exchange",market.metadata.exchange ?? "Unknown"),("Timezone",market.metadata.timezone ?? "Unknown"),("Sessions",market.metadata.sessions.joined(separator:", ")),("Currencies",market.metadata.currencies.joined(separator:", ")),("Aliases",market.metadata.aliases.joined(separator:", ")),("Registration",market.metadata.registrationState),("Readiness",market.acquisitionReadiness)])}
        if !market.existingRegistrations.isEmpty{OnboardingStage(number:6,title:"Existing Authority"){VStack(alignment:.leading,spacing:10){ForEach(market.existingRegistrations){e in Facts([("Symbol",e.canonicalSymbol),("Authority",e.authorityState),("Truth Score",e.truthScore.map(String.init) ?? "Not measured"),("CAODT",e.caodt ?? "Not measured"),("Registration Version","\(e.registrationVersion)")]);Button("Open Existing"){store.selectedTruthLaneID="\(e.canonicalSymbol):D1";store.section = .truth}.buttonStyle(.borderedProminent)}}}}
        Text("Next: operator review → registration (future) → acquisition → validation → Truth").font(.caption).foregroundStyle(.secondary)
    }.padding()}
}

private struct OnboardingStage<Content:View>:View{let number:Int;let title:String;@ViewBuilder let content:Content;init(number:Int,title:String,@ViewBuilder content:()->Content){self.number=number;self.title=title;self.content=content()};var body:some View{GroupBox{content.padding(.vertical,4)}label:{Label("\(number). \(title)",systemImage:"\(number).circle.fill")}}}
private struct UnknownMarketView:View{let discovery:MarketDiscoveryResult;var body:some View{GroupBox("Unknown Market"){VStack(alignment:.leading,spacing:10){Text(discovery.operatorGuidance);Text("Suggested Searches").font(.headline);ForEach(discovery.suggestedSearches,id:\.self){Text("• \($0)")};if !discovery.similarMarkets.isEmpty{Text("Similar Markets").font(.headline);Text(discovery.similarMarkets.joined(separator:", "))}}.frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,6)}}}
