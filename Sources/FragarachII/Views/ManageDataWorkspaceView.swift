import OperationsCore
import SwiftUI

struct ManageDataWorkspaceView: View {
    @EnvironmentObject private var store: ConsoleStore
    var body: some View {
        VStack(alignment:.leading,spacing:12) {
            Picker("Manage Data sections",selection:$store.manageDataSection) {
                ForEach(ManageDataSection.allCases){Text($0.rawValue).tag($0)}
            }
            .labelsHidden()
            .pickerStyle(.segmented)
            .frame(maxWidth:620)
            .padding([.top,.horizontal])
            Group {
                switch store.manageDataSection {
                case .discover: DiscoverMarketView()
                case .operations: DataOperationsView()
                case .system: SystemWorkspaceView()
                }
            }.frame(maxWidth:.infinity,maxHeight:.infinity)
        }
    }
}
