import OperationsCore
import SwiftUI

struct TruthMatrixView:View {
    let lanes:[EstateTruthLane]
    @Binding var selection:String?
    private var symbols:[String] { Array(Set(lanes.map(\.symbol))).sorted() }
    private var timeframes:[String] { Array(Set(lanes.map(\.timeframe))).sorted() }
    private func lane(_ symbol:String,_ timeframe:String)->EstateTruthLane? { lanes.first{$0.symbol==symbol && $0.timeframe==timeframe} }
    var body:some View {
        GroupBox("Truth Matrix") {
            if lanes.isEmpty { ContentUnavailableView("No matching authority",systemImage:"magnifyingglass") }
            else { ScrollView([.horizontal,.vertical]) {
                Grid(alignment:.leading,horizontalSpacing:8,verticalSpacing:8) {
                    GridRow { Text("Symbol").font(.caption).foregroundStyle(.secondary);ForEach(timeframes,id:\.self){Text($0).font(.caption).foregroundStyle(.secondary).frame(width:76)} }
                    Divider().gridCellUnsizedAxes(.horizontal)
                    ForEach(symbols,id:\.self){symbol in GridRow { Text(symbol).font(.headline).frame(minWidth:120,alignment:.leading);ForEach(timeframes,id:\.self){timeframe in if let lane=lane(symbol,timeframe){TruthMatrixCell(lane:lane,isSelected:selection==lane.id){selection=lane.id}}else{Text("—").foregroundStyle(.tertiary).frame(width:76,height:44)}} }}
                }.padding(8)
            }}
        }
    }
}

private struct TruthMatrixCell:View {
    let lane:EstateTruthLane;let isSelected:Bool;let action:()->Void
    var body:some View { Button(action:action){VStack(spacing:3){Text("\(lane.truthState.truthScore)").font(.headline.monospacedDigit());Text(lane.truthState.authorityState).font(.caption2)}.foregroundStyle(.primary).frame(width:76,height:44).background(TruthPresentation.color(lane.truthState.authorityState).opacity(isSelected ? 0.32:0.14),in:RoundedRectangle(cornerRadius:7)).overlay{RoundedRectangle(cornerRadius:7).stroke(isSelected ? Color.accentColor:.clear,lineWidth:2)}}.buttonStyle(.plain).accessibilityLabel("\(lane.symbol) \(lane.timeframe), score \(lane.truthState.truthScore), \(lane.truthState.authorityState)") }
}
