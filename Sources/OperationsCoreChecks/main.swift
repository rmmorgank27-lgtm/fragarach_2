import Foundation
import OperationsCore
import Darwin

enum CheckFailure: Error { case failed(String) }
func check(_ condition: @autoclosure () throws -> Bool, _ message: String) throws { if try !condition() { throw CheckFailure.failed(message) } }
final class LockedStages:@unchecked Sendable{private let lock=NSLock();private var stages:[DataOperationState]=[];func append(_ stage:DataOperationState){lock.withLock{stages.append(stage)}};func value()->[DataOperationState]{lock.withLock{stages}}}
final class LockedSchedulerBridgeProbe:@unchecked Sendable{private let lock=NSLock();private var lines:[String]=[];private var status:Int32?;private var error:String="";func append(_ line:String){lock.withLock{lines.append(line)}};func complete(_ code:Int32,_ stderr:String){lock.withLock{status=code;error=stderr}};func snapshot()->([String],Int32?,String){lock.withLock{(lines,status,error)}}}

let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
let sourceAuthority = root.appendingPathComponent("data/runtime/spec002_real_evidence_acceptance.sqlite3").path
let oldSevenTableAuthority = "/Users/raymorgan/Documents/Fragarach II Backups/spec006a_pre_migration_20260711.sqlite3"
let migratedFixtureDirectory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
try FileManager.default.createDirectory(at: migratedFixtureDirectory, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: migratedFixtureDirectory) }
let authority = migratedFixtureDirectory.appendingPathComponent("authority.sqlite3").path
let migrator = Process()
migrator.executableURL = URL(fileURLWithPath: "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3")
migrator.arguments = ["-c", "from fragarach_ii.storage import initialize_database,bootstrap_legacy_authority;import sqlite3,sys;s=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True);d=sqlite3.connect(sys.argv[2]);s.backup(d);s.close();d.close();initialize_database(sys.argv[2]);c=sqlite3.connect(sys.argv[2]);has_events=c.execute('SELECT EXISTS(SELECT 1 FROM authority_events)').fetchone()[0];c.close();bootstrap_legacy_authority(sys.argv[2]) if not has_events else None;c=sqlite3.connect(sys.argv[2]);c.execute('PRAGMA journal_mode=DELETE');c.close()", sourceAuthority, authority]
migrator.currentDirectoryURL = root
var migrationEnvironment = ProcessInfo.processInfo.environment
migrationEnvironment["PYTHONPATH"] = "\(root.path)/src"
migrator.environment = migrationEnvironment
try migrator.run(); migrator.waitUntilExit()
try check(migrator.terminationStatus == 0, "migrated fixture creation failed")
try check(FileManager.default.fileExists(atPath: authority), "migrated fixture file missing")
var passed = 0
@MainActor func run(_ name: String, _ body: () throws -> Void) throws { try body(); passed += 1; print("PASS \(name)") }
func checkImportDispatch() throws {
    let id=UUID(),fileID=UUID()
    let plan=ReviewedDataOperationPlan(id:id,mode:.importFile,instrument:"USDJPY",timeframe:"D1",filePath:"/tmp/FX_USDJPY.csv",fileChecksum:"abc123",fileSelectionID:fileID,conflict:.preserve)
    try check(plan.intent == .importCSV(file:"/tmp/FX_USDJPY.csv",symbol:"USDJPY",timeframe:"D1",sourceTimezone:nil,d1DateFormat:"auto",mode:.preserve),"import dispatched outside ingest_file")
    try check(plan.matches(mode:.importFile,instrument:"USDJPY",timeframe:"D1",fileChecksum:"abc123"),"matching import plan rejected")
    try check(!plan.matches(mode:.fetch,instrument:"USDJPY",timeframe:"D1",fileChecksum:"abc123"),"fetch result leaked into import")
    try check(!plan.matches(mode:.importFile,instrument:"USDJPY",timeframe:"D1",fileChecksum:"changed"),"stale file checksum accepted")
    let intraday=ReviewedDataOperationPlan(id:UUID(),mode:.importFile,instrument:"AUDUSD",timeframe:"H1",filePath:"/tmp/AUDUSD_H1.csv",fileChecksum:"offset",sourceTimezone:"Europe/Athens",conflict:.preserve)
    let arguments=ArgumentBuilder.arguments(for:try intraday.intent ?? {throw CheckFailure.failed("missing intraday import intent")}(),database:"/authority.sqlite3")
    try check(arguments.contains("--source-timezone") && arguments.contains("Europe/Athens"),"reviewed source timezone not dispatched")
    let d1Arguments=ArgumentBuilder.arguments(for:try plan.intent ?? {throw CheckFailure.failed("missing D1 import intent")}(),database:"/authority.sqlite3")
    try check(d1Arguments.contains("--d1-date-format") && d1Arguments.contains("auto"),"D1 date format not dispatched")
}
func checkOperationState() throws {
    try check(DataOperationState.idle.stageLabel == "Ready" && !DataOperationState.idle.isActive,"idle lifecycle")
    try check([DataOperationState.preparing,.reading,.validating,.ingesting,.refreshingAuthority].allSatisfy(\.isActive),"working lifecycle")
    try check(DataOperationState.completed.stageLabel == "Operation complete" && !DataOperationState.completed.isActive,"completed lifecycle")
    try check(DataOperationState.failed.stageLabel == "Operation failed" && !DataOperationState.failed.isActive,"failed lifecycle")
    let intent=OperationIntent.importCSV(file:"/tmp/evidence.csv",symbol:"GBPJPY",timeframe:"M5",sourceTimezone:nil,d1DateFormat:"auto",mode:.preserve)
    try check(intent.dataOperationContext?.instrument == "GBPJPY" && intent.dataOperationContext?.timeframe == "M5" && intent.dataOperationContext?.actionLabel == "Importing…","import activity context")
    let directory=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try FileManager.default.createDirectory(at:directory,withIntermediateDirectories:true);defer{try? FileManager.default.removeItem(at:directory)}
    let fake=directory.appendingPathComponent("python3");try "#!/bin/sh\necho '{\"fragarach_operation_stage\":\"reading\"}' >&2\necho '{\"fragarach_operation_stage\":\"validating\"}' >&2\necho '{\"fragarach_operation_stage\":\"ingesting\"}' >&2\necho '{\"transaction_state\":\"committed\"}'\n".write(to:fake,atomically:true,encoding:.utf8);try FileManager.default.setAttributes([.posixPermissions:0o700],ofItemAtPath:fake.path)
    let captured=LockedStages();let result=try ProcessBridge().run(intent,config:.init(python:fake.path,repository:root.path,database:authority)){captured.append($0)}
    try check(captured.value()==[.reading,.validating,.ingesting],"backend stages not streamed")
    try check(result.exitCode==0 && result.stderr.isEmpty,"progress protocol leaked into receipt")
}
func checkSchedulerRecoveryState() throws {
    let payload="""
    {"contract":"fragarach_ii.scheduler_service_status.v1","service_state":"UNREACHABLE","installed":true,"live":false,"compatibility":"Compatible","restart_count":0,"automatic_login_start":true,"acquisition_owner_active":false,"reconciliation_status":"ACTIVE_OPERATION_CONFIRMED","recommended_actions":["VIEW_DETAILS","CANCEL_OPERATION","OPEN_DIAGNOSTICS"],"mutation_status":"WAITING","mutation_stage":"WAITING_FOR_HEARTBEAT","mutation_started_at":"2026-07-14T00:00:00+00:00","mutation_last_progress_at":"2026-07-14T00:00:02+00:00","mutation_cancellable":true,"active_mutation":{"operation_id":"start-one","operation_type":"START","status":"WAITING","requested_at":"2026-07-14T00:00:00+00:00","started_at":"2026-07-14T00:00:00+00:00","last_progress_at":"2026-07-14T00:00:02+00:00","completed_at":null,"requesting_app_build":"Development","requesting_app_instance":"app-one","target_service_generation":"generation-two","current_stage":"WAITING_FOR_HEARTBEAT","progress_message":"Waiting for service heartbeat","failure_code":null,"failure_detail":null,"cancellable":true}}
    """
    let status=try JSONDecoder().decode(SchedulerServiceStatus.self,from:Data(payload.utf8))
    try check(status.activeMutation?.operationType=="START" && status.activeMutation?.currentStage=="WAITING_FOR_HEARTBEAT","active Scheduler mutation not decoded")
    try check(status.mutationCancellable && status.recommendedActions.contains("CANCEL_OPERATION"),"recovery actions not decoded")
    let compact="""
    {"contract":"fragarach_ii.scheduler_monitor.v3","service_state":"RUNNING","installed":true,"live":true,"compatibility":"Compatible","restart_count":0,"automatic_login_start":true,"acquisition_owner_active":true,"scheduler_mode":"TIME_TRIGGERED_REGISTER","next_due_check":"2026-07-14T00:05:00+00:00","register":{"contract":"fragarach_ii.lane_update_register.v1","ready_count":12,"retrying_count":1,"blocked_count":2,"paused_count":0,"running_count":0},"operational_health":{"contract":"fragarach_ii.scheduler_operational_health.v1","overall_operational_health":"IDLE","process":{"state":"ALIVE"},"heartbeat":{"state":"CURRENT","at":"2026-07-14T00:00:00+00:00","age_seconds":1.0},"monitor_transport":{"state":"CONNECTED"},"selection_loop":{"state":"IDLE","last_progress":null},"worker_pool":{"state":"IDLE","active_workers":0,"available_workers":4},"provider_dispatch":{"state":"IDLE","last_progress":null},"provider_response":{"state":"IDLE","last_progress":null},"evidence_admission":{"state":"IDLE","last_progress":null},"publication":{"state":"IDLE","last_progress":null},"queue_progress":{"state":"IDLE","last_progress":null},"actionable_queue_depth":0,"blocked_queue_depth":2,"total_queue_depth":0,"oldest_actionable_age_seconds":null,"last_meaningful_progress":null,"permitted_progress_window_seconds":45.0,"current_trace_id":null,"current_lane":null,"current_stage":null,"current_stop_reason":null}}
    """
    let compactStatus=try JSONDecoder().decode(SchedulerServiceStatus.self,from:Data(compact.utf8))
    try check(compactStatus.live && compactStatus.schedulerMode=="TIME_TRIGGERED_REGISTER" && compactStatus.register?.readyCount==12,"compact time-triggered Scheduler status not decoded")
    let force=ArgumentBuilder.arguments(for:.forceReconcileSchedulerService,database:"/authority.sqlite3")
    let cancel=ArgumentBuilder.arguments(for:.cancelSchedulerMutation(operationID:"start-one"),database:"/authority.sqlite3")
    let diagnostics=ArgumentBuilder.arguments(for:.readSchedulerDiagnostics(appBuild:"Development"),database:"/authority.sqlite3")
    try check(force.contains("force-reconcile") && cancel.contains("start-one") && diagnostics.contains("diagnostics"),"Scheduler recovery intents not routed")
}
func checkSchedulerBridgeMonitorOnly() throws {
    let directory=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try FileManager.default.createDirectory(at:directory,withIntermediateDirectories:true);defer{try? FileManager.default.removeItem(at:directory)}
    let fake=directory.appendingPathComponent("python3");try "#!/bin/sh\nprintf '%s\\n' \"$@\"\n".write(to:fake,atomically:true,encoding:.utf8);try FileManager.default.setAttributes([.posixPermissions:0o700],ofItemAtPath:fake.path)
    let probe=LockedSchedulerBridgeProbe(),finished=DispatchSemaphore(value:0)
    try SchedulerProcessBridge().start(config:.init(python:fake.path,repository:root.path,database:"/authority.sqlite3"),onLine:{probe.append($0)},onExit:{code,stderr in probe.complete(code,stderr);finished.signal()})
    try check(finished.wait(timeout:.now()+3) == .success,"Scheduler bridge status probe did not exit")
    let (arguments,status,stderr)=probe.snapshot()
    try check(status == 0 && stderr.isEmpty,"Scheduler bridge probe failed")
    try check(arguments.contains("fragarach_ii.commands.scheduler") && arguments.contains("service-status"),"Scheduler bridge did not read service status")
    try check(!arguments.contains("run") && !arguments.contains("service-run") && !arguments.contains("--monitor-only"),"Scheduler bridge attempted app-owned scheduler execution")
}
func checkDuplicateSubmission() throws {
    let directory=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try FileManager.default.createDirectory(at:directory,withIntermediateDirectories:true);defer{try? FileManager.default.removeItem(at:directory)}
    let fake=directory.appendingPathComponent("python3");try "#!/usr/bin/python3\nimport time\ntime.sleep(10)\nprint('{}')\n".write(to:fake,atomically:true,encoding:.utf8);try FileManager.default.setAttributes([.posixPermissions:0o700],ofItemAtPath:fake.path)
    let bridge=ProcessBridge(),config=CLIConfiguration(python:fake.path,repository:root.path,database:authority),group=DispatchGroup();group.enter()
    DispatchQueue.global().async { _=try? bridge.run(.verify,config:config);group.leave() }
    for _ in 0..<50 { if bridge.isActive { break }; usleep(20_000) }
    try check(bridge.isActive,"operation did not become active")
    do { _=try bridge.run(.verify,config:config);throw CheckFailure.failed("second operation accepted") } catch BridgeError.operationActive {}
    bridge.cancel();try check(group.wait(timeout: .now() + 3) == .success,"cancel did not finish")
}
func checkSpec025AInitialFetch() throws {
    let twelveData=UnifiedAcquisitionProvider(provider:"TWELVE_DATA",providerSymbol:"AUD/CAD",mappingStatus:"EXACT_REPRESENTATION",eligible:true,priority:10)
    let audcad=UnifiedAcquisitionPlan.build(instrument:"AUDCAD",timeframe:"M30",assetClass:"FX",intent:.update,canonicalEdge:"2026-07-13T04:30:00Z",expectedEdge:"2026-07-14T13:30:00Z",providers:[twelveData],reviewedRange:nil,registrationActive:true,operationActive:false,acquisitionPaused:false)
    try check(audcad.isExecutable,"AUDCAD:M30 unified plan was not executable: \(audcad.failure ?? "unknown")")
    try check(audcad.selectedProvider?.mappingStatus=="EXACT_REPRESENTATION","AUDCAD:M30 exact representation was not selected")
    try check(audcad.requestStart?.contains("T")==true && audcad.requestEnd=="2026-07-14T13:30:00Z","intraday update lost timestamp-level bounds")
    try check(audcad.operationIntent == .acquireUpdate(asset:"AUDCAD",timeframe:"M30",from:audcad.requestStart!,through:"2026-07-14T13:30:00Z",mode:.preserve),"displayed AUDCAD:M30 bounds were not submitted unchanged")
    let blocked=UnifiedAcquisitionPlan.build(instrument:"AUDCAD",timeframe:"M30",assetClass:"FX",intent:.update,canonicalEdge:"2026-07-13T04:30:00Z",expectedEdge:nil,providers:[twelveData],reviewedRange:nil,registrationActive:true,operationActive:false,acquisitionPaused:false)
    try check(blocked.isAwaitingExpectedEdge,"missing monitor edge was not presented as a neutral scheduler-loading state")
    let binance=UnifiedAcquisitionProvider(provider:"BINANCE",providerSymbol:"ETHUSD",mappingStatus:"EXACT_REPRESENTATION",eligible:true,priority:10)
    let cryptoUpdate=UnifiedAcquisitionPlan.build(
        instrument:"ETHUSD",timeframe:"M5",assetClass:"CRYPTO",intent:.update,
        canonicalEdge:"2026-07-18T02:40:00+00:00",expectedEdge:nil,providers:[binance],
        reviewedRange:nil,registrationActive:true,operationActive:false,acquisitionPaused:false,
        planningNow:ISO8601DateFormatter().date(from:"2026-07-18T02:47:00Z")!
    )
    try check(cryptoUpdate.isExecutable,"crypto M5 update without a monitor edge was not executable: \(cryptoUpdate.failure ?? "unknown")")
    try check(cryptoUpdate.expectedEdge=="2026-07-18T02:45:00Z","crypto M5 expected edge did not use the latest closed UTC boundary")
    try check(cryptoUpdate.expectedEdgeStatus=="EXPECTED_EDGE_AVAILABLE","crypto M5 fallback did not publish an expected-edge status")
    try check(cryptoUpdate.requestStart != nil && cryptoUpdate.requestEnd=="2026-07-18T02:45:00Z","crypto M5 update did not produce governed request bounds")
    try check(cryptoUpdate.selectedProvider?.provider=="BINANCE","crypto M5 fallback changed provider selection")
    let initial=ReviewedDataOperationPlan(id:UUID(),mode:.fetch,instrument:"GOOGL",timeframe:"D1",from:"2026-06-01",through:"2026-07-13",conflict:.preserve,acquisitionIntent:.initial)
    guard let initialIntent=initial.intent else{throw CheckFailure.failed("initial reviewed plan missing intent")}
    let arguments=ArgumentBuilder.arguments(for:initialIntent,database:"/authority.sqlite3")
    try check(arguments.contains("--intent") && arguments.contains("initial"),"initial intent not dispatched")
    let update=ReviewedDataOperationPlan(id:UUID(),mode:.fetch,instrument:"AAPL",timeframe:"D1",from:"2026-07-01",through:"2026-07-13",conflict:.preserve,acquisitionIntent:.update)
    let updateArguments=ArgumentBuilder.arguments(for:try update.intent ?? {throw CheckFailure.failed("update reviewed plan missing intent")}(),database:"/authority.sqlite3")
    try check(updateArguments.contains("update") && updateArguments.contains("--reviewed-historical-range"),"unified Update bounds were not marked authoritative")
    let liveArguments=ArgumentBuilder.arguments(for:audcad.operationIntent!,database:"/authority.sqlite3")
    let startIndex=try liveArguments.firstIndex(of:"--from-date") ?? {throw CheckFailure.failed("unified Update start argument missing")}()
    let endIndex=try liveArguments.firstIndex(of:"--through-date") ?? {throw CheckFailure.failed("unified Update end argument missing")}()
    try check(liveArguments[startIndex+1]==audcad.requestStart && liveArguments[endIndex+1]==audcad.requestEnd,"bridge changed the displayed unified bounds")
    try check(DataOperationState.requestingHistory.stageLabel=="Requesting history" && DataOperationState.acquiringEarlierHistory.stageLabel=="Acquiring earlier history","history lifecycle labels")

    let deliberatelyShortRange=ControlledDateRange(
        from:ISO8601DateFormatter().date(from:"2026-06-15T00:00:00Z")!,
        through:ISO8601DateFormatter().date(from:"2026-07-15T00:00:00Z")!,
        completedBoundary:ISO8601DateFormatter().date(from:"2026-07-15T00:00:00Z")!
    )
    let yahoo=UnifiedAcquisitionProvider(provider:"YAHOO_FINANCE",providerSymbol:"CAT",mappingStatus:"EXACT_REPRESENTATION",eligible:true,priority:20)
    let cat=UnifiedAcquisitionPlan.build(
        instrument:"CAT",timeframe:"D1",assetClass:"US_EQUITIES",intent:.initial,
        canonicalEdge:nil,expectedEdge:"2026-07-15T00:00:00Z",providers:[yahoo],
        reviewedRange:deliberatelyShortRange,registrationActive:true,operationActive:false,
        acquisitionPaused:false,expectedEdgeStatus:"EXPECTED_EDGE_AVAILABLE"
    )
    try check(cat.isExecutable && cat.selectedProvider?.provider=="YAHOO_FINANCE","CAT initial plan did not select the approved Yahoo representation")
    try check(cat.canonicalEdge==nil && cat.expectedEdge=="2026-07-15T00:00:00Z","CAT initial plan lost its canonical or expected edge")
    try check(cat.historicalDepth=="10 years" && cat.requestStart=="2016-07-15" && cat.requestEnd=="2026-07-15","CAT initial plan did not use governed ten-year bounds")
    try check(cat.requestStart != deliberatelyShortRange.fromISO,"manual range silently overrode Fetch Initial History")
    try check(cat.operationIntent == .acquireInitial(asset:"CAT",timeframe:"D1",from:"2016-07-15",through:"2026-07-15",mode:.preserve),"displayed CAT bounds were not submitted unchanged")

    let ethForceRefresh=UnifiedAcquisitionPlan.build(
        instrument:"ETHUSD",timeframe:"D1",assetClass:"CRYPTO",intent:.force,
        canonicalEdge:"2026-07-15T00:00:00+00:00",expectedEdge:"2026-07-15T00:00:00+00:00",providers:[
            .init(provider:"BINANCE",providerSymbol:"ETHUSDT",mappingStatus:"APPROVED_EQUIVALENT_REPRESENTATION",eligible:true,priority:10),
        ],reviewedRange:nil,registrationActive:true,operationActive:false,acquisitionPaused:false
    )
    try check(ethForceRefresh.isExecutable && ethForceRefresh.noUpdateReason == nil,"force refresh was incorrectly suppressed as current")
    try check(ethForceRefresh.requestStart=="2016-07-15" && ethForceRefresh.requestEnd=="2026-07-15","force refresh did not request the governed D1 history horizon")
    try check(ethForceRefresh.operationIntent == .acquireForceHistory(asset:"ETHUSD",timeframe:"D1",from:"2016-07-15",through:"2026-07-15",mode:.preserve),"force refresh did not retain its audited operation identity")
    let forceArguments=ArgumentBuilder.arguments(for:ethForceRefresh.operationIntent!,database:"/authority.sqlite3")
    try check(forceArguments.contains("force") && forceArguments.contains("FORCE_HISTORY_REFRESH"),"force refresh did not reach the backend as a distinct intent")

    let config=CLIConfiguration(
        python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
        repository:root.path,database:authority
    )
    let result=try ProcessBridge().run(.discoverMarket(query:"CAT"),config:config)
    try check(result.exitCode==0,"CAT Discover failed")
    let discovery=try JSONDecoder().decode(MarketDiscoveryResult.self,from:Data(result.stdout.utf8))
    let representation=try discovery.markets.first?.representations.first(where:{$0.symbol=="CAT"}) ?? {throw CheckFailure.failed("CAT representation missing")}()
    try check(representation.acquisitionReadiness=="PROVIDER_SETUP_INCOMPLETE","existing incomplete CAT state was not recognised")
    try check(MarketDiscoveryPresentation.primaryAction(for:representation) == .completeProviderSetup,"existing CAT did not offer Complete Provider Setup")
}
func checkEstateHierarchy() throws {
    try check(EstateHierarchyClassifier.marketName(assetClass:"FX") == "Forex","FX market")
    try check(EstateHierarchyClassifier.marketName(assetClass:"METALS") == "Metals","metals market")
    try check(EstateHierarchyClassifier.marketName(assetClass:"US_EQUITIES") == "Stocks","stocks market")
    try check(EstateHierarchyClassifier.marketName(assetClass:"AGRICULTURE") == "Agriculture","future market expansion")
    try check(EstateHierarchyClassifier.canonicalMarkets == ["Forex","Metals","Energy","Indices","Stocks","Crypto"],"canonical market order")
    func subgroup(_ symbol:String)->String?{EstateHierarchyClassifier.subgroupName(market:"Forex",symbol:symbol,assetClass:"FX",exchange:"OTC")}
    try check(subgroup("EURUSD") == "Majors","major route")
    try check(subgroup("AUDCAD") == "Minors","minor route")
    try check(subgroup("GBPJPY") == "Crosses","cross route")
    try check(subgroup("USDMXN") == "Exotics","exotic route")
    try check(EstateHierarchyClassifier.subgroupName(market:"Stocks",symbol:"AAPL",assetClass:"US_EQUITIES",exchange:"NASDAQ") == "US","US stock route")
    try check(EstateHierarchyClassifier.subgroupName(market:"Indices",symbol:"XJO",assetClass:"INDICES",exchange:"ASX") == "Australia","Australian index route")
    try check(EstateHierarchyClassifier.subgroupName(market:"Crypto",symbol:"BTCUSD",assetClass:"CRYPTO",exchange:"Digital asset venues") == "All","crypto route")
    try check(EstateGroupSummary.aggregateAuthorityState(["GREEN", "RED"]) == "RED","critical lane hidden by healthy average")
    try check(EstateGroupSummary.aggregateAuthorityState(["GREEN", "AMBER"]) == "AMBER","attention lane hidden by healthy average")
    try check(EstateGroupSummary.aggregateAuthorityState([]) == "NOT_MEASURED","empty group material state")
}
func checkCanonicalObservationLineage(_ state:EstateTruthState) throws {
    let expected=try state.truthMatrix.map(\.latestCanonicalObservation).max() ?? {throw CheckFailure.failed("estate has no canonical observation")}()
    try check(state.latestCanonicalObservation==expected && state.caodt==expected,"estate publication detached from canonical observation")
    try check(state.estateSummary.latestCanonicalObservation==expected && state.estateSummary.caodt==expected && state.estateSummary.overallCAODT==expected,"estate aliases diverged")
    try check(state.truthMatrix.allSatisfy{$0.latestCanonicalObservation==$0.truthState.latestCanonicalObservation && $0.truthState.caodt==$0.latestCanonicalObservation},"lane alias diverged")
    try check(state.truthMatrix.allSatisfy{!$0.authorityGenerated.isEmpty && $0.authorityRevision.hasPrefix("sha256:")},"lane authority lineage missing")
    let hierarchy=EstateHierarchy(lanes:state.truthMatrix)
    try check(hierarchy.estateSummary.latestCanonicalObservation==expected && hierarchy.estateSummary.caodt==expected,"native estate summary detached")
    let required=Set(["Forex","Metals","Energy"])
    let populated=hierarchy.markets.filter{!$0.lanes.isEmpty}
    try check(required.isSubset(of:Set(populated.map(\.name))),"Forex, Metals, or Energy lineage fixture missing")
    for market in populated {
        let latest=market.lanes.map(\.latestCanonicalObservation).max()
        try check(market.summary.latestCanonicalObservation==latest && market.summary.caodt==latest,"\(market.name) publication detached")
        for subgroup in market.subgroups where !subgroup.lanes.isEmpty {
            let subgroupLatest=subgroup.lanes.map(\.latestCanonicalObservation).max()
            try check(subgroup.summary.latestCanonicalObservation==subgroupLatest && subgroup.summary.caodt==subgroupLatest,"\(subgroup.name) publication detached")
        }
    }
}
func readEstateTruthForChecks() throws -> EstateTruthState {
    let config=CLIConfiguration(python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",repository:root.path,database:authority)
    let result=try ProcessBridge().run(.readEstateTruth,config:config)
    try check(result.exitCode==0,"estate truth service failed")
    return try JSONDecoder().decode(EstateTruthState.self,from:Data(result.stdout.utf8))
}
func checkSpec043DiscoverWorkspace() throws {
    let config=CLIConfiguration(
        python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
        repository:root.path,
        database:authority
    )
    func discover(_ query:String)throws->MarketDiscoveryResult {
        let result=try ProcessBridge().run(.discoverMarket(query:query),config:config)
        try check(result.exitCode==0,"\(query) discovery failed")
        return try JSONDecoder().decode(MarketDiscoveryResult.self,from:Data(result.stdout.utf8))
    }

    let xag=try discover("XAGUSD"),silver=try discover("Silver")
    try check(xag.markets.first?.canonicalIdentity=="COMMODITY:SILVER","XAGUSD identity")
    try check(silver.markets.first?.canonicalIdentity==xag.markets.first?.canonicalIdentity,"Silver identity parity")

    let us30=try discover("US30")
    let dow=try us30.markets.first ?? {throw CheckFailure.failed("US30 missing Dow identity")}()
    try check(dow.canonicalIdentity=="INDEX:DJIA","US30 alias identity")
    try check(Set(dow.representations.map(\.symbol)).isSuperset(of:["DJI","DIA","YM","US30"]),"US30 representations")
    let activeDowRepresentations=dow.representations.filter(MarketDiscoveryPresentation.isActive)
    let defaultDowRepresentation=MarketDiscoveryPresentation.defaultRepresentationID(for:dow)
    try check(activeDowRepresentations.count==1 && defaultDowRepresentation==activeDowRepresentations[0].id,"active Estate representation was not the only default")
    try check(defaultDowRepresentation != cfdID(dow),"US30 alias silently selected the CFD")
    let cfd=try dow.representations.first{$0.symbol=="US30"} ?? {throw CheckFailure.failed("US30 CFD missing")}()
    let futures=try dow.representations.first{$0.symbol=="YM"} ?? {throw CheckFailure.failed("YM futures missing")}()
    try check(MarketDiscoveryPresentation.availability(for:cfd,providerDiscovery:dow.providerDiscovery.first{$0.representationSymbol==cfd.symbol}) == .providerMappingRequired,"US30 mapping state")
    try check(MarketDiscoveryPresentation.availability(for:futures,providerDiscovery:dow.providerDiscovery.first{$0.representationSymbol==futures.symbol}) == .unsupported,"YM unsupported state")

    let spx=try discover("SPX500")
    try check(spx.markets.first?.canonicalIdentity=="INDEX:SP500","SPX500 alias identity")
    let googl=try discover("GOOGL")
    try check(googl.markets.first?.representations.contains{$0.symbol=="GOOGL"}==true,"GOOGL representation")
    let bitcoin=try discover("Bitcoin")
    try check(Set(bitcoin.markets.first?.representations.map(\.symbol) ?? [])==["BTCUSD","BTCUSDT"],"Bitcoin representations")
    try check((try discover("definitely-not-a-market")).markets.isEmpty,"unknown search state")
    let cleanDiscoveryDirectory=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at:cleanDiscoveryDirectory,withIntermediateDirectories:true)
    defer{try? FileManager.default.removeItem(at:cleanDiscoveryDirectory)}
    let cleanDiscoveryAuthority=cleanDiscoveryDirectory.appendingPathComponent("authority.sqlite3").path
    let cleanInitializer=Process()
    cleanInitializer.executableURL=URL(fileURLWithPath:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3")
    cleanInitializer.arguments=["-c","from fragarach_ii.storage import initialize_database;import sys;initialize_database(sys.argv[1])",cleanDiscoveryAuthority]
    cleanInitializer.currentDirectoryURL=root
    var cleanEnvironment=ProcessInfo.processInfo.environment
    cleanEnvironment["PYTHONPATH"]="\(root.path)/src"
    cleanInitializer.environment=cleanEnvironment
    try cleanInitializer.run();cleanInitializer.waitUntilExit()
    try check(cleanInitializer.terminationStatus==0,"clean Discover authority creation failed")
    let cleanConfig=CLIConfiguration(
        python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
        repository:root.path,
        database:cleanDiscoveryAuthority
    )
    func discoverClean(_ query:String)throws->MarketDiscoveryResult {
        let result=try ProcessBridge().run(.discoverMarket(query:query),config:cleanConfig)
        try check(result.exitCode==0,"clean \(query) discovery failed")
        return try JSONDecoder().decode(MarketDiscoveryResult.self,from:Data(result.stdout.utf8))
    }
    let bhp=try discoverClean("BHP")
    let bhpASX=try bhp.markets.first{$0.canonicalIdentity=="COMPANY:BHP:ASX"} ?? {throw CheckFailure.failed("BHP ASX identity missing")}()
    let bhpNYSE=try bhp.markets.first{$0.canonicalIdentity=="COMPANY:BHP:NYSE"} ?? {throw CheckFailure.failed("BHP NYSE identity missing")}()
    let bhpASXRepresentation=try bhpASX.representations.first{$0.symbol=="ASX:BHP"} ?? {throw CheckFailure.failed("BHP ASX representation missing")}()
    let bhpNYSERepresentation=try bhpNYSE.representations.first{$0.symbol=="NYSE:BHP"} ?? {throw CheckFailure.failed("BHP NYSE representation missing")}()
    try check(MarketDiscoveryPresentation.initialRepresentationID(for:bhpASX)==bhpASXRepresentation.id,"BHP ASX identity row did not select ASX:BHP")
    try check(MarketDiscoveryPresentation.initialRepresentationID(for:bhpNYSE)==bhpNYSERepresentation.id,"BHP NYSE identity row did not select NYSE:BHP")
    try check(bhpASX.providerDiscovery.first{$0.representationSymbol=="ASX:BHP"}?.knownSymbol=="BHP.AX","BHP ASX Yahoo suffix candidate")
    try check(bhpNYSE.providerDiscovery.first{$0.representationSymbol=="NYSE:BHP"}?.knownSymbol=="BHP","BHP NYSE Yahoo ADR candidate")
    try check(MarketDiscoveryPresentation.primaryAction(for:bhpASXRepresentation) == .approveMappingAndAdd,"BHP ASX action")
    try check(MarketDiscoveryPresentation.primaryAction(for:bhpNYSERepresentation) == .approveMappingAndAdd,"BHP NYSE action")
    try check(MarketDiscoveryPresentation.estateStatus(for:bhpASXRepresentation)=="Not in Estate" && MarketDiscoveryPresentation.estateStatus(for:bhpNYSERepresentation)=="Not in Estate","BHP Estate status")
    let rio=try discoverClean("RIO")
    let rioLSE=try rio.markets.first{$0.canonicalIdentity=="COMPANY:RIO:LSE"} ?? {throw CheckFailure.failed("RIO LSE identity missing")}()
    let rioNYSE=try rio.markets.first{$0.canonicalIdentity=="COMPANY:RIO:NYSE"} ?? {throw CheckFailure.failed("RIO NYSE identity missing")}()
    let rioASX=try rio.markets.first{$0.canonicalIdentity=="COMPANY:RIO:ASX"} ?? {throw CheckFailure.failed("RIO ASX identity missing")}()
    try check(rioLSE.providerDiscovery.first{$0.representationSymbol=="LSE:RIO"}?.knownSymbol=="RIO.L","RIO LSE Yahoo suffix candidate")
    try check(rioNYSE.providerDiscovery.first{$0.representationSymbol=="NYSE:RIO"}?.knownSymbol=="RIO","RIO NYSE Yahoo ADR candidate")
    try check(rioASX.providerDiscovery.first{$0.representationSymbol=="ASX:RIO"}?.knownSymbol=="RIO.AX","RIO ASX Yahoo suffix candidate")
    try check(rioLSE.representations.first{$0.symbol=="LSE:RIO"}?.registrationPlan?.sessionAuthority=="UK_EQUITIES_D1_V1","RIO LSE D1 calendar")
    let hsba=try discoverClean("HSBA")
    try check(hsba.markets.first?.providerDiscovery.first{$0.representationSymbol=="LSE:HSBA"}?.knownSymbol=="HSBA.L","HSBA LSE Yahoo suffix candidate")

    try check(MarketDiscoveryPresentation.primaryAction(for:nil) == .selectRepresentation,"empty detail action")
    try check(MarketDiscoveryPresentation.usesNarrowLayout(availableWidth:720) && !MarketDiscoveryPresentation.usesNarrowLayout(availableWidth:1000),"responsive workspace state")
    let dia=try dow.representations.first{$0.symbol=="DIA"} ?? {throw CheckFailure.failed("DIA missing")}()
    try check(MarketDiscoveryPresentation.primaryAction(for:dia) == .addToEstate,"available representation review action")
    try check(MarketAssetFilter.metals.includes(assetClass:"METALS") && !MarketAssetFilter.metals.includes(assetClass:"FX"),"asset filters")
    try check(ManageDataSection.allCases.map(\.rawValue)==["Discover","Acquire & Import","System"],"Manage Data section labels")
}
func cfdID(_ market:DiscoveredMarket)->String?{market.representations.first{$0.symbol=="US30"}?.id}

func checkSpec056ALiveSmoke() throws {
    let config=CLIConfiguration(
        python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
        repository:root.path,
        database:sourceAuthority
    )
    let bridge=ProcessBridge()
    func runIntent(_ intent:OperationIntent,_ label:String)throws->ProcessResult {
        let result=try bridge.run(intent,config:config)
        try check(result.exitCode==0,"\(label) failed: \(result.stderr.isEmpty ? result.stdout:result.stderr)")
        return result
    }
    func discover(_ query:String)throws->MarketDiscoveryResult {
        let result=try runIntent(.discoverMarket(query:query),"\(query) discovery")
        return try JSONDecoder().decode(MarketDiscoveryResult.self,from:Data(result.stdout.utf8))
    }

    let before=try SQLiteReadService().load(path:sourceAuthority)
    let nyseBefore=before.registrations.filter{$0.asset=="NYSEBHP" && $0.timeframe=="D1"}.count
    let discovery=try discover("BHP")
    let asx=try discovery.markets.first{$0.canonicalIdentity=="COMPANY:BHP:ASX"} ?? {throw CheckFailure.failed("live BHP ASX identity missing")}()
    let nyse=try discovery.markets.first{$0.canonicalIdentity=="COMPANY:BHP:NYSE"} ?? {throw CheckFailure.failed("live BHP NYSE identity missing")}()
    let asxRepresentation=try asx.representations.first{$0.symbol=="ASX:BHP"} ?? {throw CheckFailure.failed("live ASX:BHP representation missing")}()
    let nyseRepresentation=try nyse.representations.first{$0.symbol=="NYSE:BHP"} ?? {throw CheckFailure.failed("live NYSE:BHP representation missing")}()
    try check(asx.providerDiscovery.first{$0.representationSymbol=="ASX:BHP"}?.knownSymbol=="BHP.AX","live ASX:BHP Yahoo candidate")
    try check(nyse.providerDiscovery.first{$0.representationSymbol=="NYSE:BHP"}?.knownSymbol=="BHP","live NYSE:BHP Yahoo candidate")
    var canonicalASXSymbol:String
    if let plan=asxRepresentation.registrationPlan {
        canonicalASXSymbol=plan.canonicalRegistrationSymbol
        let registration=try runIntent(.registerInstrument(candidate:plan.candidate),"ASX:BHP registration")
        let receipt=try registration.JSON ?? {throw CheckFailure.failed("ASX:BHP registration receipt was not JSON")}()
        try check(["INSERTED","EXISTING_IDENTICAL"].contains(receipt["outcome"] as? String),"ASX:BHP registration outcome")
        try check(receipt["canonical_identity"] as? String=="COMPANY:BHP:ASX","ASX:BHP canonical identity")
        try check(receipt["representation"] as? String=="ASX:BHP","ASX:BHP selected representation")
        try check(receipt["provider"] as? String=="YAHOO_FINANCE","ASX:BHP provider")
        try check(receipt["provider_symbol"] as? String=="BHP.AX","ASX:BHP provider symbol")
        try check((receipt["commissioned_timeframes"] as? [String]) == ["D1"],"ASX:BHP D1 commissioning")
    } else {
        canonicalASXSymbol=try asx.existingRegistrations.first?.canonicalSymbol ?? {throw CheckFailure.failed("live ASX:BHP registration plan missing and no existing registration found")}()
        try check(canonicalASXSymbol=="ASXBHP","live ASX:BHP existing canonical symbol")
        try check(asxRepresentation.registrationStatus != "NOT_REGISTERED","live ASX:BHP existing registration state")
    }

    let afterRegistration=try discover("BHP")
    let registeredASX=try afterRegistration.markets.first{$0.canonicalIdentity=="COMPANY:BHP:ASX"}?.representations.first{$0.symbol=="ASX:BHP"} ?? {throw CheckFailure.failed("registered ASX:BHP not discoverable")}()
    let remainingNYSE=try afterRegistration.markets.first{$0.canonicalIdentity=="COMPANY:BHP:NYSE"}?.representations.first{$0.symbol=="NYSE:BHP"} ?? {throw CheckFailure.failed("live NYSE:BHP disappeared")}()
    try check(registeredASX.registrationStatus != "NOT_REGISTERED","ASX:BHP did not register")
    try check(remainingNYSE.registrationStatus == nyseRepresentation.registrationStatus,"NYSE:BHP changed during ASX add")
    let snapshotAfterRegistration=try SQLiteReadService().load(path:sourceAuthority)
    let nyseAfter=snapshotAfterRegistration.registrations.filter{$0.asset=="NYSEBHP" && $0.timeframe=="D1"}.count
    try check(nyseAfter==nyseBefore,"NYSE:BHP was accidentally registered")

    let acquisition=try runIntent(.acquireInitial(asset:canonicalASXSymbol,timeframe:"D1",from:"2024-07-15",through:"2024-07-16",mode:.preserve),"ASX:BHP D1 fetch")
    let acquisitionReceipt=try acquisition.JSON ?? {throw CheckFailure.failed("ASX:BHP fetch receipt was not JSON")}()
    let receiptSymbol=(acquisitionReceipt["asset"] as? String) ?? (acquisitionReceipt["symbol"] as? String)
    try check(receiptSymbol==canonicalASXSymbol,"ASX:BHP fetch receipt asset")
    if let providerResults=acquisitionReceipt["provider_results"] as? [[String:Any]] {
        try check(providerResults.contains{($0["provider"] as? String)=="YAHOO_FINANCE" && ($0["provider_symbol"] as? String)=="BHP.AX"},"ASX:BHP fetch provider result")
    }
    let truth=try JSONDecoder().decode(EstateTruthState.self,from:Data(runIntent(.readEstateTruth,"Estate Truth readback").stdout.utf8))
    let asxLane=try truth.truthMatrix.first{$0.symbol==canonicalASXSymbol && $0.timeframe=="D1"} ?? {throw CheckFailure.failed("ASX:BHP D1 missing from Estate Truth")}()
    try check(asxLane.providerSummary.provider=="YAHOO_FINANCE" && asxLane.providerSummary.providerSymbol=="BHP.AX","ASX:BHP Estate Truth provider")
}

func checkSpec056BLiveSmoke() throws {
    let config=CLIConfiguration(
        python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
        repository:root.path,
        database:sourceAuthority
    )
    let bridge=ProcessBridge()
    func runIntent(_ intent:OperationIntent,_ label:String)throws->ProcessResult {
        let result=try bridge.run(intent,config:config)
        try check(result.exitCode==0,"\(label) failed: \(result.stderr.isEmpty ? result.stdout:result.stderr)")
        return result
    }
    func discover(_ query:String)throws->MarketDiscoveryResult {
        let result=try runIntent(.discoverMarket(query:query),"\(query) discovery")
        return try JSONDecoder().decode(MarketDiscoveryResult.self,from:Data(result.stdout.utf8))
    }
    func externalCatalogue()throws->[String:Any] {
        let process=Process()
        process.executableURL=URL(fileURLWithPath:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3")
        process.arguments=["-m","fragarach_ii.commands.get_catalogue","--json"]
        process.currentDirectoryURL=root
        var environment=ProcessInfo.processInfo.environment
        environment["PYTHONPATH"]="\(root.path)/src"
        environment["FRAGARACH_AUTHORITY_DATABASE"]=sourceAuthority
        process.environment=environment
        let output=Pipe(),error=Pipe()
        process.standardOutput=output;process.standardError=error
        try process.run();process.waitUntilExit()
        let stdout=String(data:output.fileHandleForReading.readDataToEndOfFile(),encoding:.utf8) ?? ""
        let stderr=String(data:error.fileHandleForReading.readDataToEndOfFile(),encoding:.utf8) ?? ""
        try check(process.terminationStatus==0,"external catalogue failed: \(stderr.isEmpty ? stdout:stderr)")
        return try JSONSerialization.jsonObject(with:Data(stdout.utf8)) as? [String:Any] ?? {throw CheckFailure.failed("external catalogue was not JSON")}()
    }

    let before=try SQLiteReadService().load(path:sourceAuthority)
    let nyseBefore=before.registrations.filter{$0.asset=="NYSERIO" && $0.timeframe=="D1"}.count
    let asxBefore=before.registrations.filter{$0.asset=="ASXRIO" && $0.timeframe=="D1"}.count
    let discovery=try discover("RIO")
    let lse=try discovery.markets.first{$0.canonicalIdentity=="COMPANY:RIO:LSE"} ?? {throw CheckFailure.failed("live RIO LSE identity missing")}()
    let nyse=try discovery.markets.first{$0.canonicalIdentity=="COMPANY:RIO:NYSE"} ?? {throw CheckFailure.failed("live RIO NYSE identity missing")}()
    let asx=try discovery.markets.first{$0.canonicalIdentity=="COMPANY:RIO:ASX"} ?? {throw CheckFailure.failed("live RIO ASX identity missing")}()
    let lseRepresentation=try lse.representations.first{$0.symbol=="LSE:RIO"} ?? {throw CheckFailure.failed("live LSE:RIO representation missing")}()
    try check(lse.providerDiscovery.first{$0.representationSymbol=="LSE:RIO"}?.knownSymbol=="RIO.L","live LSE:RIO Yahoo candidate")
    try check(nyse.providerDiscovery.first{$0.representationSymbol=="NYSE:RIO"}?.knownSymbol=="RIO","live NYSE:RIO Yahoo candidate")
    try check(asx.providerDiscovery.first{$0.representationSymbol=="ASX:RIO"}?.knownSymbol=="RIO.AX","live ASX:RIO Yahoo candidate")

    var canonicalLSESymbol:String
    if let plan=lseRepresentation.registrationPlan {
        canonicalLSESymbol=plan.canonicalRegistrationSymbol
        try check(canonicalLSESymbol=="LSERIO","LSE:RIO canonical registration symbol")
        let registration=try runIntent(.registerInstrument(candidate:plan.candidate),"LSE:RIO registration")
        let receipt=try registration.JSON ?? {throw CheckFailure.failed("LSE:RIO registration receipt was not JSON")}()
        try check(["INSERTED","EXISTING_IDENTICAL"].contains(receipt["outcome"] as? String),"LSE:RIO registration outcome")
        try check(receipt["canonical_identity"] as? String=="COMPANY:RIO:LSE","LSE:RIO canonical identity")
        try check(receipt["representation"] as? String=="LSE:RIO","LSE:RIO selected representation")
        try check(receipt["provider_symbol"] as? String=="RIO.L","LSE:RIO provider symbol")
        try check((receipt["commissioned_timeframes"] as? [String]) == ["D1"],"LSE:RIO D1 commissioning")
    } else {
        canonicalLSESymbol=try lse.existingRegistrations.first?.canonicalSymbol ?? {throw CheckFailure.failed("live LSE:RIO registration plan missing and no existing registration found")}()
        try check(canonicalLSESymbol=="LSERIO","live LSE:RIO existing canonical symbol")
    }

    let snapshotAfterRegistration=try SQLiteReadService().load(path:sourceAuthority)
    try check(snapshotAfterRegistration.registrations.filter{$0.asset=="NYSERIO" && $0.timeframe=="D1"}.count==nyseBefore,"NYSE:RIO was accidentally registered")
    try check(snapshotAfterRegistration.registrations.filter{$0.asset=="ASXRIO" && $0.timeframe=="D1"}.count==asxBefore,"ASX:RIO was accidentally registered")
    let acquisition=try runIntent(.acquireInitial(asset:canonicalLSESymbol,timeframe:"D1",from:"2024-07-15",through:"2024-07-16",mode:.preserve),"LSE:RIO D1 fetch")
    let acquisitionReceipt=try acquisition.JSON ?? {throw CheckFailure.failed("LSE:RIO fetch receipt was not JSON")}()
    let receiptSymbol=(acquisitionReceipt["asset"] as? String) ?? (acquisitionReceipt["symbol"] as? String)
    try check(receiptSymbol==canonicalLSESymbol,"LSE:RIO fetch receipt asset")
    if let providerResults=acquisitionReceipt["provider_results"] as? [[String:Any]] {
        try check(providerResults.contains{($0["provider"] as? String)=="YAHOO_FINANCE" && ($0["provider_symbol"] as? String)=="RIO.L"},"LSE:RIO fetch provider result")
    }
    let truth=try JSONDecoder().decode(EstateTruthState.self,from:Data(runIntent(.readEstateTruth,"Estate Truth readback").stdout.utf8))
    let lseLane=try truth.truthMatrix.first{$0.symbol==canonicalLSESymbol && $0.timeframe=="D1"} ?? {throw CheckFailure.failed("LSE:RIO D1 missing from Estate Truth")}()
    try check(lseLane.providerSummary.provider=="YAHOO_FINANCE" && lseLane.providerSummary.providerSymbol=="RIO.L","LSE:RIO Estate Truth provider")
    let catalogue=try externalCatalogue()
    let symbols=(catalogue["symbols"] as? [[String:Any]]) ?? []
    let lseCatalogue=symbols.first{$0["symbol"] as? String==canonicalLSESymbol}
    try check((lseCatalogue?["availability"] as? String)=="AVAILABLE","LSE:RIO external catalogue availability")
}

if ProcessInfo.processInfo.environment["FOCUSED_ESTATE_HIERARCHY"] == "1" {
    try run("hierarchical Estate Truth routing and future expansion",checkEstateHierarchy)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_SPEC051"] == "1" {
    try run("canonical observation lineage reaches native hierarchy") { try checkCanonicalObservationLineage(readEstateTruthForChecks()) }
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_SPEC043"] == "1" {
    try run("SPEC-043 identity-result presentation, workspace state, and navigation",checkSpec043DiscoverWorkspace)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_SPEC056"] == "1" {
    try run("SPEC-056 atomic onboarding and governed CAT initial plan",checkSpec025AInitialFetch)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_SPEC056A_LIVE"] == "1" {
    try run("SPEC-056A live ASX:BHP native smoke",checkSpec056ALiveSmoke)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_SPEC056B_LIVE"] == "1" {
    try run("SPEC-056B live LSE:RIO native smoke",checkSpec056BLiveSmoke)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_IMPORT_DISPATCH"] == "1" {
    try run("import plans dispatch only immutable CSV ingestion and isolate results",checkImportDispatch)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_OPERATION_STATE"] == "1" {
    try run("native data-operation lifecycle and labels",checkOperationState)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
func checkPriceHistoryRead() throws {
    let url=URL(fileURLWithPath:authority), before=try Data(contentsOf:url)
    let history=try SQLiteReadService().loadPriceHistory(path:authority,symbol:"AUDUSD",timeframe:"D1")
    try check(history.symbol=="AUDUSD" && history.timeframe=="D1" && history.authority=="GOVERNED_BARS","Price History identity")
    try check(history.totalBarCount>0,"Price History total bar count")
    try check(history.profile.count<=1_200 && !history.profile.isEmpty,"Price History profile was not bounded")
    try check(history.profile.map(\.timestamp)==history.profile.map(\.timestamp).sorted(),"Price History profile order")
    try check(history.earliestGovernedObservation != nil && history.latestGovernedObservation != nil,"Price History aggregate bounds")
    try check(history.profile.first!.timestamp >= history.earliestGovernedObservation! && history.profile.last!.timestamp <= history.latestGovernedObservation!,"Price History profile exceeds aggregate bounds")
    try check(history.continuity.gaps.allSatisfy{$0.gapDuration>$0.expectedCadence},"Price History gap payload contains non-gaps")
    try check(try Data(contentsOf:url)==before,"Price History mutated database")
}
if ProcessInfo.processInfo.environment["FOCUSED_PRICE_HISTORY"] == "1" {
    try run("Price History uses bounded operational payloads",checkPriceHistoryRead)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_SPEC049A"] == "1" {
    try run("native Scheduler mutation state and recovery actions",checkSchedulerRecoveryState)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_DUPLICATE_SUBMISSION"] == "1" {
    try run("duplicate submission is rejected while an operation is active",checkDuplicateSubmission)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}
if ProcessInfo.processInfo.environment["FOCUSED_SPEC025A"] == "1" {
    try run("SPEC-025A initial-fetch review and dispatch",checkSpec025AInitialFetch)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}

try run("read-only real schema and bounded queries") {
    let url=URL(fileURLWithPath:authority), before=try Data(contentsOf:url), snapshot=try SQLiteReadService().load(path:authority,operationLimit:5)
    try check(Set(["AUDUSD","BTCUSD","XAUUSD"]).isSubset(of:Set(snapshot.lanes.map(\.asset))),"lane decode")
    try check(snapshot.operations.count==5,"bounded operations")
    try check(snapshot.authorityEvents.count>=6,"authority ledger decode")
    try check(snapshot.lanes.first{$0.asset=="AUDUSD"}?.validation?.calendarID=="FX_D1_V1","AUD validation authority")
    try check(snapshot.lanes.first{$0.asset=="XAUUSD"}?.validation?.calendarID=="METALS_D1_V1","XAU validation authority")
    try check(try Data(contentsOf:url)==before,"read mutated database")
}
try run("Price History uses bounded operational payloads",checkPriceHistoryRead)
try run("missing and incompatible rejection") {
    do { _=try SQLiteReadService().load(path:"/tmp/fragarach-ii-does-not-exist.sqlite3"); throw CheckFailure.failed("missing accepted") } catch is AuthorityReadError {}
    let url=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try Data("not sqlite".utf8).write(to:url);defer{try? FileManager.default.removeItem(at:url)}
    do { _=try SQLiteReadService().load(path:url.path);throw CheckFailure.failed("incompatible accepted") } catch is AuthorityReadError {}
}
try run("old seven-table authority rejected read-only") {
    do { _=try SQLiteReadService().load(path:oldSevenTableAuthority);throw CheckFailure.failed("unmigrated authority accepted") } catch is AuthorityReadError {}
}
try run("deterministic search filter sort") { let lanes=Array(try SQLiteReadService().load(path:authority).lanes.reversed());let usd=LaneQuery.apply(lanes,search:"usd",timeframe:"D1").map(\.asset);try check(usd==usd.sorted() && usd.contains("AUDUSD") && usd.contains("BTCUSD") && usd.contains("XAUUSD"),"sort");let xau=LaneQuery.apply(lanes,search:"xau",timeframe:nil);try check(xau.count==4 && Set(xau.map(\.asset))==["XAUUSD"] && Set(xau.map(\.timeframe))==["D1","H1","M30","M5"],"search") }
try run("native TruthState model and read-only bridge") {
    let config=CLIConfiguration(python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",repository:root.path,database:authority)
    let result=try ProcessBridge().run(.readTruth(symbol:"AUDUSD",timeframe:"D1"),config:config)
    try check(result.exitCode==0,"authority service failed")
    let state=try JSONDecoder().decode(TruthState.self,from:Data(result.stdout.utf8))
    try check(state.contract=="fragarach_ii.truth_state.v1" && state.symbol=="AUDUSD" && !state.explanation.components.isEmpty,"TruthState decode")
}
try run("native EstateTruthState model and read-only bridge") {
    let state=try readEstateTruthForChecks()
    try check(state.contract=="fragarach_ii.estate_truth_state.v1" && state.truthMatrix.count>=3,"EstateTruthState decode")
    try check(state.truthMatrix.map(\.id)==state.truthMatrix.map(\.id).sorted(),"estate ordering")
    try checkCanonicalObservationLineage(state)
}
try run("native identity resolution model and provider-free bridge") {
    let config=CLIConfiguration(python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",repository:root.path,database:authority)
    let result=try ProcessBridge().run(.resolveInstrument(query:"BHP"),config:config)
    try check(result.exitCode==0,"identity resolver failed")
    let resolution=try JSONDecoder().decode(InstrumentIdentityResolution.self,from:Data(result.stdout.utf8))
    try check(resolution.identityStatus=="AMBIGUOUS" && resolution.matches.map(\.canonicalSymbol)==["ASX:BHP","NYSE:BHP"],"identity resolution decode")
}
try run("native market discovery and onboarding model") {
    let config=CLIConfiguration(python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",repository:root.path,database:authority)
    let result=try ProcessBridge().run(.discoverMarket(query:"US30"),config:config);try check(result.exitCode==0,"market discovery failed")
    let discovery=try JSONDecoder().decode(MarketDiscoveryResult.self,from:Data(result.stdout.utf8));let market=try discovery.markets.first ?? {throw CheckFailure.failed("missing market")}()
    try check(market.recommendation.symbol=="US30" && market.representations.count==5 && !market.providerDiscovery.isEmpty,"market discovery decode")
}
try run("explicit secret-free arguments") { let db="/authority.sqlite3",secret="never-in-arguments";let intents:[OperationIntent]=[.readEstateTruth,.readTruth(symbol:"AUDUSD",timeframe:"D1"),.resolveInstrument(query:"Gold"),.discoverMarket(query:"US30"),.acquire(asset:"AUDUSD",timeframe:"H1",from:"2026-07-01",through:"2026-07-10",mode:.preserve),.importCSV(file:"/evidence.csv",symbol:"AUDUSD",timeframe:"H1",sourceTimezone:"Europe/Athens",d1DateFormat:"auto",mode:.preserve),.validate(symbol:"AUDUSD",timeframe:"D1",through:"2026-07-10",persist:true),.verify,.backup(destination:"/backup.sqlite3")];for intent in intents{let args=ArgumentBuilder.arguments(for:intent,database:db);try check(args.contains(db) && !args.contains(secret),"arguments")}}
try run("review confirmation gate") { let intent=OperationIntent.acquire(asset:"AUDUSD",timeframe:"H1",from:"2026-07-01",through:"2026-07-10",mode:.preserve);var gate=ReviewGate();try check(!gate.confirm(intent),"unreviewed");gate.review(intent);try check(gate.confirm(intent),"reviewed");try check(!gate.confirm(intent),"repeat") }
try run("secret filter") { try check(SecretFilter.filter("before SECRET middle SECRET",secrets:["SECRET"])=="before [REDACTED] middle [REDACTED]","filter") }
try run("credential authority projection decodes without secret material") { let json="{\"contract\":\"fragarach_ii.credential_authority.v1\",\"generated_at\":\"2026-07-15T05:00:00+00:00\",\"authority_revision\":\"revision\",\"providers\":[{\"provider\":\"TWELVE_DATA\",\"credential_state\":\"Available\",\"authority_revision\":\"provider-revision\",\"last_validation\":\"2026-07-15T05:00:00+00:00\",\"validation_source\":\"Twelve Data HTTP response\"}]}";let snapshot=try JSONDecoder().decode(CredentialAuthoritySnapshot.self,from:Data(json.utf8));try check(snapshot.providers.first?.credentialState=="Available" && !json.contains("fixture-only-secret"),"redacted authority projection") }
try run("known CLI identity") { let config=CLIConfiguration(python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",repository:root.path,database:authority);try ProcessBridge().validateCLI(config) }
try run("single active operation and cancellation") {
    try checkDuplicateSubmission()
}
try run("malformed child result remains factual") {
    let directory=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try FileManager.default.createDirectory(at:directory,withIntermediateDirectories:true);defer{try? FileManager.default.removeItem(at:directory)}
    let fake=directory.appendingPathComponent("python3");try "#!/bin/sh\necho not-json\nexit 7\n".write(to:fake,atomically:true,encoding:.utf8);try FileManager.default.setAttributes([.posixPermissions:0o700],ofItemAtPath:fake.path)
    let result=try ProcessBridge().run(.verify,config:.init(python:fake.path,repository:root.path,database:authority));try check(result.exitCode==7 && result.JSON==nil,"malformed result")
}
try run("zero blocking degraded decisions retain safe fallbacks") {
    let maximum=OperationalDecision.degraded(scope:"AUDUSD:D1:MAXIMUM_HISTORY",reason:"Terminal proof unavailable",safeFallbacks:["CUSTOM_RANGE","IMPORT_FILE"],unaffectedOperations:["RETIRE"])
    try check(!maximum.hardBlock && maximum.status == .degradedOperationAvailable,"degraded status")
    try check(maximum.safeFallbacks.contains("CUSTOM_RANGE") && maximum.unaffectedOperations.contains("RETIRE"),"safe continuations")
}
try run("Data Operations selection starts empty and uses stable registration identity") {
    var selection=DataOperationsSelection()
    try check(selection.selectedRegistrationID == nil,"initial selection")
    selection.select("AAPL:D1");try check(selection.selectedRegistrationID == "AAPL:D1","Apple selection")
    selection.select("EURAUD:D1");try check(selection.selectedRegistrationID == "EURAUD:D1","selection replacement")
}
try run("Data Operations selection reconciles refresh, filters, retirement, and navigation") {
    var selection=DataOperationsSelection(selectedRegistrationID:"AAPL:D1")
    selection.reconcile(visibleRegistrationIDs:["AAPL:D1","EURAUD:D1"]);try check(selection.selectedRegistrationID == "AAPL:D1","refresh preservation")
    selection.reconcile(visibleRegistrationIDs:["EURAUD:D1"]);try check(selection.selectedRegistrationID == nil,"filtered selection clearing")
    selection.applyNavigationContext("EURAUD:D1",visibleRegistrationIDs:["EURAUD:D1"]);try check(selection.selectedRegistrationID == "EURAUD:D1","valid context")
    selection.applyNavigationContext("JPYCHF:D1",visibleRegistrationIDs:["EURAUD:D1"]);try check(selection.selectedRegistrationID == nil,"invalid context")
}
try run("primary navigation contains the five SPEC-041 operator workspaces in order") {
    try check(ConsoleSection.allCases == [.overview,.estate,.scheduler,.history,.manageData],"workspace order")
    try check(ConsoleSection.allCases.map(\.rawValue)==["Overview","Estate","Scheduler","History","Manage Data"],"workspace labels")
}
try run("internal workspace sections preserve relocated capabilities") {
    try check(DataOperationsMode.allCases == [.fetch,.importFile,.retire,.history],"Data Operations modes")
    try check(SystemSection.allCases == [.status,.providerFacts,.backups,.settings,.audit],"System sections")
}
try run("provider facts bridge stays representation scoped") {
    let database="/tmp/facts.sqlite3"
    let resolve=ArgumentBuilder.arguments(for:.resolveProviderFacts(symbol:"EURUSD"),database:database)
    try check(resolve.contains("--symbol") && resolve.contains("EURUSD") && !resolve.contains("--timeframe"),"representation resolve arguments")
    let probe=ArgumentBuilder.arguments(for:.probeProviderCapability(symbol:"EURUSD",timeframe:"M5"),database:database)
    try check(probe.contains("--timeframe") && probe.contains("M5"),"timeframe probe arguments")
}
try run("credential authority transport stays redacted") {
    let secret="environment-secret"
    try check(SecretFilter.filter("value environment-secret",secrets:[secret])=="value [REDACTED]","credential redaction")
    try check(!ArgumentBuilder.arguments(for:.readProviderFacts,database:"/authority.sqlite3").contains(secret),"secret-free authority arguments")
}
try run("provider facts native contract decodes") {
    let json="""
    {"contract":"fragarach_ii.provider_facts.v1","resolver_version":1,"generated_at":"2026-07-14T04:00:00+00:00","credential_state":"Configured","resolved_automatically":[{"canonical_symbol":"EURUSD","canonical_base_asset":"EUR","canonical_quote_asset":"USD","canonical_instrument_type":"SPOT_FX","provider":"TWELVE_DATA","provider_symbol":"EUR/USD","provider_description":"Euro / US Dollar","provider_instrument_type":"Physical Currency","provider_asset_class":"FOREX","provider_base_asset":"EUR","provider_quote_asset":"USD","venue_or_market":"Forex","mapping_class":"EXACT_REPRESENTATION","resolution_method":"PROVIDER_REFERENCE_EXACT_BASE_QUOTE_AND_INSTRUMENT_CLASS","matching_rule":"STANDARD_FOREX_EXACT","status":"RESOLVED_AUTOMATICALLY","effective_time":"2026-07-14T04:00:00+00:00","last_verified":"2026-07-14T04:00:00+00:00","timeframe_capabilities":{"M5":{"timeframe":"M5","provider_interval":"5min","supported":true,"history_availability":"AVAILABLE_BY_PROVIDER_CONTRACT","maximum_rows":5000,"fragarach_request_ceiling":4000,"entitlement":"AVAILABLE","last_verified":"2026-07-14T04:00:00+00:00","verification_method":"APPROVED_TWELVE_DATA_INTERVAL_CONTRACT","reason":"TIMEFRAME_SUPPORTED"}},"resolution_evidence":{"provider_response_time":"2026-07-14T04:00:00+00:00","response_checksums":["sha256:test"],"api_credits_used":1,"api_usage_accounting":"PROVIDER_RESPONSE_HEADER"},"candidates":[]}],"needs_material_review":[],"credential_or_access_issue":null,"provider_lookup_failed":[],"retired_non_actionable":[],"reconciliation":{"lane_rows_originally_flagged":27,"retired_rows_removed":4,"representation_mappings_automatically_resolved":1,"timeframe_capabilities_verified":4,"credential_access_failures":0,"provider_lookup_failures":0,"genuine_operator_decisions_remaining":0,"decision_keys":[]}}
    """
    let facts=try JSONDecoder().decode(ProviderFactsSnapshot.self,from:Data(json.utf8))
    try check(facts.resolvedAutomatically.first?.providerSymbol=="EUR/USD","provider facts decode")
    try check(facts.resolvedAutomatically.first?.timeframeCapabilities["M5"]?.supported==true,"timeframe fact decode")
}
try run("legacy routes redirect to five-workspace destinations") {
    try check(NavigationRedirect.destination(for:.lanes).workspace == .estate,"lanes redirect")
    try check(NavigationRedirect.destination(for:.authorityLedger) == .init(workspace:.manageData,dataMode:nil,systemSection:.audit,manageDataSection:.system),"ledger redirect")
    try check(NavigationRedirect.destination(for:.operations) == .init(workspace:.manageData,dataMode:.history,systemSection:nil,manageDataSection:.operations),"operations redirect")
    try check(NavigationRedirect.destination(for:.integrityBackup).systemSection == .backups,"backup redirect")
    try check(NavigationRedirect.destination(for:.settings).systemSection == .settings,"settings redirect")
    try check(NavigationRedirect.destination(for:.acquire).dataMode == .fetch && NavigationRedirect.destination(for:.importEvidence).dataMode == .importFile,"data redirects")
}
try run("scheduler monitor contract decodes native live state") {
    let json="""
    {"contract":"fragarach_ii.scheduler_monitor.v1","generated_at":"2026-07-14T04:00:00+00:00","service_state":"Running","authority_health":{"state":"DEGRADED","detail":"1 lane requires attention"},"authority_revision":"sha256:test","summary":{"total":1,"Current":0,"Waiting":0,"Running":1,"Behind":0,"Unavailable":0,"Failed":0},"next_run":"2026-07-14T04:05:00+00:00","last_successful_acquisition":null,"last_failure":null,"active_activity":{"symbol":"AUDUSD","timeframe":"M5","stage":"Publishing","started_at":"2026-07-14T04:00:00+00:00"},"lanes":[{"id":"AUDUSD:M5","symbol":"AUDUSD","timeframe":"M5","scheduler_state":"Running","latest_canonical_observation":"2026-07-14T03:55:00+00:00","expected_latest":"2026-07-14T04:00:00+00:00","lag":{"count":1,"unit":"closed_interval"},"next_scheduled_acquisition":"2026-07-14T04:05:00+00:00","last_acquisition":"2026-07-14T04:00:00+00:00","duration_seconds":null,"result":null,"reason":null}],"events":[]}
    """
    let snapshot=try JSONDecoder().decode(SchedulerSnapshot.self,from:Data(json.utf8))
    try check(snapshot.lanes.first?.schedulerState == "Running" && snapshot.activeActivity?.stage == "Publishing","scheduler decode")
    try check(snapshot.providers.isEmpty && snapshot.manualRequests.isEmpty,"version 1 recovery defaults")
    let v2=json.replacingOccurrences(of:"fragarach_ii.scheduler_monitor.v1",with:"fragarach_ii.scheduler_monitor.v2").dropLast()+",\"providers\":[{\"provider\":\"TWELVE_DATA\",\"enabled\":true,\"supported_asset_classes\":[\"FX\"],\"supported_timeframes\":[\"D1\"],\"approved_symbol_mappings\":1,\"credential_requirement\":\"REQUIRED\",\"credentials\":\"Present\",\"entitlement\":\"AVAILABLE\",\"request_limit\":55,\"request_window_seconds\":60,\"maximum_rows_per_request\":4000,\"history_limitations\":null,\"cost_class\":2,\"priority\":10,\"health\":\"Healthy\",\"cooldown_until\":null,\"last_success\":null,\"last_failure\":null}],\"rate_budgets\":[{\"provider\":\"TWELVE_DATA\",\"limit\":55,\"window_seconds\":60,\"calls_used\":1,\"calls_available\":54,\"next_available\":null}],\"acquisition_queue\":[],\"routing_decisions\":[],\"manual_requests\":[]}"
    let upgraded=try JSONDecoder().decode(SchedulerSnapshot.self,from:Data(v2.utf8))
    try check(upgraded.providers.first?.provider=="TWELVE_DATA" && upgraded.rateBudgets.first?.callsAvailable==54,"version 2 provider and budget decode")
}
try run("controlled dates serialize canonically and validate ranges") {
    let iso=ISO8601DateFormatter(),start=iso.date(from:"1980-01-01T00:00:00Z")!,end=iso.date(from:"1990-01-01T00:00:00Z")!,boundary=iso.date(from:"2026-07-11T00:00:00Z")!
    let valid=ControlledDateRange(from:start,through:end,completedBoundary:boundary)
    try check(valid.fromISO=="1980-01-01" && valid.throughISO=="1990-01-01","ISO serialization")
    try check(valid.validation == .valid,"valid range")
    try check(ControlledDateRange(from:end,through:start,completedBoundary:boundary).validation == .reversed,"reversed range")
    if case .futureBoundary(let maximum)=ControlledDateRange(from:start,through:Date(timeIntervalSince1970:boundary.timeIntervalSince1970+86400),completedBoundary:boundary).validation{try check(maximum=="2026-07-11","future boundary")}else{throw CheckFailure.failed("future range accepted")}
}
try run("locale date input normalizes with visible ambiguous interpretation") {
    let au=try ControlledDateParser.parse("01/02/1980",locale:Locale(identifier:"en_AU")) ?? {throw CheckFailure.failed("AU date parse")}()
    try check(au.canonicalISO=="1980-02-01" && au.interpretation != nil,"ambiguous locale interpretation")
    try check(ControlledDateParser.parse("1 Jan 1980")?.canonicalISO=="1980-01-01","month date parse")
}
try run("controlled operational domains cannot emit arbitrary identifiers") {
    let registrations=try SQLiteReadService().load(path:authority).registrations
    try check(registrations.allSatisfy{$0.id=="\($0.asset):\($0.timeframe)"},"registration identity")
    try check(Set(registrations.map(\.timeframe)) == ["D1"],"controlled timeframe")
    try check(Set(registrations.map(\.providerID)).isSubset(of:["", "TWELVE_DATA", "YAHOO_FINANCE"]),"controlled provider")
}
try run("operation results are owned by one plan revision") {
    let first=UUID(),second=UUID(),result=ProcessResult(operationID:UUID(),exitCode:1,stdout:"{\"evidence_committed\":false}",stderr:"")
    let owned=OwnedOperationResult(planRevision:first,result:result)
    try check(owned.planRevision==first && owned.planRevision != second,"result ownership")
    try check(owned.result.exitCode==1 && owned.result.JSON?["evidence_committed"] as? Bool == false,"pre-mutation failure")
}
try run("import plans dispatch only immutable CSV ingestion and isolate results") {
    try checkImportDispatch()
}
try run("native data-operation lifecycle and labels") {
    try checkOperationState()
}
try run("native Scheduler mutation state and recovery actions") {
    try checkSchedulerRecoveryState()
}
try run("SPEC-057 native Scheduler bridge is monitor-only") {
    try checkSchedulerBridgeMonitorOnly()
}
try run("SPEC-055 Truth Matrix lifecycle state requires trace ownership") {
    try check(SchedulerLifecycleStateResolver.resolve(activeTrace:false,queueExists:true,queueState:"Ready",queueHasTrace:true,queueHasWorker:false,stopReason:nil,nextAttempt:nil,schedulerState:"Behind",fallback:"Behind")=="Queued","queued state")
    try check(SchedulerLifecycleStateResolver.resolve(activeTrace:false,queueExists:true,queueState:"Running",queueHasTrace:true,queueHasWorker:true,stopReason:nil,nextAttempt:nil,schedulerState:"Behind",fallback:"Behind")=="Downloading","owned download state")
    try check(SchedulerLifecycleStateResolver.resolve(activeTrace:false,queueExists:true,queueState:"Running",queueHasTrace:false,queueHasWorker:false,stopReason:nil,nextAttempt:nil,schedulerState:"Behind",fallback:"Behind")=="Queued","stale running state rejected")
    try check(SchedulerLifecycleStateResolver.resolve(activeTrace:false,queueExists:true,queueState:"Ready",queueHasTrace:true,queueHasWorker:false,stopReason:"PROVIDER_COOLDOWN",nextAttempt:"2026-07-15T02:00:00Z",schedulerState:"Behind",fallback:"Behind")=="Behind","deferred state")
    try check(SchedulerLifecycleStateResolver.resolve(activeTrace:false,queueExists:false,queueState:nil,queueHasTrace:false,queueHasWorker:false,stopReason:nil,nextAttempt:nil,schedulerState:"Current",fallback:"Behind")=="Current","completed item removal")
}
try run("SPEC-058 manual authority and Estate presentation stay separate") {
    let iso=ISO8601DateFormatter()
    let range=ControlledDateRange(
        from:iso.date(from:"2026-07-01T00:00:00Z")!,
        through:iso.date(from:"2026-07-14T00:00:00Z")!,
        completedBoundary:iso.date(from:"2026-07-14T00:00:00Z")!
    )
    let provider=UnifiedAcquisitionProvider(
        provider:"TWELVE_DATA",providerSymbol:"GBP/AUD",
        mappingStatus:"EXACT_REPRESENTATION",eligible:true,priority:10
    )
    let manual=UnifiedAcquisitionPlan.build(
        instrument:"GBPAUD",timeframe:"H1",assetClass:"FX",intent:.initial,
        canonicalEdge:nil,expectedEdge:"2026-07-14T00:00:00Z",providers:[provider],reviewedRange:range,
        registrationActive:true,operationActive:false,acquisitionPaused:false
    )
    try check(manual.isExecutable && manual.operationIntent != nil,"uncommissioned manual fetch was blocked")
    let planningNow=iso.date(from:"2026-07-14T14:02:00Z")!
    for row in [
        ("H1","2026-07-14T14:00:00Z","2023-07-14T14:00:00Z","3 years"),
        ("M30","2026-07-14T14:00:00Z","2024-07-14T14:00:00Z","2 years"),
        ("M5","2026-07-14T14:00:00Z","2025-07-14T14:00:00Z","1 year"),
    ] {
        let initial=UnifiedAcquisitionPlan.build(
            instrument:"GBPAUD",timeframe:row.0,assetClass:"FX",intent:.initial,
            canonicalEdge:nil,expectedEdge:nil,providers:[provider],reviewedRange:nil,
            registrationActive:true,operationActive:false,acquisitionPaused:false,
            planningNow:planningNow
        )
        try check(initial.isExecutable && initial.operationIntent != nil,"\(row.0) initial plan without canonical edge was blocked")
        try check(initial.canonicalEdge == nil && initial.expectedEdge == row.1,"\(row.0) initial plan did not derive the FX expected edge")
        try check(initial.requestStart == row.2 && initial.requestEnd == row.1,"\(row.0) initial plan did not use governed historical bounds")
        try check(initial.selectedProvider?.provider=="TWELVE_DATA" && initial.selectedProvider?.providerSymbol=="GBP/AUD","\(row.0) initial plan did not keep the approved Twelve Data mapping")
        try check(initial.acquisitionIntent == .initial && initial.historicalDepth == row.3,"\(row.0) initial plan lost its initial-history authority")
    }
    let unmapped=UnifiedAcquisitionProvider(
        provider:"TWELVE_DATA",providerSymbol:nil,mappingStatus:"MAPPING_REQUIRED",
        eligible:false,priority:10,rejectionReason:"NO_APPROVED_MAPPING"
    )
    let blockedInitial=UnifiedAcquisitionPlan.build(
        instrument:"GBPAUD",timeframe:"H1",assetClass:"FX",intent:.initial,
        canonicalEdge:nil,expectedEdge:nil,providers:[unmapped],reviewedRange:nil,
        registrationActive:true,operationActive:false,acquisitionPaused:false,
        planningNow:planningNow
    )
    try check(!blockedInitial.isExecutable && blockedInitial.providerSetupRequired,"unmapped initial plan became executable")
    try check(blockedInitial.expectedEdge=="2026-07-14T14:00:00Z" && blockedInitial.requestStart != nil,"unmapped initial plan hid governed bounds")
    let pendingPublication=UnifiedAcquisitionPlan.build(
        instrument:"BNBUSD",timeframe:"D1",assetClass:"CRYPTO",intent:.initial,
        canonicalEdge:nil,expectedEdge:"2026-07-17T00:00:00Z",providers:[
            .init(provider:"COINGECKO",providerSymbol:"binancecoin",mappingStatus:"APPROVED_PROVIDER_ALIAS",eligible:true,priority:30),
        ],reviewedRange:nil,registrationActive:true,operationActive:false,
        acquisitionPaused:false,publicationPending:true
    )
    try check(pendingPublication.isExecutable && !pendingPublication.providerSetupRequired,"publication status blocked a revision-safe follow-up fetch")
    try check(pendingPublication.selectedProvider?.provider=="COINGECKO" && pendingPublication.failure == nil,"pending publication hid the approved BNB fetch route")
    try check(EstateLanePresentation.operationalState(commissioned:false,resolvedState:"Unavailable",providerEligible:true)=="Not Commissioned","uncommissioned lane rendered as failure")
    try check(EstateLanePresentation.operationalState(commissioned:true,resolvedState:"Missing",providerEligible:true)=="Behind","healthy commissioned gap rendered unavailable")
    try check(EstateLanePresentation.operationalState(commissioned:true,resolvedState:"Unavailable",providerEligible:false)=="Unavailable","genuine acquisition inability hidden")
    try check(EstateLanePresentation.commissioning(false)=="Not Commissioned" && EstateLanePresentation.automation(false)=="Disabled","detail authority labels were combined")
}
try run("SPEC-059 index Update planning classifies edge and fallback authority") {
    let twelve=UnifiedAcquisitionProvider(
        provider:"TWELVE_DATA",providerSymbol:nil,mappingStatus:"MAPPING_REQUIRED",
        eligible:false,priority:10,rejectionReason:"NO_APPROVED_MAPPING"
    )
    let yahoo=UnifiedAcquisitionProvider(
        provider:"YAHOO_FINANCE",providerSymbol:"^DJI",
        mappingStatus:"APPROVED_PROVIDER_ALIAS",eligible:true,priority:20
    )
    let update=UnifiedAcquisitionPlan.build(
        instrument:"DJI",timeframe:"D1",assetClass:"INDICES",intent:.update,
        canonicalEdge:"2026-07-13T00:00:00Z",expectedEdge:"2026-07-14T00:00:00Z",
        providers:[twelve,yahoo],reviewedRange:nil,registrationActive:true,
        operationActive:false,acquisitionPaused:false,expectedEdgeStatus:"EXPECTED_EDGE_AVAILABLE"
    )
    try check(update.isExecutable && update.expectedEdge=="2026-07-14T00:00:00Z","DJI expected edge remained blank")
    try check(update.selectedProvider?.provider=="YAHOO_FINANCE" && update.selectedProvider?.providerSymbol=="^DJI","approved Yahoo fallback was not selected")
    try check(update.requestStart != nil && update.requestEnd=="2026-07-14T00:00:00Z","DJI request bounds were not explicit")
    let unresolved=UnifiedAcquisitionPlan.build(
        instrument:"DJI",timeframe:"D1",assetClass:"INDICES",intent:.update,
        canonicalEdge:"2026-07-13T00:00:00Z",expectedEdge:nil,providers:[yahoo],
        reviewedRange:nil,registrationActive:true,operationActive:false,
        acquisitionPaused:false,expectedEdgeStatus:"INSTRUMENT_CALENDAR_UNRESOLVED"
    )
    try check(unresolved.failure=="Update unavailable: operational calendar unresolved.","blank edge did not expose calendar stop reason")
    let current=UnifiedAcquisitionPlan.build(
        instrument:"SPY",timeframe:"D1",assetClass:"INDICES",intent:.update,
        canonicalEdge:"2026-07-14T00:00:00Z",expectedEdge:"2026-07-14T00:00:00Z",
        providers:[yahoo],reviewedRange:nil,registrationActive:true,
        operationActive:false,acquisitionPaused:false,expectedEdgeStatus:"NO_NEW_COMPLETED_SESSION"
    )
    try check(!current.isExecutable && current.failure==nil && current.noUpdateReason != nil,"no-update state was presented as a failure")
}
try run("SPEC-057 legacy evidence chooses Update before provider setup") {
    let unmappedYahoo=UnifiedAcquisitionProvider(
        provider:"YAHOO_FINANCE",providerSymbol:nil,mappingStatus:"MAPPING_REQUIRED",
        eligible:false,priority:20,rejectionReason:"NO_APPROVED_MAPPING"
    )
    let legacy=UnifiedAcquisitionPlan.build(
        instrument:"FDX",timeframe:"D1",assetClass:"US_EQUITIES",intent:.initial,
        canonicalEdge:"2026-07-14T00:00:00Z",expectedEdge:"2026-07-15T00:00:00Z",
        providers:[unmappedYahoo],reviewedRange:nil,registrationActive:true,
        operationActive:false,acquisitionPaused:false,expectedEdgeStatus:"EXPECTED_EDGE_AVAILABLE"
    )
    try check(legacy.acquisitionIntent == .update,"canonical evidence did not govern the acquisition intent")
    try check(legacy.providerSetupRequired && !legacy.isExecutable,"unmapped legacy provider setup became executable")
    try check(legacy.failure == "Provider setup required.","legacy provider setup was rendered as a generic provider failure")
    try check(legacy.requestStart != nil && legacy.requestEnd == "2026-07-15T00:00:00Z","Update bounds were hidden before provider setup")
    let empty=UnifiedAcquisitionPlan.build(
        instrument:"NEW",timeframe:"D1",assetClass:"US_EQUITIES",intent:.update,
        canonicalEdge:nil,expectedEdge:"2026-07-15T00:00:00Z",providers:[unmappedYahoo],
        reviewedRange:nil,registrationActive:true,operationActive:false,acquisitionPaused:false
    )
    try check(empty.acquisitionIntent == .initial && empty.historicalDepth == "10 years","an empty lane did not retain initial-history intent")
}
try run("SPEC-060 scheduler health and monitor transport remain independent") {
    let json="""
    {"contract":"fragarach_ii.scheduler_service_status.v1","service_state":"UNREACHABLE","installed":true,"live":false,"compatibility":"Compatible","restart_count":0,"automatic_login_start":true,"acquisition_owner_active":true,"recommended_actions":["RETRY_CONNECTION","REPAIR_MONITOR"],"operational_health":{"contract":"fragarach_ii.scheduler_operational_health.v1","overall_operational_health":"HEALTHY","process":{"state":"ALIVE"},"heartbeat":{"state":"CURRENT","at":"2026-07-15T05:00:00+00:00","age_seconds":1.0},"monitor_transport":{"state":"MONITOR_DISCONNECTED"},"selection_loop":{"state":"HEALTHY","last_progress":"2026-07-15T04:59:58+00:00"},"worker_pool":{"state":"HEALTHY","active_workers":1,"available_workers":0},"provider_dispatch":{"state":"HEALTHY","last_progress":"2026-07-15T04:59:59+00:00"},"provider_response":{"state":"HEALTHY","last_progress":"2026-07-15T04:59:59+00:00"},"evidence_admission":{"state":"HEALTHY","last_progress":"2026-07-15T04:59:59+00:00"},"publication":{"state":"HEALTHY","last_progress":"2026-07-15T04:59:59+00:00"},"queue_progress":{"state":"HEALTHY","last_progress":"2026-07-15T04:59:59+00:00"},"actionable_queue_depth":1,"blocked_queue_depth":0,"total_queue_depth":1,"oldest_actionable_age_seconds":20.0,"last_meaningful_progress":"2026-07-15T04:59:59+00:00","permitted_progress_window_seconds":45.0,"current_trace_id":"trace-one","current_lane":"AUDUSD:M5","current_stage":"REQUEST_STARTED","current_stop_reason":null}}
    """
    let status=try JSONDecoder().decode(SchedulerServiceStatus.self,from:Data(json.utf8))
    try check(status.operationalHealth?.overallOperationalHealth=="HEALTHY","monitor disconnect erased service health")
    try check(status.operationalHealth?.monitorTransport.state=="MONITOR_DISCONNECTED","monitor transport state not decoded")
    try check(status.operationalHealth?.currentLane=="AUDUSD:M5" && status.operationalHealth?.workerPool.activeWorkers==1,"progress facts not decoded")
    let repair=ArgumentBuilder.arguments(for:.schedulerServiceAction("repair-monitor"),database:"/authority.sqlite3")
    try check(repair.contains("repair-monitor") && !repair.contains("repair"),"Repair Monitor routed through full service repair")
}
print("OperationsCoreChecks: \(passed) checks passed")
