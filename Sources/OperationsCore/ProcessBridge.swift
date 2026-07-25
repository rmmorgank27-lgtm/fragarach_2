import Foundation

private final class PipeBuffer:@unchecked Sendable{private let lock=NSLock();private var value=Data();func set(_ data:Data){lock.withLock{value=data}};func append(_ data:Data){lock.withLock{value.append(data)}};func get()->Data{lock.withLock{value}}}

public struct OperationProgressDetail:Equatable,Sendable {
    public let state:DataOperationState
    public let provider:String?
    public let nextProvider:String?
    public let fallbackPosition:Int?
    public let fallbackCount:Int?
    public init(state:DataOperationState,provider:String?,nextProvider:String?,fallbackPosition:Int?,fallbackCount:Int?){self.state=state;self.provider=provider;self.nextProvider=nextProvider;self.fallbackPosition=fallbackPosition;self.fallbackCount=fallbackCount}
}

private final class ProgressPipeBuffer:@unchecked Sendable {
    private let buffer=PipeBuffer()
    private let lock=NSLock()
    private var pending=Data()
    private let progress: (@Sendable (DataOperationState)->Void)?
    private let progressDetail:(@Sendable (OperationProgressDetail)->Void)?
    init(progress:(@Sendable (DataOperationState)->Void)?,progressDetail:(@Sendable (OperationProgressDetail)->Void)?){self.progress=progress;self.progressDetail=progressDetail}
    func append(_ data:Data) {
        buffer.append(data)
        lock.withLock {
            pending.append(data)
            while let newline=pending.firstIndex(of:10) {
                let line=String(decoding:pending[..<newline],as:UTF8.self)
                pending.removeSubrange(...newline)
                guard let bytes=line.data(using:.utf8),
                      let object=try? JSONSerialization.jsonObject(with:bytes) as? [String:Any],
                      let raw=object["fragarach_operation_stage"],
                      let state=DataOperationState(rawValue:raw as? String ?? "") else { continue }
                progress?(state)
                progressDetail?(.init(state:state,provider:object["provider"] as? String,nextProvider:object["next_provider"] as? String,fallbackPosition:object["fallback_position"] as? Int,fallbackCount:object["fallback_count"] as? Int))
            }
        }
    }
    func filteredData()->Data {
        let text=String(decoding:buffer.get(),as:UTF8.self)
        return Data(text.split(separator:"\n",omittingEmptySubsequences:false).filter { line in
            guard let bytes=line.data(using:.utf8),
                  let object=try? JSONSerialization.jsonObject(with:bytes) as? [String:String]
            else { return true }
            return object["fragarach_operation_stage"] == nil
        }.joined(separator:"\n").utf8)
    }
}

public enum BridgeError: Error, LocalizedError, Sendable {
    case incompatibleCLI, operationActive, malformedResult, missingCredential
    public var errorDescription: String? { switch self { case .incompatibleCLI: "Fragarach II CLI identity check failed"; case .operationActive: "Another mutating operation is active"; case .malformedResult: "Child process returned malformed structured output"; case .missingCredential: "Twelve Data authentication is unavailable" } }
}

public struct CLIConfiguration: Equatable, Sendable {
    public let python: String; public let repository: String; public let database: String
    public init(python:String,repository:String,database:String){self.python=python;self.repository=repository;self.database=database}
}

