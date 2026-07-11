import Foundation
import OperationsCore
import SwiftUI

@MainActor final class ConsoleStore: ObservableObject {
    @AppStorage("databasePath") var databasePath = "/Users/raymorgan/VSC/Fragarach_2/data/runtime/spec002_real_evidence_acceptance.sqlite3"
    @AppStorage("repositoryPath") var repositoryPath = "/Users/raymorgan/VSC/Fragarach_2"
    @AppStorage("pythonPath") var pythonPath = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    @Published var section: ConsoleSection = .lanes
    @Published var snapshot: AuthoritySnapshot?
    @Published var selectedLaneID: String?
    @Published var selectedOperationID: String?
    @Published var readError: String?
    @Published var isRefreshing=false
    @Published var activeOperationID: UUID?
    @Published var lastProcessResult: ProcessResult?
    @Published var operationError: String?
    private let reader=SQLiteReadService(); let bridge=ProcessBridge()
    var configuration: CLIConfiguration { .init(python:pythonPath,repository:repositoryPath,database:databasePath) }
    var credentialAvailable: Bool { CredentialResolver.resolve() != nil }

    func refresh() async {
        guard !isRefreshing else{return}; isRefreshing=true; defer{isRefreshing=false}
        do { let path=databasePath; let result=try await Task.detached { try self.reader.load(path:path) }.value; snapshot=result; readError=nil; if selectedLaneID==nil { selectedLaneID=result.lanes.first?.id } }
        catch { readError=error.localizedDescription }
    }
    func run(_ intent:OperationIntent) async {
        guard activeOperationID==nil else{return}; operationError=nil; let id=UUID(); activeOperationID=id; QuitGuard.shared.begin { [weak self] in self?.bridge.cancel() }
        do { let config=configuration; let credential: String? = { switch intent { case .acquire,.searchInstrument:return CredentialResolver.resolve();default:return nil } }(); let result=try await Task.detached { try self.bridge.validateCLI(config); return try self.bridge.run(intent,config:config,credential:credential) }.value; lastProcessResult=result; if result.exitCode != 0 { operationError=result.stderr.isEmpty ? result.stdout:result.stderr } }
        catch { operationError=error.localizedDescription }
        QuitGuard.shared.end(); activeOperationID=nil; await refresh()
    }
    func cancel(){bridge.cancel()}
}
