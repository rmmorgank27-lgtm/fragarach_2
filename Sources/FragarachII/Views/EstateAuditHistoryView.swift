import OperationsCore
import SwiftUI

struct EstateAuditHistoryView: View {
    @EnvironmentObject private var store: ConsoleStore
    @State private var weekday = "SUNDAY"
    @State private var hour = 10
    @State private var minute = 30
    @State private var selectedRunID: String?

    private let weekdays = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Estate Audit Reports").font(.title2.bold())
                    Text("Immutable governance reports, indexed by completion date. Audits never acquire market data.")
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button("Run Audit Now") {
                    Task {
                        await store.runEstateAudit()
                        selectedRunID = store.estateAuditHistory?.reports.first?.auditRunID
                        if let selectedRunID { await store.loadEstateAuditHistory(selectedRunID: selectedRunID) }
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(store.activeOperationID != nil || store.estateAuditHistoryLoading)
            }

            GroupBox("Weekly schedule") {
                HStack(spacing: 12) {
                    Picker("Day", selection: $weekday) {
                        ForEach(weekdays, id: \.self) { Text($0.capitalized).tag($0) }
                    }.frame(width: 155)
                    Picker("Hour", selection: $hour) {
                        ForEach(0..<24, id: \.self) { Text(String(format: "%02d", $0)).tag($0) }
                    }.frame(width: 90)
                    Text(":").font(.title3.monospaced())
                    Picker("Minute", selection: $minute) {
                        ForEach(0..<60, id: \.self) { Text(String(format: "%02d", $0)).tag($0) }
                    }.frame(width: 90)
                    Text("Brisbane time").foregroundStyle(.secondary)
                    Spacer()
                    Button("Save Schedule") { Task { await store.setEstateAuditSchedule(weekday: weekday, hour: hour, minute: minute) } }
                        .disabled(store.estateAuditHistoryLoading)
                }
                if let schedule = store.estateAuditHistory?.schedule {
                    Text("Next scheduled audit: \(displayTimestamp(schedule.nextScheduledAtUTC))")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }

            if let error = store.estateAuditHistoryError { Text(error).foregroundStyle(.red) }
            if let history = store.estateAuditHistory {
                if history.reports.isEmpty {
                    ContentUnavailableView("No estate audit reports", systemImage: "checklist", description: Text("Run an audit now or wait for the configured weekly schedule."))
                } else {
                    HStack(alignment: .top, spacing: 16) {
                        List(history.reports, selection: $selectedRunID) { report in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(displayTimestamp(report.completedAtUTC)).font(.headline)
                                Text("\(report.overallResult.replacingOccurrences(of: "_", with: " ")) · \(report.trigger.replacingOccurrences(of: "_", with: " "))")
                                    .font(.caption).foregroundStyle(resultColor(report.overallResult))
                                Text(findingSummary(report.findingCounts)).font(.caption).foregroundStyle(.secondary)
                            }.tag(report.auditRunID)
                        }
                        .frame(minWidth: 285, idealWidth: 340, maxWidth: 390, minHeight: 220)

                        auditDetail
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            } else if store.estateAuditHistoryLoading {
                ProgressView("Loading audit history…")
            }
        }
        .task { await store.loadEstateAuditHistory(); syncSchedule() }
        .onChange(of: store.estateAuditHistory?.schedule) { _, _ in syncSchedule() }
        .onChange(of: selectedRunID) { _, runID in
            guard let runID else { return }
            Task { await store.loadEstateAuditHistory(selectedRunID: runID) }
        }
    }

    @ViewBuilder private var auditDetail: some View {
        if let report = store.estateAuditHistory?.selectedReport {
            VStack(alignment: .leading, spacing: 10) {
                Text("Report detail").font(.headline)
                Facts([
                    ("Completed", displayTimestamp(report.completedAtUTC)),
                    ("Result", report.overallResult.replacingOccurrences(of: "_", with: " ")),
                    ("Trigger", report.trigger.replacingOccurrences(of: "_", with: " ")),
                    ("Report size", "\(report.reportBytes) bytes"),
                ])
                if report.findings.isEmpty {
                    Text("No findings recorded.").foregroundStyle(.secondary)
                } else {
                    ForEach(report.findings) { finding in
                        GroupBox {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("\(finding.severity) · \(finding.findingClass.replacingOccurrences(of: "_", with: " "))").font(.subheadline.bold())
                                Text(finding.authorityIdentifier).font(.caption.monospaced()).foregroundStyle(.secondary)
                                Text(finding.recommendedAction).font(.caption)
                            }
                        }
                    }
                }
                if !report.repairs.isEmpty {
                    Text("Applied repairs: \(report.repairs.map(\.repairClass).joined(separator: ", "))")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
        } else {
            ContentUnavailableView("Select an audit report", systemImage: "doc.text.magnifyingglass", description: Text("Reports are ordered by date, newest first."))
        }
    }

    private func syncSchedule() {
        guard let schedule = store.estateAuditHistory?.schedule else { return }
        weekday = schedule.weekday; hour = schedule.hour; minute = schedule.minute
    }
    private func displayTimestamp(_ timestamp: String) -> String {
        SchedulerFormatting.timestamp(timestamp)
    }
    private func findingSummary(_ counts: [String: Int]) -> String {
        counts.sorted { $0.key < $1.key }.map { "\($0.key): \($0.value)" }.joined(separator: " · ")
    }
    private func resultColor(_ result: String) -> Color {
        switch result { case "HEALTHY", "REPAIRED": .green; case "BLOCKING", "INTEGRITY": .red; default: .orange }
    }
}
