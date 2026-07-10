import Foundation

final class QuitGuard: @unchecked Sendable {
    static let shared = QuitGuard()
    private let lock = NSLock(); private var cancellation: (() -> Void)?
    var isActive: Bool { lock.withLock { cancellation != nil } }
    func begin(cancel: @escaping () -> Void) { lock.withLock { cancellation = cancel } }
    func end() { lock.withLock { cancellation = nil } }
    func requestCancellation() { lock.withLock { cancellation?() } }
}
