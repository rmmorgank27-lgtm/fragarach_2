import OperationsCore
import SwiftUI

struct MarketHistoryView: View {
    @EnvironmentObject var store: ConsoleStore
    @State private var selectedLane: HistorySummaryLane?

    private var availableSymbols: [String] {
        let symbols = Set((store.snapshot?.registrations ?? [])
            .filter { !$0.retired && $0.timeframe == "D1" }.map(\.asset))
        return symbols.isEmpty ? [store.marketHistorySymbol] : symbols.sorted()
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Market History").font(.largeTitle).fontWeight(.semibold)
                Text("History held for each timeframe — total coverage and recent bar counts.")
                    .foregroundStyle(.secondary)
                HStack(spacing: 14) {
                    Picker("Symbol", selection: $store.marketHistorySymbol) {
                        ForEach(availableSymbols, id: \.self) { Text($0).tag($0) }
                    }.pickerStyle(.menu).frame(width: 210)
                    Button("Refresh History") { Task { await store.requestMarketHistory() } }
                        .disabled(store.marketHistoryLoading)
                    if store.marketHistoryLoading { ProgressView().controlSize(.small) }
                    Spacer()
                    Label("Read only", systemImage: "lock").font(.caption).foregroundStyle(.secondary)
                }
                if let error = store.marketHistoryError {
                    Text(error).foregroundStyle(.red)
                }
                if let summary = store.marketHistorySummary {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("Trading days held · \(summary.tradingDaysHeld?.formatted() ?? "Unavailable")")
                            .font(.title3.bold())
                        Text("Distinct D1 dates held that match the symbol’s calendar. Calendar closures are excluded; shortened sessions count as one full day.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    historyTable(summary)
                    VStack(alignment: .leading, spacing: 5) {
                        Text("Last year = rolling 12 months · Last month = rolling 1 month · Rolling periods end at refresh time.")
                        Text("Counts use bar opening times in UTC. Weekly and monthly bars are complete periods derived from daily history. M15 uses published M5-derived history. A dash means unavailable; 0 means no bars in that period.")
                        Text("Last active session is the most recent completed trading session. Current-session counts include closed bars only. Session dates use \(summary.sessions.timezone ?? "an unavailable timezone").")
                        Text(summary.sessions.note)
                        Text("Refreshed \(timestamp(summary.observedAtUTC))")
                    }.font(.caption).foregroundStyle(.secondary)
                } else if store.marketHistoryLoading {
                    Text("Reading history totals…").foregroundStyle(.secondary).padding(.vertical, 30)
                }
                Divider()
                EstateAuditHistoryView()
                DisclosureGroup("Synthetic product maintenance") { syntheticProducts }
            }.padding(22).frame(maxWidth: 1100, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .task(id: availableSymbols) {
            if !availableSymbols.contains(store.marketHistorySymbol) {
                store.marketHistorySymbol = availableSymbols.first ?? "AUDUSD"
            }
        }
        .task(id: store.marketHistorySymbol) {
            selectedLane = nil
            await store.requestMarketHistory()
        }
        .task { await store.refreshSyntheticProducts() }
        .popover(item: $selectedLane) { lane in
            VStack(alignment: .leading, spacing: 12) {
                Text("\(lane.timeframe) coverage").font(.headline)
                Text(lane.status.replacingOccurrences(of: "_", with: " ").capitalized)
                ForEach(lane.warnings, id: \.self) { warning in
                    Text(warning.replacingOccurrences(of: "_", with: " ").capitalized)
                        .font(.caption).foregroundStyle(.secondary)
                }
                ForEach(lane.notes ?? [], id: \.self) { note in
                    Text(note).font(.caption).foregroundStyle(.secondary)
                }
                Button("View current routing") {
                    selectedLane=nil
                    store.openRouting(symbol:store.marketHistorySymbol,timeframe:lane.timeframe)
                }.buttonStyle(.borderedProminent)
                if lane.derived && lane.timeframe != "M15" { Text("Only complete periods supported by the daily calendar are counted.").font(.caption) }
            }.padding().frame(width: 350, alignment: .leading)
        }
    }

    private func historyTable(_ summary: HistorySummary) -> some View {
        ScrollView(.horizontal) {
            Grid(alignment: .leading, horizontalSpacing: 14, verticalSpacing: 0) {
                GridRow {
                    header("Timeframe").frame(width: 76, alignment: .leading)
                    header("Total bars")
                    header("Full date range · UTC")
                    header("Last year").help("From \(timestamp(summary.lastYearStartUTC)) to refresh time")
                    header("Last month").help("From \(timestamp(summary.lastMonthStartUTC)) to refresh time")
                    sessionHeader("Last active session", window: summary.sessions.lastActive, fallback: "Unavailable")
                    sessionHeader("Current session", window: summary.sessions.current,
                                  fallback: summary.sessions.state == "CLOSED" ? "Market closed" : "Unavailable")
                    header("Coverage")
                }.padding(.bottom, 12)
                Divider().gridCellColumns(8).gridCellUnsizedAxes(.horizontal)
                ForEach(summary.lanes) { lane in
                    GridRow {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(lane.timeframe).font(.body.monospaced().bold())
                            if lane.derived { Text("Derived").font(.caption2).foregroundStyle(.secondary) }
                        }.frame(width: 76, alignment: .leading)
                        count(lane.totalBars).fontWeight(.semibold)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(shortTimestamp(lane.firstBarUTC))
                            Text(shortTimestamp(lane.lastBarUTC)).foregroundStyle(.secondary)
                        }.font(.caption.monospaced())
                            .help("First to latest bar opening time (UTC)")
                        count(lane.lastYearBars)
                        count(lane.lastMonthBars)
                        if lane.supportsSessions { count(lane.lastActiveSessionBars) }
                        else { Text("N/A").foregroundStyle(.secondary) }
                        if !lane.supportsSessions { Text("N/A").foregroundStyle(.secondary) }
                        else if summary.sessions.state == "CLOSED" {
                            Text("Market closed").font(.caption).foregroundStyle(.secondary)
                        } else { count(lane.currentSessionBars) }
                        Button { selectedLane = lane } label: {
                            Label(coverageLabel(lane), systemImage: lane.status == "AVAILABLE" && (lane.notes ?? []).isEmpty ? "checkmark.circle" : "info.circle")
                                .font(.caption).foregroundStyle(coverageColor(lane))
                        }.buttonStyle(.plain).help("Show \(lane.timeframe) coverage notes")
                    }.padding(.vertical, 13)
                    Divider().gridCellColumns(8).gridCellUnsizedAxes(.horizontal)
                }
            }.padding(16)
        }.background(.quaternary.opacity(0.18), in: RoundedRectangle(cornerRadius: 10))
    }

    private func sessionHeader(_ title: String, window: HistorySessionWindow?, fallback: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            header(title)
            Text(window?.date ?? fallback).font(.caption2).foregroundStyle(.secondary)
        }.fixedSize().help(window.map { "\(timestamp($0.openUTC)) to \(timestamp($0.closeUTC))" } ?? fallback)
    }

    private func header(_ value: String) -> some View {
        Text(value).font(.caption.bold()).foregroundStyle(.secondary).fixedSize()
    }
    private func count(_ value: Int?) -> some View { Text(value?.formatted() ?? "—").monospacedDigit() }
    private func shortTimestamp(_ value: String?) -> String {
        guard let value else { return "—" }
        return String(value.prefix(16)).replacingOccurrences(of: "T", with: " ")
    }
    private func timestamp(_ value: String) -> String { shortTimestamp(value) + " UTC" }
    private func coverageLabel(_ lane: HistorySummaryLane) -> String {
        switch lane.status {
        case "AVAILABLE": (lane.notes ?? []).isEmpty ? "Available" : "Notes"
        case "AVAILABLE_WITH_WARNINGS": "Notes"
        case "NO_HISTORY": "No history"
        case "TIMEFRAME_NOT_ACTIVE": "Not active"
        default: "Unavailable"
        }
    }
    private func coverageColor(_ lane: HistorySummaryLane) -> Color {
        switch lane.status {
        case "AVAILABLE": .green
        case "AVAILABLE_WITH_WARNINGS": .orange
        case "TIMEFRAME_NOT_ACTIVE", "NO_HISTORY": .secondary
        default: .red
        }
    }

    @ViewBuilder private var syntheticProducts:some View {
        VStack(alignment:.leading,spacing:12) {
            HStack { VStack(alignment:.leading,spacing:3){Text("Synthetic Products").font(.title2.bold());Text("Dedicated rebuildable repository — never real canonical evidence.").foregroundStyle(.secondary)};Spacer();Button("Regenerate All"){Task{await store.regenerateSyntheticProduct()}};Button("Rebuild Repository"){Task{await store.rebuildSyntheticRepository()}} }
            if let error=store.syntheticError { Text(error).foregroundStyle(.red) }
            if let snapshot=store.syntheticSnapshot {
                HStack(spacing:14){Text("SYNTHETIC").font(.caption.bold()).padding(.horizontal,7).padding(.vertical,3).background(.purple.opacity(0.18),in:Capsule());Text("\(snapshot.summary.available) available");Text("\(snapshot.summary.stale) stale");Text("\(snapshot.summary.incomplete) incomplete");Text("\(snapshot.summary.unavailable) unavailable");Spacer();Text(snapshot.repository).font(.caption.monospaced()).foregroundStyle(.secondary).lineLimit(1)}
                ForEach(snapshot.products) { product in
                    GroupBox {
                        VStack(alignment:.leading,spacing:8) {
                            HStack { Text("\(product.symbol) · \(product.targetTimeframe)").font(.headline);Text("SYNTHETIC").font(.caption.bold()).foregroundStyle(.purple);Text(product.status).foregroundStyle(syntheticColor(product.status));Spacer();Button("Regenerate"){Task{await store.regenerateSyntheticProduct(product.id)}} }
                            Grid(alignment:.leading,horizontalSpacing:16,verticalSpacing:5) {
                                GridRow{Text("Immediate source").foregroundStyle(.secondary);Text("\(product.immediateSourceSymbol) · \(product.immediateSourceTimeframe) · \(product.immediateSourceEvidenceClass)");Text("Originating real").foregroundStyle(.secondary);Text("\(product.originatingRealSymbol) · \(product.originatingRealTimeframe)")}
                                GridRow{Text("Rule").foregroundStyle(.secondary);Text("\(product.aggregationRule) v\(product.aggregationRuleVersion)");Text("Synthetic revision").foregroundStyle(.secondary);Text("\(product.syntheticRevision)")}
                                GridRow{Text("Calendar / session").foregroundStyle(.secondary);Text("\(product.calendarAuthority) · \(product.sessionAlignment)");Text("Source revision").foregroundStyle(.secondary);Text(product.sourceRevision ?? "—").font(.caption.monospaced()).lineLimit(1)}
                                GridRow{Text("Latest observation").foregroundStyle(.secondary);Text(epoch(product.latestSyntheticObservation));Text("Authorised consumers").foregroundStyle(.secondary);Text(product.authorisedConsumers.joined(separator:", "))}
                            }
                        }.frame(maxWidth:.infinity,alignment:.leading)
                    }
                }
            } else { Text("Loading synthetic registrations…").foregroundStyle(.secondary) }
        }
    }
    private func syntheticColor(_ status:String)->Color {switch status{case "Available":.green;case "Stale","Incomplete":.orange;default:.red}}
    private func epoch(_ value:Int64?)->String {guard let value else{return "—"};return ISO8601DateFormatter().string(from:Date(timeIntervalSince1970:TimeInterval(value)))}
}
