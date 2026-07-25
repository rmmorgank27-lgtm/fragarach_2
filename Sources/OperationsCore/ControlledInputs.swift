import Foundation

public enum DateRangeValidation:Equatable,Sendable { case valid;case reversed;case futureBoundary(maximum:String);case contractLimit(maximumDays:Int) }
public struct ControlledDateRange:Equatable,Sendable {
    public var from:Date;public var through:Date;public let completedBoundary:Date;public let maximumCalendarDays:Int
    public init(from:Date,through:Date,completedBoundary:Date,maximumCalendarDays:Int=5000){self.from=from;self.through=through;self.completedBoundary=completedBoundary;self.maximumCalendarDays=maximumCalendarDays}
    public var fromISO:String{Self.iso(from)};public var throughISO:String{Self.iso(through)}
    public var validation:DateRangeValidation { let cal=Self.calendar;let start=cal.startOfDay(for:from),end=cal.startOfDay(for:through),boundary=cal.startOfDay(for:completedBoundary);if start>end{return .reversed};if end>boundary{return .futureBoundary(maximum:Self.iso(boundary))};let days=cal.dateComponents([.day],from:start,to:end).day!+1;if days>maximumCalendarDays{return .contractLimit(maximumDays:maximumCalendarDays)};return .valid }
    public static func iso(_ date:Date)->String{let parts=calendar.dateComponents([.year,.month,.day],from:date);return String(format:"%04d-%02d-%02d",parts.year!,parts.month!,parts.day!)}
    private static var calendar:Calendar{var c=Calendar(identifier:.gregorian);c.timeZone=TimeZone(secondsFromGMT:0)!;return c}
}

public struct NormalizedDateInput:Equatable,Sendable { public let date:Date;public let canonicalISO:String;public let interpretation:String? }
public enum ControlledDateParser {
    public static func parse(_ text:String,locale:Locale=Locale.current)->NormalizedDateInput? { let value=text.trimmingCharacters(in:.whitespacesAndNewlines);var formats=[("yyyy-MM-dd",Locale(identifier:"en_US_POSIX"),false),("d MMM yyyy",Locale(identifier:"en_US_POSIX"),false),("MMMM d, yyyy",Locale(identifier:"en_US_POSIX"),false)];let region=locale.region?.identifier ?? "";formats.append(region=="US" ? ("M/d/yyyy",locale,true) : ("d/M/yyyy",locale,true));for (format,loc,ambiguous) in formats{if let d=date(value,format:format,locale:loc){return .init(date:d,canonicalISO:ControlledDateRange.iso(d),interpretation:ambiguous ? "Interpreted as \(ControlledDateRange.iso(d)) using \(locale.identifier)":nil)}};let template=DateFormatter();template.locale=locale;template.dateStyle = .short;template.timeStyle = .none;template.isLenient=false;if let d=template.date(from:value){let numeric=value.filter{$0=="/" || $0=="-"}.count>=2;return .init(date:d,canonicalISO:ControlledDateRange.iso(d),interpretation:numeric ? "Interpreted as \(template.string(from:d)) using \(locale.identifier)":nil)};return nil }
    private static func date(_ value:String,format:String,locale:Locale)->Date?{let f=DateFormatter();f.calendar=Calendar(identifier:.gregorian);f.locale=locale;f.timeZone=TimeZone(secondsFromGMT:0);f.dateFormat=format;f.isLenient=false;return f.date(from:value)}
}

public struct OperationPlanIdentity:Equatable,Sendable { public let revision:UUID;public let registrationID:String?;public let timeframe:String?;public let mode:DataOperationsMode;public init(revision:UUID=UUID(),registrationID:String?,timeframe:String?,mode:DataOperationsMode){self.revision=revision;self.registrationID=registrationID;self.timeframe=timeframe;self.mode=mode} }
public struct OwnedOperationResult:Equatable,Sendable { public let planRevision:UUID;public let result:ProcessResult;public init(planRevision:UUID,result:ProcessResult){self.planRevision=planRevision;self.result=result} }

public struct UnifiedAcquisitionProvider:Equatable,Sendable,Identifiable {
    public var id:String { provider }
    public let provider:String
    public let providerSymbol:String?
    public let mappingStatus:String
    public let eligible:Bool
    public let priority:Int
    public let rejectionReason:String?
    public init(provider:String,providerSymbol:String?,mappingStatus:String,eligible:Bool,priority:Int,rejectionReason:String?=nil){self.provider=provider;self.providerSymbol=providerSymbol;self.mappingStatus=mappingStatus;self.eligible=eligible;self.priority=priority;self.rejectionReason=rejectionReason}
}

