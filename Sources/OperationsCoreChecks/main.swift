import Foundation
import OperationsCore
import Darwin

enum CheckFailure: Error { case failed(String) }
func check(_ condition: @autoclosure () throws -> Bool, _ message: String) throws { if try !condition() { throw CheckFailure.failed(message) } }

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
    try check(plan.intent == .importCSV(file:"/tmp/FX_USDJPY.csv",symbol:"USDJPY",timeframe:"D1",mode:.preserve),"import dispatched outside ingest_file")
    try check(plan.matches(mode:.importFile,instrument:"USDJPY",timeframe:"D1",fileChecksum:"abc123"),"matching import plan rejected")
    try check(!plan.matches(mode:.fetch,instrument:"USDJPY",timeframe:"D1",fileChecksum:"abc123"),"fetch result leaked into import")
    try check(!plan.matches(mode:.importFile,instrument:"USDJPY",timeframe:"D1",fileChecksum:"changed"),"stale file checksum accepted")
}
if ProcessInfo.processInfo.environment["FOCUSED_IMPORT_DISPATCH"] == "1" {
    try run("import plans dispatch only immutable CSV ingestion and isolate results",checkImportDispatch)
    print("OperationsCoreChecks: \(passed) focused checks passed")
    exit(EXIT_SUCCESS)
}

