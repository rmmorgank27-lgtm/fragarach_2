import CryptoKit
import AppKit
import Foundation
import OperationsCore
import SwiftUI

private enum FetchIntent: String, CaseIterable, Hashable { case initial = "Fetch Full D1 History", update = "Update D1", custom = "Custom Range" }

struct DataOperationsView: View {
    @EnvironmentObject private var store: ConsoleStore
    @State private var search = ""
    @State private var showRetired = false
    @State private var selection = DataOperationsSelection()
    @State private var intent: FetchIntent = .initial
    @State private var fromDate = Calendar.current.date(byAdding:.year,value:-1,to:Date())!
    @State private var throughDate = Calendar.current.date(byAdding:.day,value:-1,to:Date())!
    @State private var conflict = ConflictMode.preserve
    @State private var file: URL?
    @State private var reviewing = false
    @State private var retirementImpact: RetirementImpact?
    @State private var retirementReceipt: RetirementReceipt?
    @State private var localError: String?
    @State private var dateInterpretation:String?
    @State private var reviewedPlan:ReviewedDataOperationPlan?
    @State private var completedPlan:ReviewedDataOperationPlan?
    @State private var fileSelectionID=UUID()

    private var allRegistrations: [InstrumentRegistrationRecord] { store.snapshot?.registrations ?? [] }
    private var registrations: [InstrumentRegistrationRecord] {
        allRegistrations.filter { r in
            (showRetired || !r.retired) && (search.isEmpty || r.asset.localizedCaseInsensitiveContains(search) || r.displayName.localizedCaseInsensitiveContains(search) || r.assetClass.localizedCaseInsensitiveContains(search) || r.providerID.localizedCaseInsensitiveContains(search))
        }
    }
    private var selectedRegistrationID: Binding<String?> { Binding(get:{selection.selectedRegistrationID},set:{selection.select($0)}) }
    private var registration: InstrumentRegistrationRecord? { registrations.first { $0.id == selection.selectedRegistrationID } }
    private var selectedRegistrations: [InstrumentRegistrationRecord] { guard let asset=registration?.asset else{return []};return allRegistrations.filter { $0.asset == asset } }
    private var lane: LaneRecord? { store.snapshot?.lanes.first { $0.asset == registration?.asset && $0.timeframe == registration?.timeframe } }
    private var truth: EstateTruthLane? { store.estateTruth?.truthMatrix.first { $0.symbol == registration?.asset && $0.timeframe == registration?.timeframe } }
    private var canMutate: Bool { registration?.retired == false && store.activeOperationID == nil }
    private var checksum: String { guard let file, let data=try? Data(contentsOf:file) else{return "—"};return SHA256.hash(data:data).map{String(format:"%02x",$0)}.joined() }

    var body: some View {
        HStack(spacing:0) {
            VStack(alignment:.leading,spacing:10) {
                TextField("Search active instruments",text:$search).textFieldStyle(.roundedBorder)
                Toggle("Show Retired",isOn:$showRetired)
                List(registrations,selection:selectedRegistrationID) { r in
                    VStack(alignment:.leading,spacing:3) {
                        Text(r.displayName).fontWeight(.semibold)
                        Text("\(r.asset) · \(r.assetClass)").font(.caption).foregroundStyle(.secondary)
                        Text(r.retired ? "RETIRED" : "\(r.providerID) · \(r.timeframe)").font(.caption2).foregroundStyle(r.retired ? .orange:.secondary)
                    }.tag(r.id)
                }
            }.frame(width:280).padding()
            Divider()
            Group { if store.dataOperationsMode == .history { OperationsView(filterAsset:registration?.asset) } else { ScrollView { VStack(alignment:.leading,spacing:16) {
                WorkspaceHeader(title:"Data Operations",purpose:"Add, update, import, retire, and review evidence.")
                Picker("Mode",selection:$store.dataOperationsMode){ForEach(DataOperationsMode.allCases){Text($0.rawValue).tag($0)}}.pickerStyle(.segmented)
                if let r=registration {
                    header(r)
                    if r.retired { retireView(r) }
                    else {
                        switch store.dataOperationsMode { case .fetch: fetchView(r);case .importFile: importView(r);case .retire: retireView(r);case .history:EmptyView() }
                    }
                } else if registrations.isEmpty { ContentUnavailableView("No matching active instruments",systemImage:"magnifyingglass",description:Text("Clear the search or enable Show Retired.")) }
                else { ContentUnavailableView("Select a registered instrument",systemImage:"arrow.left",description:Text("Choose one registration from the populated authority list.")) }
                if let localError { Label(localError,systemImage:"exclamationmark.triangle").foregroundStyle(.red) }
                readableResult
            }.padding().frame(maxWidth:900,alignment:.leading) } } }
        }
        .onAppear { store.clearCurrentOperationResult();applyNavigationContext() }
        .onChange(of:store.snapshot){reconcileSelection()}
        .onChange(of:search){reconcileSelection()}
        .onChange(of:showRetired){reconcileSelection()}
        .onChange(of:selection.selectedRegistrationID){resetInstrumentContext()}
        .onChange(of:store.dataOperationsMode){isolateOperationState()}
        .onChange(of:fromDate){store.clearCurrentOperationResult()}
        .onChange(of:throughDate){store.clearCurrentOperationResult()}
        .onChange(of:intent){store.clearCurrentOperationResult()}
        .onChange(of:conflict){store.clearCurrentOperationResult()}
        .onChange(of:file){fileSelectionID=UUID();isolateOperationState()}
        .sheet(isPresented:$reviewing){reviewSheet}
        .sheet(item:$retirementImpact){impact in RetirementOperationReview(impact:impact,onConfirm:confirmRetirement)}
        .sheet(item:$retirementReceipt){receipt in RetirementOperationSuccess(receipt:receipt){retirementReceipt=nil}}
    }

