import OperationsCore
import SwiftUI

struct ReplicaSystemOverviewView: View {
    let snapshot: ReadOnlyClientsSnapshot?
    let busy: Bool
    let onRefresh: (String) -> Void
    let onSetPaused: (String, Bool) -> Void

    var body: some View {
        GroupBox("Systems and data flow") {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    Label(overallState.title, systemImage: overallState.icon)
                        .font(.headline)
                        .foregroundStyle(overallState.color)
                    Spacer()
                    Text("Mac Studio authority → Tailscale HTTPS → MacBook Lite")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if let clients = snapshot?.clients, !clients.isEmpty {
                    ForEach(clients) { client in
                        clientFlow(client)
                    }
                } else {
                    ContentUnavailableView(
                        "No MacBook replica connected",
                        systemImage: "laptopcomputer.slash",
                        description: Text("The Studio publisher is visible, but no Fragarach Lite client has been added.")
                    )
                    .frame(maxWidth: .infinity, minHeight: 150)
                }
            }
            .padding(10)
        }
    }

    private func clientFlow(_ client: ReadOnlyClientRecord) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                systemCard(
                    title: "Mac Studio",
                    subtitle: "Fragarach authority",
                    icon: "macstudio",
                    roleColor: .indigo,
                    state: studioState,
                    metrics: [
                        ("Published lanes", "\(snapshot?.latestPublication?.lanes.count ?? 0)"),
                        ("Replica", snapshot?.latestPublication.map { short($0.authorityRevision) } ?? "None"),
                        ("Payload", payloadSize)
                    ]
                )

                linkCard(client)

                systemCard(
                    title: client.displayName,
                    subtitle: "Fragarach Lite · \(client.clientID)",
                    icon: "laptopcomputer",
                    roleColor: .green,
                    state: liteState(client),
                    metrics: [
                        ("Active lanes", "\(requests(client).filter{$0.state == "ACTIVE"}.count)"),
                        ("Paused lanes", "\(requests(client).filter{$0.state == "PAUSED"}.count)"),
                        ("Failed", "\(requests(client).filter{$0.state == "FAILED"}.count)")
                    ]
                )
            }

            HStack(spacing: 16) {
                Label("Last check-in \(client.report?.receivedAtUTC ?? "waiting")", systemImage: "dot.radiowaves.left.and.right")
                Label("Last sync \(client.report?.service.lastSyncOutcome ?? "waiting")", systemImage: "arrow.triangle.2.circlepath")
                if let publication = client.report?.replica?.publicationID {
                    Label(short(publication), systemImage: "shippingbox")
                }
                Spacer()
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(12)
        .background(.quaternary.opacity(0.28), in: RoundedRectangle(cornerRadius: 12))
    }

    private func linkCard(_ client: ReadOnlyClientRecord) -> some View {
        let paused = client.control?.syncPaused == true
        let state = linkState(client)
        let request = requestProgress(client)
        return VStack(spacing: 8) {
            HStack(spacing: 5) {
                Image(systemName: "arrow.right")
                Image(systemName: "network")
                Image(systemName: "arrow.right")
            }
            .font(.title2)
            .foregroundStyle(state.color)

            Text(state.title).font(.headline).foregroundStyle(state.color)
            Text("Private Tailscale HTTPS").font(.caption).foregroundStyle(.secondary)
            VStack(spacing: 4) {
                ProgressView(value: request.value)
                    .progressViewStyle(.linear)
                    .tint(request.color)
                HStack {
                    Text(request.label).fontWeight(.semibold)
                    Spacer()
                    Text("\(Int(request.value * 100))%")
                }
                .font(.caption2)
                .foregroundStyle(request.color)
            }

            Text(request.detail)
                .font(.caption2.monospaced())
                .foregroundStyle(.secondary)
                .lineLimit(1)

            HStack {
                Button("Refresh Now") { onRefresh(client.clientID) }
                    .buttonStyle(.borderedProminent)
                Button(paused ? "Resume Flow" : "Pause Flow") {
                    onSetPaused(client.clientID, !paused)
                }
            }
            .controlSize(.small)
            .disabled(busy)
        }
        .frame(maxWidth: .infinity, minHeight: 145)
        .padding(12)
        .background(state.color.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
        .overlay { RoundedRectangle(cornerRadius: 10).stroke(state.color.opacity(0.35)) }
    }

    private func systemCard(
        title: String,
        subtitle: String,
        icon: String,
        roleColor: Color,
        state: FlowState,
        metrics: [(String, String)]
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon).font(.title2).foregroundStyle(roleColor)
                VStack(alignment: .leading, spacing: 1) {
                    Text(title).font(.headline)
                    Text(subtitle).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Circle().fill(state.color).frame(width: 9, height: 9)
            }
            Divider()
            ForEach(Array(metrics.enumerated()), id: \.offset) { _, metric in
                HStack {
                    Text(metric.0).foregroundStyle(.secondary)
                    Spacer()
                    Text(metric.1).fontWeight(.semibold).lineLimit(1)
                }
                .font(.caption)
            }
            Spacer(minLength: 0)
            Text(state.title).font(.caption.bold()).foregroundStyle(state.color)
        }
        .frame(maxWidth: .infinity, minHeight: 145, alignment: .topLeading)
        .padding(12)
        .background(roleColor.opacity(0.07), in: RoundedRectangle(cornerRadius: 10))
        .overlay { RoundedRectangle(cornerRadius: 10).stroke(roleColor.opacity(0.5)) }
    }

    private var studioState: FlowState {
        guard snapshot?.publisherEnabled == true, snapshot?.service.running == true else {
            return .paused
        }
        return snapshot?.latestPublication == nil ? .waiting : .ready
    }

    private func liteState(_ client: ReadOnlyClientRecord) -> FlowState {
        guard client.enabled, !client.revoked else { return .paused }
        guard let report = client.report else { return .waiting }
        if report.service.lastSyncOutcome == "FAILED" { return .attention }
        return report.state == "READY" ? .ready : .attention
    }

    private func linkState(_ client: ReadOnlyClientRecord) -> FlowState {
        if client.control?.syncPaused == true { return .paused }
        guard snapshot?.publisherEnabled == true, snapshot?.service.running == true else { return .paused }
        guard client.report != nil else { return .waiting }
        return client.report?.service.lastSyncOutcome == "FAILED" ? .attention : .flowing
    }

    private func requestProgress(_ client: ReadOnlyClientRecord) -> RequestProgress {
        if client.control?.syncPaused == true {
            return .init(value: 0, label: "Flow paused", detail: "Verified lanes retained", color: .orange)
        }
        guard let request=requests(client).first(where:{!["ACTIVE","PAUSED","CANCELLED","REMOVED"].contains($0.state ?? "")}) ?? requests(client).first else {
            return .init(value: 0, label: "No lane requested", detail: "Standing by", color: .secondary)
        }
        let expected=request.expectedBytes ?? 0
        let transferred=request.transferredBytes ?? 0
        let progress=expected>0 ? min(max(Double(transferred)/Double(expected),0),1):0
        let detail="\(request.symbol) \(request.timeframe) · \(bytes(transferred)) / \(bytes(expected)) · verified \(bytes(request.verifiedBytes ?? 0))"
        if request.state == "FAILED" {return .init(value:progress,label:"Request failed",detail:detail,color:.red)}
        if request.state == "ACTIVE" {return .init(value:1,label:"Verified active",detail:detail,color:.green)}
        if request.state == "PAUSED" {return .init(value:progress,label:"Lane paused",detail:detail,color:.orange)}
        return .init(value:progress,label:(request.state ?? "REQUESTED").replacingOccurrences(of:"_",with:" "),detail:detail,color:.blue)
    }

    private func requests(_ client:ReadOnlyClientRecord)->[ReplicaLiteRequestReport] {client.requests ?? client.report?.requests ?? []}
    private func bytes(_ value:Int)->String {ByteCountFormatter.string(fromByteCount:Int64(value),countStyle:.file)}

    private var overallState: FlowState {
        guard let snapshot else { return .waiting }
        if !snapshot.publisherEnabled || snapshot.service.running != true { return .paused }
        if snapshot.clients.contains(where: { $0.report?.service.lastSyncOutcome == "FAILED" }) { return .attention }
        if snapshot.clients.contains(where: { $0.report == nil }) { return .waiting }
        if snapshot.clients.allSatisfy({ $0.control?.syncPaused == true }) { return .paused }
        return .flowing
    }

    private var payloadSize: String {
        guard let bytes = snapshot?.latestPublication?.payload.bytes else { return "—" }
        return ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file)
    }

    private func short(_ value: String) -> String {
        value.count > 18 ? String(value.prefix(15)) + "…" : value
    }
}

private struct RequestProgress {
    let value: Double
    let label: String
    let detail: String
    let color: Color
}

private enum FlowState {
    case ready, flowing, paused, waiting, attention

    var title: String {
        switch self {
        case .ready: "READY"
        case .flowing: "FLOWING"
        case .paused: "PAUSED"
        case .waiting: "WAITING"
        case .attention: "ATTENTION"
        }
    }

    var icon: String {
        switch self {
        case .ready: "checkmark.circle.fill"
        case .flowing: "arrow.right.circle.fill"
        case .paused: "pause.circle.fill"
        case .waiting: "clock.fill"
        case .attention: "exclamationmark.triangle.fill"
        }
    }

    var color: Color {
        switch self {
        case .ready, .flowing: .green
        case .paused: .orange
        case .waiting: .secondary
        case .attention: .red
        }
    }
}
