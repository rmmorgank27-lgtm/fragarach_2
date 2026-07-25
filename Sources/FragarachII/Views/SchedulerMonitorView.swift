import AppKit
import OperationsCore
import SwiftUI

enum SchedulerFormatting {
    static func timestamp(_ value:String?)->String {
        guard let value else{return "—"}
        return value.replacingOccurrences(of:"T",with:" ").replacingOccurrences(of:"+00:00",with:" UTC")
    }
    static func lag(_ value:SchedulerLag)->String {
        guard let count=value.count,let unit=value.unit else{return "—"}
        if count == 0{return "Current"}
        return "\(count) \(unit.replacingOccurrences(of:"_",with:" "))\(count == 1 ? "":"s")"
    }
    static func duration(_ value:Double?)->String { value.map{String(format:"%.2fs",$0)} ?? "—" }
}

struct SchedulerMetricCard: View {
    let title:String;let value:String;let detail:String;let state:String?
    var action:(()->Void)? = nil
    var body:some View {
        let content=VStack(alignment:.leading,spacing:6) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            HStack(spacing:7) { if let state{Circle().fill(stateColor(state)).frame(width:9,height:9)};Text(value).font(.title3.bold()).lineLimit(1) }
            Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
        }.padding(14).frame(maxWidth:.infinity,minHeight:92,alignment:.leading).background(.regularMaterial,in:RoundedRectangle(cornerRadius:12))
        if let action { Button(action:action){content}.buttonStyle(.plain) } else { content }
    }
    private func stateColor(_ value:String)->Color {
        switch value.uppercased() { case "HEALTHY","CURRENT","RUNNING","SUCCESS":.green;case "DEGRADED","BEHIND","WAITING","NO_NEW_DATA":.orange;case "CRITICAL","FAILED","UNAVAILABLE":.red;default:.secondary }
    }
}

struct SchedulerMonitorView: View {
    @EnvironmentObject private var store:ConsoleStore
    @State private var search=""
    @State private var selectedLaneID:String?
    @State private var selectedException:String?
    @State private var traceLane="AUDUSD:M5"
    @State private var showInstallConfirmation=false
    @State private var showOperationDetails=false
    @State private var showDiagnostics=false
    @AppStorage("m5PublicationGraceSeconds") private var m5PublicationGraceSeconds=120
    @AppStorage("m5CriticalBoundaries") private var m5CriticalBoundaries=6
    private var lanes:[SchedulerLane] {
        let values=store.schedulerSnapshot?.lanes ?? []
        guard !search.isEmpty else{return values}
        return values.filter{$0.symbol.localizedCaseInsensitiveContains(search) || $0.timeframe.localizedCaseInsensitiveContains(search) || $0.schedulerState.localizedCaseInsensitiveContains(search)}
    }
    var body:some View {
        Group {
        if let status=store.schedulerServiceStatus,!status.live {
            serviceRecoveryView(status)
        } else if let status=store.schedulerServiceStatus,status.live,store.schedulerUsesCompactStatus {
            timeTriggeredStatusView(status)
        } else if let snapshot=store.schedulerSnapshot {
            ScrollView {
                VStack(alignment:.leading,spacing:18) {
                    HStack(alignment:.firstTextBaseline) {
                        WorkspaceHeader(title:"Scheduler",purpose:"Calendar-driven acquisition and authority publication health.")
                        Spacer()
                        Button("Run Queue Now"){Task{await store.runSchedulerQueue()}}.buttonStyle(.borderedProminent)
                        pauseMenu(snapshot)
                        if !store.schedulerServiceRunning { Button("Restart Scheduler"){store.startScheduler()}.buttonStyle(.borderedProminent) }
                    }
                    schedulerServiceSection(snapshot)
                    m5FreshnessControls
                    queueControls(snapshot)
                    executionSection(snapshot)
                    if let selectedException { exceptionDrilldown(snapshot,title:selectedException) }
                    LazyVGrid(columns:[GridItem(.adaptive(minimum:190),spacing:12)],spacing:12) {
                        SchedulerMetricCard(title:"Authority Health",value:store.schedulerServiceRunning ? snapshot.authorityHealth.state:"CRITICAL",detail:store.schedulerServiceRunning ? snapshot.authorityHealth.detail:"Scheduler stopped",state:store.schedulerServiceRunning ? snapshot.authorityHealth.state:"CRITICAL")
                        SchedulerMetricCard(title:"Scheduler",value:store.schedulerServiceRunning ? "Running":"Stopped",detail:store.schedulerError ?? "Calendar service active",state:store.schedulerServiceRunning ? "RUNNING":"CRITICAL")
                        SchedulerMetricCard(title:"Next Run",value:SchedulerFormatting.timestamp(snapshot.nextRun),detail:"Exact approved close boundary",state:nil)
                        SchedulerMetricCard(title:"Current",value:"\(snapshot.summary.current)",detail:"Commissioned lanes at edge",state:"CURRENT",action:{selectedException="Current"})
                        SchedulerMetricCard(title:"Behind",value:"\(snapshot.summary.behind)",detail:"Awaiting missing observations",state:snapshot.summary.behind == 0 ? "CURRENT":"BEHIND",action:{selectedException="Behind"})
                        SchedulerMetricCard(title:"Unavailable",value:"\(snapshot.summary.unavailable)",detail:"Structured calendar or edge reasons",state:snapshot.summary.unavailable == 0 ? "CURRENT":"UNAVAILABLE",action:{selectedException="Unavailable"})
                        SchedulerMetricCard(title:"Paused",value:"\(snapshot.summary.paused ?? 0)",detail:"Effective operator pauses",state:(snapshot.summary.paused ?? 0)>0 ? "WAITING":"CURRENT",action:{selectedException="Paused"})
                        SchedulerMetricCard(title:"Last Success",value:SchedulerFormatting.timestamp(snapshot.lastSuccessfulAcquisition),detail:"Successful authority publication",state:"SUCCESS")
                        SchedulerMetricCard(title:"Last Failure",value:SchedulerFormatting.timestamp(snapshot.lastFailure),detail:"Most recent isolated failure",state:snapshot.lastFailure == nil ? "CURRENT":"FAILED")
                    }
                    if let activity=snapshot.activeActivity {
                        GroupBox("Live Activity") {
                            HStack(spacing:12) { ProgressView();Text("\(activity.symbol) · \(activity.timeframe)").font(.headline);Text(activity.stage).foregroundStyle(.secondary);Spacer();Text(SchedulerFormatting.timestamp(activity.startedAt)).font(.caption.monospaced()).foregroundStyle(.secondary) }.padding(.vertical,6)
                        }
                    }
                    providerHealth(snapshot)
                    acquisitionQueue(snapshot)
                    manualRequests(snapshot)
                    HStack { Text("Commissioned Lanes").font(.title2.bold());Spacer();TextField("Filter symbol, timeframe, or state",text:$search).textFieldStyle(.roundedBorder).frame(width:300) }
                    Table(lanes,selection:$selectedLaneID) {
                        TableColumn("Symbol",value:\.symbol).width(min:80,ideal:100)
                        TableColumn("TF",value:\.timeframe).width(45)
                        TableColumn("State") { lane in Text(lane.schedulerState).foregroundStyle(stateColor(lane.schedulerState)) }.width(min:80,ideal:95)
                        TableColumn("Latest") { lane in Text(SchedulerFormatting.timestamp(lane.latestCanonicalObservation)).font(.caption.monospaced()) }.width(min:150,ideal:190)
                        TableColumn("Expected") { lane in Text(SchedulerFormatting.timestamp(lane.expectedLatest)).font(.caption.monospaced()) }.width(min:150,ideal:190)
                        TableColumn("Lag") { lane in Text(SchedulerFormatting.lag(lane.lag)) }.width(min:80,ideal:110)
                        TableColumn("Next") { lane in Text(SchedulerFormatting.timestamp(lane.nextScheduledAcquisition)).font(.caption.monospaced()) }.width(min:150,ideal:190)
                        TableColumn("Last Acquisition") { lane in Text(SchedulerFormatting.timestamp(lane.lastAcquisition)).font(.caption.monospaced()) }.width(min:150,ideal:190)
                        TableColumn("Duration") { lane in Text(SchedulerFormatting.duration(lane.durationSeconds)) }.width(70)
                        TableColumn("Result / Publication") { lane in Text("\(lane.result ?? "—") · \(formattedStatus(lane.publicationState ?? "PUBLISHED"))").foregroundStyle(stateColor(lane.publicationState ?? lane.result ?? "")) }.width(min:150,ideal:210)
                    }.frame(minHeight:360)
                    if let lane=lanes.first(where:{$0.id==selectedLaneID}) { laneDetail(lane) }
                    VStack(alignment:.leading,spacing:10) {
                        Text("Scheduler Log").font(.title2.bold())
                        if snapshot.events.isEmpty { Text("No scheduler events recorded yet.").foregroundStyle(.secondary) }
                        ForEach(snapshot.events.prefix(20)) { event in
                            HStack { Text(SchedulerFormatting.timestamp(event.at)).font(.caption.monospaced()).frame(width:190,alignment:.leading);Text(event.symbol).fontWeight(.semibold).frame(width:90,alignment:.leading);Text(event.timeframe).frame(width:40,alignment:.leading);Text(event.result).foregroundStyle(stateColor(event.result)).frame(width:120,alignment:.leading);Text("\(event.observations) observation\(event.observations == 1 ? "":"s")").foregroundStyle(.secondary);Spacer();Text(SchedulerFormatting.duration(event.durationSeconds)).font(.caption.monospaced()).foregroundStyle(.secondary) }.padding(.vertical,5)
                            Divider()
                        }
                    }
                    VStack(alignment:.leading,spacing:10) {
                        Text("Archived Operational History").font(.title2.bold())
                        let historicalRequests=snapshot.manualRequestHistory.filter{!["Required","Acknowledged","Waiting"].contains($0.status)}
                        if snapshot.archivedOperationalWork.isEmpty && historicalRequests.isEmpty { Text("No operational work has been archived.").foregroundStyle(.secondary) }
                        ForEach(historicalRequests.prefix(50)){request in
                            GroupBox("\(request.symbol) · \(request.timeframe) · \(formattedStatus(request.reconciliationStatus ?? request.status))") {
                                VStack(alignment:.leading,spacing:3){Text("Created \(SchedulerFormatting.timestamp(request.createdAt)) from provider facts revision \(request.createdProviderFactRevision.map { String($0) } ?? "legacy")");Text("Original providers: \((request.providersConsideredAtCreation ?? []).map(\.provider).joined(separator:", "))").font(.caption).foregroundStyle(.secondary);Text("Original rejection reasons: \((request.originalRejectionReasons ?? []).map{"\($0.provider): \($0.reason ?? "INELIGIBLE")"}.joined(separator:"; "))").font(.caption).foregroundStyle(.secondary);Text("Actually attempted: \((request.providersAttemptedAtCreation ?? request.providersAttempted).isEmpty ? "None" : (request.providersAttemptedAtCreation ?? request.providersAttempted).joined(separator:", "))").font(.caption).foregroundStyle(.secondary);Text("Reconciled \(SchedulerFormatting.timestamp(request.lastEvaluatedAt)) · \(request.reconciliationReason ?? "—")").font(.caption);if let replacement=request.replacementQueueIdentifier{Text("Replacement queue: \(replacement)").font(.caption.monospaced()).foregroundStyle(.secondary)}}.frame(maxWidth:.infinity,alignment:.leading)
                            }
                        }
                        ForEach(snapshot.archivedOperationalWork.prefix(50)){item in
                            HStack{Image(systemName:"archivebox");VStack(alignment:.leading){Text(item.lane).fontWeight(.semibold);Text("Archived — \(item.reason.replacingOccurrences(of:"_",with:" ").capitalized) · \(item.kind)").font(.caption).foregroundStyle(.secondary)};Spacer();Text(SchedulerFormatting.timestamp(item.archivedAt)).font(.caption.monospaced());if let symbol=item.lane.split(separator:":").first{Button("Open History"){store.marketHistorySymbol=String(symbol);store.section = .history}}}
                            .padding(.vertical,4)
                        }
                    }
                }.padding()
            }
            .toolbar { ToolbarItem { Button("Run Queue Now",systemImage:"play.fill"){Task{await store.runSchedulerQueue()}}.help("Use currently permitted queue capacity now") } }
        } else if let error=store.schedulerError {
            ContentUnavailableView("Scheduler Service unavailable",systemImage:"calendar.badge.exclamationmark",description:Text(error)).overlay(alignment:.bottom){HStack{if store.schedulerServiceStatus?.installed == true{Button("Start Service"){store.startScheduler()};Button("Repair Service"){store.repairScheduler()}}else{installButton("Install Scheduler Service")}}.padding()}
        } else {
            VStack(spacing:12){ProgressView();Text("Loading scheduler state…").foregroundStyle(.secondary)}
        }
        }
        .sheet(isPresented:$showOperationDetails){operationDetailSheet()}
        .sheet(isPresented:$showDiagnostics){diagnosticsSheet()}
    }

