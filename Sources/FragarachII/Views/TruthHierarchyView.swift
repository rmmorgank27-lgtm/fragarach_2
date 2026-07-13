import OperationsCore
import SwiftUI

enum TruthHierarchySelection: Hashable {
    case estate
    case market(String)
    case subgroup(market: String, subgroup: String)
    case symbol(String)
}

struct TruthBreadcrumbView: View {
    let segments: [(String, TruthHierarchySelection)]
    let selection: TruthHierarchySelection
    let onSelect: (TruthHierarchySelection) -> Void

    var body: some View {
        HStack(spacing: 7) {
            ForEach(Array(segments.enumerated()), id: \.offset) { index, segment in
                if index > 0 { Image(systemName: "chevron.right").font(.caption2).foregroundStyle(.tertiary) }
                Button(segment.0) { onSelect(segment.1) }
                    .buttonStyle(.plain)
                    .fontWeight(segment.1 == selection ? .semibold : .regular)
                    .foregroundStyle(segment.1 == selection ? AnyShapeStyle(.primary) : AnyShapeStyle(.secondary))
            }
        }
        .font(.callout)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Estate navigation")
    }
}

struct EstateMarketCardsView: View {
    let markets: [EstateMarketGroup]
    let onSelect: (EstateMarketGroup) -> Void

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 245), spacing: 12)], spacing: 12) {
            ForEach(markets) { market in
                Button { onSelect(market) } label: {
                    EstateScorecard(title: market.name, systemImage: market.systemImage, summary: market.summary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("\(market.name), \(market.summary.symbolCount) symbols, Truth \(market.summary.truthScore.map(String.init) ?? "not measured")")
            }
        }
    }
}

struct EstateSubgroupCardsView: View {
    let subgroups: [EstateSubgroup]
    let onSelect: (EstateSubgroup) -> Void

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 225), spacing: 12)], spacing: 12) {
            ForEach(subgroups) { subgroup in
                Button { onSelect(subgroup) } label: {
                    EstateScorecard(title: subgroup.name, systemImage: "square.stack.3d.up", summary: subgroup.summary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("\(subgroup.name), \(subgroup.summary.symbolCount) symbols, Truth \(subgroup.summary.truthScore.map(String.init) ?? "not measured")")
            }
        }
    }
}

struct EstateScorecard: View {
    let title: String
    let systemImage: String
    let summary: EstateGroupSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(title, systemImage: systemImage).font(.title3.bold())
                Spacer()
                Text(summary.truthScore.map(String.init) ?? "—").font(.system(size: 28, weight: .semibold, design: .rounded)).monospacedDigit()
            }
            Grid(alignment: .leading, horizontalSpacing: 16, verticalSpacing: 7) {
                GridRow { metric("Healthy", summary.healthyCount, state: "GREEN"); metric("Attention", summary.attentionCount, state: "AMBER") }
                GridRow { metric("Critical", summary.criticalCount, state: "RED"); metric("Symbols", summary.symbolCount) }
                GridRow { metric("Coverage", summary.coveragePercent); metric("Freshness", summary.freshnessPercent) }
            }
            HStack { Text("CAODT").foregroundStyle(.secondary); Spacer();Text(TruthPresentation.text(summary.caodt)).lineLimit(1).monospaced() }.font(.caption)
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 165, alignment: .topLeading)
        .background(TruthPresentation.color(summary.authorityState).opacity(summary.truthScore == nil ? 0.04 : 0.11), in: RoundedRectangle(cornerRadius: 12))
        .overlay { RoundedRectangle(cornerRadius: 12).stroke(TruthPresentation.color(summary.authorityState).opacity(0.28)) }
        .contentShape(RoundedRectangle(cornerRadius: 12))
    }

    private func metric(_ title: String, _ value: Int, state: String? = nil) -> some View {
        HStack(spacing: 5) {
            if let state { Circle().fill(TruthPresentation.color(state)).frame(width: 7, height: 7) }
            Text(title).foregroundStyle(.secondary)
            Spacer(minLength: 8)
            Text("\(value)").fontWeight(.semibold).monospacedDigit()
        }.font(.caption)
    }

    private func metric(_ title: String, _ value: Int?) -> some View {
        HStack(spacing: 5) {
            Text(title).foregroundStyle(.secondary)
            Spacer(minLength: 8)
            Text(value.map { "\($0)%" } ?? "—").fontWeight(.semibold).monospacedDigit()
        }.font(.caption)
    }
}
