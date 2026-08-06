import SwiftUI

enum LiteLaneOwnershipState:String {
    case studioOnly="STUDIO ONLY"
    case requested="REQUESTED"
    case incoming="INCOMING"
    case local="MACBOOK CACHE"
    case paused="PAUSED"
    case failed="FAILED"

    var color:Color {
        switch self {
        case .studioOnly:.indigo
        case .requested:.orange
        case .incoming:.cyan
        case .local:.green
        case .paused:.gray
        case .failed:.red
        }
    }

    var ownership:String {
        switch self {
        case .studioOnly:"On Studio"
        case .requested:"Requested here"
        case .incoming:"Studio → MacBook"
        case .local:"Cached on MacBook"
        case .paused:"Local lane paused"
        case .failed:"Needs attention"
        }
    }
}

struct LiteLaneCellVisual {
    let state:LiteLaneOwnershipState
    let progress:Double
}

struct LiteLaneStatusCell:View {
    let lane:LiteLane
    let visual:LiteLaneCellVisual
    let action:()->Void

    var body:some View {
        Button(action:action) {
            ZStack(alignment:.bottom) {
                RoundedRectangle(cornerRadius:8).fill(visual.state.color.opacity(0.07))
                Rectangle()
                    .fill(visual.state.color.opacity(0.24))
                    .frame(height:58 * min(max(visual.progress,0),1))
                    .clipShape(RoundedRectangle(cornerRadius:8))
                VStack(spacing:2) {
                    Text(lane.caodt.map(short) ?? "—").font(.caption2.bold().monospacedDigit()).lineLimit(1)
                    Text(visual.state.rawValue).font(.caption2.bold()).lineLimit(1).minimumScaleFactor(0.7)
                    Text(visual.state.ownership).font(.system(size:9)).foregroundStyle(.secondary).lineLimit(1)
                }.padding(.horizontal,4)
            }
            .frame(width:118,height:58)
            .overlay {RoundedRectangle(cornerRadius:8).stroke(visual.state.color.opacity(0.75),lineWidth:visual.state == .studioOnly ? 1:1.5)}
            .overlay(alignment:.topTrailing) {
                if visual.state == .requested || visual.state == .incoming {
                    ZStack {
                        Circle().stroke(visual.state.color.opacity(0.2),lineWidth:2)
                        Circle().trim(from:0,to:min(max(visual.progress,0),1)).stroke(visual.state.color,style:StrokeStyle(lineWidth:2,lineCap:.round)).rotationEffect(.degrees(-90))
                    }.frame(width:14,height:14).padding(4)
                }
            }
            .animation(.easeInOut(duration:0.35),value:visual.progress)
        }
        .buttonStyle(.plain)
        .help("\(lane.symbol) \(lane.timeframe) · \(visual.state.rawValue) · \(Int(visual.progress * 100))% · click to \(actionLabel)")
    }

    private var actionLabel:String {switch visual.state{case .studioOnly:"request";case .local,.requested,.incoming:"pause";case .paused:"resume";case .failed:"retry"}}

    private func short(_ value:String)->String {
        value.replacingOccurrences(of:"+00:00",with:"").replacingOccurrences(of:"T",with:" ")
    }
}

struct LiteLaneLegend:View {
    var body:some View {
        HStack(spacing:14) {
            legend(.studioOnly)
            legend(.requested)
            legend(.incoming)
            legend(.local)
            legend(.paused)
            legend(.failed)
        }.font(.caption2)
    }
    private func legend(_ state:LiteLaneOwnershipState)->some View {
        HStack(spacing:4){RoundedRectangle(cornerRadius:2).fill(state.color).frame(width:10,height:10);Text(state.rawValue)}
    }
}
