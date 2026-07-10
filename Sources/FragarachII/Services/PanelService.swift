import AppKit
import Foundation

@MainActor enum PanelService {
    static func chooseCSV()->URL? { let p=NSOpenPanel(); p.allowedContentTypes=[.commaSeparatedText]; p.canChooseFiles=true;p.canChooseDirectories=false;p.allowsMultipleSelection=false;return p.runModal() == .OK ? p.url:nil }
    static func chooseDatabase()->URL? { let p=NSOpenPanel();p.canChooseFiles=true;p.canChooseDirectories=false;p.allowsMultipleSelection=false;return p.runModal() == .OK ? p.url:nil }
    static func chooseBackup()->URL? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let directory = panel.url else { return nil }
        let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
        return directory.appendingPathComponent("fragarach_ii_backup_\(stamp).sqlite3")
    }
}
