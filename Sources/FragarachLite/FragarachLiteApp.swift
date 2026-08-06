import SwiftUI

@main
struct FragarachLiteApp:App {
    @StateObject private var store=LiteEstateStore()
    var body:some Scene {
        WindowGroup("Fragarach Lite") {LiteEstateView().environmentObject(store).frame(minWidth:900,minHeight:650)}
    }
}
