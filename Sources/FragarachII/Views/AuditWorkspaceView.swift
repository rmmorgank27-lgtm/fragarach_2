import OperationsCore
import SwiftUI

private enum AuditSection:String,CaseIterable,Identifiable,Hashable { case events="Authority Events",registrations="Registrations & Lifecycle",receipts="Operation Receipts";var id:String{rawValue} }

struct AuditWorkspaceView:View {
    @EnvironmentObject private var store:ConsoleStore
    @State private var section:AuditSection = .events
    var body:some View { VStack(alignment:.leading,spacing:12) {
        Picker("Audit Evidence",selection:$section){ForEach(AuditSection.allCases){Text($0.rawValue).tag($0)}}.pickerStyle(.segmented).frame(maxWidth:720)
        switch section {
        case .events:AuthorityLedgerView()
        case .registrations:registrationHistory
        case .receipts:OperationsView()
        }
    } }
    private var registrationHistory:some View { List(store.snapshot?.registrations ?? []) { r in DisclosureGroup { Facts([("Registration ID",r.id),("Display Name",r.displayName),("Representation",r.representationType),("Asset Class",r.assetClass),("Provider",r.providerID),("Provider Symbol",r.providerSymbol),("Registration State",r.registrationStatus),("Lifecycle",r.retired ? "RETIRED · HISTORICAL_ONLY":"ACTIVE")]) } label:{HStack{VStack(alignment:.leading){Text("\(r.asset) · \(r.timeframe)").font(.headline);Text(r.displayName).foregroundStyle(.secondary)};Spacer();Text(r.retired ? "RETIRED":"ACTIVE").foregroundStyle(r.retired ? .orange:.green)}} }.searchable(text:$store.auditFilter,prompt:"Search registration or lifecycle") }
}
