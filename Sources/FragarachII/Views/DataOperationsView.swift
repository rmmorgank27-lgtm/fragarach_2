import CryptoKit
import AppKit
import Foundation
import OperationsCore
import SwiftUI

private enum FetchIntent: String, CaseIterable, Hashable { case initial = "Fetch Initial History", update = "Update", force = "Force Refresh History", custom = "Custom Range" }
private struct CompletedUnifiedAcquisition:Equatable { let revision:UUID;let instrument:String;let timeframe:String }
private struct OperatorLanePresentation { let state:String;let publication:String;let provider:String;let edge:String;let detail:String;let evidence:String;let automation:String;let action:String;let selectable:Bool;let retryable:Bool }

struct DataOperationsView: View {
    @EnvironmentObject private var store: ConsoleStore
    @State private var search = ""
    @State private var showRetired = false
    @State private var selection = DataOperationsSelection()
    @State private var intent: FetchIntent = .initial
    @State private var fromDate = Calendar.current.date(byAdding:.year,value:-1,to:Date())!
    @State private var throughDate = Calendar.current.date(byAdding:.day,value:-1,to:Date())!
    @State private var conflict = ConflictMode.preserve
    @State private var file: URL?
    @State private var reviewing = false
    @State private var retirementImpact: RetirementImpact?
    @State private var retirementReceipt: RetirementReceipt?
    @State private var localError: String?
    @State private var dateInterpretation:String?
    @State private var reviewedPlan:ReviewedDataOperationPlan?
    @State private var completedPlan:ReviewedDataOperationPlan?
    @State private var completedAcquisition:CompletedUnifiedAcquisition?
    @State private var fileSelectionID=UUID()
    @State private var showRejectedRows=false
    @State private var selectedTimeframe="D1"
    @State private var sourceTimezone=""
    @State private var d1DateFormat="auto"
    @State private var manualMissingStart:String?
    @State private var manualMissingEnd:String?

    private var allRegistrations: [InstrumentRegistrationRecord] { store.snapshot?.registrations ?? [] }
    private var registrations: [InstrumentRegistrationRecord] {
        allRegistrations.filter { r in
            (showRetired || !r.retired) && (search.isEmpty || r.asset.localizedCaseInsensitiveContains(search) || r.displayName.localizedCaseInsensitiveContains(search) || r.assetClass.localizedCaseInsensitiveContains(search) || r.providerID.localizedCaseInsensitiveContains(search))
        }
    }
    private var selectedRegistrationID: Binding<String?> { Binding(get:{selection.selectedRegistrationID},set:{selection.select($0)}) }
    private var registration: InstrumentRegistrationRecord? { registrations.first { $0.id == selection.selectedRegistrationID } }
    private var selectedRegistrations: [InstrumentRegistrationRecord] { guard let asset=registration?.asset else{return []};return allRegistrations.filter { $0.asset == asset } }
    private var lane: LaneRecord? { store.snapshot?.lanes.first { $0.asset == registration?.asset && $0.timeframe == selectedTimeframe } }
    private var truth: EstateTruthLane? { store.estateTruth?.truthMatrix.first { $0.symbol == registration?.asset && $0.timeframe == selectedTimeframe } }
    private var capability:SymbolTimeframeCapability?{store.estateTruth?.timeframeCapabilities?.first{$0.symbol==registration?.asset}}
    private var selectedCapability:TimeframeCapability?{capability?.timeframes.first{$0.timeframe==selectedTimeframe}}
    private var commissioningState:CommissionedLaneState?{store.estateTruth?.commissioningMatrix.first{$0.symbol==registration?.asset && $0.timeframe==selectedTimeframe}}
    private var isCommissioned:Bool{commissioningState?.commissioned == true}
    private func isCommissioned(_ timeframe:String)->Bool{store.estateTruth?.commissioningMatrix.first{$0.symbol==registration?.asset && $0.timeframe==timeframe}?.commissioned == true}
    private var schedulerLane:SchedulerLane?{store.schedulerSnapshot?.lanes.first{$0.symbol==registration?.asset && $0.timeframe==selectedTimeframe}}
    private var mappingDiscoveryPending:Bool { selectedCapability?.reasonCodes.contains("MAPPING_DISCOVERY_PENDING") == true }
    private var providerCapabilities:[AcquisitionCapabilityRow]{
        // A registration can have a stale scheduler plan from before the
        // mapping-discovery state was projected.  The Estate capability is the
        // representation authority in that state, so never hide its exact
        // mapping candidates behind an older route plan.
        if mappingDiscoveryPending { return selectedCapability?.providerCapabilities ?? [] }
        if let rows=schedulerLane?.providerCapabilities,!rows.isEmpty{return rows}
        return selectedCapability?.providerCapabilities ?? []
    }
    private var unifiedProviderCandidates:[UnifiedAcquisitionProvider] {
        if mappingDiscoveryPending {
            return (selectedCapability?.providerCapabilities ?? []).map {
                UnifiedAcquisitionProvider(provider:$0.provider,providerSymbol:$0.providerSymbol,mappingStatus:$0.mappingStatus,eligible:$0.eligibility=="ELIGIBLE",priority:$0.priority,rejectionReason:$0.rejectionReason)
            }
        }
        if let planned=schedulerLane?.acquisitionPlan?.providersConsidered,!planned.isEmpty {
            let approvedCrypto=planned.filter {
                $0.providerSymbol != nil && [
                    "EXACT_REPRESENTATION",
                    "APPROVED_PROVIDER_ALIAS",
                    "APPROVED_EQUIVALENT_REPRESENTATION",
                ].contains($0.mappingClass ?? $0.mappingStatus ?? "")
            }
            let candidates=registration?.assetClass == "CRYPTO" && !approvedCrypto.isEmpty ? approvedCrypto:planned
            return candidates.map {
                UnifiedAcquisitionProvider(
                    provider:$0.provider,providerSymbol:$0.providerSymbol,
                    mappingStatus:$0.mappingStatus ?? "MAPPING_REQUIRED",eligible:$0.eligible,
                    priority:$0.fallbackRank ?? 999,rejectionReason:$0.reason
                )
            }
        }
        return providerCapabilities.map {
            UnifiedAcquisitionProvider(provider:$0.provider,providerSymbol:$0.providerSymbol,mappingStatus:$0.mappingStatus,eligible:$0.eligibility=="ELIGIBLE",priority:$0.priority,rejectionReason:$0.rejectionReason)
        }
    }
    private var selectableTimeframes:[String]{capability?.timeframes.filter{$0.initialFetchEligible && $0.authorityState != "BLOCKED"}.map(\.timeframe) ?? ["D1"]}
    private var requiredSetTimeframes:[String]{let required=capability?.timeframes.filter{$0.policyState=="REQUIRED"}.map(\.timeframe) ?? [];return required.isEmpty ? (capability?.authorisedTimeframes ?? ["D1"]):required}
    private var automaticAdmission:EstateAdmissionProgress? { guard let progress=store.estateAdmissionProgress,progress.symbol==registration?.asset else{return nil};return progress }
    private var automaticAdmissionOwnsSelectedLane:Bool { automaticAdmission?.timeframes.contains(selectedTimeframe) == true }
    private var schedulerLaneIsActive:Bool { store.schedulerAcquisitionIsActive(symbol:registration?.asset,timeframe:selectedTimeframe) }
    private var requiredSetIsRunning:Bool{if automaticAdmission != nil{return true};guard let operation=store.activeDataOperation else{return false};return operation.instrument==registration?.asset && operation.timeframe=="Required Set" && store.dataOperationState.isActive}
    private var activeRequiredSetJob:SchedulerRequiredSetJob?{let job=store.schedulerSnapshot?.requiredSetActiveJob;return job?.symbol==registration?.asset ? job:nil}
    private var requiredSetHasExecutableLane:Bool{requiredSetTimeframes.contains{requiredSetLaneStatus($0).state=="Executable"}}
    private var commissionedLaneSummary:String { let lanes=requiredSetTimeframes.filter{isCommissioned($0) || schedulerLane(for:$0) != nil};return lanes.isEmpty ? "None":lanes.joined(separator:", ") }
    private var canMutate: Bool { registration?.retired == false && store.activeOperationID == nil && !schedulerLaneIsActive }
    private var operationMatchesLane:Bool{guard let operation=store.activeDataOperation else{return false};return operation.instrument==registration?.asset && (operation.timeframe==selectedTimeframe || operation.timeframe=="Required Set")}
    private var checksum: String { guard let file, let data=try? Data(contentsOf:file) else{return "—"};return SHA256.hash(data:data).map{String(format:"%02x",$0)}.joined() }
    private var acquisitionIntent:AcquisitionIntent { switch intent { case .initial:return .initial;case .update:return .update;case .force:return .force;case .custom:return .custom } }
    private var publicationPending:Bool { normalizedPublication(schedulerLane?.publicationState) == "PUBLISHING" }
    private var publicationJobID:String? { schedulerLane?.publicationJobID }
    private var planEvidenceAvailability:String {
        if publicationPending { return unifiedAcquisitionPlan?.canonicalEdge == nil ? "Publication pending · no canonical evidence yet":"Committed evidence · publication pending (not consumer-visible)" }
        return unifiedAcquisitionPlan?.canonicalEdge == nil ? "No canonical evidence":"Available"
    }
    private var planAutomationEligibility:String {
        guard let plan=unifiedAcquisitionPlan else{return "Unavailable"}
        if publicationPending { return "Publishing (non-blocking)" }
        if mappingDiscoveryPending { return "Waiting for Mapping Discovery" }
        if plan.providerSetupRequired { return "Provider setup required" }
        return plan.isExecutable ? "Eligible":"Unavailable"
    }
    private var requiredPlanAction:String {
        guard let plan=unifiedAcquisitionPlan else{return "Unavailable"}
        if mappingDiscoveryPending { return "Wait for Provider Mapping Discovery" }
        if plan.providerSetupRequired { return "Complete Provider Setup" }
        if plan.canonicalEdge == nil,plan.isExecutable {
            return "Fetch Initial History via \(plan.selectedProvider?.provider ?? "approved provider")"
        }
        return "None"
    }
    private var unifiedAcquisitionPlan:UnifiedAcquisitionPlan? {
        guard store.dataOperationsMode == .fetch else{return nil}
        let providers=unifiedProviderCandidates
        return .build(instrument:registration?.asset,timeframe:selectedTimeframe,assetClass:registration?.assetClass,intent:acquisitionIntent,canonicalEdge:schedulerLane?.latestCanonicalObservation ?? truth?.truthState.caodt,expectedEdge:schedulerLane?.expectedLatest,providers:providers,reviewedRange:intent == .update ? nil:dateRange,registrationActive:registration?.retired == false,operationActive:store.activeOperationID != nil || store.dataOperationState.isActive,acquisitionPaused:schedulerLaneIsActive,expectedEdgeStatus:schedulerLane?.expectedEdgeStatus,publicationPending:publicationPending)
    }