    private var m5FreshnessControls: some View {
        GroupBox("M5 freshness") {
            HStack(alignment:.center,spacing:12) {
                Text("Grace").foregroundStyle(.secondary)
                Stepper("\(m5PublicationGraceSeconds / 60) min",value:$m5PublicationGraceSeconds,in:0...60,step:60).frame(width:150)
                Text("Critical after").foregroundStyle(.secondary)
                Stepper("\(m5CriticalBoundaries) closed bars",value:$m5CriticalBoundaries,in:1...288).frame(width:195)
                Button("Apply now") { Task { await store.setM5Freshness(publicationDelaySeconds:m5PublicationGraceSeconds,criticalAfterClosedBoundaries:m5CriticalBoundaries) } }
                    .buttonStyle(.borderedProminent)
                Text("Applies immediately to M5 status and the next due dispatch.").font(.caption).foregroundStyle(.secondary)
                Spacer()
            }.padding(.vertical,4)
        }
    }

    @ViewBuilder private func serviceRecoveryView(_ status:SchedulerServiceStatus)->some View {
        VStack(spacing:20) {
            Spacer()
            if let operation=status.activeMutation {
                ProgressView().controlSize(.large)
                Text(operationTitle(operation)).font(.largeTitle.bold())
                Text(operation.progressMessage).font(.title3)
                Text("Started \(relativeAge(operation.startedAt)) · Last progress \(relativeAge(operation.lastProgressAt))").foregroundStyle(.secondary)
                HStack {
                    Button("View Details"){showOperationDetails=true}
                    Button("Cancel Operation"){Task{await store.cancelSchedulerMutation()}}.disabled(!operation.cancellable)
                        .help(operation.cancellable ? "Cancel at the current safe stage":"Cancellation will be available after the current protected stage completes.")
                    diagnosticsButton()
                }
            } else if let operation=status.lastMutation,["FAILED","TIMED_OUT"].contains(operation.status) {
                Image(systemName:"exclamationmark.triangle.fill").font(.system(size:42)).foregroundStyle(.orange)
                Text("Scheduler Service failed to \(operation.operationType.lowercased())").font(.largeTitle.bold())
                Text(operation.failureDetail ?? operation.progressMessage).multilineTextAlignment(.center).frame(maxWidth:680)
                Text("Failed stage: \(displayStage(operation.currentStage)) · Last progress \(relativeAge(operation.lastProgressAt))").foregroundStyle(.secondary)
                HStack {
                    Button("Retry \(operation.operationType.capitalized)"){retry(operation)}.buttonStyle(.borderedProminent)
                    Button("Repair Service"){store.repairScheduler()}
                    Button("Force Reconcile"){store.forceReconcileScheduler()}
                    diagnosticsButton()
                }
            } else if let operation=status.lastMutation,operation.status=="ABANDONED" {
                Image(systemName:"lock.open.trianglebadge.exclamationmark").font(.system(size:42)).foregroundStyle(.orange)
                Text("A previous \(operation.operationType.capitalized) operation did not complete.").font(.largeTitle.bold())
                Text(operation.failureDetail ?? "The originating app is no longer running and no service transition is active.").multilineTextAlignment(.center).frame(maxWidth:680)
                HStack {
                    Button("Clear Stale Operation"){store.forceReconcileScheduler()}.buttonStyle(.borderedProminent)
                    Button("Force Reconcile"){store.forceReconcileScheduler()}
                    diagnosticsButton()
                }
            } else {
                let health=status.operationalHealth
                Image(systemName:status.acquisitionOwnerActive ? "wave.3.right.circle.fill":"calendar.badge.exclamationmark").font(.system(size:42)).foregroundStyle(status.acquisitionOwnerActive ? .green:.orange)
                Text(status.acquisitionOwnerActive ? "Scheduler \((health?.overallOperationalHealth ?? "Healthy").capitalized)":"Scheduler Service unavailable").font(.largeTitle.bold())
                Text(status.acquisitionOwnerActive ? "Monitor disconnected. Scheduler health is reported independently.":"Live service connection lost.").font(.title3)
                Facts([
                    ("Monitor",health?.monitorTransport.state.replacingOccurrences(of:"_",with:" ").capitalized ?? "Disconnected"),
                    ("Last heartbeat",SchedulerFormatting.timestamp(health?.heartbeat.at ?? status.lastSuccessfulMonitorUpdate ?? status.heartbeatTime)),
                    ("Service process",health?.process.state.replacingOccurrences(of:"_",with:" ").capitalized ?? (status.acquisitionOwnerActive ? "Alive":"Not running")),
                    ("Queue","\(health?.actionableQueueDepth ?? 0) actionable · \(health?.blockedQueueDepth ?? 0) blocked"),
                    ("Workers","\(health?.workerPool.activeWorkers ?? 0) active · \(health?.workerPool.availableWorkers ?? 0) available"),
                    ("Last dispatch",SchedulerFormatting.timestamp(health?.providerDispatch.lastProgress)),
                    ("Last publication",SchedulerFormatting.timestamp(health?.publication.lastProgress)),
                    ("Current lane",health?.currentLane ?? "—"),
                    ("Current stage",health?.currentStage ?? health?.currentStopReason ?? "—"),
                ]).frame(maxWidth:620)
                HStack {
                    Button("Retry Connection"){Task{await store.refreshSchedulerStatus()}}.buttonStyle(.borderedProminent)
                    if status.installed && !status.acquisitionOwnerActive { Button("Start Service"){store.startScheduler()} }
                    if status.installed { Button(status.acquisitionOwnerActive ? "Repair Monitor":"Repair Service"){status.acquisitionOwnerActive ? store.repairSchedulerMonitor():store.repairScheduler()} }
                    else { installButton("Install Service") }
                    diagnosticsButton()
                }
            }
            Spacer()
        }.padding(36)
    }

