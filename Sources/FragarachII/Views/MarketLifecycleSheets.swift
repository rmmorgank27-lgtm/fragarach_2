import OperationsCore
import SwiftUI

struct MarketRetirementReview: View {
    let impact: RetirementImpact
    let onConfirm: (RetirementImpact, String, String, String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var reason = "INCORRECT_INSTRUMENT_IDENTITY"
    @State private var note = ""
    @State private var confirmation = ""

    private let reasons = [
        "INCORRECT_INSTRUMENT_IDENTITY",
        "INCORRECT_PAIR_ORIENTATION",
        "INCORRECT_PROVIDER_MAPPING",
        "WRONG_SYMBOL",
        "DUPLICATE_REGISTRATION",
        "ERRONEOUS_OPERATOR_REGISTRATION",
        "INVALID_VENUE_OR_LISTING",
        "PROVIDER_EVIDENCE_MISMATCH",
        "OTHER_REVIEWED_REASON",
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Retire \(impact.canonicalInstrument) from Estate")
                .font(.title.bold())
            Picker("Reason", selection: $reason) {
                ForEach(reasons, id: \.self) {
                    Text($0.replacingOccurrences(of: "_", with: " ").capitalized).tag($0)
                }
            }
            TextField("Operator note", text: $note)
            DiscoveryFactsGrid([
                ("Active lanes", impact.activeTimeframeLanes.joined(separator: ", ")),
                ("Completed acquisition runs", "\(impact.completedAcquisitionRuns)"),
                ("Raw evidence blocks", "\(impact.rawEvidenceBlocks) — preserved"),
                ("Canonical bars", "\(impact.canonicalBars) — preserved and quarantined"),
                ("Future acquisition", "Will be disabled"),
                ("Active serving", "Will stop"),
            ])
            if impact.typedConfirmationRequired {
                Text("Type \(impact.requiredConfirmation ?? "") to confirm")
                    .fontWeight(.semibold)
                TextField(impact.requiredConfirmation ?? "", text: $confirmation)
                    .textFieldStyle(.roundedBorder)
            }
            HStack {
                Button("Cancel", role: .cancel) { dismiss() }
                Spacer()
                Button("Confirm Retirement", role: .destructive) {
                    dismiss()
                    onConfirm(impact, reason, note, confirmation)
                }
                .disabled(
                    impact.typedConfirmationRequired
                        && confirmation.trimmingCharacters(in: .whitespaces).uppercased()
                            != impact.requiredConfirmation
                )
            }
        }
        .padding(24)
        .frame(minWidth: 680)
    }
}

struct MarketRetirementSuccess: View {
    let receipt: RetirementReceipt
    let onDone: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("\(receipt.canonicalInstrument) Retired").font(.title.bold())
            Label("Future acquisition disabled", systemImage: "checkmark.circle.fill")
            Label("Evidence preserved and quarantined", systemImage: "checkmark.circle.fill")
            DiscoveryFactsGrid([
                ("Retirement ID", receipt.retirementID),
                ("Reason", receipt.reason),
                ("Authority", receipt.newAuthorityState),
                ("Completed", receipt.completedTimestamp),
            ])
            Button("Return to Discover") {
                dismiss()
                onDone()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(24)
        .frame(minWidth: 620)
    }
}

struct MarketPermanentRemovalReview: View {
    let impact: PermanentRemovalImpact
    let onConfirm: (PermanentRemovalImpact, String) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var confirmation = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Permanently Remove \(impact.canonicalInstrument)").font(.title.bold())
            Label(
                impact.recommendedAction == "REGISTER_CORRECT_INSTRUMENT"
                    ? "This registration contains immutable evidence. Keep it retired and register the correct instrument separately."
                    : "This is exceptional. Reactivation preserves useful authority.",
                systemImage: "exclamationmark.triangle.fill"
            )
            .foregroundStyle(.orange)
            DiscoveryFactsGrid([
                ("Retired on", impact.retiredAt),
                ("Reason", impact.reason.replacingOccurrences(of: "_", with: " ").capitalized),
                ("Canonical bars", "\(impact.canonicalBars)"),
                ("Raw evidence blocks", "\(impact.rawEvidenceBlocks)"),
                ("Audit history", "Preserved as an immutable tombstone"),
            ])
            if let blocker = impact.blockingReason {
                Label(blocker, systemImage: "lock.fill").foregroundStyle(.red)
            } else {
                Text("Type \(impact.requiredConfirmation) to confirm").fontWeight(.semibold)
                TextField(impact.requiredConfirmation, text: $confirmation)
            }
            HStack {
                Button("Cancel", role: .cancel) { dismiss() }
                Spacer()
                Button("Permanently Remove", role: .destructive) {
                    dismiss()
                    onConfirm(impact, confirmation)
                }
                .disabled(
                    !impact.removable
                        || confirmation.trimmingCharacters(in: .whitespaces).uppercased()
                            != impact.requiredConfirmation
                )
            }
        }
        .padding(24)
        .frame(minWidth: 680)
    }
}

struct MarketReactivationSuccess: View {
    let receipt: ReactivationReceipt
    let onDone: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("\(receipt.canonicalInstrument) Reactivated").font(.title.bold())
            Label("Canonical identity and provider mappings preserved", systemImage: "checkmark.circle.fill")
            Label("Evidence, provenance, and Truth history preserved", systemImage: "checkmark.circle.fill")
            DiscoveryFactsGrid([
                ("Authority", receipt.newAuthorityState),
                ("Lanes", receipt.selectedLanes.joined(separator: ", ")),
                ("Completed", receipt.completedTimestamp),
            ])
            Button("Open Manage Data") {
                dismiss()
                onDone()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(24)
        .frame(minWidth: 620)
    }
}

struct MarketPermanentRemovalSuccess: View {
    let receipt: PermanentRemovalReceipt
    let onDone: () -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("\(receipt.canonicalInstrument) Removed").font(.title.bold())
            Label("Active registration authority removed", systemImage: "checkmark.circle.fill")
            Label("Immutable audit history preserved", systemImage: "checkmark.circle.fill")
            Text("Discovery can offer a reviewed fresh registration without duplicating canonical rows.")
                .foregroundStyle(.secondary)
            Button("Return to Discover") {
                dismiss()
                onDone()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(24)
        .frame(minWidth: 620)
    }
}
