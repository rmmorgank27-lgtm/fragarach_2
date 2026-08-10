import Foundation
import OperationsCore
import SwiftUI

struct EstateAdmissionProgress: Equatable {
    let symbol: String
    let timeframes: [String]
    let startedAt: Date
    var stage: String
    var activeTimeframe: String?
}

@MainActor final class ConsoleStore: ObservableObject {
    @AppStorage("databasePath") var databasePath = "/Users/raymorgan/VSC/Fragarach_2/data/runtime/spec002_real_evidence_acceptance.sqlite3"
    @AppStorage("repositoryPath") var repositoryPath = "/Users/raymorgan/VSC/Fragarach_2"
    @AppStorage("pythonPath") var pythonPath = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    @Published var section: ConsoleSection = .overview
    @Published var dataOperationsMode: DataOperationsMode = .fetch
    @Published var systemSection: SystemSection = .status
    @Published var manageDataSection: ManageDataSection = .operations
    @Published var auditFilter = ""
    @Published var snapshot: AuthoritySnapshot?
    @Published var operationalMetrics:OperationalMetricsSnapshot?
    @Published var operationalMetricsError:String?
    @Published var estateTruth: EstateTruthState?
    @Published var estateHierarchy: EstateHierarchy?
    @Published var selectedTruthLaneID: String?
    @Published var truthNavigationRequestID: String?
    @Published var estateConditionFilter: String?
    @Published var estateTruthError: String?
    @Published var selectedLaneID: String?
    @Published var selectedOperationID: String?
    @Published var readError: String?
    @Published var isRefreshing=false
    @Published var activeOperationID: UUID?
    @Published var activeOperationOwner:String?
    @Published var activeOperationStartedAt:Date?
    @Published var activeOperationState:String?
    @Published var activeDataOperation: ActiveDataOperation?
    @Published var dataOperationState: DataOperationState = .idle
    @Published var activeOperationProvider:String?
    @Published var activeOperationNextProvider:String?
    @Published var activeOperationFallbackPosition:Int?
    @Published var activeOperationFallbackCount:Int?
    @Published var estateAdmissionProgressBySymbol: [String:EstateAdmissionProgress] = [:]
    @Published var lastProcessResult: ProcessResult?
    @Published var currentPlanRevision=UUID()
    @Published var currentOperationResult: OwnedOperationResult?
    @Published var operationError: String?
    @Published var acquisitionAsset: String?
    @Published var acquisitionTimeframe: String?
    @Published var acquisitionFrom: String?
    @Published var acquisitionThrough: String?
    @Published var marketDiscoveryRequest: String?
    @Published var marketHistorySymbol = "AUDUSD"
    @Published var marketHistoryTradingDays = 5
    @Published var marketHistoryResponses: [String:MarketHistoryResponse] = [:]
    @Published var marketHistoryError: String?
    @Published var estateAuditHistory:EstateAuditHistory?
    @Published var estateAuditHistoryError:String?
    @Published var estateAuditHistoryLoading=false
    @Published var syntheticSnapshot:SyntheticSnapshot?
    @Published var syntheticError:String?
    @Published var schedulerSnapshot: SchedulerSnapshot?
    @Published var schedulerServiceStatus:SchedulerServiceStatus?
    @Published var schedulerServiceDiagnostics:SchedulerServiceDiagnostics?
    @Published var schedulerDiagnosticsError:String?
    @Published var schedulerError: String?
    @Published var schedulerActionInProgress: String?
    @Published var schedulerActionMessage: String?
    @Published var schedulerActionFailed = false
    @Published var schedulerUsesCompactStatus = false
    @Published var schedulerRegisterFilter: String?
    @Published var credentialAuthority:CredentialAuthoritySnapshot?
    @Published var schedulerServiceRunning = false
    @Published var providerFacts:ProviderFactsSnapshot?
    @Published var providerFactsError:String?
    @Published var providerFactsResolving=false
    @Published var providerCredentialRepairRequested=false
    @Published var latestProviderProbe:ProviderCapabilityProbe?
    @Published var readOnlyClientsSnapshot:ReadOnlyClientsSnapshot?
    @Published var readOnlyClientsError:String?
    @Published var readOnlyClientsBusy=false
    @Published var readOnlyIssuedToken:String?
    // SQLite serialises the short canonical admission transaction, so a
    // manual file normally coexists with scheduled acquisition.  A pause is
    // retained as an explicit operator option for exceptional investigations.
    @Published var pauseScheduledAcquisitionWhileImporting = false
    @Published var manualIngestionPauseScope = "SYMBOL"
    @Published var resumeAfterManualImport = true
    @Published var manualIngestionHoldMessage:String?
    private let reader=SQLiteReadService(); let bridge=ProcessBridge(); private let authorityReadBridge=ProcessBridge()
    private let marketDiscoveryBridge=ProcessBridge()
    private let marketHistoryBridge=ProcessBridge()
    private let auditHistoryBridge=ProcessBridge()
    private let schedulerServiceClient=SchedulerServiceClient()
    private let schedulerLifecycleBridge=ProcessBridge()
    private let schedulerDiagnosticsBridge=ProcessBridge()
    private let providerFactsBridge=ProcessBridge()
    private let readOnlyClientsBridge=ProcessBridge()
    private let readOnlyClientsStatusBridge=ProcessBridge()
    private var schedulerMonitorTask:Task<Void,Never>?
    private var estateRefreshTask:Task<Void,Never>?
    private var estateRefreshTargetToken:String?
    private var lastEstateProjectionToken:String?
    private let staleOperationInterval:TimeInterval = 10 * 60
    var configuration: CLIConfiguration { .init(python:pythonPath,repository:repositoryPath,database:databasePath) }
    var credentialAvailable: Bool { credentialAuthority?.providers.first(where:{$0.provider=="TWELVE_DATA"})?.credentialState == "Available" }
    var dataOperationIsActive: Bool { dataOperationState.isActive }
    var schedulerAcquisitionIsActive: Bool { schedulerSnapshot?.activeActivity != nil }
    var estateAdmissionProgresses: [EstateAdmissionProgress] {
        estateAdmissionProgressBySymbol.values.sorted {
            if $0.startedAt == $1.startedAt { return $0.symbol < $1.symbol }
            return $0.startedAt < $1.startedAt
        }
    }
    var estateProjectionNeedsRefresh: Bool {
        guard let token=schedulerServiceStatus?.authorityChangeToken else { return estateTruth == nil }
        return lastEstateProjectionToken != token
    }
    func schedulerAcquisitionIsActive(symbol:String?,timeframe:String?=nil) -> Bool {
        guard let activity=schedulerSnapshot?.activeActivity,
              activity.symbol==symbol else { return false }
        return timeframe == nil || activity.timeframe == timeframe
    }
    func beginEstateAdmission(
        symbol:String,timeframes:[String],stage:String="Initial history queued"
    ) {
        let lanes=timeframes.isEmpty ? ["D1"]:timeframes
        let canonicalSymbol=symbol.uppercased()
        estateAdmissionProgressBySymbol[canonicalSymbol] = .init(
            symbol:canonicalSymbol, timeframes:lanes, startedAt:Date(),
            stage:stage, activeTimeframe:nil
        )
    }
    func endEstateAdmission(symbol:String) {
        estateAdmissionProgressBySymbol.removeValue(forKey:symbol.uppercased())
    }
    func estateAdmissionProgress(for symbol:String?) -> EstateAdmissionProgress? {
        guard let symbol else{return nil}
        return estateAdmissionProgressBySymbol[symbol.uppercased()]
    }
    var activeOperationAgeSeconds:Double? {
        activeOperationStartedAt.map { Date().timeIntervalSince($0) }
    }
    var activeOperationIsStale:Bool {
        guard activeOperationID != nil,
              let age=activeOperationAgeSeconds else { return false }
        return age >= staleOperationInterval && !bridge.isActive
    }

