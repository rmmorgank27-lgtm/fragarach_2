import SwiftUI

struct ResultPanel: View {
    @EnvironmentObject var store: ConsoleStore

    var body: some View {
        if let result = store.lastProcessResult {
            GroupBox("Latest operation \(result.operationID.uuidString)") {
                VStack(alignment: .leading) {
                    Text("Exit \(result.exitCode)")
                    Text(result.stdout).font(.caption.monospaced()).textSelection(.enabled)
                }
            }
        } else if let error = store.operationError {
            Text(error).foregroundStyle(.red).textSelection(.enabled)
        }
    }
}