public struct UnifiedAcquisitionPlan:Equatable,Sendable {
    public let instrument:String
    public let timeframe:String
    public let assetClass:String
    public let acquisitionIntent:AcquisitionIntent
    public let canonicalEdge:String?
    public let expectedEdge:String?
    public let expectedEdgeStatus:String?
    public let missingStart:String?
    public let missingEnd:String?
    public let requestStart:String?
    public let requestEnd:String?
    public let historicalDepth:String?
    public let overlapDescription:String?
    public let providers:[UnifiedAcquisitionProvider]
    public let selectedProvider:UnifiedAcquisitionProvider?
    public let providerSetupRequired:Bool
    public let failure:String?
    public let noUpdateReason:String?

    public var isExecutable:Bool { failure == nil && noUpdateReason == nil }
    /// A compact scheduler monitor can omit a selected lane while its Estate
    /// evidence remains visible. This is an informational loading state, not
    /// a provider or data-integrity failure.
    public var isAwaitingExpectedEdge:Bool {
        failure == "Update is awaiting the Scheduler's completed market boundary."
    }
    public var fingerprint:String {
        [instrument,timeframe,assetClass,acquisitionIntent.rawValue,canonicalEdge ?? "",expectedEdge ?? "",expectedEdgeStatus ?? "",requestStart ?? "",requestEnd ?? "",selectedProvider?.provider ?? "",selectedProvider?.providerSymbol ?? "",selectedProvider?.mappingStatus ?? "",providerSetupRequired.description,failure ?? "",noUpdateReason ?? ""].joined(separator:"|")
    }
    public var operationIntent:OperationIntent? {
        guard isExecutable,let requestStart,let requestEnd else{return nil}
        switch acquisitionIntent {
        case .initial:return .acquireInitial(asset:instrument,timeframe:timeframe,from:requestStart,through:requestEnd,mode:.preserve)
        case .update:return .acquireUpdate(asset:instrument,timeframe:timeframe,from:requestStart,through:requestEnd,mode:.preserve)
        case .force:return .acquireForceHistory(asset:instrument,timeframe:timeframe,from:requestStart,through:requestEnd,mode:.preserve)
        case .custom:return .acquire(asset:instrument,timeframe:timeframe,from:requestStart,through:requestEnd,mode:.preserve)
        }
    }