    var body: some View {
        HStack(spacing:0) {
            VStack(alignment:.leading,spacing:10) {
                TextField("Search active instruments",text:$search).textFieldStyle(.roundedBorder)
                Toggle("Show Retired",isOn:$showRetired)
                List(registrations,selection:selectedRegistrationID) { r in
                    VStack(alignment:.leading,spacing:3) {
                        Text(r.displayName).fontWeight(.semibold)
                        Text("\(r.asset) · \(r.assetClass)").font(.caption).foregroundStyle(.secondary)
                        Text(r.retired ? "RETIRED" : "\(r.providerID) · \(r.timeframe)").font(.caption2).foregroundStyle(r.retired ? .orange:.secondary)
                    }.tag(r.id)
                }
            }.frame(width:280).padding()
            Divider()
            Group { if store.dataOperationsMode == .history { OperationsView(filterAsset:registration?.asset) } else { ScrollView { VStack(alignment:.leading,spacing:16) {
                WorkspaceHeader(title:"Acquire & Import",purpose:"Add, update, import, retire, and review evidence.")
                Picker("Mode",selection:$store.dataOperationsMode){ForEach(DataOperationsMode.allCases){Text($0.rawValue).tag($0)}}.pickerStyle(.segmented)
                if let r=registration {
                    header(r)
                    if r.retired { retireView(r) }
                    else {
                        switch store.dataOperationsMode { case .fetch: fetchView(r);case .importFile: importView(r);case .retire: retireView(r);case .history:EmptyView() }
                    }
                } else if registrations.isEmpty { ContentUnavailableView("No matching active instruments",systemImage:"magnifyingglass",description:Text("Clear the search or enable Show Retired.")) }
                else { ContentUnavailableView("Select a registered instrument",systemImage:"arrow.left",description:Text("Choose one registration from the populated authority list.")) }
                if let localError, !store.dataOperationState.isActive { Label(localError,systemImage:"exclamationmark.triangle").foregroundStyle(.red) }
                operationActivity
                readableResult
            }.padding().frame(maxWidth:900,alignment:.leading) } } }
        }
        .onAppear { store.clearCurrentOperationResult();applyNavigationContext() }
        .onChange(of:store.snapshot){reconcileSelection()}
        .onChange(of:search){reconcileSelection()}
        .onChange(of:showRetired){reconcileSelection()}
        .onChange(of:selection.selectedRegistrationID){resetInstrumentContext()}
        .onChange(of:selectedTimeframe){resetInstrumentContext()}
        .onChange(of:store.dataOperationsMode){isolateOperationState()}
        .onChange(of:fromDate){store.clearCurrentOperationResult()}
        .onChange(of:throughDate){store.clearCurrentOperationResult()}
        .onChange(of:intent){store.clearCurrentOperationResult()}
        .onChange(of:conflict){store.clearCurrentOperationResult()}
        .onChange(of:file){fileSelectionID=UUID();isolateOperationState()}
        .sheet(isPresented:$reviewing){reviewSheet}
        .sheet(item:$retirementImpact){impact in RetirementOperationReview(impact:impact,onConfirm:confirmRetirement)}
        .sheet(item:$retirementReceipt){receipt in RetirementOperationSuccess(receipt:receipt){retirementReceipt=nil}}
    }

    private func header(_ r:InstrumentRegistrationRecord)->some View { GroupBox { HStack(alignment:.top) { VStack(alignment:.leading,spacing:5) { Text("\(r.displayName) — \(r.asset)").font(.title2.bold());Text("\(r.assetClass) · \(r.representationType)");Text(r.retired ? "Retired":"Active").foregroundStyle(r.retired ? .orange:.green);Facts([("Registered anchor",selectedRegistrations.map(\.timeframe).joined(separator:", ")),("Commissioned lanes",commissionedLaneSummary),("Evidence",(lane?.barCount ?? 0)>0 ? "Present":"None"),("Truth Score",truth.map{String($0.truthState.truthScore)} ?? "Unknown"),("CAODT",truth?.truthState.caodt ?? "—")]) };Spacer();if !r.retired{Button("Retire Instrument",role:.destructive){store.dataOperationsMode = .retire}} } } }

