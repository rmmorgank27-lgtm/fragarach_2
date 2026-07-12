import OperationsCore
import SwiftUI

struct TruthEstateSummaryView:View {
    let summary:EstateSummary
    var body:some View {
        VStack(alignment:.leading,spacing:12) {
            HStack(spacing:10) {
                SummaryMetric(title:"Overall Truth",value:TruthPresentation.value(summary.overallTruthScore),state:summary.overallAuthorityState)
                SummaryMetric(title:"Authority",value:summary.overallAuthorityState,state:summary.overallAuthorityState)
                SummaryMetric(title:"CAODT",value:TruthPresentation.text(summary.overallCAODT))
                SummaryMetric(title:"Symbols",value:"\(summary.totalSymbols)")
            }
            HStack(spacing:10) {
                SummaryMetric(title:"Healthy",value:"\(summary.greenCount)",state:"GREEN")
                SummaryMetric(title:"Attention",value:"\(summary.amberCount)",state:"AMBER")
                SummaryMetric(title:"Critical",value:"\(summary.redCount)",state:"RED")
                SummaryMetric(title:"Generated",value:TruthPresentation.text(summary.generatedAt))
            }
            GroupBox("Latest operational events") {
                Facts([("Validation","Not measured"),("Provider update","Not measured"),("Snapshot","Placeholder"),("Backup","Placeholder")])
            }
        }
    }
}

private struct SummaryMetric:View {
    let title:String;let value:String;var state:String?=nil
    var body:some View {
        VStack(alignment:.leading,spacing:5){Text(title).font(.caption).foregroundStyle(.secondary);HStack{if let state{Circle().fill(TruthPresentation.color(state)).frame(width:8,height:8)};Text(value).font(.headline).lineLimit(1)}}
            .padding(12).frame(maxWidth:.infinity,alignment:.leading).background(.regularMaterial,in:RoundedRectangle(cornerRadius:10))
    }
}