    init() {
        let arguments=CommandLine.arguments
        if let modeIndex=arguments.firstIndex(of:"--mode"),arguments.indices.contains(modeIndex+1),arguments[modeIndex+1].lowercased()=="market-history" { section = .history }
        if let symbolIndex=arguments.firstIndex(of:"--symbol"),arguments.indices.contains(symbolIndex+1) { marketHistorySymbol=arguments[symbolIndex+1].uppercased() }
    }

    func startup() async {
        await refreshCredentialAuthority()
        // The scheduler monitor is an indexed, bounded operational projection.
        // Publish it first so the console is useful while the complete Estate
        // Truth projection is building in the background.
        // Startup itself owns the initial Estate read. Suppressing the token
        // callback here prevents a second identical 26-second projection from
        // being queued before the first one has even started.
        await refreshSchedulerStatus(scheduleEstateRefresh:false)
        startSchedulerMonitor()
        // Startup is observational. Provider resolution and queue dispatch are
        // explicit workflows, while the resident Scheduler already owns due
        // work. Re-running both here caused competing Python jobs on every app
        // launch and delayed the first usable screen.
        if let status=schedulerServiceStatus,!schedulerPermitsEstateProjection(status) {
            // The compact Scheduler status is already useful. Delay the full
            // authority projection until catch-up has no running or due work.
            refreshEstateProjectionIfNeeded(for:status)
            await refreshProviderFacts()
        } else {
            async let authorityRefresh: Void = refresh()
            await refreshProviderFacts()
            await authorityRefresh
        }
    }

    func startScheduler() {
        Task { await manageSchedulerService("start") }
    }

    func showBlockedSchedulerLanes() {
        schedulerRegisterFilter = "BLOCKED"
        section = .scheduler
    }

    func stopScheduler(){Task { await manageSchedulerService("stop") }}
    func restartScheduler(){Task { await manageSchedulerService("restart") }}
    func installScheduler(){Task { await manageSchedulerService("install") }}
    func repairScheduler(){Task { await manageSchedulerService("repair") }}
    func repairSchedulerMonitor(){Task { await manageSchedulerService("repair-monitor") }}
    func uninstallScheduler(){Task { await manageSchedulerService("uninstall") }}
    func forceReconcileScheduler(){Task { await manageSchedulerService("force-reconcile") }}
    func manageSchedulerServiceFromUI(_ action:String) async { await manageSchedulerService(action) }
    func disconnectSchedulerMonitor(){schedulerMonitorTask?.cancel();schedulerMonitorTask=nil}

    private func startSchedulerMonitor() {
        schedulerMonitorTask?.cancel()
        schedulerMonitorTask=Task { [weak self] in
            while !Task.isCancelled {
                await self?.refreshSchedulerStatus()
                guard let self else{return}
                let busy=self.activeOperationID != nil
                    || self.schedulerSnapshot?.activeActivity != nil
                    || (self.schedulerServiceStatus?.operationalHealth?.workerPool.activeWorkers ?? 0) > 0
                    || self.schedulerServiceStatus?.activeMutation != nil
                    || !self.estateAdmissionProgressBySymbol.isEmpty
                try? await Task.sleep(for:.seconds(busy ? 2:15))
            }
        }
    }

    func refresh() async {
        guard !isRefreshing else{return}; isRefreshing=true; defer{isRefreshing=false}
        // Mark exactly the authority revision this read was intended to
        // project. If D1 publication advances while the read is running, the
        // monitor will retain the newer token and schedule one trailing read.
        let projectionToken=schedulerServiceStatus?.authorityChangeToken
        await refreshOperationalMetrics()
        do {
            let loaded=try await loadAuthorityState()
            commitAuthorityState(loaded)
            if let projectionToken { lastEstateProjectionToken=projectionToken }
        } catch { estateTruthError=error.localizedDescription;readError=error.localizedDescription }
    }

    private func refreshOperationalMetrics() async {
        let reader=self.reader,path=databasePath
        for attempt in 0..<2 {
            do {
                operationalMetrics=try await Task.detached { try reader.loadOperationalMetrics(path:path) }.value
                operationalMetricsError=nil
                return
            } catch {
                let message=error.localizedDescription.lowercased()
                let transientContention=message.contains("database is locked")
                    || message.contains("database is busy")
                    || message.contains("unable to open database file")
                if attempt == 0 && transientContention && !Task.isCancelled {
                    try? await Task.sleep(nanoseconds:750_000_000)
                    continue
                }
                operationalMetricsError=error.localizedDescription
                return
            }
        }
    }

    /// Price History is a local, read-only operational projection. Keeping it
    /// out of ProcessBridge guarantees it cannot start Echo, research,
    /// acquisition, or a governed-data mutation.
    func loadPriceHistoryOverview(symbol: String, timeframe: String) async throws -> PriceHistoryOverview {
        let reader = self.reader, path = databasePath
        return try await Task.detached { try reader.loadPriceHistory(path: path, symbol: symbol, timeframe: timeframe) }.value
    }

