import OperationsCore
import SwiftUI

struct TruthEstateSummaryView:View {
    let summary:EstateSummary
    var scheduler:SchedulerSnapshot?=nil
    var onSelect:((String)->Void)?=nil
    var body:some View {
        VStack(alignment:.leading,spacing:12) {
            HStack(spacing:10) {
                SummaryMetric(title:"Overall Truth",value:TruthPresentation.value(summary.overallTruthScore),state:summary.overallAuthorityState)
                SummaryMetric(title:"Authority",value:summary.overallAuthorityState,state:summary.overallAuthorityState)
                SummaryMetric(title:"CAODT",value:TruthPresentation.text(summary.latestCanonicalObservation))
                SummaryMetric(title:"Symbols",value:"\(summary.totalSymbols)")
            }
            HStack(spacing:10) {
                SummaryMetric(title:"Required lanes",value:"\(summary.requiredLanes)",action:{onSelect?("Required lanes")})
                SummaryMetric(title:"Commissioned lanes",value:"\(summary.commissionedLanes)",action:{onSelect?("Commissioned lanes")})
                SummaryMetric(title:"Operational lanes",value:"\(summary.operationalLanes)",action:{onSelect?("Operational lanes")})
                SummaryMetric(title:"Missing commissions",value:"\(summary.missingCommissions)",state:summary.missingCommissions == 0 ? "GREEN":"RED",action:{onSelect?("Missing commissions")})
                SummaryMetric(title:"Not enabled",value:"\(summary.notEnabledLanes ?? 0)",action:{onSelect?("Not enabled")})
                SummaryMetric(title:"Coverage",value:summary.operationalCoveragePercent.map{"\($0)%"} ?? "Not measured",action:{onSelect?("Coverage")})
            }
            HStack(spacing:10) {
                SummaryMetric(title:"Healthy",value:"\(summary.greenCount)",state:"GREEN",action:{onSelect?("Healthy")})
                SummaryMetric(title:"Attention",value:"\(summary.amberCount)",state:"AMBER",action:{onSelect?("Attention")})
                SummaryMetric(title:"Critical",value:"\(summary.redCount)",state:"RED",action:{onSelect?("Critical")})
                SummaryMetric(title:"Generated",value:TruthPresentation.text(summary.generatedAt))
            }
            SchedulerRecentEventsView(snapshot:scheduler)
        }
    }
}

struct SchedulerRecentEventsView:View {
    let snapshot:SchedulerSnapshot?
    var body:some View {
        GroupBox("Latest scheduler activity") {
            if let events=snapshot?.events,!events.isEmpty {
                VStack(alignment:.leading,spacing:7) {
                    ForEach(events.prefix(4)) { event in
                        HStack(alignment:.firstTextBaseline,spacing:8) {
                            Circle().fill(event.result == "SUCCESS" ? Color.green:Color.red).frame(width:7,height:7)
                            Text("\(event.symbol) · \(event.timeframe)").fontWeight(.semibold)
                            Text(event.result.replacingOccurrences(of:"_",with:" ").capitalized).foregroundStyle(event.result == "SUCCESS" ? .green:.red)
                            Spacer()
                            Text(SchedulerFormatting.timestamp(event.at)).font(.caption.monospaced()).foregroundStyle(.secondary)
                        }
                        Text("\(event.observations) observation\(event.observations == 1 ? "":"s") · \(SchedulerFormatting.duration(event.durationSeconds))\(event.reason.map { " · \($0)" } ?? "")")
                            .font(.caption).foregroundStyle(.secondary).padding(.leading,15)
                    }
                }.frame(maxWidth:.infinity,alignment:.leading)
            } else {
                Text("No scheduler activity has been recorded in this monitor snapshot.").foregroundStyle(.secondary)
            }
        }
    }
}

private struct SummaryMetric:View {
    let title:String;let value:String;var state:String?=nil;var action:(()->Void)?=nil
    var body:some View {
        let card=VStack(alignment:.leading,spacing:5){Text(title).font(.caption).foregroundStyle(.secondary);HStack{if let state{Circle().fill(TruthPresentation.color(state)).frame(width:8,height:8)};Text(value).font(.headline).lineLimit(1)}}
            .padding(12).frame(maxWidth:.infinity,alignment:.leading).background(.regularMaterial,in:RoundedRectangle(cornerRadius:10))
        if let action { Button(action:action){card}.buttonStyle(.plain).help("Show the lanes behind this scorecard") } else { card }
    }
}
