import OperationsCore
import SwiftUI

struct ResolveInstrumentView:View {
    @EnvironmentObject var store:ConsoleStore
    @State private var query=""
    @State private var resolution:InstrumentIdentityResolution?
    @State private var selectedID:String?
    @State private var error:String?
    private var selected:ResolvedInstrumentIdentity? { resolution?.matches.first{$0.id==selectedID} }
    private var busy:Bool { store.activeOperationID != nil }

    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            Text("Resolve Instrument").font(.largeTitle)
            Text("Identify the instrument before provider discovery, registration, or acquisition.").foregroundStyle(.secondary)
            HStack { TextField("Ticker, alias, company, commodity, currency pair, or index",text:$query).textFieldStyle(.roundedBorder).onSubmit{resolve()};Button("Resolve"){resolve()}.buttonStyle(.borderedProminent).disabled(query.trimmingCharacters(in:.whitespaces).isEmpty || busy);if busy{ProgressView().controlSize(.small)} }
            if let error { ContentUnavailableView("Resolution failed",systemImage:"exclamationmark.triangle",description:Text(error)) }
            else if let resolution {
                HStack { Text("Identity Status").foregroundStyle(.secondary);Text(resolution.identityStatus).fontWeight(.semibold);Text("Confidence \(resolution.confidence)").foregroundStyle(.secondary) }
                Text(resolution.explanation).foregroundStyle(.secondary)
                if resolution.matches.isEmpty { UnknownIdentityView(resolution:resolution) }
                else { HSplitView {
                    List(resolution.matches,selection:$selectedID){match in VStack(alignment:.leading,spacing:3){Text(match.canonicalSymbol).font(.headline);Text(match.canonicalName).foregroundStyle(.secondary).lineLimit(1);Text("\(match.confidence) · \(match.identityStatus)").font(.caption).foregroundStyle(.secondary)}.tag(match.id)}.frame(minWidth:260,idealWidth:320)
                    ScrollView { if let selected { IdentityReviewView(identity:selected) } }.frame(minWidth:430)
                }}
            } else { ContentUnavailableView("Resolve instrument identity",systemImage:"magnifyingglass",description:Text("Examples: AUDJPY, Apple, Gold, Dow, BTC, or BHP.")) }
            Spacer(minLength:0)
        }.padding()
    }

    private func resolve(){
        resolution=nil;selectedID=nil;error=nil
        Task { await store.run(.resolveInstrument(query:query));guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let data=text.data(using:.utf8),let decoded=try? JSONDecoder().decode(InstrumentIdentityResolution.self,from:data) else{error=factualError();return};resolution=decoded;selectedID=decoded.matches.first?.id }
    }
    private func factualError()->String { guard let raw=store.operationError ?? store.lastProcessResult?.stdout,let data=raw.data(using:.utf8),let value=try? JSONSerialization.jsonObject(with:data) as? [String:Any] else{return store.operationError ?? "Identity resolution failed"};return (value["error"] as? String) ?? (value["code"] as? String) ?? "Identity resolution failed" }
}

private struct IdentityReviewView:View {
    let identity:ResolvedInstrumentIdentity
    var body:some View { VStack(alignment:.leading,spacing:16) {
        HStack(alignment:.firstTextBaseline){VStack(alignment:.leading){Text(identity.canonicalName).font(.title2).fontWeight(.semibold);Text(identity.canonicalSymbol).font(.headline.monospaced()).foregroundStyle(.secondary)};Spacer();Text("\(identity.confidence)").font(.system(size:34,weight:.semibold,design:.rounded))}
        GroupBox("Preliminary Metadata") { Facts([("Identity",identity.identityStatus),("Instrument Type",identity.instrumentType),("Market",identity.market),("Asset Class",identity.assetClass),("Exchange",identity.knownExchange ?? "Unknown"),("Currency",identity.knownCurrency ?? "Unknown"),("Base",identity.baseCurrency ?? "Unknown"),("Quote",identity.quoteCurrency ?? "Unknown"),("Timezone",identity.timezone ?? "Unknown"),("Sessions",identity.sessions.isEmpty ? "Unknown":identity.sessions.joined(separator:", "))]) }
        GroupBox("Known Aliases") { Text(identity.knownAliases.isEmpty ? "None recorded":identity.knownAliases.joined(separator:", ")).frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,6).textSelection(.enabled) }
        GroupBox("Resolution") { Text(identity.resolutionReason).frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,6) }
        GroupBox("Registration State") { Facts([("Registration",identity.registrationState),("Authority",identity.authorityState ?? "Not measured"),("Truth Score",identity.currentTruthScore.map(String.init) ?? "Not measured"),("CAODT",identity.currentCAODT ?? "Not measured")]) }
        Text("Next lifecycle stage: Review Metadata → Discover Providers").font(.caption).foregroundStyle(.secondary)
    }.padding() }
}

private struct UnknownIdentityView:View {
    let resolution:InstrumentIdentityResolution
    var body:some View { GroupBox("No known identity") { VStack(alignment:.leading,spacing:10){Text("Suggested Searches").font(.headline);ForEach(resolution.suggestedSearches,id:\.self){Text("• \($0)")};Text("Suggested Aliases").font(.headline);Text(resolution.suggestedAliases.joined(separator:", "));Text("Suggested Providers").font(.headline);ForEach(resolution.suggestedProviders,id:\.self){Text("• \($0)")}}.frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,6) } }
}
