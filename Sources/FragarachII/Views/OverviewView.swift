import OperationsCore
import SwiftUI

struct OverviewView: View {
    @EnvironmentObject private var store: ConsoleStore
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:18) {
                WorkspaceHeader(title:"Overview",purpose:"Single-glance operational fitness of the Fragarach II authority.")
                if let scheduler=store.schedulerSnapshot {
                    HStack(spacing:12) {
                        SchedulerMetricCard(title:"Authority Integrity",value:scheduler.authorityHealth.state,detail:scheduler.authorityHealth.detail,state:scheduler.authorityHealth.state)
                        SchedulerMetricCard(title:"Scheduler Service",value:store.schedulerServiceStatus?.serviceState.replacingOccurrences(of:"_",with:" ").capitalized ?? "Unknown",detail:"Heartbeat: \(SchedulerFormatting.timestamp(store.schedulerServiceStatus?.heartbeatTime)) · Next: \(SchedulerFormatting.timestamp(scheduler.nextRun))",state:store.schedulerServiceRunning ? "HEALTHY":"CRITICAL")
                        SchedulerMetricCard(title:"Current",value:"\(scheduler.summary.current)",detail:"of \(scheduler.summary.total) scheduler lanes · \(scheduler.summary.failed) failed",state:scheduler.authorityHealth.state)
                    }
                } else if let status=store.schedulerServiceStatus {
                    // The time-triggered register is a bounded indexed read.
                    // It provides an honest operational overview immediately;
                    // complete Estate scorecards appear only after their
                    // canonical projection has finished.
                    let operationalState=status.operationalHealth?.overallOperationalHealth.replacingOccurrences(of:"_",with:" ").capitalized ?? status.serviceState.replacingOccurrences(of:"_",with:" ").capitalized
                    let dueNow=status.register?.dueNowCount ?? 0
                    let scheduled=status.register?.readyCount ?? 0
                    HStack(spacing:12) {
                        SchedulerMetricCard(title:"Scheduler Service",value:operationalState,detail:"Process \(store.schedulerServiceRunning ? "running":"unavailable") · Heartbeat: \(SchedulerFormatting.timestamp(status.heartbeatTime))",state:store.schedulerServiceRunning ? "HEALTHY":"CRITICAL")
                        SchedulerMetricCard(title:"Due now",value:"\(dueNow)",detail:dueNow == 0 ? "No overdue checks · \(scheduled) scheduled" : "Overdue checks awaiting dispatch · \(scheduled) scheduled",state:dueNow == 0 ? "CURRENT":"WAITING")
                        SchedulerMetricCard(title:"Retrying",value:"\(status.register?.retryingCount ?? 0)",detail:"Lane-specific retry backoff",state:(status.register?.retryingCount ?? 0) == 0 ? "CURRENT":"WAITING")
                        SchedulerMetricCard(title:"Blocked",value:"\(status.register?.blockedCount ?? 0)",detail:"Click to inspect affected lanes",state:(status.register?.blockedCount ?? 0) == 0 ? "CURRENT":"FAILED",action:{store.showBlockedSchedulerLanes()})
                    }
                    if store.estateProjectionNeedsRefresh {
                        Label("Refreshing Estate Truth after the latest Scheduler publication.",systemImage:"arrow.triangle.2.circlepath").font(.caption).foregroundStyle(.secondary)
                    } else if store.estateTruth == nil {
                        Label("Loading complete Estate Truth in the background.",systemImage:"arrow.triangle.2.circlepath").font(.caption).foregroundStyle(.secondary)
                    }
                }
                if let estate=store.estateTruth { TruthEstateSummaryView(summary:estate.estateSummary,scheduler:store.schedulerSnapshot,onSelect:store.showEstateFindings) }
                else if let error=store.estateTruthError { ContentUnavailableView("Authority unavailable",systemImage:"exclamationmark.triangle",description:Text(error)) }
                HStack {
                    Button("Open Estate"){store.section = .estate}.buttonStyle(.borderedProminent)
                    Button("Open Scheduler"){store.section = .scheduler}
                }
            }.padding().frame(maxWidth:1100,alignment:.leading)
        }
    }
}
