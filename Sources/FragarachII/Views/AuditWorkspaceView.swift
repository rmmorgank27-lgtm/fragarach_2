import OperationsCore
import SwiftUI

private enum AuditSection:String,CaseIterable,Identifiable,Hashable { case estate="Estate Audit",events="Authority Events",registrations="Registrations & Lifecycle",receipts="Operation Receipts";var id:String{rawValue} }

struct AuditWorkspaceView:View {
    @EnvironmentObject private var store:ConsoleStore
    @State private var section:AuditSection = .estate
    var body:some View { VStack(alignment:.leading,spacing:12) {
        Picker("Audit Evidence",selection:$section){ForEach(AuditSection.allCases){Text($0.rawValue).tag($0)}}.pickerStyle(.segmented).frame(maxWidth:720)
        switch section {
        case .estate:estateAudit
        case .events:AuthorityLedgerView()
        case .registrations:registrationHistory
        case .receipts:OperationsView()
        }
    } }
    private var estateAudit:some View { VStack(alignment:.leading,spacing:16) { HStack { WorkspaceHeader(title:"Estate Audit",purpose:"Explicit full-estate governance checks. It never acquires market data.");Spacer();Button("Run Audit Estate"){Task{await store.runEstateAudit()}}.buttonStyle(.borderedProminent).disabled(store.activeOperationID != nil) }.padding(.horizontal)
        if let audit=store.schedulerServiceStatus?.audit { Facts([("Result",audit.overallResult ?? audit.state),("Trigger",audit.trigger ?? "—"),("Completed",SchedulerFormatting.timestamp(audit.completedAtUTC)),("Next weekly audit",SchedulerFormatting.timestamp(audit.nextWeeklyAuditAtUTC)),("Findings",(audit.findingCounts ?? [:]).map{"\($0.key): \($0.value)"}.sorted().joined(separator:" · ")),("Safe report size",audit.reportBytes.map{"\($0) bytes"} ?? "—"),("Review repair plan",audit.repairPlanID ?? "None")]).padding(.horizontal);if let counts=audit.findingCounts { List(counts.keys.sorted(),id:\.self){severity in HStack{Text(severity.replacingOccurrences(of:"_",with:" ").capitalized);Spacer();Text("\(counts[severity] ?? 0)").font(.headline)}}.frame(minHeight:180) } } else { ContentUnavailableView("No estate audit recorded",systemImage:"checklist",description:Text("Run Audit Estate to create a bounded governance report.")) }
    }.padding(.vertical,12) }
    private var registrationHistory:some View { List(store.snapshot?.registrations ?? []) { r in DisclosureGroup { Facts([("Registration ID",r.id),("Display Name",r.displayName),("Representation",r.representationType),("Asset Class",r.assetClass),("Provider",r.providerID.isEmpty ? "Provider Mapping Required":r.providerID),("Provider Symbol",r.providerSymbol.isEmpty ? "Not assigned":r.providerSymbol),("Registration State",r.registrationStatus),("Lifecycle",r.retired ? "RETIRED · HISTORICAL_ONLY":"ACTIVE")]) } label:{HStack{VStack(alignment:.leading){Text("\(r.asset) · \(r.timeframe)").font(.headline);Text(r.displayName).foregroundStyle(.secondary)};Spacer();Text(r.retired ? "RETIRED":"ACTIVE").foregroundStyle(r.retired ? .orange:.green)}} }.searchable(text:$store.auditFilter,prompt:"Search registration or lifecycle") }
}
