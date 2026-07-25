import OperationsCore
import SwiftUI

struct EstateContextDetailView: View {
    let estate: EstateTruthState
    let hierarchy: EstateHierarchy
    var scheduler: SchedulerSnapshot? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading) { Text("Estate Truth").font(.largeTitle);Text("Complete operational authority").foregroundStyle(.secondary) }
                Spacer()
                score(hierarchy.estateSummary)
            }
            GroupBox("Estate authority") { Facts([
                ("CAODT", TruthPresentation.text(estate.estateSummary.latestCanonicalObservation)),
                ("Markets", "\(hierarchy.markets.count)"),
                ("Symbols", "\(hierarchy.estateSummary.symbolCount)"),
                ("Required lanes", "\(estate.estateSummary.requiredLanes)"),
                ("Commissioned lanes", "\(estate.estateSummary.commissionedLanes)"),
                ("Operational lanes", "\(estate.estateSummary.operationalLanes)"),
                ("Missing commissions", "\(estate.estateSummary.missingCommissions)"),
                ("Operational coverage", estate.estateSummary.operationalCoveragePercent.map{"\($0)%"} ?? "Not measured"),
                ("Healthy", "\(hierarchy.estateSummary.healthyCount)"),
                ("Attention", "\(hierarchy.estateSummary.attentionCount)"),
                ("Critical", "\(hierarchy.estateSummary.criticalCount)"),
                ("Coverage", percent(hierarchy.estateSummary.coveragePercent)),
                ("Freshness", percent(hierarchy.estateSummary.freshnessPercent))
            ]) }
            SchedulerRecentEventsView(snapshot:scheduler)
            GroupBox("Aggregation") { Facts([("Truth", estate.estateSummary.aggregation.truthScore), ("Authority", estate.estateSummary.aggregation.authorityState), ("CAODT", estate.estateSummary.aggregation.caodt)]) }
        }.padding()
    }

    private func score(_ summary: EstateGroupSummary) -> some View { VStack(alignment:.trailing){Text(summary.truthScore.map(String.init) ?? "—").font(.system(size:36,weight:.semibold,design:.rounded));Label(summary.authorityState,systemImage:"circle.fill").foregroundStyle(TruthPresentation.color(summary.authorityState))} }
    private func percent(_ value: Int?) -> String { value.map { "\($0)%" } ?? "Not measured" }
}

struct GroupContextDetailView: View {
    let title: String
    let subtitle: String
    let summary: EstateGroupSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading) { Text(title).font(.largeTitle);Text(subtitle).foregroundStyle(.secondary) }
                Spacer()
                VStack(alignment:.trailing){Text(summary.truthScore.map(String.init) ?? "—").font(.system(size:36,weight:.semibold,design:.rounded));Label(summary.authorityState,systemImage:"circle.fill").foregroundStyle(TruthPresentation.color(summary.authorityState))}
            }
            GroupBox("Operational health") { Facts([("Symbols", "\(summary.symbolCount)"), ("Healthy", "\(summary.healthyCount)"), ("Attention", "\(summary.attentionCount)"), ("Critical", "\(summary.criticalCount)"), ("Coverage", percent(summary.coveragePercent)), ("Freshness", percent(summary.freshnessPercent)), ("CAODT", TruthPresentation.text(summary.caodt))]) }
            GroupBox("Attention symbols") {
                if summary.attentionSymbols.isEmpty { Text("No symbols currently require attention.").foregroundStyle(.secondary).frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,6) }
                else { Text(summary.attentionSymbols.joined(separator: ", ")).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,6) }
            }
            GroupBox("Provider summary") { Facts([("Providers", summary.providers.isEmpty ? "Provider Mapping Required" : summary.providers.joined(separator: ", ")), ("Provider count", "\(summary.providers.count)")]) }
        }.padding()
    }

    private func percent(_ value: Int?) -> String { value.map { "\($0)%" } ?? "Not measured" }
}