    private func header(_ r:InstrumentRegistrationRecord)->some View { GroupBox { HStack(alignment:.top) { VStack(alignment:.leading,spacing:5) { Text("\(r.displayName) — \(r.asset)").font(.title2.bold());Text("\(r.assetClass) · \(r.representationType)");Text(r.retired ? "Retired":"Active").foregroundStyle(r.retired ? .orange:.green);Facts([("Registered lanes",selectedRegistrations.map(\.timeframe).joined(separator:", ")),("Evidence",(lane?.barCount ?? 0)>0 ? "Present":"None"),("Truth Score",truth.map{String($0.truthState.truthScore)} ?? "Unknown"),("CAODT",truth?.truthState.caodt ?? "—")]) };Spacer();if !r.retired{Button("Retire Instrument",role:.destructive){store.dataOperationsMode = .retire}} } } }

    private func fetchView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:14) {
        laneMatrix(r)
        Picker("Intent",selection:$intent){ForEach(FetchIntent.allCases,id:\.self){Text($0.rawValue).tag($0)}}.pickerStyle(.segmented)
        if !hasProviderMapping { unmappedFetchView(r) }
        if intent == .initial { Label("Provider resolution requests best-available D1 history, targeting 20 years where supplied.",systemImage:"clock.arrow.circlepath").foregroundStyle(.secondary) }
        else { customRangeControls;if intent == .update { Label("Includes a five-session reconciliation overlap. Preserve remains authoritative.",systemImage:"arrow.triangle.2.circlepath").foregroundStyle(.secondary) } }
        Picker("Conflict policy",selection:$conflict){ForEach(ConflictMode.allCases,id:\.self){Text($0.rawValue.capitalized).tag($0)}}
        Text("Preserve keeps prior evidence and records the conflicting candidate without silent overwrite.").font(.caption).foregroundStyle(.secondary)
        Button("Review Data Operation"){prepareReview(r)}.buttonStyle(.borderedProminent).disabled(!customPlanValid)
        if !customPlanValid { Label(customValidationMessage,systemImage:"exclamationmark.triangle").foregroundStyle(.red) }
    } }

    private func unmappedFetchView(_ r:InstrumentRegistrationRecord)->some View { GroupBox("Provider Resolution") { VStack(alignment:.leading,spacing:10) { Text("No provider has been confirmed yet.");if store.activeOperationID != nil{HStack{ProgressView();Text("Trying Twelve Data, then Yahoo Finance…")}};HStack{Button("Find Provider and Fetch Full History"){intent = .initial;throughDate=latestCompletedBoundary;fromDate=Calendar.current.date(byAdding:.year,value:-20,to:throughDate)!;prepareReview(r)}.buttonStyle(.borderedProminent).disabled(!canMutate);Button("Import CSV"){store.dataOperationsMode = .importFile};Button("Retire Instrument",role:.destructive){store.dataOperationsMode = .retire}} } } }

    private var customRangeControls:some View { VStack(alignment:.leading,spacing:10) { HStack { DatePicker("Inclusive From Date",selection:$fromDate,displayedComponents:.date);Button("Paste From Date"){pasteDate(toFrom:true)};DatePicker("Inclusive Through Date",selection:$throughDate,in:...latestCompletedBoundary,displayedComponents:.date);Button("Paste Through Date"){pasteDate(toFrom:false)} };if let dateInterpretation{Label(dateInterpretation,systemImage:"calendar.badge.checkmark").foregroundStyle(.orange)};Text("Latest completed D1 boundary: \(ControlledDateRange.iso(latestCompletedBoundary))").font(.caption).foregroundStyle(.secondary);HStack{Text("Canonical plan: \(dateRange.fromISO) → \(dateRange.throughISO)").font(.caption.monospaced()).foregroundStyle(.secondary);Spacer();Menu("Presets"){Button("Last 7 Days"){applyPreset(days:7)};Button("Last 30 Days"){applyPreset(days:30)};Button("Year to Date"){let c=Calendar.current;fromDate=c.date(from:c.dateComponents([.year],from:latestCompletedBoundary))!;throughDate=latestCompletedBoundary};Button("Last 12 Months"){fromDate=Calendar.current.date(byAdding:.year,value:-1,to:latestCompletedBoundary)!;throughDate=latestCompletedBoundary};if let latest=lane?.latestBar{Button("Since Latest Stored"){fromDate=Date(timeIntervalSince1970:TimeInterval(latest));throughDate=latestCompletedBoundary}}}} } }

    private func unavailableCapability(title:String,reason:String)->some View { GroupBox("Capability unavailable; safe fallback active") { VStack(alignment:.leading,spacing:10) { Label(title,systemImage:"exclamationmark.triangle").foregroundStyle(.orange);Text(reason).foregroundStyle(.secondary);Facts([("Affected scope","\(registration?.asset ?? "Instrument"):D1 — selected convenience operation"),("What remains safe","Bounded D1 fetch, Import File, and Retire")]);HStack{Button("Choose Custom Range"){intent = .custom};Button("Import File"){store.dataOperationsMode = .importFile}.buttonStyle(.borderedProminent)};DisclosureGroup("Technical reason"){Text("The current implementation cannot prove a provider terminal boundary or calculate an approved automatic overlap. Ratified timeframe authority remains present; this is an implementation incompatibility.").font(.caption)} } } }

    private func importView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:14) {
        laneMatrix(r);Button("Choose CSV…"){file=PanelService.chooseCSV()}
        if let file { GroupBox("Import Preview") { Facts([("File Name",file.lastPathComponent),("Byte Size","\((try? file.resourceValues(forKeys:[.fileSizeKey]).fileSize) ?? 0)"),("Checksum",checksum),("Detected Format","CSV"),("Selected Instrument",r.asset),("Selected Timeframe",r.timeframe),("Detected Row Count",rowCount(file)),("Timestamp Range","Validated by existing ingestion authority")]) } }
        Picker("Conflict policy",selection:$conflict){ForEach(ConflictMode.allCases,id:\.self){Text($0.rawValue.capitalized).tag($0)}}
        Button("Review Import"){prepareReview(r)}.buttonStyle(.borderedProminent).disabled(!canMutate || file==nil)
    } }

    private func retireView(_ r:InstrumentRegistrationRecord)->some View { VStack(alignment:.leading,spacing:12) { if r.retired { Label("Retired authority is audit-only. Provider acquisition and import are disabled.",systemImage:"archivebox").foregroundStyle(.orange);Facts([("Lifecycle","RETIRED"),("Serving","HISTORICAL_ONLY · NOT_SERVED"),("Acquisition","ACQUISITION_DISABLED"),("Evidence","Preserved for audit")]) } else { Text("Uses the reviewed SPEC-013 impact, supersession, quarantine, acquisition shutdown, and receipt service.");Button("Review Retirement Impact",role:.destructive){planRetirement(r)}.disabled(store.activeOperationID != nil) } } }

    private func laneMatrix(_ r:InstrumentRegistrationRecord)->some View { GroupBox("Timeframe Lane Matrix") { Grid(alignment:.leading,horizontalSpacing:18,verticalSpacing:8) { GridRow{ForEach(["Timeframe","Registration","Evidence","Latest","Default intent","Selectable"],id:\.self){Text($0).font(.caption.bold())}};Divider().gridCellColumns(6);GridRow{Text(r.timeframe).monospaced();Text(r.registrationStatus);Text((lane?.barCount ?? 0)>0 ? "Yes":"No");Text(latestText);Text((lane?.barCount ?? 0)>0 ? "Update D1":"Fetch Full D1 History");Text(r.retired ? "No — retired":"Yes")} }.frame(maxWidth:.infinity,alignment:.leading) } }

    @ViewBuilder private var readableResult:some View {
        if let plan=completedPlan,plan.matches(mode:store.dataOperationsMode,instrument:registration?.asset,timeframe:registration?.timeframe,fileChecksum:file == nil ? nil:checksum),let owned=store.currentOperationResult,owned.planRevision==plan.id {
            let result=owned.result
            GroupBox(result.exitCode==0 ? "Data Operation Complete":"Data Operation Failed") {
                VStack(alignment:.leading,spacing:8) {
                    Label(result.exitCode==0 ? "Authority service completed successfully":"No evidence was written.",systemImage:result.exitCode==0 ? "checkmark.circle.fill":"xmark.octagon").foregroundStyle(result.exitCode==0 ? .green:.red)
                    if result.exitCode==0,let json=result.JSON { Facts(readableFacts(json)) }
                    else { Facts([("Rows inserted","0"),("Rows unchanged","0"),("Conflicts preserved","0"),("Raw blocks created","0")]);Text(operationFailure(result,plan:plan));if plan.mode == .fetch{HStack{Button("Import CSV"){store.dataOperationsMode = .importFile};Button("Try Again"){isolateOperationState()}}} }
                    DisclosureGroup("Technical Details"){Text(result.stdout.isEmpty ? result.stderr:result.stdout).font(.caption.monospaced()).textSelection(.enabled)}
                }
            }
        }
    }
    private func readableFacts(_ json:[String:Any])->[(String,String)] {
        let common=[("Instrument",json["asset"] as? String ?? registration?.asset ?? "—"),("Timeframe",json["timeframe"] as? String ?? registration?.timeframe ?? "—")]
        let counts=[("Rows inserted","\(json["inserted"] as? Int ?? 0)"),("Rows unchanged","\(json["unchanged"] as? Int ?? 0)"),("Conflicts preserved","\(json["conflicts_preserved"] as? Int ?? 0)"),("Raw block",json["raw_block_id"] as? String ?? "—")]
        if store.dataOperationsMode == .importFile { return common+counts }
        return common+[("Requested range","\(json["from_date"] as? String ?? dateRange.fromISO) → \(json["through_date"] as? String ?? dateRange.throughISO)"),("Actual range",json["actual_range"] as? String ?? json["canonical_high_watermark"] as? String ?? "No returned bars"),("Rows received","\(json["received"] as? Int ?? 0)")]+counts+[("CAODT",truth?.truthState.caodt ?? "Refresh pending"),("Truth Score",truth.map{String($0.truthState.truthScore)} ?? "Refresh pending"),("Warnings",(json["warnings"] as? [String])?.joined(separator:", ") ?? "None")]
    }

    @ViewBuilder private var reviewSheet:some View { if let plan=reviewedPlan { VStack(alignment:.leading,spacing:16) { Text(plan.mode == .importFile ? "Review Import":"Review Data Operation").font(.title);Facts([("Instrument",plan.instrument),("Source",plan.mode == .importFile ? "Manual file import":"Automatic provider resolution"),("Lane",plan.timeframe),("Intent",plan.mode == .importFile ? "IMPORT_FILE":intent.rawValue),("Requested range",plan.mode == .importFile ? URL(fileURLWithPath:plan.filePath ?? "").lastPathComponent:"\(plan.from ?? "—") → \(plan.through ?? "—") inclusive"),("File checksum",plan.fileChecksum ?? "—"),("Conflict Policy",plan.conflict.rawValue.capitalized)]);HStack{Button("Cancel",role:.cancel){reviewing=false;reviewedPlan=nil};Spacer();Button(plan.mode == .importFile ? "Confirm Import":"Run Data Operation"){runReviewed(plan)}.buttonStyle(.borderedProminent)} }.padding(24).frame(minWidth:620) } }

    private var latestText:String { lane?.latestBar.map{Date(timeIntervalSince1970:TimeInterval($0)).formatted(date:.numeric,time:.shortened)} ?? "—" }
    private var latestCompletedD1:String { Calendar.current.date(byAdding:.day,value:-1,to:Date())!.formatted(.iso8601.year().month().day()) }
    private var latestCompletedBoundary:Date{Calendar.current.startOfDay(for:Calendar.current.date(byAdding:.day,value:-1,to:Date())!)}
    private var dateRange:ControlledDateRange{.init(from:fromDate,through:throughDate,completedBoundary:latestCompletedBoundary)}
    private var hasProviderMapping:Bool{!(registration?.providerID.isEmpty ?? true) && !(registration?.providerSymbol.isEmpty ?? true)}
    private var customPlanValid:Bool{canMutate && (intent == .initial || dateRange.validation == .valid)}
    private var customValidationMessage:String{switch dateRange.validation{case .valid:return "Choose a valid plan before reviewing.";case .reversed:return "The start date must be on or before the through date.";case .futureBoundary(let maximum):return "The through date exceeds the latest completed D1 boundary. Maximum permitted date: \(maximum).";case .contractLimit(let days):return intent == .initial ? "Provider resolution will use the best permitted history window.":"The range exceeds the provider contract limit of \(days) calendar days."}}
    private func applyPreset(days:Int){throughDate=latestCompletedBoundary;fromDate=Calendar.current.date(byAdding:.day,value:-(days-1),to:throughDate)!}
    private func pasteDate(toFrom:Bool){guard let text=NSPasteboard.general.string(forType:.string),let parsed=ControlledDateParser.parse(text)else{dateInterpretation="The pasted date could not be understood. Choose a date from the calendar.";return};if toFrom{fromDate=parsed.date}else{throughDate=parsed.date};dateInterpretation=parsed.interpretation ?? "Normalised to \(parsed.canonicalISO)."}
    private func rowCount(_ url:URL)->String{guard let text=try? String(contentsOf:url,encoding:.utf8)else{return "Unknown"};return String(max(0,text.split(whereSeparator:\.isNewline).count-1))}
    private func reconcileSelection(){selection.reconcile(visibleRegistrationIDs:Set(registrations.map(\.id)))}
    private func applyNavigationContext(){guard let asset=store.acquisitionAsset else{return};store.acquisitionAsset=nil;let id=registrations.first(where:{$0.asset==asset})?.id;selection.applyNavigationContext(id,visibleRegistrationIDs:Set(registrations.map(\.id)))}
    private func resetInstrumentContext(){throughDate=latestCompletedBoundary;if (lane?.barCount ?? 0)==0{intent = .initial;fromDate=Calendar.current.date(byAdding:.year,value:-20,to:throughDate)!}else if let latest=lane?.latestBar{intent = .update;fromDate=reconciliationStart(latest)}else{intent = .custom;fromDate=Calendar.current.date(byAdding:.day,value:-29,to:throughDate)!};file=nil;reviewing=false;retirementImpact=nil;localError=nil;dateInterpretation=nil;conflict = .preserve;isolateOperationState()}
    private func reconciliationStart(_ timestamp:Int64)->Date{var date=Calendar.current.startOfDay(for:Date(timeIntervalSince1970:TimeInterval(timestamp)));var sessions=0;while sessions<5{date=Calendar.current.date(byAdding:.day,value:-1,to:date)!;if registration?.assetClass=="CRYPTO" || !Calendar.current.isDateInWeekend(date){sessions += 1}};return date}
    private func nextExpectedSession(after timestamp:Int64?)->Date?{guard let timestamp else{return nil};var date=Calendar.current.startOfDay(for:Date(timeIntervalSince1970:TimeInterval(timestamp))).addingTimeInterval(86400);if registration?.assetClass != "CRYPTO"{while Calendar.current.isDateInWeekend(date){date=date.addingTimeInterval(86400)}};return date}
    private func prepareReview(_ r:InstrumentRegistrationRecord){store.clearCurrentOperationResult();let plan=ReviewedDataOperationPlan(id:store.currentPlanRevision,mode:store.dataOperationsMode,instrument:r.asset,timeframe:r.timeframe,filePath:file?.path,fileChecksum:file == nil ? nil:checksum,fileSelectionID:store.dataOperationsMode == .importFile ? fileSelectionID:nil,from:store.dataOperationsMode == .fetch ? dateRange.fromISO:nil,through:store.dataOperationsMode == .fetch ? dateRange.throughISO:nil,conflict:conflict);reviewedPlan=plan;completedPlan=nil;reviewing=true}
    private func runReviewed(_ plan:ReviewedDataOperationPlan){reviewing=false;reviewedPlan=nil;guard let operation=plan.intent else{localError="The reviewed operation plan is incomplete.";return};Task{await store.run(operation);if plan.matches(mode:store.dataOperationsMode,instrument:registration?.asset,timeframe:registration?.timeframe,fileChecksum:file == nil ? nil:checksum){completedPlan=plan}}}
    private func isolateOperationState(){reviewing=false;reviewedPlan=nil;completedPlan=nil;store.clearCurrentOperationResult()}
    private func operationFailure(_ result:ProcessResult,plan:ReviewedDataOperationPlan)->String{let payload=result.JSON;let reason=(payload?["error"] as? String) ?? (result.stderr.isEmpty ? result.stdout:result.stderr);return plan.mode == .importFile ? "Import rejected: \(reason)":"No provider returned valid data."}
    private func planRetirement(_ r:InstrumentRegistrationRecord){localError=nil;Task{await store.run(.retirementPlan(asset:r.asset,scope:"WHOLE_INSTRUMENT",lanes:selectedRegistrations.map(\.timeframe)));guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let impact=try? JSONDecoder().decode(RetirementImpact.self,from:Data(text.utf8))else{localError=store.operationError ?? "Retirement impact could not be loaded";return};retirementImpact=impact}}
    private func confirmRetirement(_ impact:RetirementImpact,_ reason:String,_ note:String,_ confirmation:String){retirementImpact=nil;Task{await store.run(.retireInstrument(asset:impact.canonicalInstrument,scope:impact.scope,lanes:impact.selectedLanes,reason:reason,note:note,confirmation:confirmation));guard store.lastProcessResult?.exitCode==0,let text=store.lastProcessResult?.stdout,let receipt=try? JSONDecoder().decode(RetirementReceipt.self,from:Data(text.utf8))else{localError=store.operationError ?? "Retirement failed";return};retirementReceipt=receipt}}
}

