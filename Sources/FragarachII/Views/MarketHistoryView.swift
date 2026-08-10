import OperationsCore
import SwiftUI

struct MarketHistoryView: View {
    @EnvironmentObject var store: ConsoleStore
    @State private var coverageNoteSelection: CoverageNoteSelection?
    private let cadenceOrder = ["D1", "H1", "M30", "M5"]

    private var availableSymbols: [String] {
        let estateSymbols = Set((store.snapshot?.registrations ?? [])
            .filter { !$0.retired && $0.timeframe == "D1" }
            .map(\.asset))
        return estateSymbols.isEmpty ? [store.marketHistorySymbol] : estateSymbols.sorted()
    }

    private var timeframes: [String] {
        let lanes = Set((store.snapshot?.lanes ?? [])
            .filter { $0.asset == store.marketHistorySymbol }
            .map(\.timeframe))
        let active = lanes.isEmpty ? Set(cadenceOrder) : lanes
        return cadenceOrder.filter(active.contains)
    }

    private var totalBars: Int { store.marketHistoryResponses.values.reduce(0) { $0 + $1.ohlc.count } }
    private var latestCAODT: String? {
        store.marketHistoryResponses.values.compactMap(\.caodt).max()
    }
    private var warningCount: Int {
        store.marketHistoryResponses.values.reduce(0) { $0 + $1.warnings.count }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Market History").font(.largeTitle).fontWeight(.semibold)
                Text("Read the governed history for any active estate symbol. This view never starts acquisition or changes evidence.")
                    .foregroundStyle(.secondary)
                HStack {
                    Picker("Symbol", selection: $store.marketHistorySymbol) {
                        ForEach(availableSymbols, id: \.self) { Text($0).tag($0) }
                    }.pickerStyle(.menu).frame(width: 180)
                    Picker("Window", selection: $store.marketHistoryTradingDays) {
                        Text("5 Trading Days").tag(5)
                        Text("21 Trading Days").tag(21)
                        Text("365 Trading Days").tag(365)
                    }.pickerStyle(.menu).frame(width: 200)
                    Button("Refresh History") { Task { await store.requestMarketHistory(timeframes: timeframes) } }
                        .buttonStyle(.borderedProminent)
                    Text("\(availableSymbols.count) active symbols · \(timeframes.count) commissioned lanes")
                        .font(.caption).foregroundStyle(.secondary)
                }
                LazyVGrid(columns: [GridItem(.adaptive(minimum:170), spacing:12)], spacing:12) {
                    HistoryMetric(title:"Governed bars", value:totalBars.formatted(), detail:"Selected window across active lanes")
                    HistoryMetric(title:"Latest governed time", value:compactTimestamp(latestCAODT), detail:"Newest returned CAODT")
                    HistoryMetric(title:"Coverage notes", value:"\(warningCount)", detail:warningCount == 0 ? "No history warnings" : "Select a lane below to review")
                }
                if let error=store.marketHistoryError { Text(error).foregroundStyle(.red) }
                Grid(alignment:.leading,horizontalSpacing:18,verticalSpacing:0) {
                    GridRow { header("Lane");header("Availability");header("Governed bars");header("Latest governed time");header("Coverage notes") }
                    Divider().gridCellColumns(5)
                    ForEach(timeframes,id:\.self) { timeframe in
                        let response=store.marketHistoryResponses[timeframe]
                        GridRow {
                            Text(timeframe).font(.body.monospaced().bold())
                            coverageStatusButton(timeframe:timeframe,response:response)
                            Text("\(response?.ohlc.count ?? 0)").monospacedDigit()
                            Text(response?.caodt ?? "—").font(.caption.monospaced())
                            coverageSummaryButton(timeframe:timeframe,response:response)
                        }.padding(.vertical,9)
                        Divider().gridCellColumns(5)
                    }
                }
                .padding(14).background(.quaternary.opacity(0.18),in:RoundedRectangle(cornerRadius:10))
                .popover(item:$coverageNoteSelection,arrowEdge:.trailing) { selection in
                    CoverageNotesPopover(selection:selection)
                }
                Divider()
                EstateAuditHistoryView()
                DisclosureGroup("Synthetic product maintenance") { syntheticProducts }
            }.padding().frame(maxWidth:1100,alignment:.leading)
        }
        .task(id: availableSymbols) {
            if !availableSymbols.contains(store.marketHistorySymbol) {
                store.marketHistorySymbol = availableSymbols.first ?? "AUDUSD"
            }
            await store.requestMarketHistory(timeframes: timeframes)
        }
        .task { await store.refreshSyntheticProducts() }
        .onChange(of: store.marketHistorySymbol) { _, _ in
            Task { await store.requestMarketHistory(timeframes: timeframes) }
        }
    }

    private func header(_ text:String)->some View { Text(text).font(.caption.bold()).foregroundStyle(.secondary) }
    private func color(_ status:String?)->Color { switch status { case "AVAILABLE":.green;case "AVAILABLE_WITH_WARNINGS":.orange;case "TIMEFRAME_NOT_ACTIVE":.secondary;case nil:.secondary;default:.red } }
    private func presentedStatus(_ status:String?)->String {
        switch status {
        case "AVAILABLE": "Available"
        case "AVAILABLE_WITH_WARNINGS": "Available with notes"
        case "TIMEFRAME_NOT_ACTIVE": "Not commissioned"
        case nil: "Loading…"
        default: status?.replacingOccurrences(of:"_",with:" ").capitalized ?? "Unavailable"
        }
    }
    private func coverageNotes(_ warnings:[String])->String {
        guard !warnings.isEmpty else { return "No coverage notes" }
        let presented = warnings.prefix(3).map {
            switch $0 {
            case "HISTORICAL_GAPS_PRESENT": "Observed gaps"
            case "REQUESTED_WINDOW_HAS_MISSING_HISTORY": "Window incomplete"
            case "HISTORICAL_AUTHORITY_AMBER": "Review history"
            default: $0.replacingOccurrences(of:"_",with:" ").capitalized
            }
        }
        return presented.joined(separator:", ")
    }
    @ViewBuilder private func coverageStatusButton(timeframe:String,response:MarketHistoryResponse?)->some View {
        let warnings=response?.warnings ?? []
        if warnings.isEmpty {
            Text(presentedStatus(response?.status)).foregroundStyle(color(response?.status))
        } else {
            Button { coverageNoteSelection = .init(timeframe:timeframe,response:response) } label: {
                Label(presentedStatus(response?.status),systemImage:"info.circle")
                    .foregroundStyle(color(response?.status))
            }
            .buttonStyle(.plain)
            .help("Show \(timeframe) coverage notes")
        }
    }
    @ViewBuilder private func coverageSummaryButton(timeframe:String,response:MarketHistoryResponse?)->some View {
        let warnings=response?.warnings ?? []
        if warnings.isEmpty {
            Text(coverageNotes(warnings)).font(.caption).foregroundStyle(.secondary)
        } else {
            Button(coverageNotes(warnings)) { coverageNoteSelection = .init(timeframe:timeframe,response:response) }
                .buttonStyle(.plain).font(.caption).foregroundStyle(.secondary)
                .help("Show \(timeframe) coverage notes")
        }
    }
    private func compactTimestamp(_ value:String?)->String { value?.replacingOccurrences(of:"T",with:" ").replacingOccurrences(of:"+00:00",with:" UTC") ?? "—" }

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

