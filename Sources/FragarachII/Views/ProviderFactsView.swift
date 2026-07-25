import OperationsCore
import SwiftUI

struct ProviderFactsView: View {
    @EnvironmentObject private var store: ConsoleStore
    @State private var showingCredential = false
    @State private var credential = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                if let error = store.providerFactsError {
                    ProviderIssueBox(title: "Provider Facts Error", reason: error) {
                        Button("Retry Now") { Task { await store.refreshProviderFacts(resolve: true) } }
                        Button("Configure Twelve Data") { showingCredential = true }
                    }
                }
                if let facts = store.providerFacts {
                    reconciliation(facts.reconciliation)
                    mappingSection("Resolved Automatically", mappings: facts.resolvedAutomatically, empty: "No automatic mappings have been recorded yet.")
                    reviewSection(facts.needsMaterialReview)
                    credentialSection(facts.credentialOrAccessIssue)
                    failureSection(facts.providerLookupFailed)
                    retiredSection(facts.retiredNonActionable)
                } else if store.providerFactsError == nil {
                    ProgressView("Loading provider facts…")
                }
            }
            .frame(maxWidth: 1050, alignment: .leading)
            .padding(.vertical, 4)
        }
        .sheet(isPresented: $showingCredential) { credentialSheet }
        .task {
            if store.providerCredentialRepairRequested {
                showingCredential=true;store.providerCredentialRepairRequested=false
            }
            if store.providerFacts == nil { await store.refreshProviderFacts() }
        }
        .onChange(of: store.providerCredentialRepairRequested) { _, requested in
            guard requested else { return }
            showingCredential=true;store.providerCredentialRepairRequested=false
        }
    }

    private var header: some View {
        GroupBox {
            HStack(alignment: .center, spacing: 16) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Twelve Data Facts").font(.title2.bold())
                    Text("Representation mappings are resolved once per instrument. Timeframe support is recorded separately.")
                        .foregroundStyle(.secondary)
                    if let revision=store.providerFacts?.revision { Text("Current provider facts revision \(revision)").font(.caption.monospaced()).foregroundStyle(.secondary) }
                }
                Spacer()
                credentialBadge
                Button("Configure…") { showingCredential = true }
                Button("Resolve from Twelve Data") { Task { await store.refreshProviderFacts(resolve: true) } }
                    .buttonStyle(.borderedProminent)
                    .disabled(store.providerFactsResolving)
                if store.providerFactsResolving { ProgressView().controlSize(.small) }
            }
            .padding(.vertical, 4)
        }
    }

    private var credentialBadge: some View {
        let state = store.providerFacts?.credentialState ?? (store.credentialAvailable ? "Configured" : "Missing")
        let color: Color = state == "Configured" ? .green : state == "Invalid" ? .red : .orange
        return Label(state, systemImage: state == "Configured" ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
            .foregroundStyle(color)
            .help("Only the credential state is displayed. The credential is never included in provider facts.")
    }

    @ViewBuilder private func reconciliation(_ value: ProviderFactsReconciliation?) -> some View {
        if let value {
            DisclosureGroup("SPEC-048 Reconciliation") {
                Facts([
                    ("Lane rows originally flagged", "\(value.laneRowsOriginallyFlagged)"),
                    ("Retired rows removed", "\(value.retiredRowsRemoved)"),
                    ("Mappings automatically resolved", "\(value.representationMappingsAutomaticallyResolved)"),
                    ("Timeframe capabilities verified", "\(value.timeframeCapabilitiesVerified)"),
                    ("Credential/access failures", "\(value.credentialAccessFailures)"),
                    ("Provider lookup failures", "\(value.providerLookupFailures)"),
                    ("Operator decisions remaining", "\(value.genuineOperatorDecisionsRemaining)"),
                ])
                if !value.decisionKeys.isEmpty {
                    Text(value.decisionKeys.joined(separator: " · ")).font(.caption.monospaced()).foregroundStyle(.secondary)
                }
            }
        }
    }

    private func mappingSection(_ title: String, mappings: [ProviderFactMapping], empty: String) -> some View {
        GroupBox(title) {
            VStack(alignment: .leading, spacing: 12) {
                if mappings.isEmpty { Text(empty).foregroundStyle(.secondary) }
                ForEach(mappings) { mapping in
                    MappingFactRow(mapping: mapping)
                    if mapping.id != mappings.last?.id { Divider() }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 4)
        }
    }

    private func reviewSection(_ mappings: [ProviderFactMapping]) -> some View {
        GroupBox("Needs Material Review") {
            VStack(alignment: .leading, spacing: 14) {
                if mappings.isEmpty { Text("No unresolved economic representation decisions.").foregroundStyle(.secondary) }
                ForEach(mappings) { mapping in
                    VStack(alignment: .leading, spacing: 10) {
                        Label("\(mapping.canonicalSymbol) · Twelve Data candidates", systemImage: "questionmark.diamond")
                            .font(.headline).foregroundStyle(.orange)
                        Text(mapping.reason ?? "Provider facts do not prove an identical economic representation.").foregroundStyle(.secondary)
                        CanonicalIdentity(mapping: mapping)
                        ScrollView(.horizontal) {
                            HStack(alignment: .top, spacing: 12) {
                                ForEach(mapping.candidates) { candidate in CandidateCard(mapping: mapping, candidate: candidate) }
                            }
                        }
                    }
                    if mapping.id != mappings.last?.id { Divider() }
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 4)
        }
    }

    @ViewBuilder private func credentialSection(_ issue: ProviderFactIssue?) -> some View {
        GroupBox("Credential or Access Issue") {
            if let issue {
                ProviderIssueBox(title: issue.outcome.replacingOccurrences(of: "_", with: " ").capitalized, reason: issue.reason) {
                    Button("Configure Twelve Data") { showingCredential = true }.buttonStyle(.borderedProminent)
                    Button("Retry Lookup") { Task { await store.refreshProviderFacts(resolve: true) } }
                        .disabled(store.providerFactsResolving)
                }
            } else { Label("Credential access is configured.", systemImage: "checkmark.circle.fill").foregroundStyle(.green).padding(.vertical, 4) }
        }
    }

    private func failureSection(_ issues: [ProviderFactIssue]) -> some View {
        GroupBox("Provider Lookup Failed") {
            VStack(alignment: .leading, spacing: 12) {
                if issues.isEmpty { Text("No provider lookup failures.").foregroundStyle(.secondary) }
                ForEach(issues) { issue in
                    ProviderIssueBox(title: issue.canonicalSymbol ?? "Twelve Data lookup", reason: issue.reason) {
                        Button("Retry Now") { Task { await store.refreshProviderFacts(resolve: true, symbol: issue.canonicalSymbol) } }
                            .disabled(store.providerFactsResolving)
                        Button("Configure Twelve Data") { showingCredential = true }
                    }
                    if let tried = issue.whatWasTried, !tried.isEmpty {
                        Text("Tried: \(tried.joined(separator: ", "))").font(.caption.monospaced()).foregroundStyle(.secondary)
                    }
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 4)
        }
    }

    private func retiredSection(_ issues: [ProviderFactIssue]) -> some View {
        GroupBox("Retired / Non-Actionable") {
            VStack(alignment: .leading, spacing: 8) {
                if issues.isEmpty { Text("No retired provider-fact history.").foregroundStyle(.secondary) }
                ForEach(issues) { issue in
                    HStack { Label(issue.canonicalSymbol ?? "Retired representation", systemImage: "archivebox"); Spacer(); Text(issue.reason).foregroundStyle(.secondary) }
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 4)
        }
    }

    private var credentialSheet: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Configure Twelve Data").font(.title2.bold())
            Text("The API key is stored in macOS Keychain. Fragarach validates it with Twelve Data before it releases credential-blocked lanes for retry.").foregroundStyle(.secondary)
            SecureField("Twelve Data API key", text: $credential).textFieldStyle(.roundedBorder)
            HStack { Spacer(); Button("Cancel") { credential = ""; showingCredential = false }; Button("Save, Validate & Repair") {
                let value = credential; credential = ""; showingCredential = false
                Task { await store.configureTwelveDataCredential(value) }
            }.buttonStyle(.borderedProminent).disabled(credential.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) }
        }.padding(24).frame(width: 520)
    }
}

private struct MappingFactRow: View {
    @EnvironmentObject private var store: ConsoleStore
    let mapping: ProviderFactMapping
    private let order = ["M5", "M30", "H1", "D1"]
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack { Text(mapping.canonicalSymbol).font(.headline.monospaced()); Image(systemName: "arrow.left.arrow.right"); Text("Twelve Data \(mapping.providerSymbol ?? "Unknown")").font(.headline); Spacer(); Text(mapping.mappingClass?.replacingOccurrences(of: "_", with: " ").capitalized ?? mapping.status).foregroundStyle(.green) }
            HStack(spacing: 8) {
                ForEach(order, id: \.self) { timeframe in
                    let fact = mapping.timeframeCapabilities[timeframe]
                    Label(timeframe, systemImage: fact?.supported == true ? "checkmark.circle.fill" : "questionmark.circle")
                        .foregroundStyle(fact?.supported == true ? Color.green : Color.secondary)
                        .help(fact.map { "\($0.providerInterval) · \($0.verificationMethod)" } ?? "Not verified")
                }
                Spacer()
                Menu("Run bounded probe") {
                    ForEach(order, id: \.self) { timeframe in Button(timeframe) { Task { await store.probeProviderCapability(symbol: mapping.canonicalSymbol, timeframe: timeframe) } } }
                }.disabled(store.providerFactsResolving)
            }
            DisclosureGroup("Resolution evidence") {
                Facts([
                    ("Canonical identity", [mapping.canonicalBaseAsset, mapping.canonicalQuoteAsset].compactMap { $0 }.joined(separator: "/")),
                    ("Provider description", mapping.providerDescription ?? "Not supplied"),
                    ("Instrument type", mapping.providerInstrumentType ?? "Not supplied"),
                    ("Matching rule", mapping.matchingRule ?? mapping.resolutionMethod),
                    ("Last verified", mapping.lastVerified),
                    ("Response checksums", mapping.resolutionEvidence.responseChecksums.joined(separator: ", ")),
                    ("API credits used", mapping.resolutionEvidence.apiCreditsUsed.map(String.init) ?? "Not reported"),
                    ("Prior approved mapping", mapping.resolutionEvidence.priorApprovedMapping.map { "\($0["source_scope"] ?? "D1") · \($0["provider_symbol"] ?? "Unknown") · \($0["preservation"] ?? "Preserved")" } ?? "None"),
                ])
            }
        }
    }
}