    private func fetchView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:14) {
        GroupBox("Automation") { VStack(alignment:.leading,spacing:6) { Facts([("Status",EstateLanePresentation.commissioning(isCommissioned))]);if !isCommissioned{Text("Manual acquisition available.").foregroundStyle(.secondary)} }.frame(maxWidth:.infinity,alignment:.leading) }
        laneMatrix(r)
        requiredSetView(r)
        blockerGuidance(r)
        Picker("Timeframe",selection:$selectedTimeframe){ForEach(capability?.timeframes.filter{$0.initialFetchEligible && $0.authorityState != "BLOCKED"} ?? [],id:\.timeframe){item in Text(item.timeframe).tag(item.timeframe)}}.pickerStyle(.segmented)
        GroupBox("Unified Acquisition Plan") { VStack(alignment:.leading,spacing:10) {
            if let plan=unifiedAcquisitionPlan {
                Facts([("Selected symbol",plan.instrument),("Selected timeframe",plan.timeframe),("Canonical edge",plan.canonicalEdge ?? "—"),("Expected edge",plan.expectedEdge ?? plan.expectedEdgeStatus?.displayStatus ?? "Reason unavailable"),("Evidence availability",planEvidenceAvailability),("Automation eligibility",planAutomationEligibility),("Publication job",publicationJobID ?? (publicationPending ? "Publishing — job details unavailable":"None")),("Required operator action",requiredPlanAction),("Historical depth",plan.historicalDepth ?? "Not applicable"),("Missing range",plan.missingStart.map{"\($0) → \(plan.missingEnd ?? plan.expectedEdgeStatus?.displayStatus ?? "Reason unavailable")"} ?? plan.noUpdateReason ?? "Not available"),("Provider",plan.selectedProvider?.provider ?? "None"),("Intent",plan.acquisitionIntent.rawValue),("Request bounds",plan.requestStart.map{"\($0) → \(plan.requestEnd ?? "—")"} ?? plan.noUpdateReason ?? "Not available"),("Controlled overlap",plan.overlapDescription ?? "Not applicable")])
                ForEach(plan.providers){provider in HStack(alignment:.firstTextBaseline){Text(provider.provider).fontWeight(.semibold).frame(width:130,alignment:.leading);Text(provider.providerSymbol ?? "No approved symbol").monospaced().frame(width:110,alignment:.leading);Text(provider.eligible ? "Eligible · \(provider.mappingStatus.displayStatus)":(provider.rejectionReason ?? "INELIGIBLE").displayStatus).foregroundStyle(provider.eligible ? .green:.secondary);Spacer()}.font(.caption)}
                if plan.providerSetupRequired && !mappingDiscoveryPending { Button("Complete Provider Setup") { store.openProviderSetup(for:r.asset) }.buttonStyle(.borderedProminent).tint(.orange) }
            }
        }.frame(maxWidth:.infinity,alignment:.leading) }
        Picker("Intent",selection:$intent){ForEach(FetchIntent.allCases,id:\.self){Text($0.rawValue).tag($0)}}.pickerStyle(.segmented)
        if mappingDiscoveryPending || providerCapabilities.allSatisfy({$0.mappingStatus=="MAPPING_REQUIRED"}) { unmappedFetchView(r) }
        if intent == .initial { Label("Fetch Initial History uses the governed historical-depth authority. Manual dates apply only to Custom Range.",systemImage:"clock.arrow.circlepath").foregroundStyle(.secondary) }
        else if intent == .force { Label("Force Refresh re-requests the governed historical horizon to repair short or incomplete history. Existing evidence is preserved; it does not overwrite bars.",systemImage:"arrow.clockwise.circle").foregroundStyle(.secondary) }
        else if intent == .custom { customRangeControls;Label("The selected historical range is explicit and reviewed before dispatch.",systemImage:"clock.arrow.circlepath").foregroundStyle(.secondary) }
        else if let overlap=unifiedAcquisitionPlan?.overlapDescription { Label("Includes the approved \(overlap) reconciliation overlap. Preserve remains authoritative.",systemImage:"arrow.triangle.2.circlepath").foregroundStyle(.secondary) }
        LabeledContent("Conflict policy",value:"Preserve")
        Text("The unified plan preserves prior evidence and records conflicting candidates without silent overwrite.").font(.caption).foregroundStyle(.secondary)
        Button(mappingDiscoveryPending ? "Awaiting Provider Mapping" : automaticAdmissionOwnsSelectedLane ? "Initial History Running…" : operationMatchesLane && store.dataOperationState.isActive ? (store.activeDataOperation?.actionLabel ?? "Updating…") : unifiedAcquisitionPlan?.isAwaitingExpectedEdge == true ? "Awaiting Schedule State" : intent == .force ? "Force Refresh History" : unifiedAcquisitionPlan?.noUpdateReason == nil ? "Fetch Now":"No Update Required"){if let plan=unifiedAcquisitionPlan{runUnifiedAcquisition(plan)}}.buttonStyle(.borderedProminent).disabled(mappingDiscoveryPending || automaticAdmissionOwnsSelectedLane || unifiedAcquisitionPlan?.isExecutable != true)
        if let reason=unifiedAcquisitionPlan?.noUpdateReason { Label(reason,systemImage:"checkmark.circle").foregroundStyle(.secondary) }
        if let plan=unifiedAcquisitionPlan,let failure=plan.failure,!store.dataOperationState.isActive,!mappingDiscoveryPending {
            Label(failure,systemImage:plan.isAwaitingExpectedEdge ? "clock.badge.exclamationmark":"exclamationmark.triangle")
                .foregroundStyle(plan.isAwaitingExpectedEdge ? Color.secondary:(plan.providerSetupRequired ? Color.orange:Color.red))
        }
    } }

    private func unmappedFetchView(_ r:InstrumentRegistrationRecord)->some View { GroupBox(mappingDiscoveryPending ? "Provider Mapping Discovery":"Provider Setup") { VStack(alignment:.leading,spacing:10) { Label(unifiedAcquisitionPlan?.canonicalEdge == nil ? "No canonical evidence is published yet":"Canonical evidence remains available",systemImage:unifiedAcquisitionPlan?.canonicalEdge == nil ? "clock.badge.exclamationmark":"checkmark.circle.fill").foregroundStyle(unifiedAcquisitionPlan?.canonicalEdge == nil ? Color.secondary:Color.green);Text(mappingDiscoveryPending ? "No exact provider representation has been verified for this FX symbol yet. Discovery will not fetch data until it has one." : "Automation is paused until an operator reviews an exact provider representation. Import CSV remains available.").foregroundStyle(.secondary);HStack{Button(mappingDiscoveryPending ? "View Mapping Discovery":"Complete Provider Setup"){store.openProviderSetup(for:r.asset)}.buttonStyle(.borderedProminent).tint(.orange);Button("Import CSV"){store.dataOperationsMode = .importFile}} } } }

    @ViewBuilder private func blockerGuidance(_ r:InstrumentRegistrationRecord)->some View {
        // The live Scheduler lane is authoritative.  Capability projections are
        // deliberately cached and may describe the pre-admission state while a
        // newly admitted lane is already commissioned or publishing.
        let code=(schedulerLane?.publicationState=="FAILED_RETRYABLE" ? "PUBLICATION_FAILED":schedulerLane?.reason ?? (!isCommissioned ? "NOT_COMMISSIONED":selectedCapability?.reasonCodes.first ?? selectedCapability?.initialFetchBlockers.first))
        if let code,let guidance=guidedBlocker(code) {
            GroupBox("Next Action") { VStack(alignment:.leading,spacing:8) {
                Label(guidance.reason,systemImage:"arrow.right.circle").foregroundStyle(.orange)
                HStack {
                    if guidance.action=="MAPPING" { Button("Resolve Mapping"){store.openProviderSetup(for:r.asset)}.buttonStyle(.borderedProminent) }
                    if guidance.action=="FETCH" { Button("Fetch Required Set"){runRequiredSet(r)}.buttonStyle(.borderedProminent) }
                    if guidance.action=="RESUME" { Button("Resume Required Set"){resumeRequiredSet(r)}.buttonStyle(.borderedProminent) }
                }
                DisclosureGroup("Technical details") { Text(code).font(.caption.monospaced()) }
            }.frame(maxWidth:.infinity,alignment:.leading) }
        }
    }

    private func guidedBlocker(_ code:String)->(reason:String,action:String)? {
        switch code {
        case "MAPPING_DISCOVERY_PENDING": return ("Provider mapping discovery is pending. No acquisition will run until an exact representation is verified.","MAPPING")
        case "NO_APPROVED_MAPPING","PROVIDER_SYMBOL_MAPPING_REQUIRED": return ("No approved provider mapping exists for this lane.","MAPPING")
        case "NOT_COMMISSIONED","EVIDENCE_LANE_NOT_COMMISSIONED": return ("Estate admission is reconciling this lane for automatic initial acquisition. Fetch Required Set remains available as a manual override.","FETCH")
        case "PARTIAL_EVIDENCE": return ("Canonical evidence is partial. Resume from the canonical edge.","RESUME")
        case "PUBLICATION_FAILED","FAILED_RETRYABLE": return ("Canonical evidence is committed, but publication failed. Resume retries publication only.","RESUME")
        case "PROVIDER_CREDITS_WAIT","RATE_BUDGET_EXHAUSTED": return ("Provider credits are temporarily unavailable. The Scheduler shows the next eligible dispatch time.","NONE")
        case "EXPECTED_EDGE_MISSING","EXPECTED_CANONICAL_EDGE_UNAVAILABLE": return ("The approved expected-edge authority is unavailable for this lane.","NONE")
        case "TIMESTAMP_TIMEZONE_BLOCK": return ("A reviewed source timezone is required before intraday evidence can be admitted.","NONE")
        default: return nil
        }
    }

    private var customRangeControls:some View { VStack(alignment:.leading,spacing:10) { HStack { DatePicker("Inclusive From Date",selection:$fromDate,displayedComponents:.date);Button("Paste From Date"){pasteDate(toFrom:true)};DatePicker("Inclusive Through Date",selection:$throughDate,in:...latestCompletedBoundary,displayedComponents:.date);Button("Paste Through Date"){pasteDate(toFrom:false)} };if let dateInterpretation{Label(dateInterpretation,systemImage:"calendar.badge.checkmark").foregroundStyle(.orange)};Text("Latest completed \(selectedTimeframe) date boundary: \(ControlledDateRange.iso(latestCompletedBoundary))").font(.caption).foregroundStyle(.secondary);HStack{Text("Canonical plan: \(dateRange.fromISO) → \(dateRange.throughISO)").font(.caption.monospaced()).foregroundStyle(.secondary);Spacer();Menu("Presets"){Button("Last 7 Days"){applyPreset(days:7)};Button("Last 30 Days"){applyPreset(days:30)};Button("Year to Date"){let c=Calendar.current;fromDate=c.date(from:c.dateComponents([.year],from:latestCompletedBoundary))!;throughDate=latestCompletedBoundary};Button("Last 12 Months"){fromDate=Calendar.current.date(byAdding:.year,value:-1,to:latestCompletedBoundary)!;throughDate=latestCompletedBoundary};if let latest=lane?.latestBar{Button("Since Latest Stored"){fromDate=Date(timeIntervalSince1970:TimeInterval(latest));throughDate=latestCompletedBoundary}}}} } }

    private func unavailableCapability(title:String,reason:String)->some View { GroupBox("Capability unavailable; safe fallback active") { VStack(alignment:.leading,spacing:10) { Label(title,systemImage:"exclamationmark.triangle").foregroundStyle(.orange);Text(reason).foregroundStyle(.secondary);Facts([("Affected scope","\(registration?.asset ?? "Instrument"):D1 — selected convenience operation"),("What remains safe","Bounded D1 fetch, Import File, and Retire")]);HStack{Button("Choose Custom Range"){intent = .custom};Button("Import File"){store.dataOperationsMode = .importFile}.buttonStyle(.borderedProminent)};DisclosureGroup("Technical reason"){Text("The current implementation cannot prove a provider terminal boundary or calculate an approved automatic overlap. Ratified timeframe authority remains present; this is an implementation incompatibility.").font(.caption)} } } }

    private func importView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:14) {
        if let manualMissingStart,let manualMissingEnd { GroupBox("Manual Acquisition Request") { Facts([("Instrument",r.asset),("Timeframe",selectedTimeframe),("Required range","\(manualMissingStart) → \(manualMissingEnd)"),("Resolution","Only successful canonical publication resolves this request")]) } }
        GroupBox("Scheduled Acquisition Hold") { VStack(alignment:.leading,spacing:8) {
            Toggle("Pause scheduled acquisition while importing (normally unnecessary)",isOn:$store.pauseScheduledAcquisitionWhileImporting)
            Text("Manual evidence is admitted in a short SQLite transaction and normally runs alongside the Scheduler. Use a hold only when you need to investigate this lane without concurrent scheduled updates.").font(.caption).foregroundStyle(.secondary)
            if store.pauseScheduledAcquisitionWhileImporting { Picker("Scope",selection:$store.manualIngestionPauseScope){Text("Selected Symbol").tag("SYMBOL");Text("Selected Group").tag("MARKET_OR_GROUP");Text("All Acquisition").tag("ALL")}.pickerStyle(.segmented);Toggle("Resume after import",isOn:$store.resumeAfterManualImport) }
            if let message=store.manualIngestionHoldMessage { Label(message,systemImage:message.hasPrefix("Waiting") ? "clock":"checkmark.shield").foregroundStyle(message.hasPrefix("Waiting") ? .orange:.green) }
        }.frame(maxWidth:.infinity,alignment:.leading) }
        laneMatrix(r);Picker("Timeframe",selection:$selectedTimeframe){ForEach(capability?.timeframes.filter{$0.policyState=="REQUIRED" && $0.authorityState != "BLOCKED"} ?? [],id:\.timeframe){item in Text(item.timeframe).tag(item.timeframe)}}.pickerStyle(.segmented);Button("Choose CSV…"){file=PanelService.chooseCSV()}
        if let file { GroupBox("Import Preview") { Facts([("File Name",file.lastPathComponent),("Byte Size","\((try? file.resourceValues(forKeys:[.fileSizeKey]).fileSize) ?? 0)"),("Checksum",checksum),("Detected Format","CSV"),("Selected Instrument",r.asset),("Selected Timeframe",selectedTimeframe),("Detected Row Count",rowCount(file)),("Timestamp Range","Validated by existing ingestion authority")]) } }
        if selectedTimeframe == "D1" { Picker("Daily date format",selection:$d1DateFormat){Text("Automatic from file").tag("auto");Text("Day / Month / Year (23/07/2026)").tag("day-first");Text("Month / Day / Year (07/23/2026)").tag("month-first")};Text("Daily dates are calendar dates at UTC midnight; no source timezone is used. Automatic uses an unambiguous date elsewhere in the file, otherwise choose the file's order. Any still-open daily candle is retained as raw evidence and excluded from canonical history; closed rows are admitted and the lane is revalidated immediately.").font(.caption).foregroundStyle(.secondary) }
        if selectedTimeframe != "D1" { TextField("Reviewed source timezone (only for timestamps without an offset)",text:$sourceTimezone);Text("Leave blank when every timestamp declares an explicit offset. Naive timestamps require a reviewed IANA timezone; the app never infers one.").font(.caption).foregroundStyle(.secondary) }
        Picker("Conflict policy",selection:$conflict){ForEach(ConflictMode.allCases,id:\.self){Text($0.rawValue.capitalized).tag($0)}}
        Button(operationMatchesLane && store.dataOperationState.isActive ? "Importing…" : "Review Import"){prepareReview(r)}.buttonStyle(.borderedProminent).disabled(!canMutate || file==nil)
    } }

    private func retireView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:12) { if r.retired { Label("Retired authority is audit-only. Provider acquisition and import are disabled.",systemImage:"archivebox").foregroundStyle(.orange);Facts([("Lifecycle","RETIRED"),("Serving","HISTORICAL_ONLY · NOT_SERVED"),("Acquisition","ACQUISITION_DISABLED"),("Evidence","Preserved for audit")]) } else { Text("Uses the reviewed SPEC-013 impact, supersession, quarantine, acquisition shutdown, and receipt service.");Button("Review Retirement Impact",role:.destructive){planRetirement(r)}.disabled(store.activeOperationID != nil) } } }

    private func laneMatrix(_ r:InstrumentRegistrationRecord)->some View { GroupBox("Timeframe Lane Matrix") { Grid(alignment:.leading,horizontalSpacing:14,verticalSpacing:8) { GridRow{ForEach(["Timeframe","Status","Publication","Evidence availability","Automation eligibility","Required operator action","Selectable"],id:\.self){Text($0).font(.caption.bold())}};Divider().gridCellColumns(7);ForEach(capability?.timeframes ?? []){item in let state=operatorLanePresentation(item,r:r);let importing=(store.dataOperationState.isActive && store.activeDataOperation?.instrument==r.asset && store.activeDataOperation?.timeframe==item.timeframe) || automaticAdmission?.activeTimeframe==item.timeframe;GridRow{HStack(spacing:6){if importing{ProgressView().controlSize(.small)};Text(item.timeframe).monospaced()};Text(state.state);Text(publicationLabel(state.publication));Text(state.evidence);Text(state.automation);Text(state.action);Text(state.selectable ? "Yes":"No")}} }.frame(maxWidth:.infinity,alignment:.leading) } }

    private func requiredSetView(_ r:InstrumentRegistrationRecord)->some View {
        GroupBox("Required Timeframe Set") {
            VStack(alignment:.leading,spacing:10) {
                Grid(alignment:.leading,horizontalSpacing:14,verticalSpacing:8) {
                    GridRow {
                        ForEach(["Lane","Status","Publication","Provider","Canonical edge","Detail"],id:\.self) { Text($0).font(.caption.bold()) }
                    }
                    Divider().gridCellColumns(6)
                    ForEach(requiredSetTimeframes,id:\.self) { timeframe in
                        let status=requiredSetLaneStatus(timeframe)
                        GridRow {
                            HStack(spacing:6) {
                                if requiredSetIsRunning,store.schedulerSnapshot?.activeActivity?.timeframe==timeframe { ProgressView().controlSize(.small) }
                                Text(timeframe).monospaced()
                            }
                            Text(status.state).foregroundStyle(status.state=="Blocked" ? Color.orange:status.state=="Current" ? Color.green:Color.primary)
                            Text(publicationLabel(status.publication))
                            Text(status.provider)
                            Text(status.edge)
                            Text(status.detail).foregroundStyle(.secondary)
                        }.font(.caption)
                    }
                }
                HStack {
                    Button(requiredSetIsRunning ? "Fetching Required Set…" : "Fetch Required Set") { runRequiredSet(r) }
                        .buttonStyle(.borderedProminent)
                        .disabled(!canMutate || !requiredSetHasExecutableLane)
                    if requiredSetNeedsResume {
                        Button("Resume Required Set") { resumeRequiredSet(r) }
                            .disabled(!canMutate || requiredSetIsRunning)
                    }
                    if let active=store.schedulerSnapshot?.activeActivity,requiredSetIsRunning {
                        Text("Current lane: \(active.timeframe) · \(active.stage)").font(.caption).foregroundStyle(.secondary)
                    } else if let progress=automaticAdmission {
                        Text(progress.stage).font(.caption).foregroundStyle(.secondary)
                    }
                }
                if let job=activeRequiredSetJob {
                    Facts([("Current lane",job.currentLane ?? "—"),("Completed lanes",job.completedLanes.isEmpty ? "None":job.completedLanes.joined(separator:", ")),("Remaining lanes",job.remainingLanes.isEmpty ? "None":job.remainingLanes.joined(separator:", ")),("Partial failures",job.partialFailures.isEmpty ? "None":job.partialFailures.map{"\($0.timeframe): \($0.outcome.displayStatus)"}.joined(separator:" · ")),("Provider used",job.providerUsed.isEmpty ? "None":job.providerUsed.joined(separator:", ")),("Last published edge",job.lastPublishedEdge.isEmpty ? "—":job.lastPublishedEdge.map{"\($0.key): \($0.value)"}.sorted().joined(separator:" · "))])
                    if !job.progressTimeline.isEmpty { DisclosureGroup("Progress timeline") { ForEach(job.progressTimeline.suffix(8)) { event in Text("\(event.at) · \(event.stage.displayStatus) · running \(event.currentLanes.isEmpty ? "—" : event.currentLanes.joined(separator:", ")) · completed \(event.completedLanes.count) · publication \(event.publicationState?.displayStatus ?? "Pending")").font(.caption.monospaced()) } } }
                }
            }.frame(maxWidth:.infinity,alignment:.leading)
        }
    }

    private func requiredSetLaneStatus(_ timeframe:String)->OperatorLanePresentation {
        guard let item=capability?.timeframes.first(where:{$0.timeframe==timeframe}),let r=registration else{return .init(state:"Blocked",publication:"PUBLISHED",provider:"None",edge:"—",detail:"Lane authority unavailable",evidence:"Unavailable",automation:"Unavailable",action:"None",selectable:false,retryable:false)}
        return operatorLanePresentation(item,r:r)
    }

    private var requiredSetNeedsResume:Bool {
        requiredSetTimeframes.contains { timeframe in
            let state=requiredSetLaneStatus(timeframe)
            return state.retryable || state.state=="Blocked"
        }
    }
    private func publicationLabel(_ value:String?)->String {
        switch value { case "PUBLISHING": "Publishing"; case "FAILED_RETRYABLE": "Publication Failed"; case "PUBLISHED": "Published"; case "NOT_PUBLISHED",nil: "Not Published"; default: "Pending Publication" }
    }

    private func schedulerLane(for timeframe:String)->SchedulerLane? {
        store.schedulerSnapshot?.lanes.first{$0.symbol==registration?.asset && $0.timeframe==timeframe}
    }

    private func operatorLanePresentation(_ item:TimeframeCapability,r:InstrumentRegistrationRecord)->OperatorLanePresentation {
        let scheduler=schedulerLane(for:item.timeframe)
        let providers=scheduler?.providerCapabilities ?? item.providerCapabilities ?? []
        let provider=providers.first{$0.eligibility=="ELIGIBLE"}?.provider ?? item.provider ?? "None"
        let edge=scheduler?.latestCanonicalObservation ?? store.estateTruth?.truthMatrix.first{$0.symbol==r.asset && $0.timeframe==item.timeframe}?.latestCanonicalObservation ?? "—"
        let publication=normalizedPublication(scheduler?.publicationState,hasCanonicalEvidence:edge != "—")
        let evidence=item.evidenceState == "PRESENT" && edge != "—" ? "Available":"No Evidence"
        let selectable=item.initialFetchEligible && !r.retired
        let mappingDiscoveryPending=item.reasonCodes.contains("MAPPING_DISCOVERY_PENDING")
        if let operation=store.activeDataOperation,operation.instrument==r.asset,operation.timeframe==item.timeframe {
            if store.dataOperationState.isActive{return .init(state:"Importing",publication:publication,provider:provider,edge:edge,detail:"Operation running",evidence:evidence,automation:"Running",action:"Wait",selectable:false,retryable:false)}
            if store.dataOperationState == .failed{return .init(state:"Failed Retryable",publication:publication,provider:provider,edge:edge,detail:"Retry / Resume available",evidence:evidence,automation:"Retryable",action:"Resume Required Set",selectable:selectable,retryable:true)}
        }
        if automaticAdmission?.activeTimeframe==item.timeframe {
            return .init(state:"Importing",publication:publication,provider:provider,edge:edge,detail:"Automatic initial history running",evidence:evidence,automation:"Running",action:"Wait",selectable:false,retryable:false)
        }
        if !isCommissioned(item.timeframe){return .init(state:"Not Commissioned",publication:publication,provider:provider,edge:edge,detail:"Commission after evidence",evidence:evidence,automation:"Unavailable",action:"Fetch Required Set",selectable:selectable,retryable:false)}
        if mappingDiscoveryPending {return .init(state:"Mapping Discovery",publication:publication,provider:provider,edge:edge,detail:"No exact provider representation has been verified yet",evidence:"No Evidence",automation:"Waiting",action:"Resolve Provider Mapping",selectable:false,retryable:false)}
        if publication=="FAILED_RETRYABLE" {return .init(state:"Failed Retryable",publication:publication,provider:provider,edge:edge,detail:"Publication failed — resume to retry",evidence:evidence,automation:"Retryable",action:"Resume Required Set",selectable:selectable,retryable:true)}
        if publication=="PUBLISHING" {return .init(state:"Committed",publication:publication,provider:provider,edge:edge,detail:"Awaiting publication; not consumer-visible",evidence:evidence,automation:"Publishing",action:"Wait",selectable:false,retryable:false)}
        if ["FAILED","MANUAL_REQUIRED"].contains(scheduler?.result ?? "") {return .init(state:"Failed Retryable",publication:publication,provider:provider,edge:edge,detail:"Retry / Resume available",evidence:evidence,automation:"Retryable",action:"Resume Required Set",selectable:selectable,retryable:true)}
        if scheduler?.schedulerState=="No Evidence" || item.evidenceState=="NO_EVIDENCE" {return .init(state:"No Evidence",publication:publication,provider:provider,edge:edge,detail:"Initial history is required",evidence:evidence,automation:selectable ? "Eligible":"Unavailable",action:"Fetch Initial History",selectable:selectable,retryable:false)}
        if scheduler?.schedulerState=="Current" {return .init(state:"Current",publication:publication,provider:provider,edge:edge,detail:"No update required",evidence:evidence,automation:"Current",action:"None",selectable:false,retryable:false)}
        if scheduler?.schedulerState=="Behind" {return .init(state:"Behind",publication:publication,provider:provider,edge:edge,detail:"Canonical evidence is behind the expected edge",evidence:evidence,automation:selectable ? "Eligible":"Unavailable",action:"Update",selectable:selectable,retryable:false)}
        if item.authorityState == "BLOCKED" {let detail=blockerText(item.reasonCodes.first ?? item.initialFetchBlockers.first);return .init(state:"Blocked",publication:publication,provider:provider,edge:edge,detail:detail,evidence:evidence,automation:"Blocked",action:detail,selectable:false,retryable:false)}
        if selectable {let detail=scheduler?.reason?.displayStatus ?? item.requiredOperatorAction?.displayStatus ?? "Executable";return .init(state:"Executable",publication:publication,provider:provider,edge:edge,detail:detail,evidence:evidence,automation:"Eligible",action:"Fetch Required Set",selectable:true,retryable:false)}
        let detail=item.requiredOperatorAction == "COMPLETE_PROVIDER_SETUP" ? "Complete Provider Setup":blockerText(item.initialFetchBlockers.first ?? scheduler?.reason)
        return .init(state:"Blocked",publication:publication,provider:provider,edge:edge,detail:detail,evidence:evidence,automation:"Blocked",action:detail,selectable:false,retryable:false)
    }

    private func normalizedPublication(_ value:String?,hasCanonicalEvidence:Bool=true)->String { switch value?.trimmingCharacters(in:.whitespacesAndNewlines).uppercased(){case "PENDING","QUEUED","PUBLISHING":return "PUBLISHING";case "FAILED","FAILED_RETRYABLE":return "FAILED_RETRYABLE";case "PUBLISHED":return hasCanonicalEvidence ? "PUBLISHED":"NOT_PUBLISHED";default:return hasCanonicalEvidence ? "PUBLISHED":"NOT_PUBLISHED"} }

    @ViewBuilder private var operationActivity:some View {
        if operationMatchesLane,let operation=store.activeDataOperation,store.dataOperationState.isActive {
            GroupBox("Operation Activity") {
                VStack(alignment:.leading,spacing:8) {
                    HStack(spacing:8){ProgressView();Text("\(operation.instrument) · \(operation.timeframe)").fontWeight(.semibold);Text(operation.actionLabel).foregroundStyle(.secondary)}
                    Text(store.dataOperationState.stageLabel).foregroundStyle(.secondary)
                    if operation.timeframe=="Required Set" { Text("Current lane: \(activeRequiredSetJob?.currentLane ?? store.schedulerSnapshot?.activeActivity?.timeframe ?? "—")").font(.caption).foregroundStyle(.secondary) }
                    if let provider=store.activeOperationProvider { Text("Provider: \(provider)" + (store.activeOperationFallbackPosition.map{" · fallback \($0)"} ?? "")).font(.caption.monospaced()) }
                    if let next=store.activeOperationNextProvider { Text("Next eligible provider: \(next)").font(.caption).foregroundStyle(.secondary) }
                }.frame(maxWidth:.infinity,alignment:.leading)
            }
        } else if let progress=automaticAdmission {
            GroupBox("Automatic Onboarding") {
                VStack(alignment:.leading,spacing:8) {
                    HStack(spacing:8){ProgressView();Text("\(progress.symbol) · Initial History").fontWeight(.semibold);Text(progress.stage).foregroundStyle(.secondary)}
                    Text("The scheduler owns this transaction. Other symbols and lanes remain available.").font(.caption).foregroundStyle(.secondary)
                }.frame(maxWidth:.infinity,alignment:.leading)
            }
        }
    }

    @ViewBuilder private var readableResult:some View {
        if let completion=completedExecution {
            let result=completion.result
            let warningResult=result.JSON?["transaction_state"] as? String == "COMPLETED_WITH_WARNINGS"
            let operatorOutcome=result.JSON?["outcome"] as? String
            let successful=result.exitCode==0 && !["FAILED","MANUAL_REQUIRED"].contains(operatorOutcome ?? "")
            GroupBox(successful ? (warningResult ? "Import completed with warnings":"Data Operation Complete"):(operatorOutcome == "MANUAL_REQUIRED" ? "Manual Evidence Required":"Data Operation Failed")) {
                VStack(alignment:.leading,spacing:8) {
                    Label(successful ? "Authority service completed successfully":(operatorOutcome == "MANUAL_REQUIRED" ? "No provider could publish the missing range; the request is visible in Scheduler.":"No evidence was written."),systemImage:successful ? "checkmark.circle.fill":(operatorOutcome == "MANUAL_REQUIRED" ? "person.crop.circle.badge.exclamationmark":"xmark.octagon")).foregroundStyle(successful ? .green:(operatorOutcome == "MANUAL_REQUIRED" ? .orange:.red))
                    if result.exitCode==0,let json=result.JSON { Facts(readableFacts(json));if warningResult{HStack{Button("View rejected row"){showRejectedRows.toggle()};Button("Export rejection report"){exportRejections(json)}};if showRejectedRows{rejectionDetails(json)}};if operatorOutcome == "MANUAL_REQUIRED"{HStack{Button("Import CSV"){store.dataOperationsMode = .importFile};Button("Open Scheduler"){store.section = .scheduler}}} }
                    else { Facts([("Rows inserted","0"),("Rows unchanged","0"),("Conflicts preserved","0"),("Raw blocks created","0")]);Text(operationFailure(result,isImport:completion.isImport));if !completion.isImport{HStack{Button("Import CSV"){store.dataOperationsMode = .importFile};Button("Try Again"){isolateOperationState()}}} }
                    DisclosureGroup("Technical Details"){Text(result.stdout.isEmpty ? result.stderr:result.stdout).font(.caption.monospaced()).textSelection(.enabled)}
                }
            }
        }
    }
    private var completedExecution:(result:ProcessResult,isImport:Bool)? {
        guard let owned=store.currentOperationResult else{return nil}
        if let plan=completedPlan,plan.matches(mode:store.dataOperationsMode,instrument:registration?.asset,timeframe:selectedTimeframe,fileChecksum:file == nil ? nil:checksum),owned.planRevision==plan.id{return(owned.result,true)}
        if let completion=completedAcquisition,store.dataOperationsMode == .fetch,completion.instrument==registration?.asset,(completion.timeframe==selectedTimeframe || completion.timeframe=="Required Set"),owned.planRevision==completion.revision{return(owned.result,false)}
        return nil
    }
    private func readableFacts(_ json:[String:Any])->[(String,String)] {
        let common=[("Instrument",json["asset"] as? String ?? json["symbol"] as? String ?? registration?.asset ?? "—"),("Timeframe",json["timeframe"] as? String ?? selectedTimeframe)]
        let counts=[("Rows inserted","\(json["inserted"] as? Int ?? 0)"),("Rows unchanged","\(json["unchanged"] as? Int ?? 0)"),("Conflicts preserved","\(json["conflicts_preserved"] as? Int ?? 0)"),("Raw block",json["raw_block_id"] as? String ?? "—")]
        if store.dataOperationsMode == .importFile { return common+[("Valid rows","\(json["accepted"] as? Int ?? json["staged"] as? Int ?? 0)"),("Rejected rows","\(json["rejected"] as? Int ?? 0)")]+counts }
        if json["work_class"] as? String == "OPERATOR_FETCH_REQUIRED_SET" {
            let required=(json["required_timeframes"] as? [String] ?? []).joined(separator:", ")
            let completed=(json["completed_lanes"] as? [String] ?? []).joined(separator:", ")
            let remaining=(json["remaining_lanes"] as? [String] ?? []).joined(separator:", ")
            let providers=(json["provider_used"] as? [String] ?? []).joined(separator:", ")
            let failures=(json["partial_failures"] as? [[String:Any]] ?? []).map{"\($0["timeframe"] as? String ?? "—"): \($0["outcome"] as? String ?? $0["reason"] as? String ?? "Blocked")"}.joined(separator:" · ")
            let edges=(json["last_published_edge"] as? [String:Any] ?? [:]).map{"\($0.key): \($0.value)"}.sorted().joined(separator:" · ")
            return [("Instrument",json["symbol"] as? String ?? registration?.asset ?? "—"),("Timeframe","Required Set"),("Outcome",(json["outcome"] as? String ?? "UNKNOWN").displayStatus),("Required lanes",required.isEmpty ? "—":required),("Completed lanes",completed.isEmpty ? "None":completed),("Remaining executable lanes",remaining.isEmpty ? "None":remaining),("Partial failures",failures.isEmpty ? "None":failures),("Provider used",providers.isEmpty ? "None":providers),("Last published edge",edges.isEmpty ? "—":edges)]
        }
        if json["work_class"] as? String == "OPERATOR_FETCH" {
            let range=json["requested_range"] as? [String:Any]
            let considered=(json["providers_considered"] as? [[String:Any]] ?? []).map{"\($0["provider"] as? String ?? "—"): \(($0["reason"] as? String ?? "Eligible").displayStatus)"}.joined(separator:" · ")
            let results=(json["provider_results"] as? [[String:Any]] ?? []).map{"\($0["provider"] as? String ?? "—"): \(($0["result"] as? String ?? "UNKNOWN").displayStatus)"}.joined(separator:" · ")
            let start=range?["start"] as? String ?? "—",end=range?["end"] as? String ?? "—"
            let attempted=(json["providers_attempted"] as? [String] ?? []).joined(separator:", ")
            let observations=json["published_observations"] as? Int ?? 0
            let operatorFacts:[(String,String)]=[("Outcome",(json["outcome"] as? String ?? "UNKNOWN").displayStatus),("Requested range","\(start) → \(end)"),("Canonical edge before",json["canonical_edge_before"] as? String ?? "—"),("Canonical edge after",json["canonical_edge_after"] as? String ?? "—"),("Providers considered",considered.isEmpty ? "None":considered),("Providers attempted",attempted.isEmpty ? "None":attempted),("Provider results",results.isEmpty ? "None":results),("Published observations","\(observations)"),("Authority revision",json["authority_revision"] as? String ?? "—"),("Manual request",json["manual_request_created"] as? String ?? "No")]
            return common+operatorFacts
        }
        if json["acquisition_intent"] as? String == "MAXIMUM_AVAILABLE_HISTORY" { return common+[("Provider",json["provider"] as? String ?? json["provider_id"] as? String ?? "—"),("Provider symbol",json["provider_symbol"] as? String ?? "—"),("Request count","\(json["request_count"] as? Int ?? 0)"),("Provider rows received","\(json["provider_rows_received"] as? Int ?? 0)"),("Unique observations","\(json["unique_observations_received"] as? Int ?? 0)"),("Earliest provider observation",json["earliest_provider_observation"] as? String ?? "—"),("Latest provider observation",json["latest_provider_observation"] as? String ?? "—"),("Canonical earliest bar",json["canonical_earliest_bar"] as? String ?? "—"),("Canonical latest bar",json["canonical_latest_bar"] as? String ?? "—"),("CAODT",json["caodt"] as? String ?? "—"),("Termination reason",json["termination_reason"] as? String ?? "—"),("Rows rejected","\(json["rejected"] as? Int ?? 0)")]+counts }
        return common+[("Requested range","\(json["from_date"] as? String ?? dateRange.fromISO) → \(json["through_date"] as? String ?? dateRange.throughISO)"),("Actual range",json["actual_range"] as? String ?? json["canonical_high_watermark"] as? String ?? "No returned bars"),("Rows received","\(json["received"] as? Int ?? 0)")]+counts+[("CAODT",truth?.truthState.caodt ?? "Refresh pending"),("Truth Score",truth.map{String($0.truthState.truthScore)} ?? "Refresh pending"),("Warnings",(json["warnings"] as? [String])?.joined(separator:", ") ?? "None")]
    }

    @ViewBuilder private var reviewSheet:some View { if let plan=reviewedPlan { VStack(alignment:.leading,spacing:16) { Text("Review Import").font(.title);Facts(reviewFacts(plan));HStack{Button("Cancel",role:.cancel){reviewing=false;reviewedPlan=nil};Spacer();Button("Confirm Import"){runReviewed(plan)}.buttonStyle(.borderedProminent)} }.padding(24).frame(minWidth:720) } }

    private func reviewFacts(_ plan:ReviewedDataOperationPlan)->[(String,String)] {
        let calendar=[selectedCapability?.calendarAuthority,selectedCapability?.sessionAuthority].compactMap{$0}.joined(separator:" · ")
        return [("Instrument",plan.instrument),("Providers","Manual file import"),("Lane",plan.timeframe),("Acquisition intent","IMPORT_FILE"),("Start",URL(fileURLWithPath:plan.filePath ?? "").lastPathComponent),("Through","—"),("Representation authority","Not applicable"),("Calendar/session authority",calendar),("Source timezone",plan.timeframe == "D1" ? "Not applicable for daily calendar dates" : plan.sourceTimezone ?? "Explicit offsets in source"),("Daily date format",plan.timeframe == "D1" ? plan.d1DateFormat : "Not applicable"),("File checksum",plan.fileChecksum ?? "—"),("Conflict Policy",plan.conflict.rawValue.capitalized)]
    }

    private var latestText:String { lane?.latestBar.map{Date(timeIntervalSince1970:TimeInterval($0)).formatted(date:.numeric,time:.shortened)} ?? "—" }
    private var latestCompletedD1:String { Calendar.current.date(byAdding:.day,value:-1,to:Date())!.formatted(.iso8601.year().month().day()) }
    private var latestCompletedBoundary:Date{Calendar.current.startOfDay(for:selectedTimeframe=="D1" ? Calendar.current.date(byAdding:.day,value:-1,to:Date())!:Date())}
    private var maximumDays:Int{["H1":166,"M30":83,"M5":13][selectedTimeframe] ?? 5000}
    private var dateRange:ControlledDateRange{.init(from:fromDate,through:throughDate,completedBoundary:latestCompletedBoundary,maximumCalendarDays:maximumDays)}
    private func blockerText(_ code:String?)->String{switch code{case "PROVIDER_SYMBOL_MAPPING_REQUIRED":return "Provider symbol mapping required";case "EXCHANGE_IDENTITY_REQUIRED":return "Exchange identity required";case "TRADING_CALENDAR_REQUIRED":return registration?.assetClass=="US_EQUITIES" ? "NASDAQ trading calendar required":"Trading calendar required";case let value? where value.hasSuffix("ACQUISITION_CONTRACT_UNAVAILABLE"):return "\(selectedTimeframe) acquisition contract unavailable";case "INSTRUMENT_REGISTRATION_INACTIVE":return "Instrument registration inactive";case "POLICY_INTENTIONALLY_DEFERRED":return "Intentionally deferred";case let value?:return value.replacingOccurrences(of:"_",with:" ").capitalized;case nil:return "Not eligible"}}
    private func applyPreset(days:Int){throughDate=latestCompletedBoundary;fromDate=Calendar.current.date(byAdding:.day,value:-(days-1),to:throughDate)!}
    private func pasteDate(toFrom:Bool){guard let text=NSPasteboard.general.string(forType:.string),let parsed=ControlledDateParser.parse(text)else{dateInterpretation="The pasted date could not be understood. Choose a date from the calendar.";return};if toFrom{fromDate=parsed.date}else{throughDate=parsed.date};dateInterpretation=parsed.interpretation ?? "Normalised to \(parsed.canonicalISO)."}
    private func rowCount(_ url:URL)->String{guard let text=try? String(contentsOf:url,encoding:.utf8)else{return "Unknown"};return String(max(0,text.split(whereSeparator:\.isNewline).count-1))}
    private func reconcileSelection(){selection.reconcile(visibleRegistrationIDs:Set(registrations.map(\.id)))}
    private func applyNavigationContext(){guard let asset=store.acquisitionAsset else{return};let requestedTimeframe=store.acquisitionTimeframe,requestedFrom=store.acquisitionFrom,requestedThrough=store.acquisitionThrough;let id=registrations.first(where:{$0.asset==asset})?.id;selection.applyNavigationContext(id,visibleRegistrationIDs:Set(registrations.map(\.id)));DispatchQueue.main.async{if let requestedTimeframe{selectedTimeframe=requestedTimeframe};manualMissingStart=requestedFrom;manualMissingEnd=requestedThrough;store.acquisitionAsset=nil;store.acquisitionTimeframe=nil;store.acquisitionFrom=nil;store.acquisitionThrough=nil}}
    private func resetInstrumentContext(){if !selectableTimeframes.contains(selectedTimeframe){selectedTimeframe="D1"};throughDate=latestCompletedBoundary;if (lane?.barCount ?? 0)==0{intent = .initial;fromDate=Calendar.current.date(byAdding:.day,value:-(min(maximumDays,30)-1),to:throughDate)!}else if lane?.latestBar != nil{intent = .update}else{intent = .custom;fromDate=Calendar.current.date(byAdding:.day,value:-29,to:throughDate)!};file=nil;sourceTimezone="";d1DateFormat="auto";reviewing=false;retirementImpact=nil;localError=nil;dateInterpretation=nil;conflict = .preserve;isolateOperationState()}
    private func prepareReview(_ r:InstrumentRegistrationRecord){guard store.dataOperationsMode == .importFile else{localError="Only the displayed unified acquisition plan can start a fetch.";return};store.beginPlanReview();let reviewedTimezone=sourceTimezone.trimmingCharacters(in:.whitespacesAndNewlines);let plan=ReviewedDataOperationPlan(id:store.currentPlanRevision,mode:.importFile,instrument:r.asset,timeframe:selectedTimeframe,filePath:file?.path,fileChecksum:file == nil ? nil:checksum,fileSelectionID:fileSelectionID,sourceTimezone:reviewedTimezone.isEmpty ? nil:reviewedTimezone,d1DateFormat:d1DateFormat,conflict:conflict);reviewedPlan=plan;reviewing=true}
    private func runUnifiedAcquisition(_ plan:UnifiedAcquisitionPlan){guard plan == unifiedAcquisitionPlan else{localError="The acquisition plan changed; review the rebuilt plan and try again.";return};guard let operation=plan.operationIntent else{localError=plan.failure ?? "The acquisition plan has no executable action.";return};store.beginPlanReview();let revision=store.currentPlanRevision;completedPlan=nil;localError=nil;Task{await store.run(operation);completedAcquisition = .init(revision:revision,instrument:plan.instrument,timeframe:plan.timeframe)}}
    private func runRequiredSet(_ r:InstrumentRegistrationRecord){store.beginPlanReview();let revision=store.currentPlanRevision;completedPlan=nil;localError=nil;Task{await store.run(.acquireRequiredSet(asset:r.asset));completedAcquisition = .init(revision:revision,instrument:r.asset,timeframe:"Required Set")}}
    private func resumeRequiredSet(_ r:InstrumentRegistrationRecord){store.beginPlanReview();let revision=store.currentPlanRevision;completedPlan=nil;localError=nil;Task{await store.run(.resumeRequiredSet(asset:r.asset));completedAcquisition = .init(revision:revision,instrument:r.asset,timeframe:"Required Set")}}
    private func runReviewed(_ plan:ReviewedDataOperationPlan){reviewing=false;reviewedPlan=nil;guard let operation=plan.intent else{localError="The reviewed operation plan is incomplete.";return};Task{await store.run(operation);if plan.matches(mode:store.dataOperationsMode,instrument:registration?.asset,timeframe:selectedTimeframe,fileChecksum:file == nil ? nil:checksum){completedPlan=plan}}}
    private func isolateOperationState(){reviewing=false;reviewedPlan=nil;completedPlan=nil;completedAcquisition=nil;store.clearCurrentOperationResult()}
    private func operationFailure(_ result:ProcessResult,isImport:Bool)->String{let payload=result.JSON;let rejectedReason=(payload?["rejections"] as? [[String:Any]])?.first?["message"] as? String;let reason=(payload?["error"] as? String) ?? rejectedReason ?? (result.stderr.isEmpty ? result.stdout:result.stderr);return isImport ? "Import rejected: \(reason)":"Fetch rejected: \(reason)"}
    @ViewBuilder private func rejectionDetails(_ json:[String:Any])->some View{if let rows=json["rejections"] as? [[String:Any]]{ForEach(Array(rows.enumerated()),id:\.offset){_,row in GroupBox("Row \(row["source_row_number"] as? Int ?? 0)"){Facts([("Code",row["code"] as? String ?? "Rejected"),("Reason",row["message"] as? String ?? "No reason recorded"),("Raw evidence","Preserved unchanged in \(json["raw_block_id"] as? String ?? "raw block")")])}}}}
    private func exportRejections(_ json:[String:Any]){guard let rows=json["rejections"],let data=try? JSONSerialization.data(withJSONObject:["instrument":registration?.asset ?? "","timeframe":selectedTimeframe,"raw_block_id":json["raw_block_id"] ?? "","rejections":rows],options:[.prettyPrinted,.sortedKeys]),PanelService.exportRejections(data)else{localError="The rejection report could not be exported.";return}}
    private func planRetirement(_ r:InstrumentRegistrationRecord){localError=nil;Task{await store.run(.retirementPlan(asset:r.asset,scope:"WHOLE_INSTRUMENT",lanes:selectedRegistrations.map(\.timeframe)));guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let impact=try? JSONDecoder().decode(RetirementImpact.self,from:Data(text.utf8))else{localError=store.operationError ?? "Retirement impact could not be loaded";return};retirementImpact=impact}}
    private func confirmRetirement(_ impact:RetirementImpact,_ reason:String,_ note:String,_ confirmation:String){retirementImpact=nil;Task{await store.run(.retireInstrument(asset:impact.canonicalInstrument,scope:impact.scope,lanes:impact.selectedLanes,reason:reason,note:note,confirmation:confirmation));guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let receipt=try? JSONDecoder().decode(RetirementReceipt.self,from:Data(text.utf8))else{localError=store.operationError ?? "Retirement failed";return};retirementReceipt=receipt}}
}

