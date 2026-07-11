import OperationsCore
import SwiftUI

struct AuthorityLedgerView: View {
    @EnvironmentObject var store: ConsoleStore
    @State private var search=""
    var events:[AuthorityEventRecord] { (store.snapshot?.authorityEvents ?? []).filter { search.isEmpty || $0.entityID.localizedCaseInsensitiveContains(search) || $0.eventKind.localizedCaseInsensitiveContains(search) } }
    var body: some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Immutable Authority Ledger").font(.title)
            Text("Read-only · declaration is not activation · unresolved and rejected authority remains visible").foregroundStyle(.secondary)
            List(events) { event in
                DisclosureGroup { Facts([("Entity kind",event.entityKind),("Entity ID",event.entityID),("Effective from",event.effectiveFrom),("Effective to",event.effectiveTo ?? "OPEN"),("Compatibility",event.compatibilityState),("Reasons",event.compatibilityReasonsJSON),("Supersedes",event.supersedesEventID ?? "—"),("Payload checksum",event.payloadChecksum),("Event checksum",event.eventChecksum),("Recorded",event.recordedAt),("Actor",event.recordedBy)]) } label: { HStack { VStack(alignment:.leading){Text(event.eventKind).font(.headline);Text(event.entityID).font(.caption).foregroundStyle(.secondary)};Spacer();Text(event.compatibilityState).font(.caption).foregroundStyle(event.compatibilityState=="COMPATIBLE" ? .green:.orange) } }
            }.searchable(text:$search,prompt:"Search entity or event")
            if events.isEmpty { Text("No authority ledger events recorded.").foregroundStyle(.secondary) }
        }.padding()
    }
}
