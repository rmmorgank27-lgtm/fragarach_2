import Foundation

public struct DataOperationsSelection: Equatable, Sendable {
    public private(set) var selectedRegistrationID: String?

    public init(selectedRegistrationID: String? = nil) {
        self.selectedRegistrationID = selectedRegistrationID
    }

    public mutating func select(_ registrationID: String?) {
        selectedRegistrationID = registrationID
    }

    public mutating func reconcile(visibleRegistrationIDs: Set<String>) {
        guard let selectedRegistrationID else { return }
        if !visibleRegistrationIDs.contains(selectedRegistrationID) {
            self.selectedRegistrationID = nil
        }
    }

    public mutating func applyNavigationContext(_ registrationID: String?, visibleRegistrationIDs: Set<String>) {
        selectedRegistrationID = registrationID.flatMap { visibleRegistrationIDs.contains($0) ? $0 : nil }
    }
}