    @ViewBuilder private func timeTriggeredStatusView(_ status:SchedulerServiceStatus)->some View {
        let health=status.operationalHealth
        let register=status.register
        let dueNow=register?.dueNowCount ?? 0
        let showingBlocked=store.schedulerRegisterFilter == "BLOCKED"
        let displayedRows=showingBlocked ? status.blockedScheduleDashboard : status.scheduleDashboard
        ScrollView {
            VStack(alignment:.leading,spacing:18) {
                HStack(alignment:.firstTextBaseline) {
                    WorkspaceHeader(title:"Schedule",purpose:"Time-triggered lane checks and the next operational work horizon.")
                    Spacer()
                    Button("Run Queue Now"){Task{await store.runSchedulerQueue()}}.buttonStyle(.borderedProminent)
                    Button("Refresh Status"){Task{await store.refreshSchedulerStatus()}}
                    diagnosticsButton()
                }
                GroupBox("Update speed") {
                    HStack(spacing:12) {
                        Text("Pace")
                        Picker("Pace",selection:Binding(get:{status.schedulerPolicyKey ?? "BALANCED"},set:{policy in Task{await store.setSchedulerPolicy(policy)}})) {
                            Text("Slow").tag("CONSERVATIVE")
                            Text("Balanced").tag("BALANCED")
                            Text("High").tag("MAXIMUM_CATCH_UP")
                        }.labelsHidden().frame(width:150)
                        Text("Balanced keeps normal boundaries current. High drains overdue work as quickly as provider limits allow; Slow uses one worker with deliberate pauses.").font(.caption).foregroundStyle(.secondary)
                        Spacer()
                    }.padding(.vertical,4)
                }
                LazyVGrid(columns:[GridItem(.adaptive(minimum:180),spacing:12)],spacing:12) {
                    SchedulerMetricCard(title:"Service",value:dueNow > 0 ? "Catching up":(health?.overallOperationalHealth ?? "Healthy").capitalized,detail:dueNow > 0 ? "\(dueNow) due checks · \(status.schedulerPolicy ?? "Balanced")":"Monitor \(health?.monitorTransport.state.replacingOccurrences(of:"_",with:" ").lowercased() ?? "connected")",state:dueNow > 0 ? "RUNNING":health?.overallOperationalHealth)
                    SchedulerMetricCard(title:"Next Due Check",value:SchedulerFormatting.timestamp(status.nextDueCheck),detail:"Next approved boundary",state:nil)
                    SchedulerMetricCard(title:"Ready",value:"\(register?.readyCount ?? 0)",detail:"Scheduled checks",state:"CURRENT")
                    SchedulerMetricCard(title:"Retrying",value:"\(register?.retryingCount ?? 0)",detail:"Retry backoff applies",state:(register?.retryingCount ?? 0) == 0 ? "CURRENT":"WAITING")
                    SchedulerMetricCard(title:"Blocked",value:"\(register?.blockedCount ?? 0)",detail:"Needs review or repair",state:(register?.blockedCount ?? 0) == 0 ? "CURRENT":"FAILED",action:{store.schedulerRegisterFilter="BLOCKED"})
                    SchedulerMetricCard(title:"Weekly Audit",value:status.audit?.overallResult?.replacingOccurrences(of:"_",with:" ").capitalized ?? "Not yet run",detail:"Separate from normal updates",state:status.audit?.overallResult)
                }
                GroupBox(showingBlocked ? "Blocked Lane Findings" : "Upcoming Scheduled Checks") {
                    VStack(alignment:.leading,spacing:10) {
                        HStack {
                            Text(showingBlocked ? "Showing \(displayedRows.count) blocked register rows. Each outcome identifies the repair required." : "Showing the next \(displayedRows.count) register rows. Normal wakes do not load the full estate.").font(.caption).foregroundStyle(.secondary)
                            Spacer()
                            if showingBlocked { Button("Show schedule"){store.schedulerRegisterFilter=nil} }
                        }
                        if displayedRows.isEmpty {
                            Text(showingBlocked ? "No blocked lane findings are currently registered." : "No scheduled lane checks are currently registered.").foregroundStyle(.secondary).padding(.vertical,18)
                        } else {
                            Table(displayedRows) {
                                TableColumn("Symbol",value:\.asset).width(min:90,ideal:120)
                                TableColumn("TF",value:\.timeframe).width(55)
                                TableColumn("State") { row in Text(row.state.replacingOccurrences(of:"_",with:" ").capitalized).foregroundStyle(stateColor(row.state)) }.width(min:80,ideal:105)
                                TableColumn("Next Check") { row in Text(SchedulerFormatting.timestamp(row.nextCheckAtUTC)).font(.caption.monospaced()) }.width(min:175,ideal:215)
                                TableColumn("Boundary") { row in Text(SchedulerFormatting.timestamp(row.nextExpectedBoundaryUTC)).font(.caption.monospaced()) }.width(min:175,ideal:215)
                                TableColumn("Outcome / Retry") { row in Text(row.lastOutcome ?? ((row.retryCount ?? 0) > 0 ? "Retry \(row.retryCount ?? 0)" : "—")).foregroundStyle(.secondary) }.width(min:150,ideal:230)
                            }.frame(minHeight:280,maxHeight:430)
                        }
                    }.padding(.vertical,4)
                }
                repairActions(status.blockedScheduleDashboard)
                GroupBox("Service Monitor") {
                    Facts([
                        ("Service process",health?.process.state.replacingOccurrences(of:"_",with:" ").capitalized ?? "Alive"),
                        ("Last heartbeat",SchedulerFormatting.timestamp(health?.heartbeat.at ?? status.heartbeatTime)),
                        ("Workers","\(health?.workerPool.activeWorkers ?? 0) active · \(health?.workerPool.availableWorkers ?? 0) available"),
                        ("Queue","\(health?.actionableQueueDepth ?? 0) actionable · \(health?.blockedQueueDepth ?? 0) blocked"),
                    ])
                }
            }.padding()
        }
    }

