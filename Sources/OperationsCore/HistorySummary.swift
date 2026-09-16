import Foundation

public struct HistorySummary: Codable, Sendable {
    public let tradingDaysHeld: Int?
    public let symbol: String
    public let observedAtUTC: String
    public let lastYearStartUTC: String
    public let lastMonthStartUTC: String
    public let last24HoursStartUTC: String
    public let sessions: HistorySessions
    public let lanes: [HistorySummaryLane]
    enum CodingKeys: String, CodingKey {
        case tradingDaysHeld = "trading_days_held"
        case symbol, lanes, sessions
        case observedAtUTC = "observed_at_utc"
        case lastYearStartUTC = "last_year_start_utc"
        case lastMonthStartUTC = "last_month_start_utc"
        case last24HoursStartUTC = "last_24_hours_start_utc"
    }
}

public struct HistorySummaryLane: Codable, Sendable, Identifiable {
    public var id: String { timeframe }
    public let timeframe: String
    public let status: String
    public let totalBars: Int?
    public let firstBarUTC: String?
    public let lastBarUTC: String?
    public let lastYearBars: Int?
    public let lastMonthBars: Int?
    public let last24HoursBars: Int?
    public let warnings: [String]
    public let notes: [String]?
    public let derived: Bool
    public let lastActiveSessionBars: Int?
    public let currentSessionBars: Int?
    public var supportsSessions: Bool { !["MN1", "W1"].contains(timeframe) }
    public var supports24Hours: Bool { !["MN1", "W1", "D1"].contains(timeframe) }
    enum CodingKeys: String, CodingKey {
        case timeframe, status, warnings, derived, notes
        case totalBars = "total_bars", firstBarUTC = "first_bar_utc", lastBarUTC = "last_bar_utc"
        case lastYearBars = "last_year_bars", lastMonthBars = "last_month_bars"
        case last24HoursBars = "last_24_hours_bars"
        case lastActiveSessionBars = "last_active_session_bars", currentSessionBars = "current_session_bars"
    }
}

public struct HistorySessions: Codable, Sendable {
    public let state: String
    public let timezone: String?
    public let lastActive: HistorySessionWindow?
    public let current: HistorySessionWindow?
    public let note: String
    enum CodingKeys: String, CodingKey {
        case state, timezone, current, note
        case lastActive = "last_active"
    }
}

public struct HistorySessionWindow: Codable, Sendable {
    public let date: String
    public let openUTC: String
    public let closeUTC: String
    enum CodingKeys: String, CodingKey {
        case date
        case openUTC = "open_utc", closeUTC = "close_utc"
    }
}
