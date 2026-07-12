import Foundation

public enum DateRangeValidation:Equatable,Sendable { case valid;case reversed;case futureBoundary(maximum:String);case contractLimit(maximumDays:Int) }
public struct ControlledDateRange:Equatable,Sendable {
    public var from:Date;public var through:Date;public let completedBoundary:Date;public let maximumCalendarDays:Int
    public init(from:Date,through:Date,completedBoundary:Date,maximumCalendarDays:Int=5000){self.from=from;self.through=through;self.completedBoundary=completedBoundary;self.maximumCalendarDays=maximumCalendarDays}
    public var fromISO:String{Self.iso(from)};public var throughISO:String{Self.iso(through)}
    public var validation:DateRangeValidation { let cal=Self.calendar;let start=cal.startOfDay(for:from),end=cal.startOfDay(for:through),boundary=cal.startOfDay(for:completedBoundary);if start>end{return .reversed};if end>boundary{return .futureBoundary(maximum:Self.iso(boundary))};let days=cal.dateComponents([.day],from:start,to:end).day!+1;if days>maximumCalendarDays{return .contractLimit(maximumDays:maximumCalendarDays)};return .valid }
    public static func iso(_ date:Date)->String{let parts=Calendar.current.dateComponents([.year,.month,.day],from:date);return String(format:"%04d-%02d-%02d",parts.year!,parts.month!,parts.day!)}
    private static var calendar:Calendar{var c=Calendar(identifier:.gregorian);c.timeZone=TimeZone(secondsFromGMT:0)!;return c}
}

public struct NormalizedDateInput:Equatable,Sendable { public let date:Date;public let canonicalISO:String;public let interpretation:String? }
public enum ControlledDateParser {
    public static func parse(_ text:String,locale:Locale=Locale.current)->NormalizedDateInput? { let value=text.trimmingCharacters(in:.whitespacesAndNewlines);var formats=[("yyyy-MM-dd",Locale(identifier:"en_US_POSIX"),false),("d MMM yyyy",Locale(identifier:"en_US_POSIX"),false),("MMMM d, yyyy",Locale(identifier:"en_US_POSIX"),false)];let region=locale.region?.identifier ?? "";formats.append(region=="US" ? ("M/d/yyyy",locale,true) : ("d/M/yyyy",locale,true));for (format,loc,ambiguous) in formats{if let d=date(value,format:format,locale:loc){return .init(date:d,canonicalISO:ControlledDateRange.iso(d),interpretation:ambiguous ? "Interpreted as \(ControlledDateRange.iso(d)) using \(locale.identifier)":nil)}};let template=DateFormatter();template.locale=locale;template.dateStyle = .short;template.timeStyle = .none;template.isLenient=false;if let d=template.date(from:value){let numeric=value.filter{$0=="/" || $0=="-"}.count>=2;return .init(date:d,canonicalISO:ControlledDateRange.iso(d),interpretation:numeric ? "Interpreted as \(template.string(from:d)) using \(locale.identifier)":nil)};return nil }
    private static func date(_ value:String,format:String,locale:Locale)->Date?{let f=DateFormatter();f.calendar=Calendar(identifier:.gregorian);f.locale=locale;f.timeZone=TimeZone(secondsFromGMT:0);f.dateFormat=format;f.isLenient=false;return f.date(from:value)}
}

public struct OperationPlanIdentity:Equatable,Sendable { public let revision:UUID;public let registrationID:String?;public let timeframe:String?;public let mode:DataOperationsMode;public init(revision:UUID=UUID(),registrationID:String?,timeframe:String?,mode:DataOperationsMode){self.revision=revision;self.registrationID=registrationID;self.timeframe=timeframe;self.mode=mode} }
public struct OwnedOperationResult:Equatable,Sendable { public let planRevision:UUID;public let result:ProcessResult;public init(planRevision:UUID,result:ProcessResult){self.planRevision=planRevision;self.result=result} }