private struct RetirementOperationReview:View { let impact:RetirementImpact;let onConfirm:(RetirementImpact,String,String,String)->Void;@Environment(\.dismiss) var dismiss;@State private var reason="INCORRECT_INSTRUMENT_IDENTITY";@State private var note="";@State private var confirmation="";let reasons=["INCORRECT_INSTRUMENT_IDENTITY","INCORRECT_PAIR_ORIENTATION","INCORRECT_PROVIDER_MAPPING","WRONG_SYMBOL","DUPLICATE_REGISTRATION","ERRONEOUS_OPERATOR_REGISTRATION","INVALID_VENUE_OR_LISTING","PROVIDER_EVIDENCE_MISMATCH","OTHER_REVIEWED_REASON"];var body:some View{VStack(alignment:.leading,spacing:14){Text("Retire \(impact.canonicalInstrument)").font(.title);Text("SPEC-013 Impact Review").font(.headline);Picker("Controlled reason",selection:$reason){ForEach(reasons,id:\.self){Text($0.replacingOccurrences(of:"_",with:" ").capitalized).tag($0)}};TextField("Operator note",text:$note);Facts([("Active lanes",impact.activeTimeframeLanes.joined(separator:", ")),("Evidence counts","\(impact.canonicalBars) bars · \(impact.rawEvidenceBlocks) raw blocks"),("Acquisition history","\(impact.completedAcquisitionRuns) completed runs"),("Truth state",impact.currentServingState),("Operational effects","Acquisition disabled; active serving excluded"),("Preservation guarantees","Raw evidence and audit history preserved")]);if impact.typedConfirmationRequired{Text("Type \(impact.requiredConfirmation ?? "") to confirm").fontWeight(.semibold);TextField(impact.requiredConfirmation ?? "",text:$confirmation)};HStack{Button("Cancel",role:.cancel){dismiss()};Spacer();Button("Confirm Retirement",role:.destructive){dismiss();onConfirm(impact,reason,note,confirmation)}.disabled(impact.typedConfirmationRequired && confirmation.trimmingCharacters(in:.whitespaces).uppercased() != impact.requiredConfirmation)}}.padding(24).frame(minWidth:680)}}
private struct RetirementOperationSuccess:View { let receipt:RetirementReceipt;let done:()->Void;@Environment(\.dismiss) var dismiss;var body:some View{VStack(alignment:.leading,spacing:14){Text("\(receipt.canonicalInstrument) Retired").font(.title);Label("Acquisition disabled; evidence preserved; active serving removed",systemImage:"checkmark.circle.fill").foregroundStyle(.green);Facts([("Retirement ID",receipt.retirementID),("Reason",receipt.reason),("Authority",receipt.newAuthorityState),("Completed",receipt.completedTimestamp)]);Button("Done"){dismiss();done()}.buttonStyle(.borderedProminent)}.padding(24).frame(minWidth:620)}}
