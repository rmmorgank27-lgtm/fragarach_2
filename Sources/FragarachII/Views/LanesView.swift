import OperationsCore
import SwiftUI

struct LanesView:View {
    @EnvironmentObject var store:ConsoleStore; @State private var search=""; @State private var timeframe="All"
    var lanes:[LaneRecord] { (store.snapshot?.lanes ?? []).filter{(search.isEmpty || $0.asset.localizedCaseInsensitiveContains(search)) && (timeframe=="All" || $0.timeframe==timeframe)}.sorted{$0.id<$1.id} }
    var selected:LaneRecord? { lanes.first{$0.id==store.selectedLaneID} }
    var body:some View { HSplitView {
        VStack(alignment:.leading){HStack{Text("Lanes").font(.title);Spacer();Picker("Timeframe",selection:$timeframe){Text("All").tag("All");Text("D1").tag("D1")}.frame(width:130)}
            List(lanes,selection:$store.selectedLaneID){lane in VStack(alignment:.leading,spacing:3){HStack{Text(lane.asset).font(.headline);Text(lane.timeframe).foregroundStyle(.secondary);Spacer();Text(Format.utc(lane.highWatermark)).font(.caption)};if let v=lane.validation{Text("Through \(v.throughDate) · missing \(v.missingExpectedSessionCount) · outside \(v.outsideExpectedSessionCount)").font(.caption).foregroundStyle(.secondary)}else{Text("Not yet validated").font(.caption).foregroundStyle(.secondary)}}.tag(lane.id)}.searchable(text:$search,prompt:"Search asset")
            Text("Last read: \(store.snapshot?.readAt.formatted() ?? "Never")").font(.caption).foregroundStyle(.secondary)
        }.padding().frame(minWidth:430)
        ScrollView { if let lane=selected { LaneDetail(lane:lane) } else if let error=store.readError { ContentUnavailableView("Read failed",systemImage:"exclamationmark.triangle",description:Text("\(store.databasePath)\n\(error)")) } else { ContentUnavailableView("No lanes",systemImage:"tray",description:Text("The selected database contains no registered lane state.")) } }.frame(minWidth:440)
    }}
}

struct LaneDetail: View {
    let lane: LaneRecord
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("\(lane.asset) \(lane.timeframe)").font(.largeTitle)
            Text("Candidate Authority").font(.headline).foregroundStyle(.secondary)
            GroupBox("Canonical evidence") {
                Facts([("Bars", Format.count(lane.barCount)), ("Earliest", Format.utc(lane.earliestBar)), ("Latest", Format.utc(lane.latestBar)), ("High watermark", Format.utc(lane.highWatermark)), ("Lane version", "\(lane.stateVersion)"), ("Last ingest", lane.lastIngestRunID ?? "—"), ("Updated", lane.updatedAt)])
            }
            if let v = lane.validation {
                GroupBox("Persisted validation") {
                    Facts([("Through", v.throughDate), ("Latest expected", v.latestExpectedSession ?? "—"), ("Latest expected present", v.latestExpectedSessionPresent ? "Yes" : "No"), ("Expected", "\(v.expectedSessionCount)"), ("Present", "\(v.presentExpectedSessionCount)"), ("Missing", "\(v.missingExpectedSessionCount)"), ("Outside session", "\(v.outsideExpectedSessionCount)"), ("Empty weeks", "\(v.emptyWeekCount)"), ("Empty months", "\(v.emptyMonthCount)"), ("Material gaps", "\(v.materialGapCount)"), ("Non-material gaps", "\(v.nonMaterialGapCount)"), ("Calendar", "\(v.calendarID) v\(v.calendarVersion)"), ("Gap doctrine", "\(v.gapDoctrineID) v\(v.gapDoctrineVersion)"), ("Observed", v.validationObservedAt), ("Result checksum", v.resultChecksum)])
                }
            } else {
                ContentUnavailableView("Not yet validated", systemImage: "calendar.badge.exclamationmark")
            }
        }.padding()
    }
}

struct Facts:View { let rows:[(String,String)];init(_ rows:[(String,String)]){self.rows=rows};var body:some View{Grid(alignment:.leading,horizontalSpacing:20,verticalSpacing:7){ForEach(Array(rows.enumerated()),id:\.offset){_,row in GridRow{Text(row.0).foregroundStyle(.secondary);Text(row.1).textSelection(.enabled).font(row.0.lowercased().contains("checksum") || row.0.lowercased().contains("ingest") ? .caption.monospaced():.body)}}}.padding(.vertical,6)} }