try run("read-only real schema and bounded queries") {
    let url=URL(fileURLWithPath:authority), before=try Data(contentsOf:url), snapshot=try SQLiteReadService().load(path:authority,operationLimit:5)
    try check(Set(["AUDUSD","BTCUSD","XAUUSD"]).isSubset(of:Set(snapshot.lanes.map(\.asset))),"lane decode")
    try check(snapshot.operations.count==5,"bounded operations")
    try check(snapshot.authorityEvents.count>=6,"authority ledger decode")
    try check(snapshot.lanes.first{$0.asset=="AUDUSD"}?.validation?.outsideExpectedSessionCount==16,"AUD outside sessions")
    try check(snapshot.lanes.first{$0.asset=="XAUUSD"}?.validation?.outsideExpectedSessionCount==49,"XAU outside sessions")
    try check(try Data(contentsOf:url)==before,"read mutated database")
}
try run("missing and incompatible rejection") {
    do { _=try SQLiteReadService().load(path:"/tmp/fragarach-ii-does-not-exist.sqlite3"); throw CheckFailure.failed("missing accepted") } catch is AuthorityReadError {}
    let url=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try Data("not sqlite".utf8).write(to:url);defer{try? FileManager.default.removeItem(at:url)}
    do { _=try SQLiteReadService().load(path:url.path);throw CheckFailure.failed("incompatible accepted") } catch is AuthorityReadError {}
}
try run("old seven-table authority rejected read-only") {
    do { _=try SQLiteReadService().load(path:oldSevenTableAuthority);throw CheckFailure.failed("unmigrated authority accepted") } catch is AuthorityReadError {}
}
try run("deterministic search filter sort") { let lanes=Array(try SQLiteReadService().load(path:authority).lanes.reversed());try check(LaneQuery.apply(lanes,search:"usd",timeframe:"D1").map(\.asset)==["AUDUSD","BTCUSD","XAUUSD"],"sort");try check(LaneQuery.apply(lanes,search:"xau",timeframe:nil).map(\.asset)==["XAUUSD"],"search") }
try run("native TruthState model and read-only bridge") {
    let config=CLIConfiguration(python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",repository:root.path,database:authority)
    let result=try ProcessBridge().run(.readTruth(symbol:"AUDUSD",timeframe:"D1"),config:config)
    try check(result.exitCode==0,"authority service failed")
    let state=try JSONDecoder().decode(TruthState.self,from:Data(result.stdout.utf8))
    try check(state.contract=="fragarach_ii.truth_state.v1" && state.symbol=="AUDUSD" && !state.explanation.components.isEmpty,"TruthState decode")
}
try run("native EstateTruthState model and read-only bridge") {
    let config=CLIConfiguration(python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",repository:root.path,database:authority)
    let result=try ProcessBridge().run(.readEstateTruth,config:config)
    try check(result.exitCode==0,"estate truth service failed")
    let state=try JSONDecoder().decode(EstateTruthState.self,from:Data(result.stdout.utf8))
    try check(state.contract=="fragarach_ii.estate_truth_state.v1" && state.truthMatrix.count>=3,"EstateTruthState decode")
    try check(state.truthMatrix.map(\.id)==state.truthMatrix.map(\.id).sorted(),"estate ordering")
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
try run("explicit secret-free arguments") { let db="/authority.sqlite3",secret="never-in-arguments";let intents:[OperationIntent]=[.readEstateTruth,.readTruth(symbol:"AUDUSD",timeframe:"D1"),.resolveInstrument(query:"Gold"),.discoverMarket(query:"US30"),.acquire(asset:"AUDUSD",from:"2026-07-01",through:"2026-07-10",mode:.preserve),.importCSV(file:"/evidence.csv",symbol:"AUDUSD",timeframe:"D1",mode:.preserve),.validate(symbol:"AUDUSD",timeframe:"D1",through:"2026-07-10",persist:true),.verify,.backup(destination:"/backup.sqlite3")];for intent in intents{let args=ArgumentBuilder.arguments(for:intent,database:db);try check(args.contains(db) && !args.contains(secret),"arguments")}}
try run("review confirmation gate") { let intent=OperationIntent.acquire(asset:"AUDUSD",from:"2026-07-01",through:"2026-07-10",mode:.preserve);var gate=ReviewGate();try check(!gate.confirm(intent),"unreviewed");gate.review(intent);try check(gate.confirm(intent),"reviewed");try check(!gate.confirm(intent),"repeat") }
try run("secret filter") { try check(SecretFilter.filter("before SECRET middle SECRET",secrets:["SECRET"])=="before [REDACTED] middle [REDACTED]","filter") }
try run("credential alias memory resolution") { let file=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try "TWELVEDATA_API_KEY=fixture-only-secret\n".write(to:file,atomically:true,encoding:.utf8);defer{try? FileManager.default.removeItem(at:file)};try check(CredentialResolver.resolve(environment:[:],authorizedFile:file.path)=="fixture-only-secret","alias") }
try run("known CLI identity") { let config=CLIConfiguration(python:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",repository:root.path,database:authority);try ProcessBridge().validateCLI(config) }
try run("single active operation and cancellation") {
    let directory=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try FileManager.default.createDirectory(at:directory,withIntermediateDirectories:true);defer{try? FileManager.default.removeItem(at:directory)}
    let fake=directory.appendingPathComponent("python3");try "#!/usr/bin/python3\nimport time\ntime.sleep(10)\nprint('{}')\n".write(to:fake,atomically:true,encoding:.utf8);try FileManager.default.setAttributes([.posixPermissions:0o700],ofItemAtPath:fake.path)
    let bridge=ProcessBridge(),config=CLIConfiguration(python:fake.path,repository:root.path,database:authority),group=DispatchGroup();group.enter()
    DispatchQueue.global().async { _=try? bridge.run(.verify,config:config);group.leave() }
    for _ in 0..<50 { if bridge.isActive { break }; usleep(20_000) }
    try check(bridge.isActive,"operation did not become active")
    do { _=try bridge.run(.verify,config:config);throw CheckFailure.failed("second operation accepted") } catch BridgeError.operationActive {}
    bridge.cancel();try check(group.wait(timeout: .now() + 3) == .success,"cancel did not finish")
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
try run("primary navigation contains exactly four operator workspaces in order") {
    try check(ConsoleSection.allCases == [.truth,.discoverMarket,.dataOperations,.system],"workspace order")
    try check(ConsoleSection.allCases.map(\.rawValue)==["Truth","Discover Market","Data Operations","System"],"workspace labels")
}
try run("internal workspace sections preserve relocated capabilities") {
    try check(DataOperationsMode.allCases == [.fetch,.importFile,.retire,.history],"Data Operations modes")
    try check(SystemSection.allCases == [.status,.backups,.settings,.audit],"System sections")
}
try run("legacy routes redirect to four-workspace destinations") {
    try check(NavigationRedirect.destination(for:.lanes).workspace == .truth,"lanes redirect")
    try check(NavigationRedirect.destination(for:.authorityLedger) == .init(workspace:.system,dataMode:nil,systemSection:.audit),"ledger redirect")
    try check(NavigationRedirect.destination(for:.operations) == .init(workspace:.dataOperations,dataMode:.history,systemSection:nil),"operations redirect")
    try check(NavigationRedirect.destination(for:.integrityBackup).systemSection == .backups,"backup redirect")
    try check(NavigationRedirect.destination(for:.settings).systemSection == .settings,"settings redirect")
    try check(NavigationRedirect.destination(for:.acquire).dataMode == .fetch && NavigationRedirect.destination(for:.importEvidence).dataMode == .importFile,"data redirects")
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
print("OperationsCoreChecks: \(passed) checks passed")