    @ViewBuilder private func repairActions(_ blockedRows:[SchedulerUpdateRegisterLane])->some View {
        let credentialBlocks=blockedRows.filter { row in
            let outcome=(row.lastOutcome ?? "").lowercased()
            return outcome.contains("credential repair") || outcome.contains("authentication_failed")
        }
        let localFailures=blockedRows.filter { ($0.lastOutcome ?? "").uppercased().contains("LOCAL_PROGRAMMING_ERROR") }
        let noEligibleProvider=blockedRows.filter { ($0.lastOutcome ?? "").uppercased().contains("NO_ELIGIBLE_PROVIDER") }
        let calendarBlocks=blockedRows.filter { ($0.lastOutcome ?? "").uppercased().contains("OPERATIONAL_CALENDAR_UNAVAILABLE") }
        if !credentialBlocks.isEmpty || !localFailures.isEmpty || !noEligibleProvider.isEmpty || !calendarBlocks.isEmpty {
            GroupBox("Repair Actions") {
                VStack(alignment:.leading,spacing:14) {
                    if !credentialBlocks.isEmpty {
                        VStack(alignment:.leading,spacing:7) {
                            Label("Twelve Data credential blocks · \(credentialBlocks.count) lane\(credentialBlocks.count == 1 ? "" : "s")",systemImage:"key.fill").foregroundStyle(.orange)
                            Text("Store a replacement key only if needed. Fragarach validates it remotely, refreshes provider facts, then releases only these authentication blocks to retry.").font(.caption).foregroundStyle(.secondary)
                            HStack {
                                Button("Configure & Validate Twelve Data") { store.openProviderCredentialRepair() }.buttonStyle(.borderedProminent)
                                Button("Recheck Provider Facts") { Task { await store.refreshProviderFacts(resolve:true) } }.disabled(store.providerFactsResolving)
                            }
                        }
                    }
                    if !credentialBlocks.isEmpty && (!localFailures.isEmpty || !noEligibleProvider.isEmpty || !calendarBlocks.isEmpty) { Divider() }
                    if !localFailures.isEmpty {
                        let lane = localFailures[0]
                        VStack(alignment:.leading,spacing:7) {
                            Label("Provider route / evidence blocks · \(localFailures.count)",systemImage:"wrench.and.screwdriver.fill").foregroundStyle(.red)
                            Text("These are not credential failures. Probe the approved route before changing it; Fragarach only restores the lane after a provider returns valid evidence.").font(.caption).foregroundStyle(.secondary)
                            HStack {
                                Button("Probe \(lane.asset) \(lane.timeframe) route") { Task { await store.probeProviderCapability(symbol:lane.asset,timeframe:lane.timeframe) } }.disabled(store.providerFactsResolving)
                                Button("Open Provider Facts") { store.openProviderFacts() }
                            }
                        }
                    }
                    if !localFailures.isEmpty && (!noEligibleProvider.isEmpty || !calendarBlocks.isEmpty) { Divider() }
                    if !noEligibleProvider.isEmpty {
                        VStack(alignment:.leading,spacing:7) {
                            Label("No eligible provider route · \(noEligibleProvider.count)",systemImage:"point.3.connected.trianglepath.dotted").foregroundStyle(.orange)
                            Text("Re-evaluate the reviewed provider routes first. If a lane is still blocked afterwards, Provider Facts shows the exact mapping and runtime state that needs attention; the Scheduler will not invent a substitute.").font(.caption).foregroundStyle(.secondary)
                            HStack {
                                Button("Re-evaluate blocked routes") { Task {
                                    for lane in noEligibleProvider { await store.retrySchedulerLane(lane.id) }
                                    await store.runSchedulerQueue()
                                } }
                                Button("Open Provider Facts") { store.openProviderFacts() }
                            }
                        }
                    }
                    if !noEligibleProvider.isEmpty && !calendarBlocks.isEmpty { Divider() }
                    if !calendarBlocks.isEmpty {
                        VStack(alignment:.leading,spacing:7) {
                            Label("Operational calendar unavailable · \(calendarBlocks.count)",systemImage:"calendar.badge.exclamationmark").foregroundStyle(.orange)
                            Text("No declared session calendar exists for this instrument, so Fragarach cannot determine the last closed D1 bar. This is separate from provider availability; review the calendar/session policy before restoring it.").font(.caption).foregroundStyle(.secondary)
                            HStack {
                            Button("Calendar & Session Policy") { store.openCalendarSettings() }
                            Button("Open Scheduler Diagnostics") {
                                showDiagnostics=true
                                Task { await store.loadSchedulerDiagnostics() }
                            }
                            }
                        }
                    }
                }.frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,4)
            }
        }
    }

    private func diagnosticsButton()->some View {
        Button("Open Diagnostics") {
            showDiagnostics=true
            Task{await store.loadSchedulerDiagnostics()}
        }
    }

    @ViewBuilder private func operationDetailSheet()->some View {
        if let status=store.schedulerServiceStatus,let operation=status.activeMutation ?? status.lastMutation {
            VStack(alignment:.leading,spacing:18) {
                HStack { Text("Service Operation").font(.title.bold());Spacer();Button("Done"){showOperationDetails=false}.keyboardShortcut(.cancelAction) }
                Facts([
                    ("Operation",operation.operationType.replacingOccurrences(of:"_",with:" ").capitalized),
                    ("Status",operation.status.replacingOccurrences(of:"_",with:" ").capitalized),
                    ("Started",SchedulerFormatting.timestamp(operation.startedAt)),
                    ("Elapsed",relativeAge(operation.startedAt)),
                    ("Current stage",displayStage(operation.currentStage)),
                    ("Last progress",SchedulerFormatting.timestamp(operation.lastProgressAt)),
                    ("Requesting app",operation.requestingAppBuild ?? "Unknown build"),
                    ("Target service generation",operation.targetServiceGeneration ?? "Any healthy replacement"),
                    ("LaunchAgent state",status.installed ? (status.automaticLoginStart ? "Installed and enabled":"Installed but disabled"):"Not installed"),
                    ("Service process state",status.acquisitionOwnerActive ? "Alive":"Not running"),
                    ("Socket state",status.live ? "Reachable":"Unavailable"),
                    ("Heartbeat state",SchedulerFormatting.timestamp(status.heartbeatTime)),
                    ("Failure detail",operation.failureDetail ?? "None"),
                ])
                if !operation.cancellable && ["RUNNING","WAITING"].contains(operation.status) {
                    Label("Cancellation will be available after the current protected stage completes.",systemImage:"lock.fill").foregroundStyle(.secondary)
                }
            }.padding(24).frame(minWidth:620,minHeight:520)
        } else {
            ContentUnavailableView("No service operation",systemImage:"checkmark.circle")
                .frame(minWidth:520,minHeight:320)
        }
    }

    @ViewBuilder private func diagnosticsSheet()->some View {
        VStack(alignment:.leading,spacing:14) {
            HStack {
                Text("Scheduler Service Diagnostics").font(.title.bold())
                Spacer()
                Button("Copy Report"){copyDiagnostics()}.disabled(store.schedulerServiceDiagnostics == nil)
                Button("Done"){showDiagnostics=false}.keyboardShortcut(.cancelAction)
            }
            if let diagnostics=store.schedulerServiceDiagnostics {
                Text("Generated \(SchedulerFormatting.timestamp(diagnostics.generatedAt)) · Credentials excluded").foregroundStyle(.secondary)
                List(diagnostics.checks) { check in
                    HStack(alignment:.top,spacing:12) {
                        Image(systemName:check.passed ? "checkmark.circle.fill":"xmark.octagon.fill").foregroundStyle(check.passed ? .green:.red)
                        VStack(alignment:.leading,spacing:4) {
                            Text(check.check).fontWeight(.semibold)
                            if let code=check.failureCode { Text(code).font(.caption.monospaced()).foregroundStyle(.secondary) }
                            if let explanation=check.explanation { Text(explanation) }
                            if let repair=check.recommendedRepair { Text("Recommended: \(repair)").font(.caption).foregroundStyle(.secondary) }
                        }
                    }.padding(.vertical,4)
                }
            } else if let error=store.schedulerDiagnosticsError {
                ContentUnavailableView("Diagnostics unavailable",systemImage:"exclamationmark.triangle",description:Text(error))
            } else {
                VStack { Spacer();ProgressView("Inspecting service state…");Spacer() }.frame(maxWidth:.infinity)
            }
        }.padding(20).frame(minWidth:760,minHeight:620)
    }

    private func copyDiagnostics() {
        guard let diagnostics=store.schedulerServiceDiagnostics else{return}
        let lines=["Fragarach II Scheduler diagnostics","Generated: \(diagnostics.generatedAt)","Credentials included: no"]+diagnostics.checks.map{check in
            let state=check.passed ? "PASS":"FAIL \(check.failureCode ?? "UNKNOWN")"
            return "\(state) — \(check.check)\(check.explanation.map{" — \($0)"} ?? "")\(check.recommendedRepair.map{" — Recommended: \($0)"} ?? "")"
        }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(lines.joined(separator:"\n"),forType:.string)
    }

    private func retry(_ operation:SchedulerServiceMutation) {
        let action=operation.operationType.lowercased()
        Task{await store.manageSchedulerServiceFromUI(action)}
    }

    private func operationTitle(_ operation:SchedulerServiceMutation)->String {
        let verb:[String:String]=["INSTALL":"Installing","START":"Starting","STOP":"Stopping","RESTART":"Restarting","UPDATE":"Updating","REPAIR":"Repairing","ENABLE":"Enabling","DISABLE":"Disabling","UNINSTALL":"Uninstalling","FORCE_RECONCILE":"Reconciling"]
        return "\(verb[operation.operationType] ?? operation.operationType.capitalized) Scheduler Service"
    }

    private func displayStage(_ value:String)->String { value.replacingOccurrences(of:"_",with:" ").capitalized }
    private func relativeAge(_ value:String?)->String {
        guard let value,let date=ISO8601DateFormatter().date(from:value) else{return "at an unknown time"}
        let seconds=max(0,Int(Date().timeIntervalSince(date)))
        if seconds<60{return "\(seconds) second\(seconds == 1 ? "":"s") ago"}
        let minutes=seconds/60
        return "\(minutes) minute\(minutes == 1 ? "":"s") ago"
    }

    @ViewBuilder private func schedulerServiceSection(_ snapshot:SchedulerSnapshot)->some View {
        let status=store.schedulerServiceStatus
        let mutation=status?.activeMutation
        GroupBox("Scheduler Service") {
            VStack(alignment:.leading,spacing:12) {
                HStack(alignment:.top) {
                    VStack(alignment:.leading,spacing:5) {
                        Label(status?.serviceState.replacingOccurrences(of:"_",with:" ").capitalized ?? "Unreachable",systemImage:store.schedulerServiceRunning ? "checkmark.circle.fill":"exclamationmark.triangle.fill").foregroundStyle(store.schedulerServiceRunning ? .green:.orange).font(.headline)
                        Text(status?.live == true ? "Live service connection" : "Cached status — not live").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    if status?.installed != true { installButton("Install") }
                    else {
                        Button("Start"){store.startScheduler()}.disabled(store.schedulerServiceRunning || mutation != nil)
                        Button("Stop"){store.stopScheduler()}.disabled(!store.schedulerServiceRunning || mutation != nil).help("Gracefully stops the service and all acquisition. Pause All keeps the service and monitor running.")
                        Button("Restart"){store.restartScheduler()}.disabled(!store.schedulerServiceRunning || mutation != nil)
                        if status?.compatibility == "Service Update Available" || status?.compatibility == "Service Update Required" { Button("Update"){Task{await store.manageSchedulerServiceFromUI("update")}}.buttonStyle(.borderedProminent).disabled(mutation != nil) }
                        Button("Repair"){store.repairScheduler()}.disabled(mutation != nil)
                        Menu("More") { Button("Open Diagnostics"){showDiagnostics=true;Task{await store.loadSchedulerDiagnostics()}};Button("Force Reconcile"){store.forceReconcileScheduler()}.disabled(mutation != nil);Divider();Button("Enable at Login"){Task{await store.manageSchedulerServiceFromUI("enable")}}.disabled(mutation != nil);Button("Disable at Login"){Task{await store.manageSchedulerServiceFromUI("disable")}}.disabled(mutation != nil);Divider();Button("Uninstall",role:.destructive){store.uninstallScheduler()}.disabled(mutation != nil) }
                    }
                }
                if let mutation {
                    HStack(spacing:10) {
                        ProgressView()
                        VStack(alignment:.leading) { Text(operationTitle(mutation)).fontWeight(.semibold);Text("\(mutation.progressMessage) · Last progress \(relativeAge(mutation.lastProgressAt))").font(.caption).foregroundStyle(.secondary) }
                        Spacer()
                        Button("View Details"){showOperationDetails=true}
                        Button("Cancel"){Task{await store.cancelSchedulerMutation()}}.disabled(!mutation.cancellable)
                    }.padding(10).background(.quaternary.opacity(0.5),in:RoundedRectangle(cornerRadius:8))
                }
                Facts([
                    ("Installed build",status?.serviceBuild ?? "—"),
                    ("Running build",status?.runningBuild ?? "—"),
                    ("App compatibility",status?.compatibility ?? "Unknown"),
                    ("Started",SchedulerFormatting.timestamp(status?.serviceStartTime)),
                    ("Last heartbeat",SchedulerFormatting.timestamp(status?.heartbeatTime)),
                    ("Next wake",SchedulerFormatting.timestamp(snapshot.nextRun)),
                    ("Active acquisition",snapshot.activeActivity.map{"\($0.symbol) · \($0.timeframe) · \($0.stage)"} ?? "None"),
                    ("Queue count","\(snapshot.queueSummary?.totalQueued ?? snapshot.acquisitionQueue.count)"),
                    ("Restart count","\(status?.restartCount ?? 0)"),
                    ("Last exit reason",status?.live == false ? status?.lastExitReason ?? "—" : "None (current service healthy)"),
                ])
                Text("Pause All leaves this service alive and calculating boundaries. Stop Service drains/checkpoints work and disables all acquisition until explicitly started.").font(.caption).foregroundStyle(.secondary)
            }.padding(.vertical,4)
        }
    }

    private func installButton(_ title:String)->some View {
        Button(title){showInstallConfirmation=true}
            .buttonStyle(.borderedProminent)
            .alert("Install Scheduler Service",isPresented:$showInstallConfirmation) {
                Button("Cancel",role:.cancel){}
                Button("Install and Enable"){store.installScheduler()}
            } message: {
                Text("Service location: \(store.schedulerServiceStatus?.serviceLocation ?? "~/Library/Application Support/Fragarach II/Scheduler")\nAuthority database: \(store.databasePath)\nOperational journal: \(store.schedulerServiceStatus?.operationalJournal ?? "\(store.databasePath).scheduler.json")\nInstalled build: bundled app service\nAutomatic login start: Enabled\nCredential source: macOS Keychain / approved credential chain")
            }
    }

    @ViewBuilder private func queueControls(_ snapshot:SchedulerSnapshot)->some View {
        GroupBox("Queue Control") {
            VStack(alignment:.leading,spacing:12) {
                HStack {
                    Text("Operational Policy").font(.headline)
                    Picker("Operational Policy",selection:Binding(get:{snapshot.schedulerPolicyKey},set:{policy in Task{await store.setSchedulerPolicy(policy)}})) {
                        Text("Slow").tag("CONSERVATIVE")
                        Text("Balanced").tag("BALANCED")
                        Text("High").tag("MAXIMUM_CATCH_UP")
                    }.labelsHidden().frame(width:190)
                    Text("Utilisation adapts to queue pressure, age, protected work, and provider health.").font(.caption).foregroundStyle(.secondary)
                }
                if let throughput=snapshot.throughput {
                    LazyVGrid(columns:[GridItem(.adaptive(minimum:170),spacing:10)],spacing:10) {
                        SchedulerMetricCard(title:"Current Policy",value:snapshot.schedulerPolicy,detail:throughput.reasons.joined(separator:" · "),state:nil)
                        SchedulerMetricCard(title:"Current Utilisation",value:"\(throughput.currentRequestsPerMinute) / \(throughput.safeCapacityPerMinute) req/min",detail:"Adaptive target \(throughput.targetRequestsPerMinute) req/min · \(throughput.targetUtilizationPercent)%",state:nil)
                        SchedulerMetricCard(title:"Reserved Capacity",value:"\(throughput.reservedCapacity)",detail:"Dynamic operator, retry, boundary, and publication demand",state:nil)
                        SchedulerMetricCard(title:"Available Capacity",value:"\(throughput.availableCapacity)",detail:"Dispatchable now across healthy providers",state:nil)
                    }
                }
                if let summary=snapshot.queueSummary {
                    LazyVGrid(columns:[GridItem(.adaptive(minimum:150),spacing:10)],spacing:10) {
                        if let dispatch=snapshot.dispatchState { SchedulerMetricCard(title:"Dispatch State",value:dispatch.state,detail:dispatch.reason,state:dispatch.state.hasPrefix("BUG:") ? "FAILED" : dispatch.state == "Dispatching" ? "RUNNING" : dispatch.state.contains("Waiting") || dispatch.state.contains("Cooling") ? "WAITING" : "CURRENT",action:{selectedException="Dispatch State"}) }
                        SchedulerMetricCard(title:"Total Queued",value:"\(summary.totalQueued)",detail:"All persisted queue work",state:nil,action:{selectedException="Total Queued"})
                        SchedulerMetricCard(title:"Ready Now",value:"\(summary.readyNow)",detail:"Eligible for dispatch",state:summary.readyNow > 0 ? "RUNNING":"CURRENT",action:{selectedException="Ready Now"})
                        SchedulerMetricCard(title:"Running",value:"\(summary.running)",detail:"Active lane tasks",state:summary.running > 0 ? "RUNNING":"CURRENT",action:{selectedException="Running"})
                        SchedulerMetricCard(title:"Waiting for Budget",value:"\(summary.waitingForBudget)",detail:"Local budget; exact release per lane",state:summary.waitingForBudget > 0 ? "WAITING":"CURRENT",action:{selectedException="Waiting for Budget"})
                        SchedulerMetricCard(title:"Cooling or Backoff",value:"\(summary.coolingDown)",detail:"Classified cause and scope",state:summary.coolingDown > 0 ? "WAITING":"CURRENT",action:{selectedException="Cooling or Backoff"})
                        SchedulerMetricCard(title:"Blocked",value:"\(summary.blocked)",detail:"Authority or provider restriction",state:summary.blocked > 0 ? "FAILED":"CURRENT",action:{selectedException="Blocked"})
                        SchedulerMetricCard(title:"Manual Required",value:"\(summary.manualRequired)",detail:"\(snapshot.manualRequestUniqueLanes) lanes · \(snapshot.manualRequestUniqueSymbols) symbols",state:summary.manualRequired > 0 ? "FAILED":"CURRENT",action:{selectedException="Manual Required"})
                        SchedulerMetricCard(title:"Oldest Queued Age",value:summary.oldestQueuedAgeSeconds.map{durationAge($0)} ?? "—",detail:"Age of oldest persisted item",state:nil)
                        SchedulerMetricCard(title:"Last Dispatch",value:SchedulerFormatting.timestamp(summary.lastDispatch),detail:"Most recent queue dispatch",state:nil)
                        SchedulerMetricCard(title:"Estimated Clear Time",value:summary.estimatedClearTimeSeconds.map{durationAge($0)} ?? "—",detail:summary.estimatedClearTimeLabel,state:nil)
                    }
                    if let dispatch=snapshot.dispatchState,dispatch.state.hasPrefix("BUG:") {
                        GroupBox("Ready Work Idle Diagnosis") {
                            Facts([
                                ("Why no dispatch",dispatch.reason),
                                ("Oldest ready age",dispatch.oldestReadyAgeSeconds.map{durationAge($0)} ?? "—"),
                                ("Last dispatch attempt",SchedulerFormatting.timestamp(dispatch.lastDispatchAttempt)),
                                ("Last scheduler lock holder",dispatch.lastSchedulerLockHolder ?? "—"),
                                ("Last cycle overrun",dispatch.lastCycleOverrunReason ?? "None"),
                                ("Next wake",SchedulerFormatting.timestamp(dispatch.nextWake)),
                            ])
                        }
                    }
                }
            }.padding(.vertical,4)
        }
    }

    @ViewBuilder private func executionSection(_ snapshot:SchedulerSnapshot)->some View {
        GroupBox("Execution") {
            if let execution=snapshot.execution {
                VStack(alignment:.leading,spacing:12) {
                    let twelve=snapshot.providers.first{$0.provider=="TWELVE_DATA"}
                    LazyVGrid(columns:[GridItem(.adaptive(minimum:165),spacing:10)],spacing:10) {
                        SchedulerMetricCard(title:"Last Completed Cycle",value:SchedulerFormatting.timestamp(execution.completedAt),detail:execution.cycleID ?? "No completed cycle",state:nil)
                        SchedulerMetricCard(title:"Cycle Duration",value:execution.durationMS.map{String(format:"%.0f ms",$0)} ?? "—",detail:"Next intended \(SchedulerFormatting.timestamp(execution.nextIntendedCycle))",state:nil)
                        SchedulerMetricCard(title:"Cycle Overrun",value:(execution.cycleOverrun ?? false) ? "Yes":"No",detail:execution.cycleOverrunMS.map{String(format:"%.0f ms",$0)} ?? "0 ms",state:(execution.cycleOverrun ?? false) ? "FAILED":"CURRENT")
                        SchedulerMetricCard(title:"Dispatch Attempts",value:"\(execution.dispatchAttemptedCount ?? 0)",detail:"\(execution.workerAllocatedCount ?? 0) workers started",state:nil)
                        SchedulerMetricCard(title:"Queue Depth",value:"\(execution.queueDepthAfter ?? snapshot.acquisitionQueue.count)",detail:"\(execution.eligibleCount ?? 0) eligible · \(execution.selectedCount ?? 0) selected",state:nil)
                        SchedulerMetricCard(title:"Requests",value:"\(execution.requestStartedCount ?? 0) → \(execution.requestCompletedCount ?? 0)",detail:"Started → completed",state:nil)
                        SchedulerMetricCard(title:"Canonical Edges",value:"\(execution.canonicalAdvancedCount ?? 0)",detail:"\(execution.queueCompletedCount ?? 0) queue items completed",state:nil)
                        SchedulerMetricCard(title:"Oldest Queue Age",value:age(execution.oldestQueueAgeAfter),detail:"Age after completed cycle",state:nil)
                        SchedulerMetricCard(title:"Workers",value:"\(execution.activeWorkers ?? 0) active",detail:"Single authoritative executor",state:nil)
                        SchedulerMetricCard(title:"Provider Budget",value:"\(execution.providerBudgetRemaining ?? 0)",detail:"Calls remaining across request budgets",state:nil)
                        SchedulerMetricCard(title:"Twelve Data Limits",value:"\(twelve?.operationalCreditLimit ?? 0) / \(twelve?.planLimit ?? twelve?.requestLimit ?? 0)",detail:"Operational / hard plan credits per minute",state:nil)
                        SchedulerMetricCard(title:"Current Credit Window",value:SchedulerFormatting.timestamp(twelve?.windowStartedAt),detail:"Ends \(SchedulerFormatting.timestamp(twelve?.windowEndsAt))",state:nil)
                        SchedulerMetricCard(title:"Credits",value:"\(twelve?.creditsConsumed ?? execution.creditsConsumed ?? 0) used · \(twelve?.creditsRemaining ?? execution.creditsRemaining ?? 0) remaining",detail:"Next dispatch \(SchedulerFormatting.timestamp(twelve?.nextDispatchAt))",state:nil)
                        SchedulerMetricCard(title:"Requests Last Minute",value:"\(twelve?.requestsLastMinute ?? 0)",detail:String(format:"%.1f credits/min",twelve?.currentDispatchRate ?? execution.dispatchRatePerMinute ?? 0),state:nil)
                        SchedulerMetricCard(title:"Eligible Backlog",value:"\(execution.eligibleCount ?? snapshot.queueSummary?.readyNow ?? 0)",detail:"\(execution.dispatchableCredits ?? 0) dispatchable credits",state:nil)
                        SchedulerMetricCard(title:"Worker Utilisation",value:String(format:"%.0f%%",(execution.workerUtilisation ?? 0)*100),detail:"\(execution.activeWorkers ?? 0) active workers",state:nil)
                        SchedulerMetricCard(title:"SQLite Lock Wait",value:String(format:"%.1f ms",execution.databaseWaitMS ?? 0),detail:"\(execution.schedulerDispatchSlotsMissedDatabase ?? 0) dispatch slots missed",state:(execution.schedulerDispatchSlotsMissedDatabase ?? 0)>0 ? "WAITING":"CURRENT")
                        SchedulerMetricCard(title:"Estate Snapshot",value:execution.estateSnapshotDurationMS.map{String(format:"%.0f ms",$0)} ?? "—",detail:"Dispatch is not blocked by monitor projection",state:nil)
                        SchedulerMetricCard(title:"Publication",value:execution.publicationDurationMS.map{String(format:"%.0f ms",$0)} ?? "—",detail:"Runs after worker allocation",state:nil)
                        SchedulerMetricCard(title:"Throughput Limited By",value:(execution.throughputLimitedBy ?? "NONE").replacingOccurrences(of:"_",with:" ").capitalized,detail:"Exact current limiter",state:execution.throughputLimitedBy=="NONE" ? "CURRENT":"WAITING")
                        if twelve?.last429At != nil { SchedulerMetricCard(title:"Credit Window Exhausted",value:"Resumes at \(SchedulerFormatting.timestamp(twelve?.windowEndsAt))",detail:"Last HTTP 429 \(SchedulerFormatting.timestamp(twelve?.last429At))",state:"WAITING") }
                    }
                    Divider()
                    HStack {
                        Text("Trace Lane").font(.headline)
                        TextField("SYMBOL:TIMEFRAME",text:$traceLane).textFieldStyle(.roundedBorder).frame(width:210)
                        Spacer()
                    }
                    let normalized=traceLane.trimmingCharacters(in:.whitespacesAndNewlines).uppercased()
                    if let trace=execution.traceSummaries.first(where:{$0.lane==normalized}) {
                        Facts([
                            ("Current stage",trace.currentStage ?? "—"),
                            ("Last transition",trace.lastSuccessfulStage ?? "—"),
                            ("Stop reason",trace.stopReason ?? "None"),
                            ("Queue age",age(trace.queueAgeSeconds)),
                            ("Attempt count","\(trace.attemptCount)"),
                            ("Provider",trace.provider ?? "—"),
                            ("Canonical edge", "\(SchedulerFormatting.timestamp(trace.canonicalEdgeBefore)) → \(SchedulerFormatting.timestamp(trace.canonicalEdgeAfter))"),
                        ])
                    } else {
                        Text("No execution trace exists for \(normalized.isEmpty ? "this lane":normalized).").foregroundStyle(.secondary)
                    }
                }.padding(.vertical,4)
            } else {
                Text("No completed execution cycle has been published.").foregroundStyle(.secondary)
            }
        }
    }

    private func age(_ seconds:Double?)->String {
        guard let seconds else{return "—"}
        let total=max(0,Int(seconds)),hours=total/3600,minutes=(total%3600)/60
        return hours>0 ? "\(hours)h \(minutes)m":"\(minutes)m"
    }

    private func pauseMenu(_ snapshot:SchedulerSnapshot)->some View {
        let active=snapshot.pauseRecords.filter{["PAUSE_REQUESTED","DRAINING_ACTIVE_WORK","PAUSED"].contains($0.status)}
        return Menu(active.isEmpty ? "Pause Acquisition":"Acquisition Paused") {
            Button("Pause All"){Task{await store.pauseAcquisition(scopeType:"ALL",scopeIdentifier:nil)}}
            Menu("Pause Group") { ForEach(["Forex","Metals","Energy","Indices","Stocks","Crypto"],id:\.self){group in Button(group){Task{await store.pauseAcquisition(scopeType:"MARKET_OR_GROUP",scopeIdentifier:group)}}} }
            Menu("Pause Symbol") { ForEach(Array(Set(snapshot.lanes.map(\.symbol))).sorted(),id:\.self){symbol in Button(symbol){Task{await store.pauseAcquisition(scopeType:"SYMBOL",scopeIdentifier:symbol)}}} }
            if !active.isEmpty { Divider();ForEach(active){record in Button("Resume \(record.scopeIdentifier)"){Task{await store.resumeAcquisition(record)}}} }
        }
    }

    @ViewBuilder private func exceptionDrilldown(_ snapshot:SchedulerSnapshot,title:String)->some View {
        let identifiers=Set(snapshot.exceptionFilters[title] ?? [])
        GroupBox {
            VStack(alignment:.leading,spacing:10) {
                HStack { Text(title).font(.title2.bold());Spacer();Button("Close"){selectedException=nil} }
                if title=="Manual Required" {
                    Text("\(snapshot.manualRequestCount) requests · \(snapshot.manualRequestUniqueLanes) lanes · \(snapshot.manualRequestUniqueSymbols) symbols").foregroundStyle(.secondary)
                    ForEach(snapshot.manualRequests.filter{identifiers.contains($0.id)}){request in
                        HStack(alignment:.top){VStack(alignment:.leading,spacing:3){Text("\(request.symbol) · \(request.timeframe)").fontWeight(.semibold);Text("\(request.missingStart) → \(request.missingEnd)").font(.caption.monospaced());Text("Reason: \(request.reconciliationReason ?? request.reason) · Age \(request.requestAgeSeconds.map{durationAge($0)} ?? "unknown")").font(.caption);Text("Created from provider facts: revision \(request.createdProviderFactRevision.map { String($0) } ?? "legacy")").font(.caption).foregroundStyle(.secondary);Text("Last evaluated: \(SchedulerFormatting.timestamp(request.lastEvaluatedAt)) · current provider facts: revision \(request.lastEvaluatedProviderFactRevision.map { String($0) } ?? "unknown")").font(.caption).foregroundStyle(.secondary);Text("Reconciliation status: \(formattedStatus(request.reconciliationStatus ?? "NOT_EVALUATED"))").font(.caption).foregroundStyle(.secondary);Text("Providers currently eligible: \((request.providersCurrentlyEligible ?? []).isEmpty ? "None" : (request.providersCurrentlyEligible ?? []).joined(separator:", "))").font(.caption).foregroundStyle(.secondary);Text("Providers currently ineligible: \((request.providersCurrentlyIneligible ?? request.providersRejected ?? []).map{"\($0.provider): \($0.reason ?? "INELIGIBLE")"}.joined(separator:"; "))").font(.caption).foregroundStyle(.secondary);Text("Providers actually attempted: \(request.providersAttempted.isEmpty ? "None":request.providersAttempted.joined(separator:", "))").font(.caption).foregroundStyle(.secondary);Text("Recommended action: \(formattedStatus(request.recommendedOperatorAction ?? "IMPORT_REVIEWED_MANUAL_EVIDENCE"))").font(.caption).foregroundStyle(.secondary);Text("Lifecycle \(request.instrumentLifecycleState ?? "Unknown") · Lane \(request.laneCommissioningState ?? "Unknown") · Pause \(request.pauseState ?? "None")").font(.caption).foregroundStyle(.secondary);if let failure=request.latestFailure{Text("Latest failure: \(failure.provider) · \(failure.reason)").font(.caption).foregroundStyle(.red)}};Spacer();Button("Retry Now"){Task{await store.retryManualRequest(request.id)}};Button("Open Acquire & Import"){store.openManualRequest(request)};Button("Open Lane Detail"){selectedLaneID="\(request.symbol):\(request.timeframe)"};Button("Open History"){store.marketHistorySymbol=request.symbol;store.section = .history}}
                        Divider()
                    }
                } else if title=="Unavailable" {
                    Text("\(snapshot.unavailableLaneDetails.count) commissioned lanes").foregroundStyle(.secondary)
                    ForEach(snapshot.unavailableLaneDetails.filter{identifiers.contains($0.id)}){lane in
                        HStack(alignment:.top){VStack(alignment:.leading,spacing:3){Text("\(lane.symbol) · \(lane.timeframe)").fontWeight(.semibold);Text("\(lane.market ?? "Unknown market") · \(lane.structuredReason)");Text("Latest \(SchedulerFormatting.timestamp(lane.latestCanonicalEdge)) · Expected \(SchedulerFormatting.timestamp(lane.expectedEdge))").font(.caption.monospaced()).foregroundStyle(.secondary);Text("Calendar \(lane.calendarIdentifier ?? "Unavailable") · \(lane.calendarStatus ?? "Unknown") · \(lane.timezone ?? "Unknown timezone")").font(.caption);Text(lane.exactFailureReason ?? lane.recommendedAction).font(.caption).foregroundStyle(.secondary)};Spacer();Button("Open Lane Detail"){selectedLaneID=lane.id};Button("Open System Diagnostics"){store.manageDataSection = .system;store.section = .manageData}}
                        Divider()
                    }
                } else {
                    let queue=snapshot.acquisitionQueue.filter{identifiers.contains($0.id)}
                    let lanes=snapshot.lanes.filter{identifiers.contains($0.id)}
                    Text("\(queue.count) requests · \(lanes.count) lanes · \(Set((queue.map(\.symbol)+lanes.map(\.symbol))).count) symbols").foregroundStyle(.secondary)
                    ForEach(queue){item in HStack{Text(item.lane).fontWeight(.semibold);Text(item.operationalState ?? "Ready");Text(item.waitingReason ?? item.queueReason).font(.caption).foregroundStyle(.secondary);Spacer();Button("Open Lane Detail"){selectedLaneID=item.lane}}}
                    ForEach(lanes){lane in HStack{Text(lane.id).fontWeight(.semibold);Text(lane.schedulerState);Text(lane.reason ?? "No exception reason").font(.caption).foregroundStyle(.secondary);Spacer();Button("Open Lane Detail"){selectedLaneID=lane.id}}}
                    if queue.isEmpty && lanes.isEmpty { Text("No contributing objects.").foregroundStyle(.secondary) }
                }
            }.frame(maxWidth:.infinity,alignment:.leading)
        }
    }

    private func durationAge(_ seconds:Double)->String { let total=Int(seconds);if total >= 3600{return "\(total/3600)h \((total%3600)/60)m"};if total >= 60{return "\(total/60)m \(total%60)s"};return "\(total)s" }
    private func stateColor(_ value:String)->Color {
        switch value.uppercased(){case "CURRENT","RUNNING","SUCCESS","HEALTHY","READY","AVAILABLE":.green;case "WAITING","WAITING FOR BUDGET","BEHIND","NO_NEW_DATA","DEGRADED","COOLING DOWN","RATE LIMITED":.orange;case "FAILED","BLOCKED","MANUAL REQUIRED","UNAVAILABLE","CREDENTIAL MISSING","AUTHENTICATION FAILED","QUOTA EXCEEDED","ENTITLEMENT BLOCKED","INVALID","EXPIRED":.red;default:.secondary}
    }

    @ViewBuilder private func providerHealth(_ snapshot:SchedulerSnapshot)->some View {
        VStack(alignment:.leading,spacing:10) {
            Text("Provider Health").font(.title2.bold())
            if snapshot.providers.isEmpty { Text("Provider metadata is unavailable in this version 1 recovery snapshot.").foregroundStyle(.secondary) }
            else { ForEach(snapshot.providers) { provider in let budget=snapshot.rateBudgets.first{$0.provider==provider.provider};GroupBox { Grid(alignment:.leading,horizontalSpacing:18,verticalSpacing:6) { GridRow { Text(provider.provider).font(.headline);Text(provider.providerWaitReason?.replacingOccurrences(of:"_",with:" ").capitalized ?? provider.health).foregroundStyle(stateColor(provider.health));Spacer();Text(provider.budgetPolicy ?? "Rate Policy Unverified").foregroundStyle(provider.ratePolicyVerified == true ? Color.secondary:Color.orange) };GridRow { Text("Credential State").foregroundStyle(.secondary);Text(provider.credentialState ?? provider.credentials);Text("Authority Revision").foregroundStyle(.secondary);Text(String((provider.credentialAuthorityRevision ?? "Unknown").prefix(12))).font(.caption.monospaced());Text("Validation Source").foregroundStyle(.secondary);Text(provider.credentialValidationSource ?? "Unknown") };GridRow { Text("Last Validation").foregroundStyle(.secondary);Text(SchedulerFormatting.timestamp(provider.credentialLastValidation));Text("Configured capacity").foregroundStyle(.secondary);Text("\(provider.requestLimit) \(provider.budgetUnit ?? "units") / \(provider.requestWindowSeconds)s");Text("Adaptive target").foregroundStyle(.secondary);Text("\(provider.adaptiveTarget ?? 0) · \(provider.targetUtilizationPercent ?? 0)%") };GridRow { Text("Actual calls dispatched").foregroundStyle(.secondary);Text("\(provider.actualDispatchedCalls ?? provider.budgetUsed ?? 0)");Text("Dispatch available").foregroundStyle(.secondary);Text("\(provider.dispatchAvailable ?? 0)");Text("Active reservations").foregroundStyle(.secondary);Text("\(provider.capacityReserved ?? 0) in \(provider.activeReservations ?? 0)") };GridRow { Text("Responses / rate limits").foregroundStyle(.secondary);Text("\(provider.responsesReceived ?? 0) / \(provider.rateLimitResponses ?? 0)");Text("Transient failures").foregroundStyle(.secondary);Text("\(provider.transientFailures ?? 0)");Text("Budget available").foregroundStyle(.secondary);Text("\(provider.budgetAvailable ?? budget?.callsAvailable ?? 0)") };GridRow { Text("Next local budget release").foregroundStyle(.secondary);Text(SchedulerFormatting.timestamp(provider.nextBudgetRelease ?? budget?.nextAvailable));Text("Wait scope").foregroundStyle(.secondary);Text(provider.providerWaitScope ?? "—");Text("Active requests").foregroundStyle(.secondary);Text("\(provider.activeRequests ?? 0) / \(provider.concurrencyLimit ?? 1)") };GridRow { Text("Wait expiry").foregroundStyle(.secondary);Text(SchedulerFormatting.timestamp(provider.cooldownUntil));Text("Last success").foregroundStyle(.secondary);Text(SchedulerFormatting.timestamp(provider.lastSuccess));Text("Last failure").foregroundStyle(.secondary);Text(SchedulerFormatting.timestamp(provider.lastFailure)) } }.frame(maxWidth:.infinity,alignment:.leading) } } }
        }
    }

    @ViewBuilder private func acquisitionQueue(_ snapshot:SchedulerSnapshot)->some View {
        VStack(alignment:.leading,spacing:10) { Text("Acquisition Queue").font(.title2.bold());if snapshot.acquisitionQueue.isEmpty { Text("No acquisition work is queued.").foregroundStyle(.secondary) } else { ForEach(snapshot.acquisitionQueue) { item in GroupBox { HStack { VStack(alignment:.leading,spacing:4) { HStack{Text(item.lane).fontWeight(.semibold);Text(item.workClass ?? "QUEUE").font(.caption.bold()).padding(.horizontal,6).padding(.vertical,2).background(.quaternary,in:Capsule());Text(item.operationalState ?? "Ready").foregroundStyle(stateColor(item.operationalState ?? "Ready"))};Text("\(item.missingRange.start ?? "No canonical edge") → \(item.missingRange.end)").font(.caption.monospaced());Text(item.waitingReason ?? item.queueReason).font(.caption).foregroundStyle(.secondary) };Spacer();VStack(alignment:.trailing,spacing:4) { Text(item.selectedProvider ?? "Routing pending");Text("Fallback \(item.fallbackPosition) · \(item.estimatedRequests) request(s)").font(.caption);Text("Next \(SchedulerFormatting.timestamp(item.nextAttempt))").font(.caption).foregroundStyle(.secondary);Button("Retry Now"){Task{await store.retrySchedulerLane(item.lane)}}.disabled(item.operationalState == "Running") } } } } } }
    }

    @ViewBuilder private func manualRequests(_ snapshot:SchedulerSnapshot)->some View {
        VStack(alignment:.leading,spacing:10) { Text("Manual Acquisition Requests").font(.title2.bold());if snapshot.manualRequests.isEmpty { Text("No operator-supplied evidence is required.").foregroundStyle(.secondary) } else { ForEach(snapshot.manualRequests) { request in GroupBox { HStack(alignment:.top) { VStack(alignment:.leading,spacing:4) { Text("\(request.symbol) · \(request.timeframe)").fontWeight(.semibold);Text("\(request.missingStart) → \(request.missingEnd)").font(.caption.monospaced());Text("\(request.reconciliationReason ?? request.reason) · \(request.status) · created \(SchedulerFormatting.timestamp(request.createdAt))").font(.caption).foregroundStyle(.secondary);Text("Created from provider facts: revision \(request.createdProviderFactRevision.map { String($0) } ?? "legacy")").font(.caption).foregroundStyle(.secondary);Text("Last evaluated \(SchedulerFormatting.timestamp(request.lastEvaluatedAt)) · current provider facts revision \(request.lastEvaluatedProviderFactRevision.map { String($0) } ?? "unknown")").font(.caption).foregroundStyle(.secondary);Text("Reconciliation: \(formattedStatus(request.reconciliationStatus ?? "NOT_EVALUATED"))").font(.caption).foregroundStyle(.secondary);Text("Eligible now: \((request.providersCurrentlyEligible ?? []).isEmpty ? "None" : (request.providersCurrentlyEligible ?? []).joined(separator:", "))").font(.caption);Text("Ineligible now: \((request.providersCurrentlyIneligible ?? request.providersRejected ?? []).map{"\($0.provider): \($0.reason ?? "INELIGIBLE")"}.joined(separator:"; "))").font(.caption).foregroundStyle(.secondary);Text("Actually attempted: \(request.providersAttempted.isEmpty ? "None" : request.providersAttempted.joined(separator:", "))").font(.caption);Text("Next action: \(formattedStatus(request.recommendedOperatorAction ?? "IMPORT_REVIEWED_MANUAL_EVIDENCE"))").font(.caption).foregroundStyle(.secondary);if let failure=request.latestFailure{Text("Latest failure: \(failure.provider) · \(failure.reason)").font(.caption).foregroundStyle(.red)}};Spacer();Button("Retry Now"){Task{await store.retryManualRequest(request.id)}}.disabled(!["Required","Acknowledged"].contains(request.status));Button("Open Manage Data"){store.openManualRequest(request)};Button("Acknowledge"){Task{await store.acknowledgeManualRequest(request.id)}}.disabled(request.status != "Required");Button("Dismiss",role:.destructive){Task{await store.dismissManualRequest(request.id)}}.disabled(!["Required","Acknowledged"].contains(request.status)) } } } } }
    }

    private func laneDetail(_ lane:SchedulerLane)->some View {
        let considered = lane.providersConsidered.map { decision in
            let representation = decision.providerRepresentation ?? decision.providerSymbol ?? "no approved representation"
            let capability = decision.mappingClass ?? decision.mappingStatus ?? "capability unknown"
            let policy = decision.routingPolicy ?? "default routing"
            let quote = decision.quoteEquivalenceReason ?? "exact quote"
            let rank = decision.fallbackRank.map { "fallback \($0)" } ?? (decision.reason ?? "rejected")
            return "\(decision.provider) [\(representation); \(capability); \(quote); \(policy); \(rank)]"
        }.joined(separator:"; ")
        let capabilities = lane.providerCapabilities.map { "\($0.provider): \(formattedStatus($0.capabilityState))" }.joined(separator:"; ")
        let rejected = lane.providersRejected.map { "\($0.provider): \($0.reason ?? "INELIGIBLE")" }.joined(separator:"; ")
        let publication = "\(formattedStatus(lane.publicationState ?? "PUBLISHED")) · " + (lane.publicationResult.map { "\($0.displayStatus) via \($0.provider) · \($0.inserted) inserted · \(formattedStatus($0.mappingClass ?? "mapping not recorded"))" } ?? "no Scheduler publication receipt")
        let facts = [("Market",lane.market ?? "—"),("Lifecycle",lane.lifecycleState ?? "ACTIVE"),("Freshness",lane.operationalState ?? lane.schedulerState),("Pause",lane.pauseState ?? "Not paused"),("Routing decision",lane.routingDecision ?? "Not routed"),("Current provider",lane.currentProvider ?? "—"),("Providers considered",considered),("Provider capability",capabilities),("Providers rejected",rejected),("Publication",publication),("Manual request",lane.manualRequest ?? "—")]
        return GroupBox("Lane Detail — \(lane.id)") { VStack(alignment:.leading,spacing:8) { HStack{Text(lane.reason ?? "No blocking reason").foregroundStyle(.secondary);Spacer();if lane.pauseState==nil{Button("Pause Symbol"){Task{await store.pauseAcquisition(scopeType:"SYMBOL",scopeIdentifier:lane.symbol)}}};Button("Retry Now"){Task{await store.retrySchedulerLane(lane.id)}}.disabled(lane.schedulerState == "Current" || lane.schedulerState == "Running" || lane.pauseState != nil)};Facts(facts);if !lane.attemptHistory.isEmpty { Divider();Text("Attempt history").font(.headline);ForEach(lane.attemptHistory.prefix(10)){attempt in Text("\(SchedulerFormatting.timestamp(attempt.at)) · \(attempt.provider) · \(attempt.reason) · \(SchedulerFormatting.duration(attempt.durationSeconds))").font(.caption.monospaced())} } }.frame(maxWidth:.infinity,alignment:.leading) }
    }

    private func formattedStatus(_ value:String)->String { value.replacingOccurrences(of:"_",with:" ").capitalized }
}
