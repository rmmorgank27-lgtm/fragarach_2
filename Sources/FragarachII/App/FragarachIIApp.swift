import AppKit
import OperationsCore
import SwiftUI

@MainActor final class AppDelegate: NSObject, NSApplicationDelegate {
    var terminationHandler:(()->Void)?
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard QuitGuard.shared.isActive else { return .terminateNow }
        let alert = NSAlert()
        alert.messageText = "An operation is active"
        alert.informativeText = "Keep the app open, or request cancellation and wait for the registered CLI transaction boundary to finish."
        alert.addButton(withTitle: "Keep App Open")
        alert.addButton(withTitle: "Request Cancellation")
        if alert.runModal() == .alertSecondButtonReturn { QuitGuard.shared.requestCancellation() }
        return .terminateCancel
    }
    func applicationWillTerminate(_ notification: Notification) { terminationHandler?() }
}

@main struct FragarachIIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var store = ConsoleStore()
    var body: some Scene {
        WindowGroup("Fragarach II — Operations Console") { ContentView().environmentObject(store).frame(minWidth: 720,minHeight: 650).task { delegate.terminationHandler={store.disconnectSchedulerMonitor()};await store.startup() } }
            .defaultSize(width: 1280,height: 800)
            .commands { MarketSearchCommands() }
        Settings { DiagnosticsSettingsView().environmentObject(store).frame(width:600) }
    }
}
