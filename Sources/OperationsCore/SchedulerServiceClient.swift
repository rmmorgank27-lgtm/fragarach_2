import CryptoKit
import Darwin
import Foundation

public enum SchedulerServiceClientError: Error, LocalizedError, Sendable {
    case invalidDatabasePath
    case socketPathTooLong
    case socketCreation(Int32)
    case socketConnection(Int32)
    case socketWrite(Int32)
    case socketRead(Int32)
    case responseTooLarge
    case incompleteResponse

    public var errorDescription: String? {
        switch self {
        case .invalidDatabasePath: "The Scheduler authority database path is invalid."
        case .socketPathTooLong: "The Scheduler monitor socket path exceeds the macOS limit."
        case .socketCreation(let code): "The Scheduler monitor socket could not be created (errno \(code))."
        case .socketConnection(let code): "The Scheduler monitor is unavailable (errno \(code))."
        case .socketWrite(let code): "The Scheduler status request could not be sent (errno \(code))."
        case .socketRead(let code): "The Scheduler status response could not be read (errno \(code))."
        case .responseTooLarge: "The Scheduler status response exceeded its bounded transport limit."
        case .incompleteResponse: "The Scheduler returned an incomplete status response."
        }
    }
}

/// Native client for the persistent Scheduler's framed Unix-domain socket.
///
/// Recurring UI reads must not launch the Python CLI. The CLI remains the
/// operator boundary for lifecycle mutations and manual commands, while this
/// client reads the daemon-owned monitor contract directly.
public struct SchedulerServiceClient: Sendable {
    public static let statusContract = "fragarach_ii.scheduler_service_status.v1"
    private static let maximumResponseBytes = 8 * 1024 * 1024

    public init() {}

    public func readStatus(database: String, appBuild: String) throws -> Data {
        do {
            return try readLiveStatus(database: database, appBuild: appBuild)
        } catch {
            return try Self.cachedStatus(database: database)
        }
    }