    public static func build(
        instrument:String?,timeframe:String?,assetClass:String?,intent:AcquisitionIntent,
        canonicalEdge:String?,expectedEdge:String?,providers:[UnifiedAcquisitionProvider],
        reviewedRange:ControlledDateRange?,registrationActive:Bool,
        operationActive:Bool,acquisitionPaused:Bool,expectedEdgeStatus:String?=nil,
        publicationPending:Bool=false,
        planningNow:Date=Date()
    )->UnifiedAcquisitionPlan {
        let symbol=instrument?.trimmingCharacters(in:.whitespacesAndNewlines).uppercased() ?? ""
        let lane=timeframe?.trimmingCharacters(in:.whitespacesAndNewlines).uppercased() ?? ""
        let family=assetClass?.trimmingCharacters(in:.whitespacesAndNewlines).uppercased() ?? ""
        let canonicalEdge=Self.present(canonicalEdge)
        var expectedEdge=Self.present(expectedEdge)
        var expectedEdgeStatus=expectedEdgeStatus
        let ordered=providers.sorted{($0.priority,$0.provider)<($1.priority,$1.provider)}
        let selected=ordered.first(where:{$0.eligible})
        // Initial history and Update are governed by canonical evidence, not by
        // whether acquisition authority is currently available.  Custom remains
        // an explicit reviewed operator path.
        let governedIntent:AcquisitionIntent = intent == .custom || intent == .force ? intent : canonicalEdge == nil ? .initial : .update
        if (governedIntent == .initial || governedIntent == .force),expectedEdge == nil {
            expectedEdge=Self.latestClosedBoundary(timeframe:lane,assetClass:family,now:planningNow)
        }
        // A manually declared intraday lane can contain canonical evidence
        // before it is admitted to the scheduler monitor.  The monitor omits
        // that lane by design, so it cannot supply an expected edge to this
        // plan. Crypto has an approved continuous UTC calendar, however, and
        // its closed boundary is derivable without inferring a market session.
        // Keep FX and every other market dependent on their backend calendar
        // projection; only the 24x7 crypto fallback is authority-complete.
        if governedIntent == .update,expectedEdge == nil,family == "CRYPTO",canonicalEdge != nil {
            expectedEdge=Self.latestClosedBoundary(timeframe:lane,assetClass:family,now:planningNow)
            if expectedEdge != nil { expectedEdgeStatus="EXPECTED_EDGE_AVAILABLE" }
        }
        var failure:String?,noUpdateReason:String?
        var start:String?,end:String?,overlap:String?,historicalDepth:String?
        if symbol.isEmpty { failure="Selected symbol is missing." }
        else if lane.isEmpty { failure="Selected timeframe is missing." }
        else if !registrationActive { failure="Instrument registration is inactive." }
        else if operationActive { failure="Another data operation is already active." }
        // Publication is revision-transactional.  A newer fetch may stage a
        // successor revision while an earlier publication job runs; stale jobs
        // cannot finalize over it.  Do not turn a status indicator into a lane
        // admission lock.
        else if acquisitionPaused { failure="Scheduled acquisition is active." }
        switch governedIntent {
        case .update:
            if failure == nil,canonicalEdge == nil { failure="Canonical edge is missing for Update." }
            if failure == nil,expectedEdge == nil {
                switch expectedEdgeStatus {
                case "NO_NEW_COMPLETED_SESSION","MARKET_CLOSED":
                    noUpdateReason="No update required — no new completed market session."
                case "INSTRUMENT_CALENDAR_UNRESOLVED":
                    failure="Update unavailable: operational calendar unresolved."
                case "CALENDAR_UNAVAILABLE":
                    failure="Update unavailable: operational calendar unavailable."
                default:
                    failure="Update is awaiting the Scheduler's completed market boundary."
                }
            }
            if failure == nil,let canonicalEdge,let expectedEdge {
                guard let canonical=Self.parseTimestamp(canonicalEdge) else {
                    failure="Canonical edge is not a valid timestamp."
                    break
                }
                guard let expected=Self.parseTimestamp(expectedEdge) else {
                    failure="Expected edge is not a valid timestamp."
                    break
                }
                if expected == canonical { noUpdateReason="No update required — no new completed market session." }
                else if expected < canonical { failure="Expected edge precedes the canonical edge." }
                else {
                    let bounds=Self.approvedUpdateBounds(canonical:canonical,expected:expected,timeframe:lane,assetClass:family)
                    start=Self.timestamp(bounds.start);end=Self.timestamp(bounds.end);overlap=bounds.description
                }
            }
        case .initial, .force:
            guard let expectedEdge else {
                if failure == nil { failure=governedIntent == .force ? "Expected edge is missing for Force Refresh History." : "Expected edge is missing for Fetch Initial History." }
                break
            }
            guard let expected=Self.parseTimestamp(expectedEdge) else {
                if failure == nil { failure="Expected edge is not a valid timestamp." }
                break
            }
            let governed=Self.governedInitialBounds(expected:expected,timeframe:lane)
            start=governed.start;end=governed.end
            historicalDepth=governed.depth
            overlap=governedIntent == .force ? "Inclusive governed historical horizon · force refresh" : "Inclusive governed historical horizon"
        case .custom:
            guard let reviewedRange else {
                if failure == nil { failure="Reviewed date range is missing." }
                break
            }
            switch reviewedRange.validation {
            case .valid:start=reviewedRange.fromISO;end=reviewedRange.throughISO
            case .reversed:if failure == nil { failure="Start date must be on or before the through date." }
            case .futureBoundary(let maximum):if failure == nil { failure="Through date exceeds the latest completed \(lane) boundary (\(maximum))." }
            case .contractLimit(let days):if failure == nil { failure="Requested range exceeds the provider contract limit of \(days) calendar days." }
            }
        }
        let providerSetupRequired = selected == nil && ordered.contains { provider in
            provider.mappingStatus == "MAPPING_REQUIRED" && provider.rejectionReason == "NO_APPROVED_MAPPING"
        }
        if failure == nil && noUpdateReason == nil && selected == nil {
            failure = providerSetupRequired
                ? "Provider setup required."
                : ordered.compactMap(\.rejectionReason).first.map { "Provider plan is not executable: \(Self.display($0))." } ?? "Provider plan has no eligible provider."
        }
        return .init(instrument:symbol,timeframe:lane,assetClass:family,acquisitionIntent:governedIntent,canonicalEdge:canonicalEdge,expectedEdge:expectedEdge,expectedEdgeStatus:expectedEdgeStatus,missingStart:governedIntent == .update ? canonicalEdge:start,missingEnd:governedIntent == .update ? expectedEdge:end,requestStart:start,requestEnd:end,historicalDepth:historicalDepth,overlapDescription:overlap,providers:ordered,selectedProvider:selected,providerSetupRequired:providerSetupRequired,failure:failure,noUpdateReason:noUpdateReason)
    }

