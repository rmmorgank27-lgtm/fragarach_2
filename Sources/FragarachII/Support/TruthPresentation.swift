import SwiftUI

enum TruthPresentation {
    static func color(_ state:String)->Color {
        switch state {
        case "GREEN","Current": .green
        case "AMBER","Behind","Queued": .orange
        case "Downloading": .blue
        case "RED","Unavailable","Missing": .red
        case "Not Commissioned": .secondary
        default: .secondary
        }
    }
    static func value(_ value:Int?)->String { value.map(String.init) ?? "Not measured" }
    static func text(_ value:String?)->String { value ?? "Not measured" }
    static let componentOrder=["authority","integrity","freshness","historical_depth","continuity","provider"]
}
