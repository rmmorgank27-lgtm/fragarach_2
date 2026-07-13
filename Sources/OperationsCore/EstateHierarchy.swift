import Foundation

public struct EstateGroupSummary: Equatable, Sendable {
    public let truthScore: Int?
    public let authorityState: String
    public let symbolCount: Int
    public let laneCount: Int
    public let healthyCount: Int
    public let attentionCount: Int
    public let criticalCount: Int
    public let coveragePercent: Int?
    public let freshnessPercent: Int?
    public let caodt: String?
    public let providers: [String]
    public let attentionSymbols: [String]

    public init(lanes: [EstateTruthLane]) {
        let scores = lanes.map(\.truthState.truthScore)
        truthScore = scores.isEmpty ? nil : Int((Double(scores.reduce(0, +)) / Double(scores.count)).rounded())
        authorityState = Self.state(for: truthScore)
        symbolCount = Set(lanes.map(\.symbol)).count
        laneCount = lanes.count
        healthyCount = lanes.filter { $0.truthState.authorityState == "GREEN" }.count
        attentionCount = lanes.filter { $0.truthState.authorityState == "AMBER" }.count
        criticalCount = lanes.filter { $0.truthState.authorityState == "RED" }.count
        coveragePercent = Self.average(lanes.compactMap(\.truthState.coverageScore))
        freshnessPercent = Self.average(lanes.compactMap(\.truthState.freshnessScore))
        caodt = lanes.map(\.truthState.caodt).min()
        providers = Array(Set(lanes.compactMap(\.providerSummary.provider).filter { !$0.isEmpty })).sorted()
        attentionSymbols = Array(Set(lanes.filter { $0.truthState.authorityState != "GREEN" }.map(\.symbol))).sorted()
    }

    private static func average(_ values: [Int]) -> Int? {
        values.isEmpty ? nil : Int((Double(values.reduce(0, +)) / Double(values.count)).rounded())
    }

    private static func state(for score: Int?) -> String {
        guard let score else { return "NOT_MEASURED" }
        return score >= 80 ? "GREEN" : score >= 50 ? "AMBER" : "RED"
    }
}

public struct EstateSubgroup: Identifiable, Equatable, Sendable {
    public var id: String { name }
    public let name: String
    public let lanes: [EstateTruthLane]
    public let summary: EstateGroupSummary

    public init(name: String, lanes: [EstateTruthLane]) {
        self.name = name
        self.lanes = lanes.sorted { ($0.symbol, $0.timeframe) < ($1.symbol, $1.timeframe) }
        summary = EstateGroupSummary(lanes: lanes)
    }
}

public struct EstateMarketGroup: Identifiable, Equatable, Sendable {
    public var id: String { name }
    public let name: String
    public let systemImage: String
    public let lanes: [EstateTruthLane]
    public let subgroups: [EstateSubgroup]
    public let summary: EstateGroupSummary

    public init(name: String, systemImage: String, lanes: [EstateTruthLane], subgroups: [EstateSubgroup]) {
        self.name = name
        self.systemImage = systemImage
        self.lanes = lanes.sorted { ($0.symbol, $0.timeframe) < ($1.symbol, $1.timeframe) }
        self.subgroups = subgroups
        summary = EstateGroupSummary(lanes: lanes)
    }
}

public struct EstateHierarchy: Equatable, Sendable {
    public let markets: [EstateMarketGroup]
    public let estateSummary: EstateGroupSummary

    public init(lanes: [EstateTruthLane]) {
        let grouped = Dictionary(grouping: lanes) { EstateHierarchyClassifier.marketName(assetClass: $0.searchMetadata.assetClass) }
        let canonical = EstateHierarchyClassifier.canonicalMarkets
        let extras = grouped.keys.filter { !canonical.contains($0) }.sorted()
        markets = (canonical + extras).map { market in
            let marketLanes = grouped[market] ?? []
            let subgroupNames = EstateHierarchyClassifier.subgroupNames(market: market)
            let subgroups = subgroupNames.map { subgroup in
                EstateSubgroup(name: subgroup, lanes: marketLanes.filter {
                    EstateHierarchyClassifier.subgroupName(
                        market: market,
                        symbol: $0.symbol,
                        assetClass: $0.searchMetadata.assetClass,
                        exchange: $0.searchMetadata.exchange
                    ) == subgroup
                })
            }
            return EstateMarketGroup(name: market, systemImage: EstateHierarchyClassifier.systemImage(market: market), lanes: marketLanes, subgroups: subgroups)
        }
        estateSummary = EstateGroupSummary(lanes: lanes)
    }

