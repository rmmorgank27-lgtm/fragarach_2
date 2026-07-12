import CryptoKit
import Foundation
import OperationsCore
import SwiftUI

private enum DataMode: String, CaseIterable { case fetch = "Fetch / Update", importFile = "Import File", retire = "Retire" }
private enum FetchIntent: String, CaseIterable { case maximum = "Maximum Available", update = "Update to Current", custom = "Custom Range" }

struct DataOperationsView: View {
    @EnvironmentObject private var store: ConsoleStore
    @State private var search = ""
    @State private var showRetired = false
    @State private var selectedAsset: String?
    @State private var mode: DataMode = .fetch
    @State private var intent: FetchIntent = .maximum
    @State private var from = ""
    @State private var through = ""
    @State private var conflict = ConflictMode.preserve
    @State private var file: URL?
    @State private var reviewing = false
    @State private var retirementImpact: RetirementImpact?
    @State private var retirementReceipt: RetirementReceipt?
    @State private var localError: String?

    private var allRegistrations: [InstrumentRegistrationRecord] { store.snapshot?.registrations ?? [] }
    private var registrations: [InstrumentRegistrationRecord] {
        allRegistrations.filter { r in
            (showRetired || !r.retired) && (search.isEmpty || r.asset.localizedCaseInsensitiveContains(search) || r.displayName.localizedCaseInsensitiveContains(search) || r.assetClass.localizedCaseInsensitiveContains(search) || r.providerID.localizedCaseInsensitiveContains(search))
        }
    }
    private var selectedRegistrations: [InstrumentRegistrationRecord] { allRegistrations.filter { $0.asset == selectedAsset } }
    private var registration: InstrumentRegistrationRecord? { selectedRegistrations.first }
    private var lane: LaneRecord? { store.snapshot?.lanes.first { $0.asset == selectedAsset && $0.timeframe == registration?.timeframe } }
    private var truth: EstateTruthLane? { store.estateTruth?.truthMatrix.first { $0.symbol == selectedAsset && $0.timeframe == registration?.timeframe } }
    private var canMutate: Bool { registration?.retired == false && store.activeOperationID == nil }
    private var checksum: String { guard let file, let data=try? Data(contentsOf:file) else{return "—"};return SHA256.hash(data:data).map{String(format:"%02x",$0)}.joined() }

    var body: some View {
        HStack(spacing:0) {
            VStack(alignment:.leading,spacing:10) {
                TextField("Search active instruments",text:$search).textFieldStyle(.roundedBorder)
                Toggle("Show Retired",isOn:$showRetired)
                List(registrations,selection:$selectedAsset) { r in
                    VStack(alignment:.leading,spacing:3) {
                        Text(r.displayName).fontWeight(.semibold)
                        Text("\(r.asset) · \(r.assetClass)").font(.caption).foregroundStyle(.secondary)
                        Text(r.retired ? "RETIRED" : "\(r.providerID) · \(r.timeframe)").font(.caption2).foregroundStyle(r.retired ? .orange:.secondary)
                    }.tag(Optional(r.asset))
                }
            }.frame(width:280).padding()
            Divider()
            ScrollView { VStack(alignment:.leading,spacing:16) {
                Text("Data Operations").font(.largeTitle)
                if let r=registration {
                    header(r)
                    Picker("Mode",selection:$mode){ForEach(DataMode.allCases,id:\.self){Text($0.rawValue)}}.pickerStyle(.segmented)
                    switch mode { case .fetch: fetchView(r);case .importFile: importView(r);case .retire: retireView(r) }
                } else { ContentUnavailableView("Select a registered instrument",systemImage:"arrow.left",description:Text("Active authority drives this selector; retired registrations are hidden by default.")) }
                if let localError { Label(localError,systemImage:"exclamationmark.triangle").foregroundStyle(.red) }
                readableResult
            }.padding().frame(maxWidth:900,alignment:.leading) }
        }
        .onAppear { if let asset=store.acquisitionAsset{selectedAsset=asset;store.acquisitionAsset=nil};selectFirst() }
        .onChange(of:store.snapshot){selectFirst()}
        .onChange(of:selectedAsset){intent=(lane?.barCount ?? 0)>0 ? .update:.maximum}
        .sheet(isPresented:$reviewing){reviewSheet}
        .sheet(item:$retirementImpact){impact in RetirementOperationReview(impact:impact,onConfirm:confirmRetirement)}
        .sheet(item:$retirementReceipt){receipt in RetirementOperationSuccess(receipt:receipt){retirementReceipt=nil}}
    }

