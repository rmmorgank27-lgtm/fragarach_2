import OperationsCore
import SwiftUI

struct TruthMatrixView:View {
    let lanes:[EstateTruthLane]
    let commissioning:[CommissionedLaneState]
    let scheduler:SchedulerSnapshot?
    @Binding var selection:String?
    var queueUpdate:((String)->Void)?=nil
    private let canonicalTimeframes=["D1","H1","M30","M5"]
    private var symbols:[String] { Array(Set(lanes.map(\.symbol)+commissioning.map(\.symbol))).sorted() }
    private var timeframes:[String] {
        let required=Set(commissioning.filter(\.required).map(\.timeframe))
        return canonicalTimeframes.filter(required.contains)
    }
    private func lane(_ symbol:String,_ timeframe:String)->EstateTruthLane? { lanes.first{$0.symbol==symbol && $0.timeframe==timeframe} }
    private func state(_ symbol:String,_ timeframe:String)->CommissionedLaneState? { commissioning.first{$0.symbol==symbol && $0.timeframe==timeframe} }
    private func operationalState(_ symbol:String,_ timeframe:String)->String {
        let commissioning=state(symbol,timeframe)
        if commissioning?.commissioned != true{return "Not Commissioned"}
        let id="\(symbol):\(timeframe)"
        let active=scheduler?.activeActivity
        let queued=scheduler?.acquisitionQueue.first(where:{$0.lane==id})
        let schedulerLane=scheduler?.lanes.first(where:{$0.id==id})
        let resolved=SchedulerLifecycleStateResolver.resolve(
            activeTrace:active?.symbol==symbol && active?.timeframe==timeframe && active?.traceID != nil,
            queueExists:queued != nil,queueState:queued?.operationalState,
            queueHasTrace:queued?.traceID != nil,queueHasWorker:queued?.activeWorkerID != nil,
            stopReason:queued?.stopReason,nextAttempt:queued?.nextAttempt,
            schedulerState:schedulerLane?.schedulerState,
            fallback:commissioning?.operationalState ?? "Behind"
        )
        let providerEligible=lane(symbol,timeframe)?.acquisitionDimension?.eligibleProviders.isEmpty == false
        return EstateLanePresentation.operationalState(
            commissioned:true,resolvedState:resolved,providerEligible:providerEligible
        )
    }
    var body:some View {
        GroupBox("Truth Matrix") {
            if lanes.isEmpty { ContentUnavailableView("No matching authority",systemImage:"magnifyingglass") }
            else { ScrollView([.horizontal,.vertical]) {
                Grid(alignment:.leading,horizontalSpacing:8,verticalSpacing:8) {
                    GridRow { Text("Symbol").font(.caption).foregroundStyle(.secondary);ForEach(timeframes,id:\.self){Text($0).font(.caption).foregroundStyle(.secondary).frame(width:108)} }
                    Divider().gridCellUnsizedAxes(.horizontal)
                    ForEach(symbols,id:\.self){symbol in GridRow { Text(symbol).font(.headline).frame(minWidth:120,alignment:.leading);ForEach(timeframes,id:\.self){timeframe in
                        let commissioned=state(symbol,timeframe)
                        if let lane=lane(symbol,timeframe) {
                            TruthMatrixCell(lane:lane,operationalState:operationalState(symbol,timeframe),isSelected:selection==lane.id,queueUpdate:queueUpdate){selection=lane.id}
                        } else {
                            MissingCommissionCell(state:commissioned?.operationalState ?? "Not Commissioned")
                        }
                    } }}
                }.padding(8)
            }}
        }
    }
}

private struct TruthMatrixCell:View {
    let lane:EstateTruthLane;let operationalState:String;let isSelected:Bool;let queueUpdate:((String)->Void)?;let action:()->Void
    var body:some View { Button(action:action){VStack(spacing:3){Text("\(lane.truthState.truthScore)").font(.headline.monospacedDigit());Text(operationalState.uppercased()).font(.caption2).lineLimit(1)}.foregroundStyle(.primary).frame(width:108,height:48).background(TruthPresentation.color(operationalState).opacity(isSelected ? 0.32:0.14),in:RoundedRectangle(cornerRadius:7)).overlay{RoundedRectangle(cornerRadius:7).stroke(isSelected ? Color.accentColor:.clear,lineWidth:2)}}.buttonStyle(.plain).contextMenu { if lane.timeframe == "M5", operationalState == "Behind" { Button("Queue M5 update now",systemImage:"play.fill"){queueUpdate?(lane.id)} } }.accessibilityLabel("\(lane.symbol) \(lane.timeframe), score \(lane.truthState.truthScore), \(operationalState)") }
}

private struct MissingCommissionCell:View {
    let state:String
    var body:some View {
        Text(state.uppercased())
            .font(.caption2.weight(.semibold)).multilineTextAlignment(.center).lineLimit(2)
            .foregroundStyle(TruthPresentation.color(state))
            .frame(width:108,height:48)
            .background(TruthPresentation.color(state).opacity(0.12),in:RoundedRectangle(cornerRadius:7))
            .accessibilityLabel(state)
    }
}
