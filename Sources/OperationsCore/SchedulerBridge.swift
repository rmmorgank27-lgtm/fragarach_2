import Foundation
import Darwin

private final class SchedulerDataBuffer: @unchecked Sendable {
    private let lock = NSLock()
    private var value = Data()
    func append(_ data: Data) { lock.withLock { value.append(data) } }
    func get() -> Data { lock.withLock { value } }
}

private final class SchedulerStreamBuffer: @unchecked Sendable {
    private let lock = NSLock()
    private var pending = Data()
    private let onLine: @Sendable (String) -> Void
    init(onLine: @escaping @Sendable (String) -> Void) { self.onLine = onLine }
    func append(_ data: Data) {
        lock.withLock {
            pending.append(data)
            while let newline = pending.firstIndex(of: 10) {
                let line = String(decoding: pending[..<newline], as: UTF8.self)
                pending.removeSubrange(...newline)
                if !line.isEmpty { onLine(line) }
            }
        }
    }
}

public final class SchedulerProcessBridge: @unchecked Sendable {
    private let lock = NSLock()
    private var process: Process?
    public init() {}
    public var isActive: Bool { lock.withLock { process != nil } }

    public func start(
        config: CLIConfiguration,
        onLine: @escaping @Sendable (String) -> Void,
        onExit: @escaping @Sendable (Int32, String) -> Void
    ) throws {
        let child = Process(), output = Pipe(), errors = Pipe()
        lock.lock()
        guard process == nil else { lock.unlock(); throw BridgeError.operationActive }
        process = child
        lock.unlock()

        child.executableURL = URL(fileURLWithPath: config.python)
        // The native app is a monitor/control surface. Scheduler ownership lives
        // in the LaunchAgent service, so this legacy bridge may only read status.
        child.arguments = ["-m", "fragarach_ii.commands.scheduler", "--database", config.database, "--mode", "service-status", "--json"]
        child.currentDirectoryURL = URL(fileURLWithPath: config.repository)
        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONPATH"] = "\(config.repository)/src"
        child.environment = environment
        child.standardOutput = output
        child.standardError = errors

        let stream = SchedulerStreamBuffer(onLine: onLine)
        output.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil }
            else { stream.append(data) }
        }
        let errorBuffer = SchedulerDataBuffer()
        errors.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil }
            else { errorBuffer.append(data) }
        }
        child.terminationHandler = { [weak self] process in
            output.fileHandleForReading.readabilityHandler = nil
            errors.fileHandleForReading.readabilityHandler = nil
            self?.lock.withLock { self?.process = nil }
            let error = SecretFilter.filter(
                String(decoding: errorBuffer.get(), as: UTF8.self),
                secrets: []
            ).trimmingCharacters(in: .whitespacesAndNewlines)
            onExit(process.terminationStatus, error)
        }
        do { try child.run() }
        catch {
            output.fileHandleForReading.readabilityHandler = nil
            errors.fileHandleForReading.readabilityHandler = nil
            lock.withLock { process = nil }
            throw error
        }
    }

    public func stop() { lock.withLock { process?.terminate() } }
    public func wake() {
        let identifier = lock.withLock { process?.processIdentifier }
        if let identifier { Darwin.kill(identifier, SIGUSR1) }
    }
}
