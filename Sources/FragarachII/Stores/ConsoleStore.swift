import Foundation
import OperationsCore
import SwiftUI

@MainActor final class ConsoleStore: ObservableObject {
    @AppStorage("databasePath") var databasePath = "/Users/raymorgan/VSC/Fragarach_2/data/runtime/spec002_real_evidence_acceptance.sqlite3"
    @AppStorage("repositoryPath") var repositoryPath = "/Users/raymorgan/VSC/Fragarach_2"
    @AppStorage("pythonPath") var pythonPath = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    @Published var section: ConsoleSection = .truth
    @Published var dataOperationsMode: DataOperationsMode = .fetch
    @Published var systemSection: SystemSection = .status
    @Published var auditFilter = ""
    @Published var snapshot: AuthoritySnapshot?
    @Published var estateTruth: EstateTruthState?
    @Published var selectedTruthLaneID: String?
    @Published var estateTruthError: String?
    @Published var selectedLaneID: String?
    @Published var selectedOperationID: String?
    @Published var readError: String?
    @Published var isRefreshing=false
    @Published var activeOperationID: UUID?
    @Published var lastProcessResult: ProcessResult?
    @Published var currentPlanRevision=UUID()
    @Published var currentOperationResult: OwnedOperationResult?
    @Published var operationError: String?
    @Published var acquisitionAsset: String?
    private let reader=SQLiteReadService(); let bridge=ProcessBridge()
    var configuration: CLIConfiguration { .init(python:pythonPath,repository:repositoryPath,database:databasePath) }
    var credentialAvailable: Bool { CredentialResolver.resolve() != nil }

    func refresh() async {
        guard !isRefreshing else{return}; isRefreshing=true; defer{isRefreshing=false}
        do {
            let config=configuration, bridge=self.bridge
            let result=try await Task.detached {
                try bridge.validateCLI(config)
                let process=try bridge.run(.readEstateTruth,config:config)
                guard process.exitCode==0 else { throw BridgeError.malformedResult }
                return try JSONDecoder().decode(EstateTruthState.self,from:Data(process.stdout.utf8))
            }.value
            estateTruth=result; estateTruthError=nil
            if selectedTruthLaneID==nil || !result.truthMatrix.contains(where:{$0.id==selectedTruthLaneID}) { selectedTruthLaneID=result.truthMatrix.first?.id }
        } catch { estateTruthError=error.localizedDescription }
        do { let path=databasePath; let result=try await Task.detached { try self.reader.load(path:path) }.value; snapshot=result; readError=nil; if selectedLaneID==nil { selectedLaneID=result.lanes.first?.id } }
        catch { readError=error.localizedDescription }
    }
    func run(_ intent:OperationIntent) async {
        guard activeOperationID==nil else{return}; operationError=nil;currentOperationResult=nil;let id=UUID();activeOperationID=id;QuitGuard.shared.begin { [weak self] in self?.bridge.cancel() }
        do { let config=configuration,revision=currentPlanRevision;let credential: String? = { switch intent { case .acquire,.searchInstrument:return CredentialResolver.resolve();default:return nil } }(); let result=try await Task.detached { try self.bridge.validateCLI(config); return try self.bridge.run(intent,config:config,credential:credential) }.value; lastProcessResult=result;currentOperationResult = .init(planRevision:revision,result:result);if result.exitCode != 0 { operationError=result.stderr.isEmpty ? result.stdout:result.stderr } }
        catch { operationError=error.localizedDescription }
        QuitGuard.shared.end(); activeOperationID=nil; await refresh()
    }
    func cancel(){bridge.cancel()}
    func clearCurrentOperationResult(){currentPlanRevision=UUID();currentOperationResult=nil;operationError=nil}
    func navigate(_ route:LegacyRoute,asset:String?=nil){let target=NavigationRedirect.destination(for:route);section=target.workspace;if let mode=target.dataMode{dataOperationsMode=mode};if let system=target.systemSection{systemSection=system};if let asset{acquisitionAsset=asset}}
}
