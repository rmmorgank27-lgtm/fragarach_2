import Foundation
import OperationsCore

enum CheckFailure: Error { case failed(String) }
func check(_ condition: @autoclosure () throws -> Bool, _ message: String) throws { if try !condition() { throw CheckFailure.failed(message) } }

let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
let authority = root.appendingPathComponent("data/runtime/spec002_real_evidence_acceptance.sqlite3").path
var passed = 0
@MainActor func run(_ name: String, _ body: () throws -> Void) throws { try body(); passed += 1; print("PASS \(name)") }

try run("read-only real schema and bounded queries") {
    let url=URL(fileURLWithPath:authority), before=try Data(contentsOf:url), snapshot=try SQLiteReadService().load(path:authority,operationLimit:5)
    try check(snapshot.lanes.map(\.asset)==["AUDUSD","BTCUSD","XAUUSD"],"lane decode")
    try check(snapshot.operations.count==5,"bounded operations")
    try check(snapshot.lanes.first{$0.asset=="AUDUSD"}?.validation?.outsideExpectedSessionCount==16,"AUD outside sessions")
    try check(snapshot.lanes.first{$0.asset=="XAUUSD"}?.validation?.outsideExpectedSessionCount==49,"XAU outside sessions")
    try check(try Data(contentsOf:url)==before,"read mutated database")
}
try run("missing and incompatible rejection") {
    do { _=try SQLiteReadService().load(path:"/tmp/fragarach-ii-does-not-exist.sqlite3"); throw CheckFailure.failed("missing accepted") } catch is AuthorityReadError {}
    let url=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString);try Data("not sqlite".utf8).write(to:url);defer{try? FileManager.default.removeItem(at:url)}
    do { _=try SQLiteReadService().load(path:url.path);throw CheckFailure.failed("incompatible accepted") } catch is AuthorityReadError {}
}
try run("deterministic search filter sort") { let lanes=Array(try SQLiteReadService().load(path:authority).lanes.reversed());try check(LaneQuery.apply(lanes,search:"usd",timeframe:"D1").map(\.asset)==["AUDUSD","BTCUSD","XAUUSD"],"sort");try check(LaneQuery.apply(lanes,search:"xau",timeframe:nil).map(\.asset)==["XAUUSD"],"search") }
try run("explicit secret-free arguments") { let db="/authority.sqlite3",secret="never-in-arguments";let intents:[OperationIntent]=[.acquire(asset:"AUDUSD",from:"2026-07-01",through:"2026-07-10",mode:.preserve),.importCSV(file:"/evidence.csv",symbol:"AUDUSD",timeframe:"D1",mode:.preserve),.validate(symbol:"AUDUSD",timeframe:"D1",through:"2026-07-10",persist:true),.verify,.backup(destination:"/backup.sqlite3")];for intent in intents{let args=ArgumentBuilder.arguments(for:intent,database:db);try check(args.contains(db) && !args.contains(secret),"arguments")}}
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
print("OperationsCoreChecks: \(passed) checks passed")