public enum ArgumentBuilder {
    public static func arguments(for intent: OperationIntent, database: String) -> [String] {
        switch intent {
        case .readEstateTruth: ["-m","fragarach_ii.commands.estate_truth","--database",database,"--json"]
        case .readTruth(let symbol,let timeframe): ["-m","fragarach_ii.commands.truth_state","--database",database,"--symbol",symbol,"--timeframe",timeframe,"--json"]
        case .marketHistory(let symbol,let timeframe,let tradingDays): ["-m","fragarach_ii.commands.get_market_history","--database",database,"--symbol",symbol,"--timeframe",timeframe,"--last-trading-days","\(tradingDays)","--json"]
        case .resolveInstrument(let query): ["-m","fragarach_ii.commands.resolve_instrument","--database",database,"--query",query,"--json"]
        case .discoverMarket(let query): ["-m","fragarach_ii.commands.discover_market","--database",database,"--query",query,"--json"]
        case .searchInstrument(let query): ["-m","fragarach_ii.commands.search_instrument","--database",database,"--query",query,"--json"]
        case .readProviderFacts: ["-m","fragarach_ii.commands.provider_facts","--database",database,"--mode","status","--json"]
        case .resolveProviderFacts(let symbol): ["-m","fragarach_ii.commands.provider_facts","--database",database,"--mode","resolve"]+(symbol.map{["--symbol",$0]} ?? [])+["--json"]
        case .probeProviderCapability(let symbol,let timeframe): ["-m","fragarach_ii.commands.provider_facts","--database",database,"--mode","probe","--symbol",symbol,"--timeframe",timeframe,"--json"]
        case .recordProviderMappingDecision(let symbol,let decision,let candidate): ["-m","fragarach_ii.commands.provider_facts","--database",database,"--mode","decision","--symbol",symbol,"--decision",decision,"--candidate-symbol",candidate,"--json"]
        case .registerInstrument(let candidate): ["-m","fragarach_ii.commands.register_instrument","--database",database,"--candidate",candidate,"--json"]
        case .retirementPlan(let asset,let scope,let lanes): ["-m","fragarach_ii.commands.retire_instrument","--database",database,"--asset",asset,"--scope",scope,"--lanes",lanes.joined(separator:","),"--json"]
        case .retireInstrument(let asset,let scope,let lanes,let reason,let note,let confirmation): ["-m","fragarach_ii.commands.retire_instrument","--database",database,"--asset",asset,"--scope",scope,"--lanes",lanes.joined(separator:","),"--reason",reason,"--note",note,"--confirmation",confirmation,"--confirm","--json"]
        case .reactivateInstrument(let asset): ["-m","fragarach_ii.commands.reactivate_instrument","--database",database,"--asset",asset,"--confirm","--json"]
        case .permanentRemovalPlan(let asset): ["-m","fragarach_ii.commands.permanently_remove_instrument","--database",database,"--asset",asset,"--json"]
        case .permanentlyRemoveInstrument(let asset,let confirmation): ["-m","fragarach_ii.commands.permanently_remove_instrument","--database",database,"--asset",asset,"--confirmation",confirmation,"--confirm","--json"]
        case .acquire(let asset,let timeframe,let from,let through,let mode): ["-m","fragarach_ii.commands.acquire","--database",database,"--provider","AUTO","--asset",asset,"--timeframe",timeframe,"--from-date",from,"--through-date",through,"--intent","custom","--operator-reason","REVIEWED_HISTORICAL_RANGE","--reviewed-historical-range","--conflict-mode",mode.rawValue,"--json"]
        case .acquireInitial(let asset,let timeframe,let from,let through,let mode): ["-m","fragarach_ii.commands.acquire","--database",database,"--provider","AUTO","--asset",asset,"--timeframe",timeframe,"--from-date",from,"--through-date",through,"--intent","initial","--operator-reason","REVIEWED_INITIAL_HISTORY","--reviewed-historical-range","--conflict-mode",mode.rawValue,"--json"]
        case .acquireUpdate(let asset,let timeframe,let from,let through,let mode): ["-m","fragarach_ii.commands.acquire","--database",database,"--provider","AUTO","--asset",asset,"--timeframe",timeframe,"--from-date",from,"--through-date",through,"--intent","update","--operator-reason","UNIFIED_ACQUISITION_PLAN","--reviewed-historical-range","--conflict-mode",mode.rawValue,"--json"]
        case .acquireForceHistory(let asset,let timeframe,let from,let through,let mode): ["-m","fragarach_ii.commands.acquire","--database",database,"--provider","AUTO","--asset",asset,"--timeframe",timeframe,"--from-date",from,"--through-date",through,"--intent","force","--operator-reason","FORCE_HISTORY_REFRESH","--reviewed-historical-range","--conflict-mode",mode.rawValue,"--json"]
        case .acquireRequiredSet(let asset): ["-m","fragarach_ii.commands.acquire","--database",database,"--provider","AUTO","--asset",asset,"--required-set","--operator-reason","REQUIRED_TIMEFRAME_SET","--conflict-mode","preserve","--json"]
        case .resumeRequiredSet(let asset): ["-m","fragarach_ii.commands.acquire","--database",database,"--provider","AUTO","--asset",asset,"--resume-required-set","--conflict-mode","preserve","--json"]
        case .importCSV(let file,let symbol,let timeframe,let sourceTimezone,let d1DateFormat,let mode):
            ["-m","fragarach_ii.commands.ingest_file","--database",database,"--file",file,"--symbol",symbol,"--timeframe",timeframe,"--merge-mode",mode.rawValue,"--d1-date-format",d1DateFormat]+(sourceTimezone.map{["--source-timezone",$0]} ?? [])+["--json"]
        case .validate(let symbol,let timeframe,let through,let persist): ["-m","fragarach_ii.commands.validate_lane","--database",database,"--symbol",symbol,"--timeframe",timeframe,"--through-date",through,persist ? "--persist":"--no-persist","--json"]
        case .verify: ["-m","fragarach_ii.commands.operations","verify","--database",database,"--json"]
        case .backup(let destination): ["-m","fragarach_ii.commands.operations","backup","--database",database,"--destination",destination,"--json"]
        case .readScheduler: ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","status","--json"]
        case .readSchedulerService(let appBuild): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","service-status","--app-build",appBuild,"--json"]
        case .installSchedulerService: ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","install","--json"]
        case .schedulerServiceAction(let action): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode",action,"--json"]
        case .repairSchedulerService: ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","repair","--json"]
        case .forceReconcileSchedulerService: ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","force-reconcile","--json"]
        case .readSchedulerDiagnostics(let appBuild): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","diagnostics","--app-build",appBuild,"--json"]
        case .cancelSchedulerMutation(let operationID): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","cancel-operation"]+(operationID.map{["--operation-id",$0]} ?? [])+["--json"]
        case .dismissManualRequest(let id): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","manual-request","--request-id",id,"--action","dismiss","--json"]
        case .acknowledgeManualRequest(let id): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","manual-request","--request-id",id,"--action","acknowledge","--json"]
        case .retrySchedulerLane(let id): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","retry","--lane-id",id,"--json"]
        case .retryManualRequest(let id): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","retry","--request-id",id,"--json"]
        case .queueLaneUpdate(let id): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","fetch","--lane-id",id,"--json"]
        case .runSchedulerQueue: ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","run-queue","--json"]
        case .runEstateAudit: ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","audit-estate","--json"]
        case .setSchedulerPolicy(let policy): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","scheduler-policy","--policy",policy,"--json"]
        case .setM5Freshness(let delay,let critical): ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","m5-freshness","--publication-delay-seconds","\(delay)","--critical-after-closed-boundaries","\(critical)","--json"]
        case .pauseAcquisition(let scopeType,let scopeIdentifier,let reason,let temporary,let ingestionSession):
            ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","pause","--scope-type",scopeType,"--reason",reason]+(scopeIdentifier.map{["--scope-identifier",$0]} ?? [])+(temporary ? ["--temporary"]:[])+(ingestionSession.map{["--ingestion-session",$0]} ?? [])+["--json"]
        case .resumeAcquisition(let pauseIdentifier,let scopeType,let scopeIdentifier,let ingestionSession):
            ["-m","fragarach_ii.commands.scheduler","--database",database,"--mode","resume"]+(pauseIdentifier.map{["--pause-identifier",$0]} ?? [])+(scopeType.map{["--scope-type",$0]} ?? [])+(scopeIdentifier.map{["--scope-identifier",$0]} ?? [])+(ingestionSession.map{["--ingestion-session",$0]} ?? [])+["--json"]
        case .readSyntheticProducts: ["-m","fragarach_ii.commands.synthetic","--database",database,"--mode","list","--json"]
        case .regenerateSyntheticProduct(let id): ["-m","fragarach_ii.commands.synthetic","--database",database,"--mode","generate"]+(id.map{["--registration-id",$0]} ?? [])+["--json"]
        case .rebuildSyntheticRepository: ["-m","fragarach_ii.commands.synthetic","--database",database,"--mode","rebuild","--json"]
        }
    }
}

