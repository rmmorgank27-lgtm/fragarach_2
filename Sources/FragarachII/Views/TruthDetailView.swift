import OperationsCore
import SwiftUI

struct TruthDetailView:View {
    @EnvironmentObject var store:ConsoleStore
    let lane:EstateTruthLane
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            HStack(alignment:.firstTextBaseline){VStack(alignment:.leading){Text(lane.symbol).font(.largeTitle);Text(lane.timeframe).foregroundStyle(.secondary)};Spacer();VStack(alignment:.trailing){Text("\(lane.truthState.truthScore)").font(.system(size:36,weight:.semibold,design:.rounded));Label(lane.truthState.authorityState,systemImage:"circle.fill").foregroundStyle(TruthPresentation.color(lane.truthState.authorityState))}}
            HStack{Button("Manage Data"){store.navigate(.acquire,asset:lane.symbol)}.buttonStyle(.borderedProminent);Button("View Authority History"){store.auditFilter=lane.symbol;store.navigate(.authorityLedger)}}
            GroupBox("Authority") { Facts([("CAODT",lane.truthState.caodt),("Validation",lane.truthState.validationState),("Epoch",lane.truthState.epoch),("Contract",lane.truthState.contract)]) }
            GroupBox("Coverage and freshness") { Facts([("Earliest",lane.truthState.coverage.earliestBar),("Latest",lane.truthState.coverage.latestBar),("Rows","\(lane.truthState.coverage.rowCount)"),("Expected start",TruthPresentation.text(lane.truthState.coverage.expectedRange.start)),("Expected end",TruthPresentation.text(lane.truthState.coverage.expectedRange.end)),("Available start",TruthPresentation.text(lane.truthState.coverage.availableRange.start)),("Available end",TruthPresentation.text(lane.truthState.coverage.availableRange.end)),("Freshness score",TruthPresentation.value(lane.truthState.freshnessScore)),("Coverage score",TruthPresentation.value(lane.truthState.coverageScore))]) }
            TruthComponentsView(state:lane.truthState)
            GroupBox("Provider Summary") { Facts([("Provider",lane.providerSummary.provider ?? "Provider Mapping Required"),("Confidence",lane.providerSummary.providerConfidence),("Freshness",lane.providerSummary.providerFreshness),("Entitlement",lane.providerSummary.entitlement)]) }
            GroupBox("Gap Summary") { Facts([("Classification",lane.gapSummary.gapClassification),("Impact",lane.gapSummary.operationalImpact),("Current",TruthPresentation.value(lane.gapSummary.currentGapCount)),("Recent",TruthPresentation.value(lane.gapSummary.recentGapCount)),("Historical",TruthPresentation.value(lane.gapSummary.historicalGapCount)),("Total",TruthPresentation.value(lane.gapSummary.totalGapCount))]) }
            GroupBox("Explanation") { VStack(alignment:.leading,spacing:8){Text(lane.truthState.explanation.method).textSelection(.enabled);if lane.truthState.explanation.limitations.isEmpty{Text("No recorded limitations").foregroundStyle(.secondary)}else{ForEach(lane.truthState.explanation.limitations,id:\.self){Text($0).font(.caption.monospaced()).textSelection(.enabled)}}}.frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,6) }
        }.padding()
    }
}

private struct TruthComponentsView:View {
    let state:TruthState
    var body:some View { GroupBox("Truth Components") { VStack(spacing:0){ForEach(TruthPresentation.componentOrder,id:\.self){name in if let component=state.explanation.components[name]{HStack(alignment:.firstTextBaseline){Text(name.capitalized).frame(width:90,alignment:.leading);Text(TruthPresentation.value(component.score)).font(.headline.monospacedDigit()).frame(width:80,alignment:.trailing);Text(component.basis).font(.caption).foregroundStyle(.secondary).textSelection(.enabled);Spacer()}.padding(.vertical,7);Divider()}}}.padding(.vertical,2) } }
}