    private func readLiveStatus(database: String, appBuild: String) throws -> Data {
        let path = try Self.socketPath(database: database)
        let descriptor = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
        guard descriptor >= 0 else { throw SchedulerServiceClientError.socketCreation(errno) }
        defer { Darwin.close(descriptor) }

        var timeout = timeval(tv_sec: 3, tv_usec: 0)
        withUnsafePointer(to: &timeout) { pointer in
            _ = setsockopt(descriptor, SOL_SOCKET, SO_RCVTIMEO, pointer, socklen_t(MemoryLayout<timeval>.size))
            _ = setsockopt(descriptor, SOL_SOCKET, SO_SNDTIMEO, pointer, socklen_t(MemoryLayout<timeval>.size))
        }

        var address = sockaddr_un()
        address.sun_family = sa_family_t(AF_UNIX)
        let encodedPath = path.utf8CString
        guard encodedPath.count <= MemoryLayout.size(ofValue: address.sun_path) else {
            throw SchedulerServiceClientError.socketPathTooLong
        }
        withUnsafeMutablePointer(to: &address.sun_path) { pointer in
            pointer.withMemoryRebound(to: CChar.self, capacity: encodedPath.count) { destination in
                _ = encodedPath.withUnsafeBufferPointer { source in
                    memcpy(destination, source.baseAddress, source.count)
                }
            }
        }
        let addressLength = socklen_t(MemoryLayout<sa_family_t>.size + encodedPath.count)
        let connected = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(descriptor, $0, addressLength)
            }
        }
        guard connected == 0 else { throw SchedulerServiceClientError.socketConnection(errno) }

        let request: [String: Any] = [
            "contract": Self.statusContract,
            "request": "status",
            "app_build": appBuild,
        ]
        var frame = try JSONSerialization.data(withJSONObject: request, options: [.sortedKeys])
        frame.append(0x0A)
        try writeAll(frame, to: descriptor)
        return try readFrame(from: descriptor)
    }

    public static func socketPath(database: String) throws -> String {
        let identity = try authorityIdentity(database: database)
        let root = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appendingPathComponent("fragarach-scheduler-\(getuid())", isDirectory: true)
        return root.appendingPathComponent("\(identity.prefix(16)).sock").path
    }

    private static func authorityIdentity(database: String) throws -> String {
        guard !database.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw SchedulerServiceClientError.invalidDatabasePath
        }
        let resolved = URL(fileURLWithPath: database)
            .standardizedFileURL
            .resolvingSymlinksInPath()
            .path
        let digest = SHA256.hash(data: Data(resolved.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
        return digest
    }

    private static func cachedStatus(database: String) throws -> Data {
        let identity = try authorityIdentity(database: database)
        let support = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Fragarach II/Scheduler", isDirectory: true)
            .appendingPathComponent(String(identity.prefix(16)), isDirectory: true)
        let statusURL = support.appendingPathComponent("service-status.json")
        let ownerURL = support.appendingPathComponent("acquisition-owner.lock")
        let metadataURL = support.appendingPathComponent("installation.json")
        let launchAgentURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/com.raymorgan.fragarach-ii.scheduler.plist")
        var value = ((try? Data(contentsOf: statusURL))
            .flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }) ?? [:]
        let installed = FileManager.default.fileExists(atPath: metadataURL.path)
            && FileManager.default.fileExists(atPath: launchAgentURL.path)
        let heartbeat = (value["heartbeat_time"] as? String).flatMap {
            ISO8601DateFormatter().date(from: $0)
        }
        let cachedState = value["service_state"] as? String
        let heartbeatAge = heartbeat.map { max(0, Date().timeIntervalSince($0)) }
        let owner = ((try? Data(contentsOf: ownerURL))
            .flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }) ?? [:]
        let ownerHeartbeat = (owner["heartbeat_time"] as? String).flatMap {
            ISO8601DateFormatter().date(from: $0)
        }
        let ownerHeartbeatAge = ownerHeartbeat.map {
            max(0, Date().timeIntervalSince($0))
        }
        let ownerPID = (owner["process_id"] as? NSNumber)?.int32Value
        let ownerProcessAlive = ownerPID.map {
            Darwin.kill(pid_t($0), 0) == 0 || errno == EPERM
        } ?? false
        let health = value["operational_health"] as? [String: Any]
        let permittedProgressWindow = health?["permitted_progress_window_seconds"] as? Double ?? 45
        let terminalState = ["STOPPED", "CRASH_LOOP_PROTECTED", "REPAIR_REQUIRED"].contains(cachedState)
        let ownerLikelyActive = !terminalState
            && (
                (ownerProcessAlive && (ownerHeartbeatAge.map { $0 <= 15 } ?? false))
                || (heartbeatAge.map { $0 <= max(60, permittedProgressWindow * 2) } ?? false)
            )
        let state: String
        if !installed {
            state = "NOT_INSTALLED"
        } else if terminalState {
            state = cachedState ?? "STOPPED"
        } else {
            state = "UNREACHABLE"
        }
        value.merge([
            "contract": statusContract,
            "service_state": state,
            "live": false,
            "installed": installed,
            "compatibility": "Compatible",
            "restart_count": value["restart_count"] as? Int ?? 0,
            "service_location": support.path,
            "authority_database": URL(fileURLWithPath: database).standardizedFileURL.path,
            "automatic_login_start": installed,
            "acquisition_owner_active": ownerLikelyActive,
            "recommended_actions": ownerLikelyActive
                ? ["RETRY_CONNECTION", "REPAIR_MONITOR", "OPEN_DIAGNOSTICS"]
                : installed
                    ? ["RETRY_CONNECTION", "START_SERVICE", "REPAIR_SERVICE", "OPEN_DIAGNOSTICS"]
                    : ["INSTALL_SERVICE", "OPEN_DIAGNOSTICS"],
        ], uniquingKeysWith: { _, replacement in replacement })
        value["last_successful_monitor_update"] = value["heartbeat_time"] ?? NSNull()
        var fallbackHealth = health ?? [:]
        fallbackHealth["overall_operational_health"] = ownerLikelyActive ? "DEGRADED" : "UNAVAILABLE"
        fallbackHealth["process"] = ["state": ownerLikelyActive ? "ALIVE" : "NOT_RUNNING"]
        fallbackHealth["monitor_transport"] = ["state": "MONITOR_DISCONNECTED"]
        value["operational_health"] = fallbackHealth
        return try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    }

    private func writeAll(_ data: Data, to descriptor: Int32) throws {
        try data.withUnsafeBytes { rawBuffer in
            guard let base = rawBuffer.baseAddress else { return }
            var written = 0
            while written < rawBuffer.count {
                let count = Darwin.write(descriptor, base.advanced(by: written), rawBuffer.count - written)
                if count < 0 {
                    if errno == EINTR { continue }
                    throw SchedulerServiceClientError.socketWrite(errno)
                }
                guard count > 0 else { throw SchedulerServiceClientError.socketWrite(EPIPE) }
                written += count
            }
        }
    }

    private func readFrame(from descriptor: Int32) throws -> Data {
        var response = Data()
        var buffer = [UInt8](repeating: 0, count: 64 * 1024)
        while response.count <= Self.maximumResponseBytes {
            let count = Darwin.read(descriptor, &buffer, buffer.count)
            if count < 0 {
                if errno == EINTR { continue }
                throw SchedulerServiceClientError.socketRead(errno)
            }
            if count == 0 { break }
            response.append(buffer, count: count)
            if let newline = response.firstIndex(of: 0x0A) {
                return Data(response[..<newline])
            }
        }
        if response.count > Self.maximumResponseBytes {
            throw SchedulerServiceClientError.responseTooLarge
        }
        throw SchedulerServiceClientError.incompleteResponse
    }
}
