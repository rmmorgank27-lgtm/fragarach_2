import SwiftUI

enum TruthPresentation {
    static func color(_ state:String)->Color {
        switch state { case "GREEN": .green; case "AMBER": .orange; case "RED": .red; default: .secondary }
    }
    static func value(_ value:Int?)->String { value.map(String.init) ?? "Not measured" }
    static func text(_ value:String?)->String { value ?? "Not measured" }
    static let componentOrder=["authority","freshness","coverage","continuity","validation","provider"]
}
