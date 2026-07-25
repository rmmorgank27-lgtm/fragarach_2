import OperationsCore
import SwiftUI

struct TruthDetailView:View {
    @EnvironmentObject var store:ConsoleStore
    let lane:EstateTruthLane
    let commissioning:CommissionedLaneState?
    @State private var showPriceHistory = false
    @State private var historyOverview: PriceHistoryOverview?
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            HStack(alignment:.firstTextBaseline){VStack(alignment:.leading){Text(lane.symbol).font(.largeTitle);Text(lane.timeframe).foregroundStyle(.secondary);Text(lane.operationalStateLabel ?? lane.truthState.authorityState).font(.headline)};Spacer();VStack(alignment:.trailing){Text("\(lane.truthState.truthScore)").font(.system(size:36,weight:.semibold,design:.rounded));Label(lane.overallOperationalState ?? lane.truthState.authorityState,systemImage:"circle.fill").foregroundStyle(TruthPresentation.color(lane.truthState.authorityState))}}
            HStack{
                Button("Manage Data"){store.navigate(.acquire,asset:lane.symbol)}.buttonStyle(.borderedProminent)
                Button("Price History"){showPriceHistory=true}
                if lane.timeframe == "M5", lane.freshnessDimension?.label != "Current" {
                    Button("Queue M5 update now",systemImage:"play.fill"){Task{await store.queueLaneUpdate(lane.id)}}
                        .buttonStyle(.borderedProminent)
                        .help("Queues only this M5 lane for the Scheduler; it does not block the estate refresh.")
                }
            }
            GroupBox("At a glance") { Facts(glanceFacts) }
            GroupBox("Estate membership") { Facts([
                ("Registered", registrationText),
                ("Commissioning",EstateLanePresentation.commissioning(commissioning?.commissioned == true)),
                ("Automation",EstateLanePresentation.automation(commissioning?.commissioned == true)),
                ("CAODT",compactDate(lane.latestCanonicalObservation)),
            ]) }
            GroupBox("Operational health") { Facts(operationalFacts) }
            DisclosureGroup("Detailed health evidence") {
                VStack(alignment:.leading,spacing:14) {
                    GroupBox("Coverage") { Facts([("Expected range",dateRange(lane.truthState.coverage.expectedRange.start,lane.truthState.coverage.expectedRange.end)),("Available range",dateRange(lane.truthState.coverage.availableRange.start,lane.truthState.coverage.availableRange.end)),("Coverage score",TruthPresentation.value(lane.truthState.coverageScore)),("Freshness score",TruthPresentation.value(lane.truthState.freshnessScore))]) }
                    GroupBox("Provider") { Facts([("Provider",lane.providerSummary.provider ?? "Provider Mapping Required"),("Confidence",lane.providerSummary.providerConfidence),("Provider freshness",lane.providerSummary.providerFreshness),("Entitlement",lane.providerSummary.entitlement)]) }
                    GroupBox("Gap classification") { Facts([("Classification",lane.gapSummary.gapClassification),("Impact",lane.gapSummary.operationalImpact),("Current",TruthPresentation.value(lane.gapSummary.currentGapCount)),("Recent",TruthPresentation.value(lane.gapSummary.recentGapCount)),("Historical",TruthPresentation.value(lane.gapSummary.historicalGapCount))]) }
                    TruthComponentsView(state:lane.truthState)
                    GroupBox("Scoring notes") { VStack(alignment:.leading,spacing:8){Text(lane.truthState.explanation.method).textSelection(.enabled);if let weights=lane.truthState.explanation.weights{Text(weights.sorted{$0.key<$1.key}.map{"\($0.key)=\($0.value)%"}.joined(separator:", ")).font(.caption.monospaced()).textSelection(.enabled)};if lane.truthState.explanation.limitations.isEmpty{Text("No recorded limitations").foregroundStyle(.secondary)}else{ForEach(lane.truthState.explanation.limitations,id:\.self){Text($0).font(.caption.monospaced()).textSelection(.enabled)}}}.frame(maxWidth:.infinity,alignment:.leading).padding(.vertical,6) }
                }
                .padding(.top,8)
            }
        }
        .padding()
        .sheet(isPresented:$showPriceHistory) { PriceHistoryView(lane:lane).environmentObject(store) }
        .task(id:lane.id) { historyOverview = try? await store.loadPriceHistoryOverview(symbol:lane.symbol,timeframe:lane.timeframe) }
    }

    private var glanceFacts:[(String,String)] {
        let rows=historyOverview?.totalBarCount ?? lane.truthState.coverage.rowCount
        guard rows > 0 else {
            return [("Available data","No governed data yet"),("Bars","0"),("Gaps","Not measured — no governed data")]
        }
        let coverage=historyOverview.map { "\(compactTimestamp($0.earliestGovernedObservation)) — \(compactTimestamp($0.latestGovernedObservation))" }
            ?? dateRange(lane.truthState.coverage.availableRange.start,lane.truthState.coverage.availableRange.end)
        let gaps: String
        if let historyOverview {
            let largest=historyOverview.continuity.largestGap.map { duration($0.gapDuration) } ?? "None"
            gaps="\(historyOverview.continuity.gapCount) total · largest \(largest)"
        } else if let total=lane.gapSummary.totalGapCount {
            gaps="\(total) total · reading largest gap…"
        } else { gaps="Reading continuity…" }
        return [("Available data",coverage),("Bars",rows.formatted()),("Gaps",gaps)]
    }

    private var operationalFacts:[(String,String)] {
        let lag=lane.freshnessDimension?.lag
        let lagText=lag.map{"\($0.count ?? 0) \($0.unit ?? "boundaries")"} ?? "—"
        let providers=lane.acquisitionDimension?.eligibleProviders.joined(separator:", ") ?? "None"
        let acquisition=lane.operationalStateLabel?.localizedCaseInsensitiveContains("in progress") == true
            ? "Initial history in progress"
            : (lane.acquisitionDimension?.state ?? "Not measured").displayStatus
        return [("Overall",lane.overallOperationalState ?? lane.truthState.authorityState),("Freshness",lane.freshnessDimension?.label ?? "Not measured"),("Integrity",lane.evidenceIntegrity?.state ?? lane.truthState.validationState),("Lag",lagText),("Acquisition",acquisition),("Eligible providers",providers)]
    }
    private var providerEligible:Bool{lane.acquisitionDimension?.eligibleProviders.isEmpty == false}
    private var registrationText:String {
        guard let value=store.snapshot?.registrations.filter({$0.asset==lane.symbol}).map(\.registeredAt).min(),let date=Self.isoDate(value) else { return "Registered · date unavailable" }
        return "\(Self.dateFormatter.string(from:date)) · \(estateAge(since:date))"
    }
    private func dateRange(_ start:String?,_ end:String?)->String { "\(compactDate(start)) — \(compactDate(end))" }
    private func compactDate(_ value:String?)->String { guard let value,!value.isEmpty else{return "No governed data"};return String(value.prefix(10)) }
    private func compactTimestamp(_ value:Int64?)->String { guard let value else{return "No governed data"};return Self.dateFormatter.string(from:Date(timeIntervalSince1970:TimeInterval(value))) }
    private func duration(_ seconds:Int64)->String { if seconds % 86_400 == 0{return "\(seconds / 86_400)d"};if seconds % 3_600 == 0{return "\(seconds / 3_600)h"};if seconds % 60 == 0{return "\(seconds / 60)m"};return "\(seconds)s" }
    private func estateAge(since date:Date)->String { let parts=Calendar.current.dateComponents([.year,.month,.day],from:date,to:Date());if let years=parts.year,years>0{return "\(years)y in estate"};if let months=parts.month,months>0{return "\(months)mo in estate"};let days=max(0,parts.day ?? 0);return days == 0 ? "registered today":"\(days)d in estate" }
    private static func isoDate(_ value:String)->Date? { let fractional=ISO8601DateFormatter();fractional.formatOptions=[.withInternetDateTime,.withFractionalSeconds];return fractional.date(from:value) ?? ISO8601DateFormatter().date(from:value) }
    private static let dateFormatter:DateFormatter = { let formatter=DateFormatter();formatter.locale=Locale(identifier:"en_US_POSIX");formatter.timeZone=TimeZone(secondsFromGMT:0);formatter.dateFormat="d MMM yyyy";return formatter }()
}

private struct TruthComponentsView:View {
    let state:TruthState
    var body:some View { GroupBox("Truth Components") { VStack(spacing:0){ForEach(TruthPresentation.componentOrder,id:\.self){name in if let component=state.explanation.components[name]{HStack(alignment:.firstTextBaseline){Text(name.replacingOccurrences(of:"_",with:" ").capitalized).frame(width:120,alignment:.leading);Text(TruthPresentation.value(component.score)).font(.headline.monospacedDigit()).frame(width:80,alignment:.trailing);Text(component.basis).font(.caption).foregroundStyle(.secondary).textSelection(.enabled);Spacer()}.padding(.vertical,7);Divider()}}}.padding(.vertical,2) } }
}
