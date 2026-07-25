import OperationsCore
import SwiftUI

/// A compact operational inspector: how much governed history is available,
/// where discontinuities occur, and whether its overall price action is sane.
struct PriceHistoryView: View {
    @EnvironmentObject private var store: ConsoleStore
    let lane: EstateTruthLane
    @Environment(\.dismiss) private var dismiss
    @State private var overview: PriceHistoryOverview?
    @State private var error: String?
    @State private var loadedLaneRevision: Int?

    private var selectedLaneRevision: Int? {
        store.snapshot?.lanes.first { $0.asset == lane.symbol && $0.timeframe == lane.timeframe }?.stateVersion
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Price History").font(.title.bold())
                    Text("Available governed bars, continuity, and a compact price-action profile")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Done") { dismiss() }.keyboardShortcut(.defaultAction)
            }
            .padding([.horizontal, .top], 20)

            if let overview {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        if overview.totalBarCount == 0 {
                            ContentUnavailableView(
                                "Governed bars unavailable",
                                systemImage: "chart.xyaxis.line",
                                description: Text("No governed price bars exist for \(overview.symbol) \(overview.timeframe).")
                            )
                            .frame(maxWidth: .infinity, minHeight: 280)
                        } else {
                            availability(overview)
                            PriceActionProfileChart(
                                profile: overview.profile,
                                gaps: overview.continuity.gaps,
                                expectedCadence: overview.continuity.expectedCadence
                            )
                            continuity(overview)
                        }

                        if let warning = overview.metadataWarning {
                            Label(warning, systemImage: "exclamationmark.triangle.fill")
                                .foregroundStyle(.orange)
                                .padding(10)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
                        }
                    }
                    .padding(20)
                }
            } else if let error {
                ContentUnavailableView("Price History unavailable", systemImage: "exclamationmark.triangle", description: Text(error))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ProgressView("Reading Price History…").frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .frame(minWidth: 920, minHeight: 720)
        .task { await reload() }
        .onChange(of: selectedLaneRevision) { _, revision in
            // Estate refreshes are intentionally ignored unless this lane's
            // state version changed after the overview was read.
            guard let revision, revision != loadedLaneRevision else { return }
            Task { await reload() }
        }
    }

    private func availability(_ overview: PriceHistoryOverview) -> some View {
        GroupBox("Available governed history") {
            Grid(alignment: .leading, horizontalSpacing: 28, verticalSpacing: 10) {
                GridRow {
                    primaryFact("Governed bars available", overview.totalBarCount.formatted())
                    fact("Symbol", overview.symbol)
                    fact("Timeframe", overview.timeframe)
                    fact("Lane revision", overview.governedInputRevision)
                }
                GridRow {
                    primaryFact("Available span", "\(date(overview.earliestGovernedObservation)) — \(date(overview.latestGovernedObservation))")
                    fact("Span", availableSpan(overview))
                    fact("Latest boundary", "\(overview.continuity.latestState.replacingOccurrences(of: "_", with: " ").capitalized) · \(date(overview.latestGovernedObservation))")
                    fact("Validation", overview.validationState.replacingOccurrences(of: "_", with: " ").capitalized)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .textSelection(.enabled)
        }
    }

    private func continuity(_ overview: PriceHistoryOverview) -> some View {
        GroupBox("Continuity") {
            VStack(alignment: .leading, spacing: 10) {
                Grid(alignment: .leading, horizontalSpacing: 28, verticalSpacing: 7) {
                    GridRow {
                        fact("Expected cadence", duration(overview.continuity.expectedCadence))
                        fact("Gap count", "\(overview.continuity.gapCount)")
                        fact("Largest gap", overview.continuity.largestGap.map { duration($0.gapDuration) } ?? "None")
                        fact("Most recent gap", overview.continuity.mostRecentGap.map { date($0.nextObservationTimestamp) } ?? "None")
                    }
                }
                if overview.continuity.observedGaps.isEmpty {
                    Text("No observed interval gaps.").foregroundStyle(.secondary)
                } else {
                    Divider()
                    ForEach(overview.continuity.observedGaps) { gap in
                        HStack(alignment: .firstTextBaseline, spacing: 14) {
                            Text("\(date(gap.previousObservationTimestamp)) → \(date(gap.nextObservationTimestamp))")
                                .frame(width: 245, alignment: .leading)
                            Text(duration(gap.gapDuration)).frame(width: 80, alignment: .leading)
                            Text(gap.classification.replacingOccurrences(of: "_", with: " ").capitalized)
                                .foregroundStyle(.secondary)
                        }
                        .font(.caption.monospaced())
                        Divider()
                    }
                }
                if !overview.continuity.expectedMarketClosures.isEmpty {
                    Text("\(overview.continuity.expectedMarketClosures.count) expected FX weekend closure\(overview.continuity.expectedMarketClosures.count == 1 ? "" : "s") shown as grey breaks in the profile.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                ForEach(overview.continuity.warnings, id: \.self) { warning in
                    Label(warning, systemImage: "exclamationmark.triangle").font(.caption).foregroundStyle(.orange)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func primaryFact(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.title3.weight(.semibold)).lineLimit(2)
        }
    }

    private func fact(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.callout).lineLimit(2)
        }
    }

    private func date(_ timestamp: Int64?) -> String {
        guard let timestamp else { return "—" }
        return Self.dateFormatter.string(from: Date(timeIntervalSince1970: TimeInterval(timestamp)))
    }

    private func duration(_ seconds: Int64) -> String {
        if seconds % 86_400 == 0 { return "\(seconds / 86_400)d" }
        if seconds % 3_600 == 0 { return "\(seconds / 3_600)h" }
        if seconds % 60 == 0 { return "\(seconds / 60)m" }
        return "\(seconds)s"
    }

    private func availableSpan(_ overview: PriceHistoryOverview) -> String {
        guard let start = overview.earliestGovernedObservation, let end = overview.latestGovernedObservation else { return "—" }
        let days = max(0, (end - start) / 86_400)
        if days >= 365 { return "\(days / 365)y \((days % 365) / 30)m" }
        return "\(days)d"
    }

    private func reload() async {
        do {
            overview = try await store.loadPriceHistoryOverview(symbol: lane.symbol, timeframe: lane.timeframe)
            loadedLaneRevision = selectedLaneRevision
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}

private struct PriceActionProfileChart: View {
    let profile: [PriceHistoryProfilePoint]
    let gaps: [GovernedObservationGap]
    let expectedCadence: Int64

    private var prices: [Double] { profile.flatMap { [$0.low, $0.high] } }

    /// A price-action trace must never bridge an interval which the governed
    /// history explicitly reports as absent.  The bounded profile can still
    /// show the observations on either side, but joining them would imply an
    /// interpolated price path that Fragarach does not possess.
    private var contiguousSegments: [[PriceHistoryProfilePoint]] {
        guard let first = profile.first else { return [] }
        var segments = [[first]]
        for point in profile.dropFirst() {
            guard let previous = segments[segments.count - 1].last else { continue }
            if hasObservedGap(between: previous, and: point) {
                segments.append([point])
            } else {
                segments[segments.count - 1].append(point)
            }
        }
        return segments
    }

    var body: some View {
        GroupBox("General price-action profile") {
            GeometryReader { geometry in
                Canvas { context, size in
                    guard let first = profile.first, let last = profile.last,
                          let low = prices.min(), let high = prices.max() else { return }
                    let timeSpan = max(Double(last.timestamp - first.timestamp), Double(expectedCadence))
                    let priceSpan = max(high - low, max(abs(high) * 0.02, 0.000_001))
                    func x(_ timestamp: Int64) -> CGFloat { CGFloat(Double(timestamp - first.timestamp) / timeSpan) * size.width }
                    func y(_ price: Double) -> CGFloat { size.height - CGFloat((price - low) / priceSpan) * size.height }

                    for gap in gaps where gap.previousObservationTimestamp >= first.timestamp && gap.nextObservationTimestamp <= last.timestamp {
                        var path = Path()
                        let position = x(gap.nextObservationTimestamp)
                        path.move(to: CGPoint(x: position, y: 0))
                        path.addLine(to: CGPoint(x: position, y: size.height))
                        let expectedClosure = gap.classification == "EXPECTED_MARKET_CLOSURE"
                        context.stroke(
                            path,
                            with: .color(expectedClosure ? .secondary.opacity(0.55) : .orange.opacity(0.7)),
                            style: .init(lineWidth: 1, dash: [4, 4])
                        )
                    }

                    for segment in contiguousSegments where !segment.isEmpty {
                        var rangePath = Path()
                        for (index, point) in segment.enumerated() {
                            let position = CGPoint(x: x(point.timestamp), y: y(point.high))
                            if index == 0 { rangePath.move(to: position) } else { rangePath.addLine(to: position) }
                        }
                        for point in segment.reversed() { rangePath.addLine(to: CGPoint(x: x(point.timestamp), y: y(point.low))) }
                        rangePath.closeSubpath()
                        context.fill(rangePath, with: .color(.accentColor.opacity(0.14)))
                    }

                    for segment in contiguousSegments where !segment.isEmpty {
                        var closePath = Path()
                        for (index, point) in segment.enumerated() {
                            let position = CGPoint(x: x(point.timestamp), y: y(point.close))
                            if index == 0 { closePath.move(to: position) } else { closePath.addLine(to: position) }
                        }
                        context.stroke(closePath, with: .color(.accentColor), lineWidth: 1.5)
                    }
                }
                .background(.quaternary.opacity(0.45), in: RoundedRectangle(cornerRadius: 6))
                .overlay(alignment: .bottomLeading) { chartLabel(profile.first?.timestamp).padding(6) }
                .overlay(alignment: .bottomTrailing) { chartLabel(profile.last?.timestamp).padding(6) }
            }
            .frame(height: 290)
            Text("A fixed-size aggregate profile for orientation only. The trace stops at discontinuities; Fragarach never interpolates a price path. The band shows the recorded high–low range; grey markers are expected market closures and orange markers are missing intervals.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private func hasObservedGap(
        between previous: PriceHistoryProfilePoint,
        and next: PriceHistoryProfilePoint
    ) -> Bool {
        gaps.contains {
            $0.previousObservationTimestamp < next.timestamp
            && $0.nextObservationTimestamp > previous.timestamp
        }
    }

    private func chartLabel(_ timestamp: Int64?) -> some View {
        Text(timestamp.map { DateFormatter.localizedString(from: Date(timeIntervalSince1970: TimeInterval($0)), dateStyle: .medium, timeStyle: .none) } ?? "—")
            .font(.caption2).foregroundStyle(.secondary)
    }
}