    private static func present(_ value:String?)->String? {
        guard let trimmed=value?.trimmingCharacters(in:.whitespacesAndNewlines),!trimmed.isEmpty else{return nil}
        return trimmed
    }

    private static func governedInitialBounds(expected:Date,timeframe:String)->(start:String,end:String,depth:String) {
        var calendar=Calendar(identifier:.gregorian);calendar.timeZone=TimeZone(secondsFromGMT:0)!
        let years=["D1":10,"H1":3,"M30":2,"M5":1][timeframe] ?? 10
        let start=calendar.date(byAdding:.year,value:-years,to:expected)!
        let depth=years == 1 ? "1 year":"\(years) years"
        if timeframe=="D1" { return (ControlledDateRange.iso(start),ControlledDateRange.iso(expected),depth) }
        return (timestamp(start),timestamp(expected),depth)
    }

    private static func latestClosedBoundary(timeframe:String,assetClass:String,now:Date)->String? {
        if timeframe == "D1" {
            return latestClosedD1Boundary(assetClass:assetClass,now:now).map(timestamp)
        }
        guard let seconds=intervalSeconds(timeframe),let market=intradayMarket(assetClass) else{return nil}
        let nowEpoch=Int(floor(now.timeIntervalSince1970))
        var candidateClose=nowEpoch - (nowEpoch % seconds)
        for _ in 0..<(14 * 86_400 / seconds) {
            let candidateOpen=candidateClose - seconds
            if market == "CRYPTO" || expectedIntradayOpen(epoch:candidateOpen,market:market) {
                return timestamp(Date(timeIntervalSince1970:TimeInterval(candidateClose)))
            }
            candidateClose -= seconds
        }
        return nil
    }

    private static func latestClosedD1Boundary(assetClass:String,now:Date)->Date? {
        guard let market=intradayMarket(assetClass) else{return nil}
        if market == "CRYPTO" {
            var calendar=Calendar(identifier:.gregorian);calendar.timeZone=TimeZone(secondsFromGMT:0)!
            return calendar.startOfDay(for:calendar.date(byAdding:.day,value:-1,to:now) ?? now)
        }
        var calendar=Calendar(identifier:.gregorian);calendar.timeZone=TimeZone(identifier:"America/New_York")!
        let localNow=now
        for offset in 0...370 {
            guard let ownerDate=calendar.date(byAdding:.day,value:-offset,to:calendar.startOfDay(for:localNow)),
                  let close=calendar.date(bySettingHour:17,minute:0,second:0,of:ownerDate),
                  close <= now,
                  expectedD1OwnerDate(ownerDate,calendar:calendar)
            else { continue }
            var utc=Calendar(identifier:.gregorian);utc.timeZone=TimeZone(secondsFromGMT:0)!
            let parts=calendar.dateComponents([.year,.month,.day],from:ownerDate)
            return utc.date(from:DateComponents(year:parts.year,month:parts.month,day:parts.day))
        }
        return nil
    }

    private static func intervalSeconds(_ timeframe:String)->Int? {
        ["H1":3_600,"M30":1_800,"M5":300][timeframe]
    }

    private static func intradayMarket(_ assetClass:String)->String? {
        if assetClass.contains("CRYPTO") { return "CRYPTO" }
        if assetClass.contains("FX") || assetClass.contains("FOREX") { return "FX" }
        if assetClass.contains("METAL") { return "METALS" }
        return nil
    }

    private static func expectedIntradayOpen(epoch:Int,market:String)->Bool {
        var calendar=Calendar(identifier:.gregorian);calendar.timeZone=TimeZone(identifier:"America/New_York")!
        let date=Date(timeIntervalSince1970:TimeInterval(epoch))
        let weekday=calendar.component(.weekday,from:date),hour=calendar.component(.hour,from:date)
        return weekday>=2 && weekday<=5 || weekday==6 && hour<17 || weekday==1 && hour>=17
    }

    private static func expectedD1OwnerDate(_ date:Date,calendar:Calendar)->Bool {
        let weekday=calendar.component(.weekday,from:date)
        guard weekday>=2 && weekday<=6 else{return false}
        let month=calendar.component(.month,from:date),day=calendar.component(.day,from:date)
        return !((month == 1 && day == 1) || (month == 12 && day == 25))
    }