    public func market(named name: String) -> EstateMarketGroup? { markets.first { $0.name == name } }
}

public enum EstateHierarchyClassifier {
    public static let canonicalMarkets = ["Forex", "Metals", "Energy", "Indices", "Stocks", "Crypto"]
    private static let majorPairs = Set(["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD"])
    private static let g10Currencies = Set(["USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"])
    private static let secondaryCurrencies = Set(["AUD", "NZD", "CAD"])

    public static func marketName(assetClass: String) -> String {
        let value = assetClass.uppercased()
        if value == "FX" || value.contains("FOREX") { return "Forex" }
        if value.contains("METAL") { return "Metals" }
        if value.contains("ENERGY") { return "Energy" }
        if value.contains("INDIC") { return "Indices" }
        if value.contains("EQUIT") || value.contains("STOCK") { return "Stocks" }
        if value.contains("CRYPTO") || value.contains("DIGITAL_ASSET") { return "Crypto" }
        return assetClass.replacingOccurrences(of: "_", with: " ").capitalized
    }

    public static func subgroupNames(market: String) -> [String] {
        switch market {
        case "Forex": ["Majors", "Minors", "Crosses", "Exotics"]
        case "Stocks": ["US", "UK", "Germany", "Australia", "Canada", "Japan"]
        case "Indices": ["US", "Europe", "Asia", "Australia"]
        case "Crypto": ["All"]
        default: []
        }
    }

    public static func subgroupName(market: String, symbol: String, assetClass: String, exchange: String) -> String? {
        switch market {
        case "Forex": return forexSubgroup(symbol: symbol)
        case "Stocks": return stockSubgroup(assetClass: assetClass, exchange: exchange)
        case "Indices": return indexSubgroup(symbol: symbol, exchange: exchange)
        case "Crypto": return "All"
        default: return nil
        }
    }

    public static func systemImage(market: String) -> String {
        switch market {
        case "Forex": "dollarsign.arrow.circlepath"
        case "Metals": "seal"
        case "Energy": "bolt"
        case "Indices": "chart.line.uptrend.xyaxis"
        case "Stocks": "building.columns"
        case "Crypto": "bitcoinsign.circle"
        default: "square.grid.2x2"
        }
    }

    private static func forexSubgroup(symbol: String) -> String {
        let value = symbol.uppercased()
        guard value.count == 6 else { return "Exotics" }
        if majorPairs.contains(value) { return "Majors" }
        let base = String(value.prefix(3)), quote = String(value.suffix(3))
        guard g10Currencies.contains(base), g10Currencies.contains(quote) else { return "Exotics" }
        return secondaryCurrencies.contains(base) || secondaryCurrencies.contains(quote) ? "Minors" : "Crosses"
    }

    private static func stockSubgroup(assetClass: String, exchange: String) -> String {
        let text = "\(assetClass) \(exchange)".uppercased()
        if text.contains("UK") || text.contains("LONDON") || text.contains("LSE") { return "UK" }
        if text.contains("GERMAN") || text.contains("DEUTSCHE") || text.contains("XETRA") { return "Germany" }
        if text.contains("AUSTRAL") || text.contains("ASX") { return "Australia" }
        if text.contains("CANAD") || text.contains("TSX") { return "Canada" }
        if text.contains("JAPAN") || text.contains("TOKYO") || text.contains("TSE") { return "Japan" }
        return "US"
    }

    private static func indexSubgroup(symbol: String, exchange: String) -> String {
        let value = "\(symbol) \(exchange)".uppercased()
        if ["XJO", "ASX", "AUS200"].contains(where: { value.contains($0) }) { return "Australia" }
        if ["NIKKEI", "N225", "HSI", "HANG SENG", "ASIA"].contains(where: { value.contains($0) }) { return "Asia" }
        if ["DAX", "FTSE", "STOXX", "EUROPE", "DEUTSCHE"].contains(where: { value.contains($0) }) { return "Europe" }
        return "US"
    }
}
