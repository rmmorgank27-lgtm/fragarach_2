import Foundation

public enum OperationalStatus: String, Codable, Sendable {
    case success = "SUCCESS"
    case completedWithWarnings = "COMPLETED_WITH_WARNINGS"
    case degradedOperationAvailable = "DEGRADED_OPERATION_AVAILABLE"
    case hardBlockAffectedPath = "HARD_BLOCK_AFFECTED_PATH"
    case operatorCancelled = "OPERATOR_CANCELLED"
}

public struct OperationalDecision: Codable, Equatable, Sendable {
    public let status: OperationalStatus
    public let hardBlock: Bool
    public let affectedScope: String
    public let reason: String
    public let warnings: [String]
    public let safeFallbacks: [String]
    public let fallbackExecuted: String?
    public let unaffectedOperations: [String]
    public let repairOwner: String?

    public init(status:OperationalStatus,hardBlock:Bool,affectedScope:String,reason:String,warnings:[String]=[],safeFallbacks:[String]=[],fallbackExecuted:String?=nil,unaffectedOperations:[String]=[],repairOwner:String?=nil) {
        self.status=status;self.hardBlock=hardBlock;self.affectedScope=affectedScope;self.reason=reason;self.warnings=warnings;self.safeFallbacks=safeFallbacks;self.fallbackExecuted=fallbackExecuted;self.unaffectedOperations=unaffectedOperations;self.repairOwner=repairOwner
    }

    enum CodingKeys:String,CodingKey { case status,reason,warnings;case hardBlock="hard_block",affectedScope="affected_scope",safeFallbacks="safe_fallbacks",fallbackExecuted="fallback_executed",unaffectedOperations="unaffected_operations",repairOwner="repair_owner" }

    public static func degraded(scope:String,reason:String,safeFallbacks:[String],unaffectedOperations:[String]=[]) -> Self {
        precondition(!safeFallbacks.isEmpty)
        return .init(status:.degradedOperationAvailable,hardBlock:false,affectedScope:scope,reason:reason,warnings:[reason],safeFallbacks:safeFallbacks,unaffectedOperations:unaffectedOperations,repairOwner:"IMPLEMENTATION")
    }
}
