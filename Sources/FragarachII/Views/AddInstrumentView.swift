import Foundation
import OperationsCore
import SwiftUI

struct AddInstrumentView: View {
    @EnvironmentObject var store: ConsoleStore
    @State private var query=""; @State private var response:InstrumentSearchResponse?
    @State private var state="Not Found"; @State private var message:String?
    @State private var from=Calendar.current.date(byAdding:.day,value:-30,to:Date())!.formatted(.iso8601.year().month().day())
    @State private var through=Date().formatted(.iso8601.year().month().day())

    var body: some View {
        ScrollView { VStack(alignment:.leading,spacing:18) {
            Text("Add Instrument").font(.largeTitle)
            Text("Discover, review, register, and acquire through the Python authority.").foregroundStyle(.secondary)
            HStack { TextField("Search Instrument",text:$query).textFieldStyle(.roundedBorder).onSubmit{search()}; Button("Search"){search()}.buttonStyle(.borderedProminent).disabled(query.trimmingCharacters(in:.whitespaces).isEmpty || busy) }
            HStack { Text("Current State").foregroundStyle(.secondary); Text(state).fontWeight(.semibold); if busy { ProgressView().controlSize(.small) } }
            if let message { Text(message).foregroundStyle(state=="Ready" ? .green:.secondary) }
            if let candidate=response?.candidate { reviewCard(candidate) }
        }.padding().frame(maxWidth:780,alignment:.leading) }
    }
    private var busy:Bool { store.activeOperationID != nil }
    @ViewBuilder private func reviewCard(_ c:InstrumentCandidate)->some View {
        GroupBox(response?.alreadyRegistered == true ? "Already Registered":"Review Instrument") { VStack(alignment:.leading,spacing:10) {
            Text(c.displayName).font(.title2).fontWeight(.semibold)
            Facts([("Canonical",c.asset),("Provider Symbol",c.providerSymbol),("Provider","Twelve Data"),("Exchange",c.exchangeName),("MIC",c.exchangeMIC ?? "—"),("Currency",c.tradingCurrency),("Instrument Type",c.instrumentType),("Representation",c.representationType),("Calendar","\(c.calendarID) v\(c.calendarVersion)"),("Gap Doctrine","\(c.gapDoctrineID) v\(c.gapDoctrineVersion)")])
            Divider()
            HStack {
                Button("Register Instrument"){register(c)}.buttonStyle(.borderedProminent).disabled(response?.alreadyRegistered == true || busy)
                if response?.alreadyRegistered == true || state=="Registered" || state=="Ready" { Button("Acquire D1 History"){acquire(c)}.disabled(!store.credentialAvailable || busy) }
            }
            if response?.alreadyRegistered == true || state=="Registered" { HStack { TextField("From",text:$from);TextField("Through",text:$through) }.textFieldStyle(.roundedBorder) }
        }.padding(8) }
    }
    private func search(){
        state="Searching";message=nil;response=nil
        Task { await store.run(.searchInstrument(query:query)); guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let data=text.data(using:.utf8),let decoded=try? JSONDecoder().decode(InstrumentSearchResponse.self,from:data) else { state="Not Found";message=factualError();return };response=decoded
            if !decoded.found {state="Not Found";message="No provider matches found."} else if decoded.alreadyRegistered {state=decoded.registrationStatus=="REGISTERED_WITH_EVIDENCE" ? "Ready":"Registered";message="Already Registered"} else {state="Review"}
        }
    }
    private func register(_ candidate:InstrumentCandidate){
        guard let data=try? JSONEncoder().encode(candidate) else {state="Review";message="Registration rejected";return}
        Task { await store.run(.registerInstrument(candidate:data.base64EncodedString()));if store.lastProcessResult?.exitCode==0 {state="Registered";message="REGISTERED_NO_EVIDENCE";response=InstrumentSearchResponse(found:true,alreadyRegistered:true,candidate:candidate,registrationStatus:"REGISTERED_NO_EVIDENCE")} else {state="Review";message=factualError()} }
    }
    private func acquire(_ candidate:InstrumentCandidate){
        state="Acquiring";message=nil
        Task { await store.run(.acquire(asset:candidate.asset,from:from,through:through,mode:.preserve));if store.lastProcessResult?.exitCode==0 {state="Validating";await store.refresh();state="Ready";message="REGISTERED_WITH_EVIDENCE — visible in Lanes"} else {state="Registered";message=factualError()} }
    }
    private func factualError()->String { guard let raw=store.operationError ?? store.lastProcessResult?.stdout,let data=raw.data(using:.utf8),let value=try? JSONSerialization.jsonObject(with:data) as? [String:Any] else{return store.operationError ?? "Operation failed"};return (value["error"] as? String) ?? (value["code"] as? String) ?? "Operation failed" }
}
