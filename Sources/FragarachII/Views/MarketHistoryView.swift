import OperationsCore
import SwiftUI

struct MarketHistoryView: View {
    @EnvironmentObject var store: ConsoleStore
    private let timeframes = ["D1", "H4", "H1", "M30", "M15", "M5"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Market History Service").font(.largeTitle).fontWeight(.semibold)
                Text("Fragarach answers what happened. Consumers receive only OHLC, CAODT, Status, and Warnings.")
                    .foregroundStyle(.secondary)
                HStack {
                    Picker("Symbol", selection: $store.marketHistorySymbol) {
                        ForEach(["AUDUSD", "XAUUSD"], id: \.self) { Text($0).tag($0) }
                    }.frame(width: 180)
                    Picker("Window", selection: $store.marketHistoryTradingDays) {
                        Text("5 Trading Days").tag(5)
                        Text("21 Trading Days").tag(21)
                        Text("365 Trading Days").tag(365)
                    }.frame(width: 200)
                    Button("Request Market History") { Task { await store.requestMarketHistory() } }
                        .buttonStyle(.borderedProminent)
                }
                if let error=store.marketHistoryError { Text(error).foregroundStyle(.red) }
                Grid(alignment:.leading,horizontalSpacing:18,verticalSpacing:0) {
                    GridRow { header("Timeframe");header("Status");header("OHLC Bars");header("CAODT");header("Warnings") }
                    Divider().gridCellColumns(5)
                    ForEach(timeframes,id:\.self) { timeframe in
                        let response=store.marketHistoryResponses[timeframe]
                        GridRow {
                            Text(timeframe).font(.body.monospaced().bold())
                            Text(response?.status ?? "NOT_REQUESTED").foregroundStyle(color(response?.status))
                            Text("\(response?.ohlc.count ?? 0)").monospacedDigit()
                            Text(response?.caodt ?? "—").font(.caption.monospaced())
                            Text(response?.warnings.joined(separator:", ") ?? "—").font(.caption).foregroundStyle(.secondary)
                        }.padding(.vertical,9)
                        Divider().gridCellColumns(5)
                    }
                }.padding(14).background(.quaternary.opacity(0.18),in:RoundedRectangle(cornerRadius:10))
            }.padding().frame(maxWidth:1100,alignment:.leading)
        }.task { await store.requestMarketHistory() }
    }

    private func header(_ text:String)->some View { Text(text).font(.caption.bold()).foregroundStyle(.secondary) }
    private func color(_ status:String?)->Color { switch status { case "AVAILABLE":.green;case "AVAILABLE_WITH_WARNINGS":.orange;case "TIMEFRAME_NOT_ACTIVE":.secondary;default:.red } }
}