    private static func approvedUpdateBounds(canonical:Date,expected:Date,timeframe:String,assetClass:String)->(start:Date,end:Date,description:String) {
        if timeframe == "D1" {
            let count=5
            return (walkBack(from:canonical,interval:86_400,count:count,assetClass:assetClass),expected,"5 expected trading days")
        }
        let durations:[String:TimeInterval]=["M5":300,"M30":1_800,"H1":3_600]
        let overlaps:[String:Int]=["M5":576,"M30":96,"H1":48]
        let seconds=durations[timeframe] ?? 0
        let count=overlaps[timeframe] ?? 0
        guard seconds>0,count>0 else{return(canonical,expected,"No additional overlap")}
        return (walkBack(from:canonical,interval:seconds,count:count,assetClass:assetClass),expected,"\(count) \(timeframe) intervals (2 trading days)")
    }
    private static func walkBack(from edge:Date,interval:TimeInterval,count:Int,assetClass:String)->Date {
        var cursor=edge,accepted=0
        while accepted<count {
            cursor=cursor.addingTimeInterval(-interval)
            if assetClass=="CRYPTO" || expectedFXBoundary(cursor) { accepted += 1 }
        }
        return cursor
    }
    private static func expectedFXBoundary(_ date:Date)->Bool {
        var calendar=Calendar(identifier:.gregorian);calendar.timeZone=TimeZone(identifier:"America/New_York")!
        let weekday=calendar.component(.weekday,from:date),hour=calendar.component(.hour,from:date)
        return weekday>=2 && weekday<=5 || weekday==6 && hour<=17 || weekday==1 && hour>=17
    }
    private static func parseTimestamp(_ value:String)->Date? {
        let formatter=ISO8601DateFormatter();formatter.formatOptions=[.withInternetDateTime,.withFractionalSeconds]
        return formatter.date(from:value) ?? ISO8601DateFormatter().date(from:value)
    }
    private static func timestamp(_ date:Date)->String {
        let formatter=ISO8601DateFormatter();formatter.timeZone=TimeZone(secondsFromGMT:0);formatter.formatOptions=[.withInternetDateTime]
        return formatter.string(from:date)
    }
    private static func display(_ value:String)->String { value.replacingOccurrences(of:"_",with:" ").lowercased().capitalized }
}

public struct ReviewedDataOperationPlan:Identifiable,Equatable,Sendable {
    public let id:UUID;public let mode:DataOperationsMode;public let instrument:String;public let timeframe:String
    public let filePath:String?;public let fileChecksum:String?;public let fileSelectionID:UUID?
    public let from:String?;public let through:String?;public let sourceTimezone:String?;public let d1DateFormat:String;public let conflict:ConflictMode;public let acquisitionIntent:AcquisitionIntent
    public init(id:UUID,mode:DataOperationsMode,instrument:String,timeframe:String,filePath:String?=nil,fileChecksum:String?=nil,fileSelectionID:UUID?=nil,from:String?=nil,through:String?=nil,sourceTimezone:String?=nil,d1DateFormat:String="auto",conflict:ConflictMode,acquisitionIntent:AcquisitionIntent = .custom){self.id=id;self.mode=mode;self.instrument=instrument;self.timeframe=timeframe;self.filePath=filePath;self.fileChecksum=fileChecksum;self.fileSelectionID=fileSelectionID;self.from=from;self.through=through;self.sourceTimezone=sourceTimezone;self.d1DateFormat=d1DateFormat;self.conflict=conflict;self.acquisitionIntent=acquisitionIntent}
    public var intent:OperationIntent? { switch mode { case .importFile: guard let filePath else{return nil};return .importCSV(file:filePath,symbol:instrument,timeframe:timeframe,sourceTimezone:sourceTimezone,d1DateFormat:d1DateFormat,mode:conflict);case .fetch:guard let through else{return nil};switch acquisitionIntent{case .initial:guard let from else{return nil};return .acquireInitial(asset:instrument,timeframe:timeframe,from:from,through:through,mode:conflict);case .update:guard let from else{return nil};return .acquireUpdate(asset:instrument,timeframe:timeframe,from:from,through:through,mode:conflict);case .force:guard let from else{return nil};return .acquireForceHistory(asset:instrument,timeframe:timeframe,from:from,through:through,mode:conflict);case .custom:guard let from else{return nil};return .acquire(asset:instrument,timeframe:timeframe,from:from,through:through,mode:conflict)};default:return nil } }
    public func matches(mode:DataOperationsMode,instrument:String?,timeframe:String?,fileChecksum:String?)->Bool { self.mode==mode && self.instrument==instrument && self.timeframe==timeframe && (mode != .importFile || self.fileChecksum==fileChecksum) }
}
