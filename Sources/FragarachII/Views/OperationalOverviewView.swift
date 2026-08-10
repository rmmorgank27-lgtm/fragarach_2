import Foundation
import OperationsCore
import SwiftUI

struct OperationalOverviewView: View {
    let snapshot:AuthoritySnapshot?
    let metrics:OperationalMetricsSnapshot?
    let metricsError:String?
    let schedulerStatus:SchedulerServiceStatus?

    private var totalBars:Int? {
        snapshot.map { $0.lanes.reduce(0) { $0 + $1.barCount } }
    }

    var body:some View {
        VStack(alignment:.leading,spacing:10) {
            HStack(alignment:.firstTextBaseline) {
                Text("Operational State").font(.title2.bold())
                Spacer()
                if let readAt=metrics?.readAt {
                    Text("Local metrics updated \(readAt.formatted(date:.omitted,time:.shortened))")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            TimelineView(.periodic(from:.now,by:60)) { context in
                LazyVGrid(columns:[GridItem(.adaptive(minimum:280),spacing:12)],spacing:12) {
                    SchedulerMetricCard(
                        title:"Total bars",
                        value:totalBars?.formatted() ?? "—",
                        detail:totalBars == nil ? "Loading governed lane totals":"Governed observations across active lanes",
                        state:nil
                    )
                    SchedulerMetricCard(
                        title:"Storage",
                        value:formattedStorage,
                        detail:metrics == nil ? "Authority storage unavailable":"SQLite database + live WAL + shared memory",
                        state:nil
                    )
                    SchedulerMetricCard(
                        title:"Average response time",
                        value:formattedResponseTime,
                        detail:responseTimeDetail,
                        state:nil
                    )
                    SchedulerMetricCard(
                        title:"Last audit",
                        value:SchedulerFormatting.timestamp(schedulerStatus?.audit?.completedAtUTC),
                        detail:auditDetail,
                        state:schedulerStatus?.audit?.overallResult
                    )
                    SchedulerMetricCard(
                        title:"Last failed packet",
                        value:failedPacketValue,
                        detail:failedPacketDetail,
                        state:nil
                    )
                    SchedulerMetricCard(
                        title:"Total uptime",
                        value:formattedUptime(at:context.date),
                        detail:uptimeDetail,
                        state:schedulerStatus?.live == true ? "RUNNING":"UNAVAILABLE"
                    )
                }
            }
            if let metricsError {
                Label(metricsError,systemImage:"exclamationmark.triangle")
                    .font(.caption).foregroundStyle(.orange)
            }
        }
    }

    private var formattedStorage:String {
        guard let bytes=metrics?.storageBytes else{return "—"}
        return ByteCountFormatter.string(fromByteCount:bytes,countStyle:.file)
    }

    private var formattedResponseTime:String {
        guard let milliseconds=metrics?.averageProviderResponseMilliseconds else{return "—"}
        if milliseconds < 1_000 {return "\(Int(milliseconds.rounded())) ms"}
        return String(format:"%.1f s",milliseconds / 1_000)
    }

    private var responseTimeDetail:String {
        guard let count=metrics?.providerResponseSampleCount,count > 0 else {
            return "No recent completed provider calls"
        }
        return "Mean of \(count) recent completed provider call\(count == 1 ? "":"s")"
    }

    private var auditDetail:String {
        guard let audit=schedulerStatus?.audit else{return "No estate audit has been recorded"}
        let findings=audit.findingCounts?.values.reduce(0,+) ?? 0
        let result=(audit.overallResult ?? audit.state).replacingOccurrences(of:"_",with:" ").capitalized
        return "\(result) · \(findings) finding\(findings == 1 ? "":"s")"
    }

    private var failedPacketValue:String {
        guard let failure=metrics?.lastFailedPacket else{return "None recorded"}
        return "\(failure.asset) · \(failure.timeframe)"
    }

    private var failedPacketDetail:String {
        guard let failure=metrics?.lastFailedPacket else{return "No failed ingest packet in authority history"}
        let reason=failure.reason.replacingOccurrences(of:"_",with:" ").capitalized
        return "\(failure.provider) · \(reason) · \(SchedulerFormatting.timestamp(failure.occurredAt))"
    }

    private func formattedUptime(at now:Date)->String {
        guard let started=parseTimestamp(schedulerStatus?.serviceStartTime) else{return "—"}
        let seconds=max(0,Int(now.timeIntervalSince(started)))
        let days=seconds / 86_400
        let hours=(seconds % 86_400) / 3_600
        let minutes=(seconds % 3_600) / 60
        if days > 0 {return "\(days)d \(hours)h \(minutes)m"}
        if hours > 0 {return "\(hours)h \(minutes)m"}
        return "\(minutes)m"
    }

    private var uptimeDetail:String {
        guard let started=schedulerStatus?.serviceStartTime else{return "Scheduler start time unavailable"}
        return "Since \(SchedulerFormatting.timestamp(started))"
    }

    private func parseTimestamp(_ value:String?)->Date? {
        guard let value else{return nil}
        let fractional=ISO8601DateFormatter()
        fractional.formatOptions=[.withInternetDateTime,.withFractionalSeconds]
        return fractional.date(from:value) ?? ISO8601DateFormatter().date(from:value)
    }
}