private struct CanonicalIdentity: View {
    let mapping: ProviderFactMapping
    var body: some View { Facts([
        ("Canonical identity", [mapping.canonicalBaseAsset, mapping.canonicalQuoteAsset].compactMap { $0 }.joined(separator: "/")),
        ("Canonical instrument type", mapping.canonicalInstrumentType ?? "Not recorded"),
    ]) }
}

private struct CandidateCard: View {
    @EnvironmentObject private var store: ConsoleStore
    let mapping: ProviderFactMapping
    let candidate: ProviderFactCandidate
    var body: some View {
        GroupBox(candidate.providerSymbol) {
            VStack(alignment: .leading, spacing: 9) {
                Facts([
                    ("Description", candidate.providerDescription),
                    ("Instrument type", candidate.providerInstrumentType),
                    ("Base / quote", [candidate.providerBaseAsset, candidate.providerQuoteAsset].compactMap { $0 }.joined(separator: " / ")),
                    ("Venue / market", candidate.venueOrMarket),
                    ("Intervals", candidate.supportedIntervals.joined(separator: " · ")),
                    ("Sample range", candidate.samplePriceRange.map { "\($0["low"] ?? "?") – \($0["high"] ?? "?")" } ?? "Not probed"),
                    ("Classification", candidate.mappingClassification),
                ])
                Divider()
                HStack {
                    Button("Approve Exact") { decide("APPROVE_EXACT") }
                    Button("Approve Alias") { decide("APPROVE_ALIAS") }
                    Button("Not Equivalent") { decide("MARK_NOT_EQUIVALENT") }
                    Button("Defer") { decide("DEFER") }
                }.disabled(store.providerFactsResolving)
            }.frame(width: 560, alignment: .leading).padding(.vertical, 3)
        }
    }
    private func decide(_ decision: String) { Task { await store.recordProviderMappingDecision(symbol: mapping.canonicalSymbol, decision: decision, candidate: candidate.providerSymbol) } }
}

private struct ProviderIssueBox<Actions: View>: View {
    let title: String
    let reason: String
    @ViewBuilder let actions: Actions
    init(title: String, reason: String, @ViewBuilder actions: () -> Actions) { self.title = title; self.reason = reason; self.actions = actions() }
    var body: some View { VStack(alignment: .leading, spacing: 8) { Label(title, systemImage: "exclamationmark.triangle.fill").font(.headline).foregroundStyle(.orange); Text(reason).textSelection(.enabled); HStack { actions } }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 4) }
}
