import SwiftUI

@main
struct FragarachLiteApp:App {
    @StateObject private var store=LiteEstateStore()
    var body:some Scene {
        WindowGroup("Fragarach Lite") {LiteRootView().environmentObject(store).frame(minWidth:1000,minHeight:650)}
    }
}