private struct CoverageNoteSelection: Identifiable {
    let timeframe:String
    let response:MarketHistoryResponse?
    var id:String { timeframe }
}

private struct CoverageNotesPopover:View {
    let selection:CoverageNoteSelection
    @Environment(\.dismiss) private var dismiss
    private var response:MarketHistoryResponse? { selection.response }
    private var warnings:[String] { response?.warnings ?? [] }
    var body:some View {
        VStack(alignment:.leading,spacing:12) {
            HStack { Label("\(selection.timeframe) coverage notes",systemImage:"text.magnifyingglass").font(.headline);Spacer();Button("Done"){dismiss()} }
            Grid(alignment:.leading,horizontalSpacing:12,verticalSpacing:6) {
                GridRow { Text("Availability").foregroundStyle(.secondary);Text(presentedStatus(response?.status)) }
                GridRow { Text("Governed bars").foregroundStyle(.secondary);Text("\(response?.ohlc.count ?? 0)") }
                GridRow { Text("Latest time").foregroundStyle(.secondary);Text(response?.caodt ?? "—").font(.caption.monospaced()) }
            }
            Divider()
            ForEach(warnings,id:\.self) { warning in
                VStack(alignment:.leading,spacing:3) {
                    Text(noteTitle(warning)).font(.subheadline.bold())
                    Text(noteDetail(warning)).font(.caption).foregroundStyle(.secondary)
                    Text(warning).font(.caption2.monospaced()).foregroundStyle(.tertiary)
                }
            }
        }.padding().frame(width:420,alignment:.leading)
    }
    private func presentedStatus(_ status:String?)->String { status?.replacingOccurrences(of:"_",with:" ").capitalized ?? "Loading" }
    private func noteTitle(_ warning:String)->String { switch warning {
    case "HISTORICAL_GAPS_PRESENT": "Observed historical gaps"
    case "REQUESTED_WINDOW_HAS_MISSING_HISTORY": "Selected window is incomplete"
    case "HISTORICAL_AUTHORITY_AMBER": "History requires review"
    default: warning.replacingOccurrences(of:"_",with:" ").capitalized
    } }
    private func noteDetail(_ warning:String)->String { switch warning {
    case "HISTORICAL_GAPS_PRESENT": "The governed record contains one or more gaps in the selected timeframe."
    case "REQUESTED_WINDOW_HAS_MISSING_HISTORY": "Some expected observations in the selected window are not present in the governed record."
    case "HISTORICAL_AUTHORITY_AMBER": "The evidence is available, but its history authority has an amber review condition."
    default: "This coverage condition was returned by the governed history service."
    } }
}

private struct HistoryMetric: View {
    let title:String;let value:String;let detail:String
    var body: some View {
        VStack(alignment:.leading,spacing:5) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.title3.bold()).lineLimit(1)
            Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
        }.padding(12).frame(maxWidth:.infinity,minHeight:80,alignment:.leading)
            .background(.regularMaterial,in:RoundedRectangle(cornerRadius:10))
    }
}
