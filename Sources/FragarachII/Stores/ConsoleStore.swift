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
    @Published var estateAdmissionProgress: EstateAdmissionProgress?
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
    @Published var syntheticSnapshot:SyntheticSnapshot?
    @Published var syntheticError:String?
    @Published var schedulerSnapshot: SchedulerSnapshot?
    @Published var schedulerServiceStatus:SchedulerServiceStatus?
    @Published var schedulerServiceDiagnostics:SchedulerServiceDiagnostics?
    @Published var schedulerDiagnosticsError:String?
    @Published var schedulerError: String?
    @Published var schedulerUsesCompactStatus = false
    @Published var schedulerRegisterFilter: String?
    @Published var credentialAuthority:CredentialAuthoritySnapshot?
    @Published var schedulerServiceRunning = false
    @Published var providerFacts:ProviderFactsSnapshot?
    @Published var providerFactsError:String?
    @Published var providerFactsResolving=false
    @Published var providerCredentialRepairRequested=false
    @Published var latestProviderProbe:ProviderCapabilityProbe?
    @Published var pauseScheduledAcquisitionWhileImporting = true
    @Published var manualIngestionPauseScope = "SYMBOL"
    @Published var resumeAfterManualImport = true
    @Published var manualIngestionHoldMessage:String?
    private let reader=SQLiteReadService(); let bridge=ProcessBridge(); private let authorityReadBridge=ProcessBridge()
    private let marketDiscoveryBridge=ProcessBridge()
    private let marketHistoryBridge=ProcessBridge()
    private let schedulerServiceBridge=ProcessBridge()
    private let schedulerLifecycleBridge=ProcessBridge()
    private let schedulerDiagnosticsBridge=ProcessBridge()
    private let providerFactsBridge=ProcessBridge()
    private var schedulerMonitorTask:Task<Void,Never>?
    private var estateRefreshTargetToken:String?
    private var lastEstateProjectionToken:String?
    private let staleOperationInterval:TimeInterval = 10 * 60
    var configuration: CLIConfiguration { .init(python:pythonPath,repository:repositoryPath,database:databasePath) }
    var credentialAvailable: Bool { credentialAuthority?.providers.first(where:{$0.provider=="TWELVE_DATA"})?.credentialState == "Available" }
    var dataOperationIsActive: Bool { dataOperationState.isActive }
    var schedulerAcquisitionIsActive: Bool { schedulerSnapshot?.activeActivity != nil }
    var estateProjectionNeedsRefresh: Bool {
        guard let token=schedulerServiceStatus?.authorityChangeToken else { return estateTruth == nil }
        return lastEstateProjectionToken != token
    }
    func schedulerAcquisitionIsActive(symbol:String?,timeframe:String?=nil) -> Bool {
        guard let activity=schedulerSnapshot?.activeActivity,
              activity.symbol==symbol else { return false }
        return timeframe == nil || activity.timeframe == timeframe
    }
    func beginEstateAdmission(symbol:String,timeframes:[String]) {
        let lanes=timeframes.isEmpty ? ["D1"]:timeframes
        estateAdmissionProgress = .init(
            symbol:symbol, timeframes:lanes, startedAt:Date(),
            stage:"Initial history queued", activeTimeframe:nil
        )
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
        async let authorityRefresh: Void = refresh()
        await refreshSchedulerStatus()
        startSchedulerMonitor()
        await refreshProviderFacts(resolve:true)
        await authorityRefresh
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
                try? await Task.sleep(for:.seconds(2))
            }
        }
    }

    func refresh() async {
        guard !isRefreshing else{return}; isRefreshing=true; defer{isRefreshing=false}
        do {
            let loaded=try await loadAuthorityState()
            commitAuthorityState(loaded)
        } catch { estateTruthError=error.localizedDescription;readError=error.localizedDescription }
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
            operationError=activeOperationStatusMessage()
            return
        }
        var ingestionSession:String?
        func releaseManualIngestionPauseIfNeeded() async {
            guard let session=ingestionSession,resumeAfterManualImport else{return}
            await performSchedulerControl(.resumeAcquisition(pauseIdentifier:nil,scopeType:nil,scopeIdentifier:nil,ingestionSession:session))
            manualIngestionHoldMessage=nil
        }
        if case .importCSV(_,let symbol,_,_,_,_) = intent, pauseScheduledAcquisitionWhileImporting {
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
        guard !intent.isAuthorityMutation || !schedulerAcquisitionIsActive else {
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
            if case .registerInstrument = intent {
                // Estate admission has already committed its provider mapping,
                // registration, commissioning decision, and durable initial
                // work requests before the CLI returns.  A complete estate
                // read can be slow while the Scheduler is admitting history;
                // never keep the registration modal in "Preparing" merely
                // because that non-mutating refresh is still running.
                Task { [weak self] in
                    await self?.refresh()
                    await self?.refreshSchedulerStatus()
                }
            } else {
                // A provider operation is complete as soon as the Scheduler
                // returns its durable result.  Estate Truth is a complete
                // authority projection and can be expensive for a large
                // historical store; never present that read as an ongoing
                // import or retain the operator lock after evidence has
                // already been published.  Refresh it independently.
                Task { [weak self] in
                    await self?.refresh()
                    await self?.refreshSchedulerStatus()
                }
            }
        } catch {
            operationError=error.localizedDescription
            if activeDataOperation != nil { dataOperationState = .failed;activeOperationState=dataOperationState.stageLabel }
        }
        await releaseManualIngestionPauseIfNeeded()
    }
    func discoverMarket(_ query:String) async throws -> MarketDiscoveryResult {
        releaseStaleOperationLockIfSafe()
        guard activeOperationID == nil else { throw LocalOperationLockError.active(activeOperationStatusMessage()) }
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
    func runSchedulerQueue() async {await performSchedulerControl(.runSchedulerQueue)}
    func runEstateAudit() async {await performSchedulerControl(.runEstateAudit)}
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
            if resolve { await runSchedulerQueue();await refresh();await refreshSchedulerStatus() }
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
            await runSchedulerQueue()
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

    func refreshSchedulerStatus() async {
        do {
            let config=configuration,bridge=self.schedulerServiceBridge,appBuild=Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "Development"
            let result=try await Task.detached{try bridge.run(.readSchedulerService(appBuild:appBuild),config:config)}.value
            guard result.exitCode==0 else { schedulerError=result.stderr.isEmpty ? result.stdout:result.stderr;schedulerServiceRunning=false;return }
            let data=Data(result.stdout.utf8)
            let status=try JSONDecoder().decode(SchedulerServiceStatus.self,from:data)
            schedulerServiceStatus=status
            schedulerServiceRunning=status.operationalHealth?.process.state == "ALIVE" || status.acquisitionOwnerActive
            refreshEstateProjectionIfNeeded(for:status)
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

    private func acceptSchedulerSnapshot(_ value:SchedulerSnapshot) {
        let prior=schedulerSnapshot?.authorityRevision
        schedulerSnapshot=value;schedulerServiceRunning=true;schedulerError=nil
        reconcileEstateAdmissionProgress(value)
        if let prior,prior != value.authorityRevision { Task{await refresh()} }
    }

    /// Normal scheduler wakes publish a compact, indexed status.  Its cheap
    /// authority change token drives the complete Estate Truth refresh without
    /// asking the service for a full monitor projection every two seconds.
    private func refreshEstateProjectionIfNeeded(for status:SchedulerServiceStatus) {
        guard status.live,
              let token=status.authorityChangeToken,
              lastEstateProjectionToken != token,
              estateRefreshTargetToken != token,
              !isRefreshing else { return }
        estateRefreshTargetToken=token
        Task { [weak self] in
            guard let self else { return }
            await self.refresh()
            if self.estateTruthError == nil {
                self.lastEstateProjectionToken=token
            }
            if self.estateRefreshTargetToken == token {
                self.estateRefreshTargetToken=nil
            }
        }
    }

    private func reconcileEstateAdmissionProgress(_ value:SchedulerSnapshot) {
        guard var progress=estateAdmissionProgress else { return }
        let lanes=value.lanes.filter { $0.symbol==progress.symbol && progress.timeframes.contains($0.timeframe) }
        let queued=value.acquisitionQueue.filter { $0.symbol==progress.symbol && progress.timeframes.contains($0.timeframe) }
        if let activity=value.activeActivity,
           activity.symbol==progress.symbol,
           progress.timeframes.contains(activity.timeframe) {
            progress.activeTimeframe=activity.timeframe
            progress.stage="Acquiring \(activity.timeframe) · \(activity.stage.replacingOccurrences(of:"_",with:" ").capitalized)"
            estateAdmissionProgress=progress
            return
        }
        if !queued.isEmpty {
            progress.activeTimeframe=nil
            progress.stage="Initial history queued · \(queued.count) lane\(queued.count == 1 ? "" : "s") ready"
            estateAdmissionProgress=progress
            return
        }
        if lanes.contains(where: { ["FAILED","MANUAL_REQUIRED"].contains($0.result ?? "") || $0.publicationState == "FAILED_RETRYABLE" }) {
            progress.activeTimeframe=nil
            progress.stage="Initial history needs attention"
            estateAdmissionProgress=progress
            return
        }
        guard lanes.count == progress.timeframes.count else { return }
        if lanes.allSatisfy({ $0.latestCanonicalObservation != nil && ($0.publicationState ?? "PUBLISHED") == "PUBLISHED" }) {
            estateAdmissionProgress=nil
            return
        }
        if lanes.contains(where: { $0.publicationState == "PUBLISHING" || $0.latestCanonicalObservation != nil }) {
            progress.activeTimeframe=nil
            progress.stage="Publishing initial evidence"
            estateAdmissionProgress=progress
        }
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
            return (state,EstateHierarchy(lanes:state.truthMatrix),try reader.load(path:path))
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

private enum LocalOperationLockError:Error,LocalizedError,Sendable {
    case active(String)
    var errorDescription:String? {
        switch self {
        case .active(let message): return message
        }
    }
}
