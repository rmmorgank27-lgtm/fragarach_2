import SwiftUI

enum TruthPresentation {
    static func color(_ state:String)->Color {
        switch state {
        case "GOLD": Color(red: 1.0, green: 0.843, blue: 0.0)
        case "GREEN","Current": Color(red: 0.133, green: 0.545, blue: 0.133)
        case "AMBER","Behind","Queued": Color(red: 0.78, green: 0.082, blue: 0.522)
        case "Downloading": .blue
        case "RED","Unavailable","Missing": Color(red: 0.50, green: 0.0, blue: 0.0)
        case "Not Commissioned": .secondary
        default: .secondary
        }
    }
    static func value(_ value:Int?)->String { value.map(String.init) ?? "Not measured" }
    static func text(_ value:String?)->String { value ?? "Not measured" }
    static let componentOrder=["authority","integrity","freshness","historical_depth","continuity","provider"]

    /// A single visual cue must never say both "healthy" and "behind".
    /// A critical truth assessment is always Red; otherwise operational action
    /// takes precedence over a healthy score.
    static func visualState(authority: String, operational: String?) -> String {
        let authority = authority.uppercased()
        if authority == "RED" { return "RED" }
        switch (operational ?? "").uppercased() {
        case "BEHIND", "QUEUED", "WAITING", "DEGRADED", "ATTENTION", "NO_NEW_DATA":
            return "AMBER"
        case "CRITICAL", "FAILED", "UNAVAILABLE", "MISSING", "BLOCKED", "NOT COMMISSIONED":
            return "RED"
        case "CURRENT", "HEALTHY", "READY", "SUCCESS":
            return ["GOLD", "GREEN", "AMBER"].contains(authority) ? authority : "GREEN"
        default:
            return authority
        }
    }
}

/// The truth state is never conveyed by colour alone.  These marks provide a
/// fast, colour-independent read: excellent, standard, caution, critical.
struct TruthStateMark: View {
    let state: String
    var size: CGFloat = 12

    private var normalized: String {
        switch state.uppercased() {
        case "GOLD": "GOLD"
        case "GREEN", "CURRENT", "HEALTHY", "READY", "SUCCESS": "GREEN"
        case "AMBER", "BEHIND", "QUEUED", "WAITING", "DEGRADED": "AMBER"
        case "RED", "CRITICAL", "FAILED", "UNAVAILABLE", "MISSING": "RED"
        default: "UNKNOWN"
        }
    }

    var body: some View {
        Group {
            switch normalized {
            case "GOLD":
                HStack(spacing: -3) {
                    thumb
                    thumb
                }
            case "GREEN": thumb
            case "AMBER": thumb.rotationEffect(.degrees(90))
            case "RED": Image(systemName: "hand.thumbsdown.fill")
            default: Image(systemName: "questionmark.circle.fill")
            }
        }
        .font(.system(size: size, weight: .semibold))
        .foregroundStyle(TruthPresentation.color(normalized))
        .accessibilityLabel(accessibilityState)
    }

    private var thumb: some View { Image(systemName: "hand.thumbsup.fill") }

    private var accessibilityState: String {
        switch normalized {
        case "GOLD": "Excellent, Gold, double thumbs up"
        case "GREEN": "Standard, Green, thumbs up"
        case "AMBER": "Caution, Amber, sideways thumb"
        case "RED": "Critical, Red, thumbs down"
        default: "Unknown state"
        }
    }
}