    func run(_ intent:OperationIntent) async {
        releaseStaleOperationLockIfSafe()
        guard activeOperationID==nil else{
            lastProcessResult=nil
            operationError=activeOperationStatusMessage()
            return
        }
        var ingestionSession:String?
        func releaseManualIngestionPauseIfNeeded() async {
            guard let session=ingestionSession,resumeAfterManualImport else{return}
            await performSchedulerControl(.resumeAcquisition(pauseIdentifier:nil,scopeType:nil,scopeIdentifier:nil,ingestionSession:session))
            manualIngestionHoldMessage=nil
        }
        if case .importCSV(_,let symbol,_,_,_,_,_) = intent, pauseScheduledAcquisitionWhileImporting {
            let session=UUID().uuidString;ingestionSession=session
            let group=estateHierarchy?.markets.first(where:{$0.lanes.contains(where:{$0.symbol==symbol})})?.name
            let scopeIdentifier=manualIngestionPauseScope=="ALL" ? nil:manualIngestionPauseScope=="MARKET_OR_GROUP" ? group:symbol
            await performSchedulerControl(.pauseAcquisition(scopeType:manualIngestionPauseScope,scopeIdentifier:scopeIdentifier,reason:"MANUAL_INGESTION",temporary:true,ingestionSession:session))
            manualIngestionHoldMessage="Waiting for scheduled acquisition to pause"
            for _ in 0..<120 {
                await refreshSchedulerStatus()
                let hold=schedulerSnapshot?.pauseRecords.first{$0.relatedIngestionSession==session && ["PAUSED","DRAINING_ACTIVE_WORK"].contains($0.status)}
                if hold?.status=="PAUSED" { manualIngestionHoldMessage="Scheduled acquisition paused · Safe to publish manual evidence";break }
                try? await Task.sleep(for:.milliseconds(250))
            }
            guard schedulerSnapshot?.pauseRecords.first(where:{$0.relatedIngestionSession==session})?.status=="PAUSED" else {
                operationError="Manual publication is unavailable until scheduled acquisition is quiescent."
                await releaseManualIngestionPauseIfNeeded()
                return
            }
        }
        guard !(intent.isAuthorityMutation && !intent.isManualImport && !intent.mayRunDuringSchedulerAcquisition)
                || !schedulerAcquisitionIsActive else {
            operationError="A scheduled acquisition is publishing authority. Try again when the active lane completes."
            await releaseManualIngestionPauseIfNeeded()
            return
        }
        operationError=nil
        let id=UUID(),revision=currentPlanRevision
        activeOperationID=id
        activeOperationStartedAt=Date()
        activeOperationOwner=operationOwner(for:intent)
        activeOperationState="Preparing"
        if let context=intent.dataOperationContext {
            activeDataOperation = .init(id:id,instrument:context.instrument,timeframe:context.timeframe,actionLabel:context.actionLabel)
            dataOperationState = .preparing
            activeOperationState=dataOperationState.stageLabel
            activeOperationProvider=nil;activeOperationNextProvider=nil;activeOperationFallbackPosition=nil;activeOperationFallbackCount=nil
        }
        QuitGuard.shared.begin { [weak self] in self?.bridge.cancel() }
        defer {
            QuitGuard.shared.end()
            finishOperationLock(id)
        }
        do {
            let config=configuration,bridge=self.bridge
            let (stream,continuation)=AsyncStream<DataOperationState>.makeStream()
            let progressTask=Task { [weak self] in
                for await state in stream where state.isActive {
                    self?.dataOperationState=state
                    self?.activeOperationState=state.stageLabel
                }
            }
            let result=try await Task.detached {
                try bridge.validateCLI(config)
                return try bridge.run(intent,config:config,progress:{continuation.yield($0)},progressDetail:{detail in
                    Task { @MainActor [weak self] in
                        self?.activeOperationProvider=detail.provider
                        self?.activeOperationNextProvider=detail.nextProvider
                        self?.activeOperationFallbackPosition=detail.fallbackPosition
                        self?.activeOperationFallbackCount=detail.fallbackCount
                    }
                })
            }.value
            continuation.finish()
            await progressTask.value
            lastProcessResult=result
            currentOperationResult = .init(planRevision:revision,result:result)
            if result.exitCode == 0 {
                if activeDataOperation != nil { dataOperationState = .completed;activeOperationState=dataOperationState.stageLabel }
            } else {
                operationError=result.stderr.isEmpty ? result.stdout:result.stderr
                if activeDataOperation != nil { dataOperationState = .failed;activeOperationState=dataOperationState.stageLabel }
            }
            // The operation is complete when its durable result returns. The
            // lightweight Scheduler status notices the authority token change
            // and owns the one coalesced Estate projection refresh; starting a
            // second full read here needlessly competes with onboarding work.
            Task { [weak self] in await self?.refreshSchedulerStatus() }
        } catch {
            operationError=error.localizedDescription
            if activeDataOperation != nil { dataOperationState = .failed;activeOperationState=dataOperationState.stageLabel }
        }
        await releaseManualIngestionPauseIfNeeded()
    }
    func discoverMarket(_ query:String) async throws -> MarketDiscoveryResult {
        // Discovery is a read-only command on its own bridge. SQLite WAL reads
        // safely coexist with the short registration writer, so searching for
        // the next symbol must not inherit the global mutation lock.
        let config=configuration,bridge=marketDiscoveryBridge
        return try await Task.detached {
            try bridge.validateCLI(config)
            let result=try bridge.run(.discoverMarket(query:query),config:config)
            guard result.exitCode==0 else {
                let detail=result.stderr.isEmpty ? result.stdout:result.stderr
                throw MarketDiscoveryReadError.serviceFailure(detail)
            }
            guard let data=result.stdout.data(using:.utf8),
                  let decoded=try? JSONDecoder().decode(MarketDiscoveryResult.self,from:data) else {
                throw BridgeError.malformedResult
            }
            return decoded
        }.value
    }
    func cancel(){bridge.cancel();activeOperationState="Cancelling"}
    func releaseStaleOperationLockIfSafe() {
        guard activeOperationIsStale else { return }
        let released=activeOperationStatusMessage()
        finishOperationLock(activeOperationID)
        operationError="Released stale operation lock. \(released)"
    }
    func activeOperationStatusMessage() -> String {
        let owner=activeOperationOwner ?? "Unknown operation"
        let state=activeOperationState ?? (bridge.isActive ? "Running":"No active process")
        let age=activeOperationAgeSeconds.map(formatAge) ?? "unknown age"
        let recovery=activeOperationIsStale ? " Safe recovery: clear stale operation." : " Recovery: cancel or wait for completion."
        return "Active mutation owner: \(owner). State: \(state). Age: \(age).\(recovery)"
    }
    private func finishOperationLock(_ id:UUID?) {
        guard id == nil || activeOperationID == id else { return }
        activeOperationID=nil
        activeOperationOwner=nil
        activeOperationStartedAt=nil
        activeOperationState=nil
    }
    private func formatAge(_ seconds:Double)->String {
        if seconds < 60 { return "\(Int(max(0, seconds)))s" }
        let minutes=Int(seconds/60)
        if minutes < 60 { return "\(minutes)m \(Int(seconds) % 60)s" }
        return "\(minutes/60)h \(minutes % 60)m"
    }
    private func operationOwner(for intent:OperationIntent)->String {
        switch intent {
        case .registerInstrument: return "Discover/Add registration"
        case .retirementPlan: return "Retirement review"
        case .retireInstrument: return "Retirement mutation"
        case .reactivateInstrument: return "Reactivation mutation"
        case .permanentRemovalPlan: return "Permanent removal review"
        case .permanentlyRemoveInstrument: return "Permanent removal mutation"
        case .acquire, .acquireInitial, .acquireUpdate, .acquireRequiredSet, .resumeRequiredSet: return "Provider acquisition"
        case .importCSV: return "Manual evidence import"
        case .validate: return "Lane validation"
        case .verify: return "Database verification"
        case .backup: return "Verified backup"
        case .runSchedulerQueue: return "Scheduler queue dispatch"
        case .queueLaneUpdate: return "Targeted lane update"
        case .runEstateAudit: return "Estate audit"
        case .setM5Freshness: return "M5 freshness settings"
        case .pauseAcquisition: return "Scheduler acquisition pause"
        case .resumeAcquisition: return "Scheduler acquisition resume"
        default: return "Fragarach operation"
        }
    }
    func requestMarketHistory(timeframes: [String] = ["D1", "H4", "H1", "M30", "M15", "M5"]) async {
        releaseStaleOperationLockIfSafe()
        guard activeOperationID == nil else { return }
        let config=configuration,bridge=self.marketHistoryBridge,symbol=marketHistorySymbol,tradingDays=marketHistoryTradingDays,requestedTimeframes=timeframes
        marketHistoryError=nil
        marketHistoryResponses=[:]
        do {
            let result:[String:MarketHistoryResponse] = try await Task.detached {
                try bridge.validateCLI(config)
                var responses:[String:MarketHistoryResponse]=[:]
                for timeframe in requestedTimeframes {
                    let process=try bridge.run(.marketHistory(symbol:symbol,timeframe:timeframe,tradingDays:tradingDays),config:config)
                    guard process.exitCode==0 else { throw BridgeError.malformedResult }
                    responses[timeframe]=try JSONDecoder().decode(MarketHistoryResponse.self,from:Data(process.stdout.utf8))
                }
                return responses
            }.value
            marketHistoryResponses=result
        } catch { marketHistoryError=error.localizedDescription }
    }
    func refreshSyntheticProducts() async {
        let config=configuration,bridge=self.marketHistoryBridge
        syntheticError=nil
        do {
            let result=try await Task.detached { try bridge.run(.readSyntheticProducts,config:config) }.value
            guard result.exitCode == 0 else { syntheticError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            syntheticSnapshot=try JSONDecoder().decode(SyntheticSnapshot.self,from:Data(result.stdout.utf8));syntheticError=nil
        } catch { syntheticError=error.localizedDescription }
    }
    func regenerateSyntheticProduct(_ id:String?=nil) async {
        let config=configuration,bridge=self.marketHistoryBridge
        syntheticError=nil
        do {
            let result=try await Task.detached { try bridge.run(.regenerateSyntheticProduct(id:id),config:config) }.value
            guard result.exitCode == 0 else { syntheticError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            await refreshSyntheticProducts()
        } catch { syntheticError=error.localizedDescription }
    }
    func rebuildSyntheticRepository() async {
        let config=configuration,bridge=self.marketHistoryBridge
        syntheticError=nil
        do {
            let result=try await Task.detached { try bridge.run(.rebuildSyntheticRepository,config:config) }.value
            guard result.exitCode == 0 else { syntheticError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            await refreshSyntheticProducts()
        } catch { syntheticError=error.localizedDescription }
    }

    func refreshReadOnlyClients(silently:Bool=false) async {
        guard !readOnlyClientsBusy else{return}
        if !silently {readOnlyClientsBusy=true;readOnlyClientsError=nil}
        defer{if !silently{readOnlyClientsBusy=false}}
        let config=configuration,bridge=readOnlyClientsStatusBridge
        do {
            let result=try await Task.detached { try bridge.run(.readOnlyClientsStatus,config:config) }.value
            guard result.exitCode==0 else {if !silently{readOnlyClientsError=result.stderr.isEmpty ? result.stdout:result.stderr};return}
            readOnlyClientsSnapshot=try JSONDecoder().decode(ReadOnlyClientsSnapshot.self,from:Data(result.stdout.utf8))
        } catch {if !silently{readOnlyClientsError=error.localizedDescription}}
    }

    func setReadOnlyPublisherEnabled(_ enabled:Bool) async {
        await performReadOnlyControl(.setReadOnlyPublisherEnabled(enabled))
    }

    func addReadOnlyClient(clientID:String,displayName:String,symbols:String,timeframes:String) async {
        await performReadOnlyControl(.addReadOnlyClient(clientID:clientID,displayName:displayName,symbols:symbols,timeframes:timeframes),capturesToken:true)
    }

    func setReadOnlyClientEnabled(_ clientID:String,enabled:Bool) async {
        await performReadOnlyControl(.setReadOnlyClientEnabled(clientID:clientID,enabled:enabled))
    }

    func revokeReadOnlyClient(_ clientID:String) async {
        await performReadOnlyControl(.revokeReadOnlyClient(clientID:clientID))
    }

    func rotateReadOnlyClientToken(_ clientID:String) async {
        await performReadOnlyControl(.rotateReadOnlyClientToken(clientID:clientID),capturesToken:true)
    }

    func setReplicaSyncPaused(_ clientID:String,paused:Bool) async {await performReadOnlyControl(.setReplicaSyncPaused(clientID:clientID,paused:paused))}
    func refreshReplicaClient(_ clientID:String) async {
        await performReadOnlyControl(.refreshReplicaClient(clientID:clientID))
        for _ in 0..<12 {
            if replicaRequestCompleted(clientID) { return }
            try? await Task.sleep(nanoseconds: 250_000_000)
            await refreshReadOnlyClients(silently:true)
        }
    }
    func setReplicaLanePaused(_ clientID:String,symbol:String,timeframe:String,paused:Bool) async {await performReadOnlyControl(.setReplicaLanePaused(clientID:clientID,symbol:symbol,timeframe:timeframe,paused:paused))}

    func publishReadOnlySnapshot(symbols:String="*",timeframes:String="*") async {
        await performReadOnlyControl(.publishReadOnlySnapshot(symbols:symbols,timeframes:timeframes))
    }

    func installReadOnlyPublisherService() async {
        await performReadOnlyControl(.installReadOnlyPublisherService(python:pythonPath,repository:repositoryPath))
    }

    func startReadOnlyPublisherService() async {await performReadOnlyControl(.startReadOnlyPublisherService)}
    func stopReadOnlyPublisherService() async {await performReadOnlyControl(.stopReadOnlyPublisherService)}
    func uninstallReadOnlyPublisherService() async {await performReadOnlyControl(.uninstallReadOnlyPublisherService)}

    func clearReadOnlyIssuedToken(){readOnlyIssuedToken=nil}

    private func performReadOnlyControl(_ intent:OperationIntent,capturesToken:Bool=false) async {
        guard !readOnlyClientsBusy else{return};readOnlyClientsBusy=true;readOnlyClientsError=nil
        let config=configuration,bridge=readOnlyClientsBridge
        do {
            let result=try await Task.detached { try bridge.run(intent,config:config) }.value
            guard result.exitCode==0 else { readOnlyClientsError=result.stderr.isEmpty ? result.stdout:result.stderr;readOnlyClientsBusy=false;return }
            if capturesToken {
                guard let token=result.JSON?["issued_token"] as? String else {throw BridgeError.malformedResult}
                readOnlyIssuedToken=token
            }
            readOnlyClientsBusy=false
            await refreshReadOnlyClients()
        } catch { readOnlyClientsBusy=false;readOnlyClientsError=error.localizedDescription }
    }
    private func replicaRequestCompleted(_ clientID:String)->Bool {
        guard let client=readOnlyClientsSnapshot?.clients.first(where:{$0.clientID==clientID}) else{return false}
        let requested=client.control?.refreshGeneration ?? 0
        let completed=client.report?.service.refreshGenerationCompleted ?? 0
        return requested > 0 && completed >= requested
    }
    func clearCurrentOperationResult(){
        guard !dataOperationState.isActive else{return}
        currentPlanRevision=UUID();currentOperationResult=nil;operationError=nil
        activeDataOperation=nil;dataOperationState = .idle;activeOperationState=nil;activeOperationProvider=nil;activeOperationNextProvider=nil;activeOperationFallbackPosition=nil;activeOperationFallbackCount=nil
    }
    func beginPlanReview(){guard !dataOperationState.isActive else{return};currentPlanRevision=UUID();operationError=nil;activeDataOperation=nil;dataOperationState = .idle;activeOperationState=nil;activeOperationProvider=nil;activeOperationNextProvider=nil;activeOperationFallbackPosition=nil;activeOperationFallbackCount=nil}
    func navigate(_ route:LegacyRoute,asset:String?=nil){let target=NavigationRedirect.destination(for:route);section=target.workspace;if let mode=target.dataMode{dataOperationsMode=mode};if let system=target.systemSection{systemSection=system};if let manage=target.manageDataSection{manageDataSection=manage};if let asset{acquisitionAsset=asset}}
    func openProviderSetup(for asset:String){marketDiscoveryRequest = asset;manageDataSection = .discover;section = .manageData}
    func openManualRequest(_ request:SchedulerManualRequest){acquisitionAsset=request.symbol;acquisitionTimeframe=request.timeframe;acquisitionFrom=request.missingStart;acquisitionThrough=request.missingEnd;manageDataSection = .operations;dataOperationsMode = .importFile;section = .manageData}
    func dismissManualRequest(_ id:String) async {await performSchedulerControl(.dismissManualRequest(id:id))}
    func acknowledgeManualRequest(_ id:String) async {await performSchedulerControl(.acknowledgeManualRequest(id:id))}
    func retrySchedulerLane(_ id:String) async {await performSchedulerControl(.retrySchedulerLane(id:id))}
    func retryManualRequest(_ id:String) async {await performSchedulerControl(.retryManualRequest(id:id))}
    func queueLaneUpdate(_ id:String) async {await performSchedulerControl(.queueLaneUpdate(id:id))}
    func runSchedulerQueue() async {
        guard schedulerActionInProgress == nil else{return}
        schedulerActionInProgress="RUN_QUEUE"
        schedulerActionMessage=nil
        schedulerActionFailed=false
        schedulerError=nil
        await performSchedulerControl(.runSchedulerQueue)
        if let schedulerError {
            schedulerActionMessage=schedulerError
            schedulerActionFailed=true
        } else {
            schedulerActionMessage="Queue wake accepted · dispatch status refreshed"
        }
        schedulerActionInProgress=nil
    }
    func runEstateAudit() async {await performSchedulerControl(.runEstateAudit);await loadEstateAuditHistory(selectedRunID:nil)}
    func loadEstateAuditHistory(selectedRunID:String?=nil) async {
        guard !estateAuditHistoryLoading else{return};estateAuditHistoryLoading=true;estateAuditHistoryError=nil;defer{estateAuditHistoryLoading=false}
        let config=configuration,bridge=auditHistoryBridge
        do {
            let result=try await Task.detached { try bridge.run(.readEstateAuditHistory(auditRunID:selectedRunID),config:config) }.value
            guard result.exitCode == 0 else { estateAuditHistoryError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            estateAuditHistory=try JSONDecoder().decode(EstateAuditHistory.self,from:Data(result.stdout.utf8))
        } catch { estateAuditHistoryError=error.localizedDescription }
    }
    func setEstateAuditSchedule(weekday:String,hour:Int,minute:Int) async {
        let config=configuration,bridge=auditHistoryBridge
        do {
            let result=try await Task.detached { try bridge.run(.setEstateAuditSchedule(weekday:weekday,hour:hour,minute:minute),config:config) }.value
            guard result.exitCode == 0 else { estateAuditHistoryError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            await loadEstateAuditHistory()
            await refreshSchedulerStatus()
        } catch { estateAuditHistoryError=error.localizedDescription }
    }
    func setSchedulerPolicy(_ policy:String) async {await performSchedulerControl(.setSchedulerPolicy(policy))}
    func setM5Freshness(publicationDelaySeconds:Int,criticalAfterClosedBoundaries:Int) async {await performSchedulerControl(.setM5Freshness(publicationDelaySeconds:publicationDelaySeconds,criticalAfterClosedBoundaries:criticalAfterClosedBoundaries));await refresh()}
    func showEstateFindings(_ condition:String) { estateConditionFilter = condition; section = .estate }
    func pauseAcquisition(scopeType:String,scopeIdentifier:String?,reason:String="OPERATOR_MAINTENANCE") async {await performSchedulerControl(.pauseAcquisition(scopeType:scopeType,scopeIdentifier:scopeIdentifier,reason:reason,temporary:false,ingestionSession:nil))}
    func resumeAcquisition(_ record:SchedulerPauseRecord) async {await performSchedulerControl(.resumeAcquisition(pauseIdentifier:record.pauseIdentifier,scopeType:nil,scopeIdentifier:nil,ingestionSession:nil))}

    func refreshProviderFacts(resolve:Bool=false,symbol:String?=nil) async {
        guard !providerFactsResolving else{return};providerFactsResolving=true;providerFactsError=nil;defer{providerFactsResolving=false}
        let config=configuration,bridge=providerFactsBridge,intent:OperationIntent=resolve ? .resolveProviderFacts(symbol:symbol):.readProviderFacts
        do {
            let result=try await Task.detached{try bridge.run(intent,config:config)}.value
            guard result.exitCode==0 else{providerFactsError=result.stderr.isEmpty ? result.stdout:result.stderr;return}
            providerFacts=try JSONDecoder().decode(ProviderFactsSnapshot.self,from:Data(result.stdout.utf8));providerFactsError=nil
            if resolve { await runSchedulerQueue() }
        } catch { providerFactsError=error.localizedDescription }
    }

    func configureTwelveDataCredential(_ value:String) async {
        do {
            let config=configuration,bridge=providerFactsBridge
            let result=try await Task.detached{try bridge.storeCredential(value,config:config)}.value
            guard result.exitCode==0 else { throw MarketDiscoveryReadError.serviceFailure(result.stderr.isEmpty ? result.stdout:result.stderr) }
            let validation=try await Task.detached{try bridge.validateCredential(config:config)}.value
            guard validation.exitCode==0 else { throw MarketDiscoveryReadError.serviceFailure(validation.stderr.isEmpty ? validation.stdout:validation.stderr) }
            if validation.JSON?["credential_state"] as? String == "Invalid" {
                throw MarketDiscoveryReadError.serviceFailure("Twelve Data rejected this API key. The blocked lanes were not released.")
            }
            await refreshCredentialAuthority()
            await refreshProviderFacts(resolve:true)
        } catch { providerFactsError=error.localizedDescription }
    }

    func openProviderCredentialRepair() {
        providerCredentialRepairRequested = true
        manageDataSection = .system
        systemSection = .providerFacts
        section = .manageData
    }

    func openProviderFacts() {
        manageDataSection = .system
        systemSection = .providerFacts
        section = .manageData
    }

    func openCalendarSettings() {
        manageDataSection = .system
        systemSection = .settings
        section = .manageData
    }

    func configureProvider(_ provider:ProviderInventoryItem,enabled:Bool,operationalLimit:Int,concurrencyLimit:Int) async -> Bool {
        guard !providerFactsResolving else{return false};providerFactsResolving=true;providerFactsError=nil
        let config=configuration,bridge=providerFactsBridge
        do {
            let result=try await Task.detached{try bridge.run(.configureProvider(provider:provider.provider,enabled:enabled,operationalLimit:operationalLimit,concurrencyLimit:concurrencyLimit),config:config)}.value
            guard result.exitCode==0 else { throw MarketDiscoveryReadError.serviceFailure(result.stderr.isEmpty ? result.stdout:result.stderr) }
            providerFactsResolving=false
            await refreshProviderFacts()
            await runSchedulerQueue()
            return true
        } catch { providerFactsResolving=false;providerFactsError=error.localizedDescription;return false }
    }

    func probeProviderCapability(symbol:String,timeframe:String) async {
        guard !providerFactsResolving else{return};providerFactsResolving=true;providerFactsError=nil;defer{providerFactsResolving=false}
        let config=configuration,bridge=providerFactsBridge
        do {
            let result=try await Task.detached{try bridge.run(.probeProviderCapability(symbol:symbol,timeframe:timeframe),config:config)}.value
            guard result.exitCode==0 else{providerFactsError=result.stderr.isEmpty ? result.stdout:result.stderr;return}
            latestProviderProbe=try JSONDecoder().decode(ProviderCapabilityProbe.self,from:Data(result.stdout.utf8))
            let status=try await Task.detached{try bridge.run(.readProviderFacts,config:config)}.value
            if status.exitCode==0 { providerFacts=try JSONDecoder().decode(ProviderFactsSnapshot.self,from:Data(status.stdout.utf8)) }
            await refreshSchedulerStatus()
        } catch { providerFactsError=error.localizedDescription }
    }

    func recordProviderMappingDecision(symbol:String,decision:String,candidate:String) async {
        guard !providerFactsResolving else{return};providerFactsResolving=true;providerFactsError=nil;defer{providerFactsResolving=false}
        let config=configuration,bridge=providerFactsBridge
        do {
            let result=try await Task.detached{try bridge.run(.recordProviderMappingDecision(symbol:symbol,decision:decision,candidate:candidate),config:config)}.value
            guard result.exitCode==0 else{providerFactsError=result.stderr.isEmpty ? result.stdout:result.stderr;return}
            providerFacts=try JSONDecoder().decode(ProviderFactsSnapshot.self,from:Data(result.stdout.utf8))
            await refresh();await refreshSchedulerStatus()
        } catch { providerFactsError=error.localizedDescription }
    }

    func configureProviderRoute(provider:String,asset:String,providerSymbol:String,timeframe:String,mappingClass:String,calendarID:String) async -> Bool {
        guard !providerFactsResolving else{return false};providerFactsResolving=true;providerFactsError=nil;defer{providerFactsResolving=false}
        let config=configuration,bridge=providerFactsBridge
        do {
            let result=try await Task.detached { try bridge.run(.configureProviderRoute(provider:provider,asset:asset,providerSymbol:providerSymbol,timeframe:timeframe,mappingClass:mappingClass,calendarID:calendarID),config:config) }.value
            guard result.exitCode==0 else { throw MarketDiscoveryReadError.serviceFailure(result.stderr.isEmpty ? result.stdout:result.stderr) }
            await refreshProviderFacts();await refreshSchedulerStatus();await runSchedulerQueue();return true
        } catch { providerFactsError=error.localizedDescription;return false }
    }

    private func performSchedulerControl(_ intent:OperationIntent) async {
        let config=configuration,bridge=self.bridge
        do {
            let result=try await Task.detached {
                try bridge.validateCLI(config)
                return try bridge.run(intent,config:config)
            }.value
            guard result.exitCode == 0 else {
                schedulerError=result.stderr.isEmpty ? result.stdout:result.stderr
                return
            }
            await refreshSchedulerStatus()
        } catch { schedulerError=error.localizedDescription }
    }

    func refreshSchedulerStatus(scheduleEstateRefresh:Bool=true) async {
        do {
            let database=databasePath,client=schedulerServiceClient,appBuild=Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "Development"
            let data=try await Task.detached{try client.readStatus(database:database,appBuild:appBuild)}.value
            let status=try JSONDecoder().decode(SchedulerServiceStatus.self,from:data)
            schedulerServiceStatus=status
            schedulerServiceRunning=status.operationalHealth?.process.state == "ALIVE" || status.acquisitionOwnerActive
            if scheduleEstateRefresh { refreshEstateProjectionIfNeeded(for:status) }
            if status.live,let snapshot=try? JSONDecoder().decode(SchedulerSnapshot.self,from:data) {
                schedulerUsesCompactStatus=false
                acceptSchedulerSnapshot(snapshot)
            }
            else if status.live,status.schedulerMode == "TIME_TRIGGERED_REGISTER" {
                // Normal SPEC-063 wakes intentionally publish only the compact
                // register status.  Treat that live response as healthy instead
                // of forcing a full-estate monitor projection just for the UI.
                schedulerSnapshot=nil
                schedulerUsesCompactStatus=true
                schedulerError=nil
            }
            else if status.live {
                schedulerSnapshot=nil
                schedulerUsesCompactStatus=false
                schedulerError="Live Scheduler status could not be decoded. Open Diagnostics to inspect the service contract."
            }
            else if let mutation=status.activeMutation { schedulerError="\(mutation.operationType.replacingOccurrences(of:"_",with:" ").capitalized) · \(mutation.progressMessage)" }
            else if let failure=status.mutationFailure?.detail { schedulerError=failure }
            else if status.acquisitionOwnerActive {
                let health=status.operationalHealth?.overallOperationalHealth.replacingOccurrences(of:"_",with:" ").capitalized ?? "Healthy"
                schedulerError="Scheduler \(health.lowercased()); monitor connection is unavailable."
            }
            else if status.installed { schedulerError="Live service connection lost · Last update \(SchedulerFormatting.timestamp(status.lastSuccessfulMonitorUpdate))" }
            else { schedulerError="Scheduler Service is not installed." }
        } catch { schedulerServiceRunning=false;schedulerError=error.localizedDescription }
    }

    func refreshSchedulerStatusFromUI() async {
        guard schedulerActionInProgress == nil else{return}
        schedulerActionInProgress="REFRESH"
        schedulerActionMessage=nil
        schedulerActionFailed=false
        await refreshSchedulerStatus()
        if let schedulerError {
            schedulerActionMessage=schedulerError
            schedulerActionFailed=true
        } else {
            schedulerActionMessage="Status refreshed · (SchedulerFormatting.timestamp(schedulerServiceStatus?.heartbeatTime))"
        }
        schedulerActionInProgress=nil
    }

    private func acceptSchedulerSnapshot(_ value:SchedulerSnapshot) {
        schedulerSnapshot=value;schedulerServiceRunning=true;schedulerError=nil
        reconcileEstateAdmissionProgress(value)
    }

    /// Normal scheduler wakes publish a compact, indexed status. Its cheap
    /// authority token eventually drives one complete Estate Truth refresh.
    /// D1 lanes publish in a burst, so require a quiet interval and an idle
    /// worker pool before starting the expensive immutable-authority read.
    private func schedulerPermitsEstateProjection(_ status:SchedulerServiceStatus) -> Bool {
        status.live
            && (status.operationalHealth?.workerPool.activeWorkers ?? 0) == 0
            && status.register?.runningCount == 0
            && status.register?.dueNowCount == 0
    }

    private func refreshEstateProjectionIfNeeded(for status:SchedulerServiceStatus) {
        guard status.live,
              let token=status.authorityChangeToken,
              lastEstateProjectionToken != token else { return }
        if isRefreshing {
            // Preserve the newest revision. The completing refresh schedules
            // this trailing projection instead of overlapping Python readers.
            estateRefreshTargetToken=token
            return
        }
        guard estateRefreshTargetToken != token else { return }
        estateRefreshTask?.cancel()
        estateRefreshTargetToken=token
        estateRefreshTask=Task { [weak self] in
            // A short debounce coalesces the rapid token changes emitted by a
            // publication burst. The fresh 20-second proof below is the
            // actual idle gate and still prevents work from overlapping.
            do { try await Task.sleep(for:.seconds(5)) }
            catch { return }
            guard let self else { return }
            // The monitor may have been sleeping on an earlier idle status
            // while a boundary became due. Re-read the daemon now, then
            // require that fresh settled state to remain true for the whole
            // quiet interval before launching the authority process.
            await self.refreshSchedulerStatus(scheduleEstateRefresh:false)
            guard !Task.isCancelled,
                  self.schedulerServiceStatus?.authorityChangeToken == token,
                  self.schedulerServiceStatus.map(self.schedulerPermitsEstateProjection) == true,
                  !self.isRefreshing else {
                if self.estateRefreshTargetToken == token { self.estateRefreshTargetToken=nil }
                self.estateRefreshTask=nil
                return
            }
            do { try await Task.sleep(for:.seconds(20)) }
            catch { return }
            await self.refreshSchedulerStatus(scheduleEstateRefresh:false)
            guard !Task.isCancelled,
                  self.schedulerServiceStatus?.authorityChangeToken == token,
                  self.schedulerServiceStatus.map(self.schedulerPermitsEstateProjection) == true,
                  !self.isRefreshing else {
                if self.estateRefreshTargetToken == token { self.estateRefreshTargetToken=nil }
                self.estateRefreshTask=nil
                return
            }
            await self.refresh()
            self.estateRefreshTargetToken=nil
            self.estateRefreshTask=nil
            if let latest=self.schedulerServiceStatus {
                self.refreshEstateProjectionIfNeeded(for:latest)
            }
        }
    }

    private func reconcileEstateAdmissionProgress(_ value:SchedulerSnapshot) {
        for symbol in Array(estateAdmissionProgressBySymbol.keys) {
            guard let progress=estateAdmissionProgressBySymbol[symbol] else{continue}
            estateAdmissionProgressBySymbol[symbol]=reconciledEstateAdmissionProgress(progress,with:value)
        }
    }

    private func reconciledEstateAdmissionProgress(
        _ current:EstateAdmissionProgress,
        with value:SchedulerSnapshot
    ) -> EstateAdmissionProgress? {
        var progress=current
        let lanes=value.lanes.filter { $0.symbol==progress.symbol && progress.timeframes.contains($0.timeframe) }
        let queued=value.acquisitionQueue.filter { $0.symbol==progress.symbol && progress.timeframes.contains($0.timeframe) }
        if let activity=value.activeActivity,
           activity.symbol==progress.symbol,
           progress.timeframes.contains(activity.timeframe) {
            progress.activeTimeframe=activity.timeframe
            progress.stage="Acquiring \(activity.timeframe) · \(activity.stage.replacingOccurrences(of:"_",with:" ").capitalized)"
            return progress
        }
        if !queued.isEmpty {
            progress.activeTimeframe=nil
            progress.stage="Initial history queued · \(queued.count) lane\(queued.count == 1 ? "" : "s") ready"
            return progress
        }
        if lanes.contains(where: { ["FAILED","MANUAL_REQUIRED"].contains($0.result ?? "") || $0.publicationState == "FAILED_RETRYABLE" }) {
            progress.activeTimeframe=nil
            progress.stage="Initial history needs attention"
            return progress
        }
        guard lanes.count == progress.timeframes.count else { return progress }
        if lanes.allSatisfy({ $0.latestCanonicalObservation != nil && ($0.publicationState ?? "PUBLISHED") == "PUBLISHED" }) {
            let projected=progress.timeframes.allSatisfy { timeframe in
                estateTruth?.truthMatrix.contains {
                    $0.symbol==progress.symbol && $0.timeframe==timeframe
                } == true
            }
            if projected{return nil}
            progress.activeTimeframe=nil
            progress.stage="Published · refreshing Estate"
            return progress
        }
        if lanes.contains(where: { $0.publicationState == "PUBLISHING" || $0.latestCanonicalObservation != nil }) {
            progress.activeTimeframe=nil
            progress.stage="Publishing initial evidence"
        }
        return progress
    }

    private func manageSchedulerService(_ action:String) async {
        let config=configuration,bridge=self.schedulerLifecycleBridge
        let intent:OperationIntent = action=="install" ? .installSchedulerService : action=="repair" ? .repairSchedulerService : action=="force-reconcile" ? .forceReconcileSchedulerService : .schedulerServiceAction(action)
        do {
            let result=try await Task.detached{try bridge.run(intent,config:config)}.value
            guard result.exitCode==0 else { schedulerError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            if ["install","start","restart","enable"].contains(action) { try? await Task.sleep(for:.seconds(1)) }
            await refreshSchedulerStatus()
        } catch BridgeError.operationActive {
            if let active=schedulerServiceStatus?.activeMutation {
                schedulerError="\(active.operationType.replacingOccurrences(of:"_",with:" ").capitalized) is active at \(active.currentStage.replacingOccurrences(of:"_",with:" ").capitalized). Last progress: \(SchedulerFormatting.timestamp(active.lastProgressAt)). View details or cancel when available."
            } else {
                await refreshSchedulerStatus()
                if let active=schedulerServiceStatus?.activeMutation {
                    schedulerError="\(active.operationType.replacingOccurrences(of:"_",with:" ").capitalized) is active at \(active.currentStage.replacingOccurrences(of:"_",with:" ").capitalized). View details or cancel when available."
                } else { schedulerError="A service lifecycle request is being recorded. Retry Connection to view its operation and recovery actions." }
            }
        } catch { schedulerError=error.localizedDescription }
    }

    func cancelSchedulerMutation() async {
        let config=configuration,bridge=self.schedulerDiagnosticsBridge,operationID=schedulerServiceStatus?.activeMutation?.operationID
        do {
            let result=try await Task.detached{try bridge.run(.cancelSchedulerMutation(operationID:operationID),config:config)}.value
            guard result.exitCode==0 else { schedulerError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            await refreshSchedulerStatus()
        } catch { schedulerError=error.localizedDescription }
    }

    func loadSchedulerDiagnostics() async {
        let config=configuration,bridge=self.schedulerDiagnosticsBridge,appBuild=Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "Development"
        schedulerDiagnosticsError=nil
        do {
            let result=try await Task.detached{try bridge.run(.readSchedulerDiagnostics(appBuild:appBuild),config:config)}.value
            guard result.exitCode==0 else { schedulerDiagnosticsError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            schedulerServiceDiagnostics=try JSONDecoder().decode(SchedulerServiceDiagnostics.self,from:Data(result.stdout.utf8))
        } catch { schedulerDiagnosticsError=error.localizedDescription }
    }

    private func loadAuthorityState() async throws -> (EstateTruthState,EstateHierarchy,AuthoritySnapshot) {
        // Estate reads may continue in the background after a registration.
        // They must never borrow the mutation bridge: doing so made a quick
        // second Add to Estate fail with the false "another mutating operation"
        // message while a read-only refresh was still decoding the estate.
        let config=configuration,bridge=self.authorityReadBridge,reader=self.reader,path=databasePath
        return try await Task.detached {
            try bridge.validateCLI(config)
            let process=try bridge.run(.readEstateTruth,config:config)
            guard process.exitCode==0 else { throw BridgeError.malformedResult }
            let state=try JSONDecoder().decode(EstateTruthState.self,from:Data(process.stdout.utf8))
            return (state,EstateHierarchy(lanes:state.truthMatrix),try reader.load(path:path,estateTruth:state))
        }.value
    }

    func refreshCredentialAuthority() async {
        let config=configuration,bridge=providerFactsBridge
        do {
            let result=try await Task.detached{try bridge.readCredentialAuthority(config:config)}.value
            guard result.exitCode==0 else { providerFactsError=result.stderr.isEmpty ? result.stdout:result.stderr;return }
            credentialAuthority=try JSONDecoder().decode(CredentialAuthoritySnapshot.self,from:Data(result.stdout.utf8))
        } catch { providerFactsError=error.localizedDescription }
    }

    private func commitAuthorityState(_ loaded:(EstateTruthState,EstateHierarchy,AuthoritySnapshot)) {
        estateTruth=loaded.0;estateHierarchy=loaded.1;snapshot=loaded.2
        estateTruthError=nil;readError=nil
        for progress in estateAdmissionProgresses where progress.timeframes.allSatisfy({ timeframe in
            loaded.0.truthMatrix.contains{$0.symbol==progress.symbol && $0.timeframe==timeframe}
        }) {
            estateAdmissionProgressBySymbol.removeValue(forKey:progress.symbol)
        }
        if selectedTruthLaneID==nil || !loaded.0.truthMatrix.contains(where:{$0.id==selectedTruthLaneID}) { selectedTruthLaneID=loaded.0.truthMatrix.first?.id }
        if selectedLaneID==nil || !loaded.2.lanes.contains(where:{$0.id==selectedLaneID}) { selectedLaneID=loaded.2.lanes.first?.id }
    }
}

private enum MarketDiscoveryReadError:Error,LocalizedError,Sendable {
    case serviceFailure(String)
    var errorDescription:String? {
        switch self {
        case .serviceFailure(let detail):
            return detail.isEmpty ? "Market discovery service failed.":detail
        }
    }
}