public enum SecretFilter {
    public static func filter(_ text: String, secrets: [String]) -> String { secrets.filter{!$0.isEmpty}.reduce(text){$0.replacingOccurrences(of:$1,with:"[REDACTED]")} }
}

public final class ProcessBridge: @unchecked Sendable {
    private let lock=NSLock(); private var process: Process?;private var cancellationRequested=false
    public init() {}
    public var isActive: Bool { lock.withLock { process != nil } }
    public func validateCLI(_ config: CLIConfiguration) throws {
        let result=try runRaw(config:config,args:["-m","fragarach_ii.commands.operations","identity","--json"],environment:[:])
        guard result.exitCode==0, result.JSON?["cli_id"] as? String == "fragarach_ii.operations_cli.v1", result.JSON?["cli_version"] as? Int == 1 else { throw BridgeError.incompatibleCLI }
    }
    public func run(_ intent: OperationIntent, config: CLIConfiguration, progress: (@Sendable (DataOperationState)->Void)? = nil, progressDetail: (@Sendable (OperationProgressDetail)->Void)? = nil) throws -> ProcessResult {
        var environment:[String:String]=[:]
        if progress != nil { environment["FRAGARACH_OPERATION_PROGRESS"]="1" }
        return try runRaw(config:config,args:ArgumentBuilder.arguments(for:intent,database:config.database),environment:environment,progress:progress,progressDetail:progressDetail)
    }
    public func readCredentialAuthority(config:CLIConfiguration) throws -> ProcessResult {
        try runRaw(config:config,args:["-m","fragarach_ii.commands.credentials","--mode","status","--json"],environment:[:])
    }
    public func storeCredential(_ credential:String,provider:String="TWELVE_DATA",config:CLIConfiguration) throws -> ProcessResult {
        let value=credential.trimmingCharacters(in:.whitespacesAndNewlines)
        guard !value.isEmpty else { throw CredentialStorageError.empty }
        return try runRaw(config:config,args:["-m","fragarach_ii.commands.credentials","--mode","store","--provider",provider,"--json"],environment:["FRAGARACH_CREDENTIAL_INPUT":value])
    }
    public func cancel() { lock.withLock { cancellationRequested=true;if let process,process.isRunning{process.terminate()} } }
    private func runRaw(config:CLIConfiguration,args:[String],environment:[String:String],progress:(@Sendable (DataOperationState)->Void)?=nil,progressDetail:(@Sendable (OperationProgressDetail)->Void)?=nil) throws -> ProcessResult {
        let child=Process(), out=Pipe(), err=Pipe(); let id=UUID()
        lock.lock(); guard process==nil else { lock.unlock(); throw BridgeError.operationActive }; process=child;cancellationRequested=false; lock.unlock()
        defer { lock.withLock { process=nil } }
        child.executableURL=URL(fileURLWithPath:config.python); child.arguments=args; child.currentDirectoryURL=URL(fileURLWithPath:config.repository)
        var env=ProcessInfo.processInfo.environment; env["PYTHONPATH"]="\(config.repository)/src"; for (k,v) in environment { env[k]=v }; child.environment=env; child.standardOutput=out; child.standardError=err
        try child.run()
        lock.withLock { if cancellationRequested,child.isRunning{child.terminate()} }
        let group=DispatchGroup(),outBuffer=PipeBuffer(),errBuffer=ProgressPipeBuffer(progress:progress,progressDetail:progressDetail)
        group.enter();DispatchQueue.global(qos:.userInitiated).async{outBuffer.set(out.fileHandleForReading.readDataToEndOfFile());group.leave()}
        group.enter();DispatchQueue.global(qos:.userInitiated).async{while true{let data=err.fileHandleForReading.availableData;if data.isEmpty{break};errBuffer.append(data)};group.leave()}
        child.waitUntilExit();group.wait()
        let secrets=environment.filter{$0.key.contains("API_KEY") || $0.key.contains("CREDENTIAL") || $0.key.contains("SECRET")}.map(\.value)
        let stdout=SecretFilter.filter(String(decoding:outBuffer.get(),as:UTF8.self),secrets:secrets).trimmingCharacters(in:.whitespacesAndNewlines)
        let stderr=SecretFilter.filter(String(decoding:errBuffer.filteredData(),as:UTF8.self),secrets:secrets).trimmingCharacters(in:.whitespacesAndNewlines)
        return ProcessResult(operationID:id,exitCode:child.terminationStatus,stdout:stdout,stderr:stderr)
    }
}

public enum CredentialStorageError:Error,LocalizedError { case empty;public var errorDescription:String?{"Enter a provider credential."} }