    private func header(_ r:InstrumentRegistrationRecord)->some View { GroupBox { HStack(alignment:.top) { VStack(alignment:.leading,spacing:5) { Text("\(r.displayName) — \(r.asset)").font(.title2.bold());Text("\(r.assetClass) · \(r.representationType)");Text(r.retired ? "Retired":"Active").foregroundStyle(r.retired ? .orange:.green);Facts([("Registered lanes",selectedRegistrations.map(\.timeframe).joined(separator:", ")),("Evidence",(lane?.barCount ?? 0)>0 ? "Present":"None"),("Truth Score",truth.map{String($0.truthState.truthScore)} ?? "Unknown"),("CAODT",truth?.truthState.caodt ?? "—")]) };Spacer();if !r.retired{Button("Retire Instrument",role:.destructive){mode = .retire}} } } }

    private func fetchView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:14) {
        laneMatrix(r)
        Picker("Intent",selection:$intent){ForEach(FetchIntent.allCases,id:\.self){Text($0.rawValue)}}.pickerStyle(.segmented)
        if intent == .maximum { unavailableCapability(title:"Maximum history cannot yet be proven.",reason:"Terminal-boundary proof and resume behavior are not implemented.") }
        else if intent == .update { unavailableCapability(title:"Automatic update range is unavailable.",reason:"The correction-overlap resolver is not implemented.");Facts([("Latest stored",latestText),("Latest completed D1",latestCompletedD1)]) }
        else { Form { TextField("Inclusive from date",text:$from);TextField("Inclusive through date",text:$through) } }
        Picker("Conflict policy",selection:$conflict){ForEach(ConflictMode.allCases,id:\.self){Text($0.rawValue.capitalized)}}
        Text("Preserve keeps prior evidence and records the conflicting candidate without silent overwrite.").font(.caption).foregroundStyle(.secondary)
        Button("Review Data Operation"){reviewing=true}.buttonStyle(.borderedProminent).disabled(!canMutate || intent != .custom || from.isEmpty || through.isEmpty || !store.credentialAvailable)
    } }

    private func unavailableCapability(title:String,reason:String)->some View { GroupBox("Capability unavailable; safe fallback active") { VStack(alignment:.leading,spacing:10) { Label(title,systemImage:"exclamationmark.triangle").foregroundStyle(.orange);Text(reason).foregroundStyle(.secondary);Facts([("Affected scope","\(registration?.asset ?? "Instrument"):D1 — selected convenience operation"),("What remains safe","Bounded D1 fetch, Import File, and Retire")]);HStack{Button("Choose Custom Range"){intent = .custom};Button("Import File"){mode = .importFile}.buttonStyle(.borderedProminent)};DisclosureGroup("Technical reason"){Text("The current implementation cannot prove a provider terminal boundary or calculate an approved automatic overlap. Ratified timeframe authority remains present; this is an implementation incompatibility.").font(.caption)} } } }

    private func importView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:14) {
        laneMatrix(r);Button("Choose CSV…"){file=PanelService.chooseCSV()}
        if let file { GroupBox("Import Preview") { Facts([("File Name",file.lastPathComponent),("Byte Size","\((try? file.resourceValues(forKeys:[.fileSizeKey]).fileSize) ?? 0)"),("Checksum",checksum),("Detected Format","CSV"),("Selected Instrument",r.asset),("Selected Timeframe",r.timeframe),("Detected Row Count",rowCount(file)),("Timestamp Range","Validated by existing ingestion authority")]) } }
        Picker("Conflict policy",selection:$conflict){ForEach(ConflictMode.allCases,id:\.self){Text($0.rawValue.capitalized)}}
        Button("Review Import"){reviewing=true}.buttonStyle(.borderedProminent).disabled(!canMutate || file==nil)
    } }

    private func retireView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:12) { if r.retired { Label("Retired authority is audit-only. Provider acquisition and import are disabled.",systemImage:"archivebox").foregroundStyle(.orange) } else { Text("Uses the reviewed SPEC-013 impact, supersession, quarantine, acquisition shutdown, and receipt service.");Button("Review Retirement Impact",role:.destructive){planRetirement(r)}.disabled(store.activeOperationID != nil) } } }

    private func laneMatrix(_ r:InstrumentRegistrationRecord)->some View { GroupBox("Timeframe Lane Matrix") { Grid(alignment:.leading,horizontalSpacing:18,verticalSpacing:8) { GridRow{ForEach(["Timeframe","Registration","Evidence","Latest","Default intent","Selectable"],id:\.self){Text($0).font(.caption.bold())}};Divider().gridCellColumns(6);GridRow{Text(r.timeframe).monospaced();Text(r.retired ? "Retired":"Existing");Text((lane?.barCount ?? 0)>0 ? "Yes":"No");Text(latestText);Text((lane?.barCount ?? 0)>0 ? "Update to Current":"Maximum Available");Text(r.retired ? "No — retired":"Yes")} }.frame(maxWidth:.infinity,alignment:.leading) } }

    @ViewBuilder private var readableResult:some View { if let result=store.lastProcessResult { GroupBox(result.exitCode==0 ? "Data Operation Complete":"Data Operation Failed") { VStack(alignment:.leading,spacing:8) { Label(result.exitCode==0 ? "Authority service completed successfully":"No success was claimed",systemImage:result.exitCode==0 ? "checkmark.circle.fill":"xmark.octagon").foregroundStyle(result.exitCode==0 ? .green:.red);if let op=store.snapshot?.operations.first{Facts([("Rows inserted","\(op.inserted)"),("Rows unchanged","\(op.unchanged)"),("Conflicts preserved","\(op.conflicts)"),("Raw block",op.rawBlockID ?? "—")])};DisclosureGroup("Technical Details"){Text(result.stdout.isEmpty ? result.stderr:result.stdout).font(.caption.monospaced()).textSelection(.enabled)} } } } }

    @ViewBuilder private var reviewSheet:some View { if let r=registration { VStack(alignment:.leading,spacing:16) { Text("Review Data Operation").font(.title);Facts([("Instrument","\(r.asset) — \(r.displayName)"),("Source",mode == .importFile ? "Manual file import":"Twelve Data"),("Lane",r.timeframe),("Intent",mode == .fetch ? intent.rawValue:"Import File"),("Requested range",mode == .fetch ? "\(from) → \(through) inclusive":file?.lastPathComponent ?? "—"),("Conflict Policy",conflict.rawValue.capitalized)]);HStack{Button("Cancel",role:.cancel){reviewing=false};Spacer();Button("Run Data Operation"){runReviewed(r)}.buttonStyle(.borderedProminent)} }.padding(24).frame(minWidth:620) } }

    private var latestText:String { lane?.latestBar.map{Date(timeIntervalSince1970:TimeInterval($0)).formatted(date:.numeric,time:.shortened)} ?? "—" }
    private var latestCompletedD1:String { Calendar.current.date(byAdding:.day,value:-1,to:Date())!.formatted(.iso8601.year().month().day()) }
    private func rowCount(_ url:URL)->String{guard let text=try? String(contentsOf:url,encoding:.utf8)else{return "Unknown"};return String(max(0,text.split(whereSeparator:\.isNewline).count-1))}
    private func selectFirst(){if selectedAsset==nil || !allRegistrations.contains(where:{$0.asset==selectedAsset}){selectedAsset=registrations.first?.asset}}
    private func runReviewed(_ r:InstrumentRegistrationRecord){reviewing=false;Task{if mode == .fetch{await store.run(.acquire(asset:r.asset,from:from,through:through,mode:conflict))}else if let file{await store.run(.importCSV(file:file.path,symbol:r.asset,timeframe:r.timeframe,mode:conflict))}}}
    private func planRetirement(_ r:InstrumentRegistrationRecord){localError=nil;Task{await store.run(.retirementPlan(asset:r.asset,scope:"WHOLE_INSTRUMENT",lanes:selectedRegistrations.map(\.timeframe)));guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let impact=try? JSONDecoder().decode(RetirementImpact.self,from:Data(text.utf8))else{localError=store.operationError ?? "Retirement impact could not be loaded";return};retirementImpact=impact}}
    private func confirmRetirement(_ impact:RetirementImpact,_ reason:String,_ note:String,_ confirmation:String){retirementImpact=nil;Task{await store.run(.retireInstrument(asset:impact.canonicalInstrument,scope:impact.scope,lanes:impact.selectedLanes,reason:reason,note:note,confirmation:confirmation));guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let receipt=try? JSONDecoder().decode(RetirementReceipt.self,from:Data(text.utf8))else{localError=store.operationError ?? "Retirement failed";return};retirementReceipt=receipt}}
}

