import Foundation

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
        case .readTruth(let symbol,let timeframe): ["-m","fragarach_ii.commands.truth_state","--database",database,"--symbol",symbol,"--timeframe",timeframe,"--json"]
        case .searchInstrument(let query): ["-m","fragarach_ii.commands.search_instrument","--database",database,"--query",query,"--json"]
        case .registerInstrument(let candidate): ["-m","fragarach_ii.commands.register_instrument","--database",database,"--candidate",candidate,"--json"]
        case .acquire(let asset,let from,let through,let mode): ["-m","fragarach_ii.commands.acquire","--database",database,"--provider","TWELVE_DATA","--asset",asset,"--timeframe","D1","--from-date",from,"--through-date",through,"--conflict-mode",mode.rawValue,"--json"]
        case .importCSV(let file,let symbol,let timeframe,let mode): ["-m","fragarach_ii.commands.ingest_file","--database",database,"--file",file,"--symbol",symbol,"--timeframe",timeframe,"--merge-mode",mode.rawValue,"--json"]
        case .validate(let symbol,let timeframe,let through,let persist): ["-m","fragarach_ii.commands.validate_lane","--database",database,"--symbol",symbol,"--timeframe",timeframe,"--through-date",through,persist ? "--persist":"--no-persist","--json"]
        case .verify: ["-m","fragarach_ii.commands.operations","verify","--database",database,"--json"]
        case .backup(let destination): ["-m","fragarach_ii.commands.operations","backup","--database",database,"--destination",destination,"--json"]
        }
    }
}

public enum SecretFilter {
    public static func filter(_ text: String, secrets: [String]) -> String { secrets.filter{!$0.isEmpty}.reduce(text){$0.replacingOccurrences(of:$1,with:"[REDACTED]")} }
}

public final class ProcessBridge: @unchecked Sendable {
    private let lock=NSLock(); private var process: Process?
    public init() {}
    public var isActive: Bool { lock.withLock { process != nil } }
    public func validateCLI(_ config: CLIConfiguration) throws {
        let result=try runRaw(config:config,args:["-m","fragarach_ii.commands.operations","identity","--json"],environment:[:])
        guard result.exitCode==0, result.JSON?["cli_id"] as? String == "fragarach_ii.operations_cli.v1", result.JSON?["cli_version"] as? Int == 1 else { throw BridgeError.incompatibleCLI }
    }
    public func run(_ intent: OperationIntent, config: CLIConfiguration, credential: String? = nil) throws -> ProcessResult {
        if case .acquire = intent, credential == nil { throw BridgeError.missingCredential }
        return try runRaw(config:config,args:ArgumentBuilder.arguments(for:intent,database:config.database),environment:credential.map{["TWELVE_DATA_API_KEY":$0]} ?? [:])
    }
    public func cancel() { lock.withLock { process?.terminate() } }
    private func runRaw(config:CLIConfiguration,args:[String],environment:[String:String]) throws -> ProcessResult {
        let child=Process(), out=Pipe(), err=Pipe(); let id=UUID()
        lock.lock(); guard process==nil else { lock.unlock(); throw BridgeError.operationActive }; process=child; lock.unlock()
        defer { lock.withLock { process=nil } }
        child.executableURL=URL(fileURLWithPath:config.python); child.arguments=args; child.currentDirectoryURL=URL(fileURLWithPath:config.repository)
        var env=ProcessInfo.processInfo.environment; env["PYTHONPATH"]="\(config.repository)/src"; for (k,v) in environment { env[k]=v }; child.environment=env; child.standardOutput=out; child.standardError=err
        try child.run(); child.waitUntilExit()
        let secrets=Array(environment.values)
        let stdout=SecretFilter.filter(String(decoding:out.fileHandleForReading.readDataToEndOfFile(),as:UTF8.self),secrets:secrets).trimmingCharacters(in:.whitespacesAndNewlines)
        let stderr=SecretFilter.filter(String(decoding:err.fileHandleForReading.readDataToEndOfFile(),as:UTF8.self),secrets:secrets).trimmingCharacters(in:.whitespacesAndNewlines)
        return ProcessResult(operationID:id,exitCode:child.terminationStatus,stdout:stdout,stderr:stderr)
    }
}

public enum CredentialResolver {
    public static func resolve(environment:[String:String]=ProcessInfo.processInfo.environment, authorizedFile:String="/Users/raymorgan/VSC/Morphix_Data_Hot/runtime_state/secrets/local.env") -> String? {
        if let value=environment["TWELVE_DATA_API_KEY"],!value.isEmpty{return value}
        guard let text=try? String(contentsOfFile:authorizedFile,encoding:.utf8) else{return nil}
        for line in text.split(separator:"\n") { let s=line.trimmingCharacters(in:.whitespaces); guard !s.hasPrefix("#"),let i=s.firstIndex(of:"=") else{continue}; let name=s[..<i].trimmingCharacters(in:.whitespaces); if name=="TWELVEDATA_API_KEY" { var value=String(s[s.index(after:i)...]).trimmingCharacters(in:.whitespaces); if value.count>=2, value.first==value.last, value.first=="\"" || value.first=="'" { value.removeFirst(); value.removeLast() }; return value.isEmpty ? nil:value } }
        return nil
    }
}
