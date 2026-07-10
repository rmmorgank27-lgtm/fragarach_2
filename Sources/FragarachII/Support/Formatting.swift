import Foundation

enum Format {
    static func utc(_ epoch:Int64?)->String { guard let epoch else{return "—"}; return Date(timeIntervalSince1970:TimeInterval(epoch)).formatted(.iso8601.year().month().day().timeZone(separator:.omitted)) }
    static func count(_ value:Int)->String { value.formatted(.number.grouping(.automatic)) }
}