private struct RetirementOperationReview:View { let impact:RetirementImpact;let onConfirm:(RetirementImpact,String,String,String)->Void;@Environment(\.dismiss) var dismiss;@State private var reason="INCORRECT_INSTRUMENT_IDENTITY";@State private var note="";@State private var confirmation="";let reasons=["INCORRECT_INSTRUMENT_IDENTITY","INCORRECT_PAIR_ORIENTATION","INCORRECT_PROVIDER_MAPPING","WRONG_SYMBOL","DUPLICATE_REGISTRATION","ERRONEOUS_OPERATOR_REGISTRATION","INVALID_VENUE_OR_LISTING","PROVIDER_EVIDENCE_MISMATCH","OTHER_REVIEWED_REASON"];var body:some View{VStack(alignment:.leading,spacing:14){Text("Retire \(impact.canonicalInstrument)").font(.title);Text("SPEC-013 Impact Review").font(.headline);Picker("Controlled reason",selection:$reason){ForEach(reasons,id:\.self){Text($0.replacingOccurrences(of:"_",with:" ").capitalized)}};TextField("Operator note",text:$note);Facts([("Active lanes",impact.activeTimeframeLanes.joined(separator:", ")),("Evidence counts","\(impact.canonicalBars) bars · \(impact.rawEvidenceBlocks) raw blocks"),("Acquisition history","\(impact.completedAcquisitionRuns) completed runs"),("Truth state",impact.currentServingState),("Operational effects","Acquisition disabled; active serving excluded"),("Preservation guarantees","Raw evidence and audit history preserved")]);if impact.typedConfirmationRequired{Text("Type \(impact.requiredConfirmation ?? "") to confirm").fontWeight(.semibold);TextField(impact.requiredConfirmation ?? "",text:$confirmation)};HStack{Button("Cancel",role:.cancel){dismiss()};Spacer();Button("Confirm Retirement",role:.destructive){dismiss();onConfirm(impact,reason,note,confirmation)}.disabled(impact.typedConfirmationRequired && confirmation.trimmingCharacters(in:.whitespaces).uppercased() != impact.requiredConfirmation)}}.padding(24).frame(minWidth:680)}}
private struct RetirementOperationSuccess:View { let receipt:RetirementReceipt;let done:()->Void;@Environment(\.dismiss) var dismiss;var body:some View{VStack(alignment:.leading,spacing:14){Text("\(receipt.canonicalInstrument) Retired").font(.title);Label("Acquisition disabled; evidence preserved; active serving removed",systemImage:"checkmark.circle.fill").foregroundStyle(.green);Facts([("Retirement ID",receipt.retirementID),("Reason",receipt.reason),("Authority",receipt.newAuthorityState),("Completed",receipt.completedTimestamp)]);Button("Done"){dismiss();done()}.buttonStyle(.borderedProminent)}.padding(24).frame(minWidth:620)}}