private struct RetirementOperationReview:View { let impact:RetirementImpact;let onConfirm:(RetirementImpact,String,String,String)->Void;@Environment(\.dismiss) var dismiss;@State private var reason="INCORRECT_INSTRUMENT_IDENTITY";@State private var note="";@State private var confirmation="";let reasons=["INCORRECT_INSTRUMENT_IDENTITY","INCORRECT_PAIR_ORIENTATION","INCORRECT_PROVIDER_MAPPING","WRONG_SYMBOL","DUPLICATE_REGISTRATION","ERRONEOUS_OPERATOR_REGISTRATION","INVALID_VENUE_OR_LISTING","PROVIDER_EVIDENCE_MISMATCH","OTHER_REVIEWED_REASON"];var body:some View{VStack(alignment:.leading,spacing:14){Text("Retire \(impact.canonicalInstrument)").font(.title);Text("SPEC-013 Impact Review").font(.headline);Picker("Controlled reason",selection:$reason){ForEach(reasons,id:\.self){Text($0.replacingOccurrences(of:"_",with:" ").capitalized).tag($0)}};TextField("Operator note",text:$note);Facts([("Active lanes",impact.activeTimeframeLanes.joined(separator:", ")),("Evidence counts","\(impact.canonicalBars) bars · \(impact.rawEvidenceBlocks) raw blocks"),("Acquisition history","\(impact.completedAcquisitionRuns) completed runs"),("Truth state",impact.currentServingState),("Operational effects","Acquisition disabled; active serving excluded"),("Preservation guarantees","Raw evidence and audit history preserved")]);if impact.typedConfirmationRequired{Text("Type \(impact.requiredConfirmation ?? "") to confirm").fontWeight(.semibold);TextField(impact.requiredConfirmation ?? "",text:$confirmation)};HStack{Button("Cancel",role:.cancel){dismiss()};Spacer();Button("Confirm Retirement",role:.destructive){dismiss();onConfirm(impact,reason,note,confirmation)}.disabled(impact.typedConfirmationRequired && confirmation.trimmingCharacters(in:.whitespaces).uppercased() != impact.requiredConfirmation)}}.padding(24).frame(minWidth:680)}}
private struct RetirementOperationSuccess:View { let receipt:RetirementReceipt;let done:()->Void;@Environment(\.dismiss) var dismiss;var body:some View{VStack(alignment:.leading,spacing:14){Text("\(receipt.canonicalInstrument) Retired").font(.title);Label("Acquisition disabled; evidence preserved; active serving removed",systemImage:"checkmark.circle.fill").foregroundStyle(.green);Facts([("Retirement ID",receipt.retirementID),("Reason",receipt.reason),("Authority",receipt.newAuthorityState),("Completed",receipt.completedTimestamp)]);Button("Done"){dismiss();done()}.buttonStyle(.borderedProminent)}.padding(24).frame(minWidth:620)}}
