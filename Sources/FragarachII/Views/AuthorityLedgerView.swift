import OperationsCore
import SwiftUI

struct AuthorityLedgerView: View {
    @EnvironmentObject var store: ConsoleStore
    var events:[AuthorityEventRecord] { (store.snapshot?.authorityEvents ?? []).filter { store.auditFilter.isEmpty || $0.entityID.localizedCaseInsensitiveContains(store.auditFilter) || $0.eventKind.localizedCaseInsensitiveContains(store.auditFilter) } }
    var body: some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Immutable Authority Ledger").font(.title)
            Text("Read-only · declaration is not activation · unresolved and rejected authority remains visible").foregroundStyle(.secondary)
            List(events) { event in
                DisclosureGroup { Facts([("Entity kind",event.entityKind),("Entity ID",event.entityID),("Effective from",event.effectiveFrom),("Effective to",event.effectiveTo ?? "OPEN"),("Compatibility",event.compatibilityState),("Reasons",event.compatibilityReasonsJSON),("Supersedes",event.supersedesEventID ?? "—"),("Payload checksum",event.payloadChecksum),("Event checksum",event.eventChecksum),("Recorded",event.recordedAt),("Actor",event.recordedBy)]) } label: { HStack { VStack(alignment:.leading){Text(event.eventKind).font(.headline);Text(event.entityID).font(.caption).foregroundStyle(.secondary)};Spacer();Text(event.compatibilityState).font(.caption).foregroundStyle(event.compatibilityState=="COMPATIBLE" ? .green:.orange) } }
            }.searchable(text:$store.auditFilter,prompt:"Search entity, event, receipt, or instrument")
            if events.isEmpty { Text("No authority ledger events recorded.").foregroundStyle(.secondary) }
        }.padding()
    }
}
