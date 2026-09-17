import OperationsCore
import SwiftUI

struct RoutingProvidersView:View {
    @EnvironmentObject private var store:ConsoleStore
    @State private var search=""
    @State private var selectedLaneID:String?
    @State private var providerOrder:[String]=[]
    @State private var disabled:Set<String>=[]
    @State private var reason=""
    @State private var mode=0
    private let matrixTimeframes=["D1","H1","M30","M15","M5"]

    private var lanes:[RoutingLane] {
        let values=store.routingSnapshot?.lanes ?? []
        guard !search.isEmpty else{return values}
        return values.filter{$0.symbol.localizedCaseInsensitiveContains(search) || $0.timeframe.localizedCaseInsensitiveContains(search) || ($0.assetClass ?? "").localizedCaseInsensitiveContains(search)}
    }
    private var selected:RoutingLane? { store.routingSnapshot?.lanes.first{$0.id==selectedLaneID} }
    private var symbols:[String] { Array(Set(lanes.map(\.symbol))).sorted() }

    var body:some View {
        VStack(alignment:.leading,spacing:12) {
            HStack {
                WorkspaceHeader(title:"Routing & Providers",purpose:"Control future acquisition routes by symbol and timeframe. Historical evidence is never rewritten.")
                Spacer()
                if let snapshot=store.routingSnapshot { Text("Revision \(snapshot.routingRevision.prefix(10)) · \(SchedulerFormatting.timestamp(snapshot.generatedAtUTC))").font(.caption.monospaced()).foregroundStyle(.secondary) }
                if store.routingLoading { ProgressView().controlSize(.small) }
                Button("Refresh"){Task{await store.refreshRouting()}}
            }
            Picker("Routing workspace",selection:$mode){Text("Symbol routing").tag(0);Text("Provider catalogue").tag(1)}
                .pickerStyle(.segmented).frame(maxWidth:430)
            if let error=store.routingError { Text(error).foregroundStyle(.red).textSelection(.enabled) }
            if mode==0 { routingWorkspace } else { providerCatalogue }
        }.padding()
        .task { if store.routingSnapshot==nil { await store.refreshRouting() };acceptRequestedLane() }
        .onChange(of:store.routingRequestedLaneID){_,_ in acceptRequestedLane()}
        .onChange(of:selectedLaneID){_,_ in loadEditor()}
    }

    private var routingWorkspace:some View {
        HSplitView {
            VStack(alignment:.leading,spacing:8) {
                TextField("Filter symbol, market, timeframe, or provider",text:$search).textFieldStyle(.roundedBorder)
                ScrollView([.horizontal,.vertical]) {
                    LazyVStack(alignment:.leading,spacing:6) {
                        HStack(spacing:8) {
                            Text("Symbol").font(.caption.bold()).frame(width:82,alignment:.leading)
                            ForEach(matrixTimeframes,id:\.self){Text($0).font(.caption.bold()).frame(width:112)}
                            Text("Attention").font(.caption.bold()).frame(width:72,alignment:.leading)
                        }
                        Divider()
                        ForEach(symbols,id:\.self) { symbol in
                            HStack(spacing:8) {
                                Text(symbol).font(.caption.bold()).frame(width:82,alignment:.leading)
                                ForEach(matrixTimeframes,id:\.self) { timeframe in
                                    routeCell(symbol:symbol,timeframe:timeframe)
                                }
                                let attention=lanes.filter{$0.symbol==symbol}.contains{isAttention($0)}
                                Label(attention ? "Review":"Ready",systemImage:attention ? "exclamationmark.triangle.fill":"checkmark.circle.fill")
                                    .font(.caption2).foregroundStyle(attention ? .orange:.green).frame(width:72,alignment:.leading)
                            }
                        }
                    }.padding(.vertical,4)
                }
            }.frame(minWidth:650,idealWidth:720,maxWidth:820)
            Group {
                if let lane=selected { laneEditor(lane) }
                else { ContentUnavailableView("Select a routing lane",systemImage:"arrow.triangle.branch",description:Text("Choose a symbol and timeframe to inspect or change its reviewed provider sequence.")) }
            }.frame(minWidth:520,maxWidth:.infinity,maxHeight:.infinity)
        }
    }

    @ViewBuilder private func routeCell(symbol:String,timeframe:String)->some View {
        if let lane=lanes.first(where:{$0.symbol==symbol && $0.timeframe==timeframe}) {
            Button { selectedLaneID=lane.id } label: {
                VStack(alignment:.leading,spacing:2) {
                    Text(routeLabel(lane)).font(.caption2.bold()).lineLimit(2)
                    Text(!lane.active ? "Inactive":lane.inheritance=="LANE_OVERRIDE" ? "Lane override":lane.derivationState.hasPrefix("DERIVED") ? "Derived":"Estate default")
                        .font(.system(size:9)).foregroundStyle(.secondary)
                }.frame(width:104,alignment:.leading).frame(minHeight:32,alignment:.leading).padding(4)
                    .background(selectedLaneID==lane.id ? Color.accentColor.opacity(0.18):isAttention(lane) ? Color.orange.opacity(0.10):Color.clear,in:RoundedRectangle(cornerRadius:6))
            }.buttonStyle(.plain).help("\(lane.symbol) \(lane.timeframe) · revision \(store.routingSnapshot?.routingRevision ?? "—")")
        } else {
            Text("—").font(.caption).foregroundStyle(.tertiary).frame(width:112)
        }
    }

    private func routeLabel(_ lane:RoutingLane)->String {
        if !lane.active { return "Inactive" }
        if lane.derivationState.hasPrefix("DERIVED") { return "Derived from M5" }
        if lane.effectiveProviderOrder.isEmpty { return "No provider" }
        return lane.effectiveProviderOrder.map{$0.replacingOccurrences(of:"_",with:" ").replacingOccurrences(of:" FINANCE",with:"")}.joined(separator:" → ")
    }

    private func isAttention(_ lane:RoutingLane)->Bool {
        lane.active && (lane.routeState != "EXECUTABLE" || lane.attemptState.count >= lane.attemptState.cap)
    }

    private func laneEditor(_ lane:RoutingLane)->some View {
        ScrollView {
            VStack(alignment:.leading,spacing:16) {
                HStack(alignment:.firstTextBaseline) {
                    Text("\(lane.symbol) · \(lane.timeframe)").font(.title2.bold())
                    Text(lane.inheritance.replacingOccurrences(of:"_",with:" ").capitalized).font(.caption.bold()).padding(.horizontal,8).padding(.vertical,3).background(.quaternary,in:Capsule())
                    Spacer()
                    Text(lane.routeState.replacingOccurrences(of:"_",with:" ").capitalized).foregroundStyle(lane.routeState=="NO_PROVIDER_FAIL_CLOSED" ? .red:.secondary)
                }
                if lane.derivationState.hasPrefix("DERIVED") {
                    Label("This lane is derived from M5. Its source route is shown for inspection.",systemImage:"function").foregroundStyle(.secondary)
                }
                if !lane.active {
                    Label("This historical lane is inactive (\(lane.ineligibilityReason ?? lane.lifecycleState ?? "not active")) and cannot be routed or acquired.",systemImage:"archivebox").foregroundStyle(.secondary)
                }
                GroupBox("Ordered reviewed route") {
                    VStack(spacing:0) {
                        ForEach(Array(providerOrder.enumerated()),id:\.element) { index,provider in
                            let candidate=lane.candidates.first{$0.provider==provider}
                            HStack(spacing:12) {
                                Text("\(index+1)").font(.caption.monospaced()).foregroundStyle(.secondary).frame(width:20)
                                Toggle("",isOn:Binding(get:{!disabled.contains(provider)},set:{enabled in if enabled{disabled.remove(provider)}else{disabled.insert(provider)};store.routingValidation=nil})).labelsHidden().disabled(!lane.active)
                                VStack(alignment:.leading,spacing:3) {
                                    Text(provider.replacingOccurrences(of:"_",with:" ")).fontWeight(.semibold)
                                    Text(candidate?.providerSymbol ?? "No provider symbol").font(.caption.monospaced()).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(candidate?.capabilityState.replacingOccurrences(of:"_",with:" ").capitalized ?? "Unknown").font(.caption).foregroundStyle(.secondary)
                                Button{move(index,-1)}label:{Image(systemName:"arrow.up")}.disabled(!lane.active || index==0)
                                Button{move(index,1)}label:{Image(systemName:"arrow.down")}.disabled(!lane.active || index==providerOrder.count-1)
                            }.padding(.vertical,9)
                            if index<providerOrder.count-1 { Divider() }
                        }
                    }.padding(.horizontal,8)
                }
                if !providerOrder.isEmpty && disabled.count==providerOrder.count {
                    Label("No provider — this lane will fail closed until its route is changed.",systemImage:"exclamationmark.octagon.fill").foregroundStyle(.red)
                }
                TextField("Reason for this routing change",text:$reason).textFieldStyle(.roundedBorder).disabled(!lane.active)
                HStack {
                    Button("Preview change"){Task{_ = await store.previewRouting(symbol:lane.symbol,timeframe:lane.timeframe,providers:providerOrder,disabled:Array(disabled),reason:reason)}}.buttonStyle(.borderedProminent).disabled(!lane.active || reason.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || store.routingLoading)
                    Button("Preview estate defaults"){Task{_ = await store.previewRoutingRestore(symbol:lane.symbol,timeframe:lane.timeframe,reason:reason)}}.disabled(!lane.active || lane.inheritance != "LANE_OVERRIDE" || reason.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty || store.routingLoading)
                    Spacer()
                }
                if let validation=store.routingValidation,validation.lane==lane.id {
                    GroupBox("Activation preview") {
                        VStack(alignment:.leading,spacing:8) {
                            Text(validation.activationGate == nil && validation.valid ? "Ready to activate":"Review required").font(.headline).foregroundStyle(validation.activationGate == nil && validation.valid ? .green:.orange)
                            if validation.activationGate != nil {
                                Label("Route preview is available, but activation is paused until fresh Fusion MT5 receipts verify both the index and non-index authority references.",systemImage:"lock.shield").font(.caption).foregroundStyle(.orange)
                            }
                            Text("Before: \(validation.beforeOrder.joined(separator:" → "))").font(.caption)
                            Text("After: \(validation.afterOrder.isEmpty ? "No provider — fail closed":validation.afterOrder.joined(separator:" → "))").font(.caption)
                            ForEach(validation.warnings,id:\.self){Text($0.replacingOccurrences(of:"_",with:" ").capitalized).foregroundStyle(.orange)}
                            ForEach(validation.issues,id:\.self){Text($0).foregroundStyle(.red)}
                            Button("Activate routing revision"){Task{_ = await store.activateRoutingDraft()}}.buttonStyle(.borderedProminent).disabled(!validation.valid || validation.activationGate != nil || store.routingLoading)
                        }.frame(maxWidth:.infinity,alignment:.leading)
                    }
                }
                GroupBox("Current authority") {
                    VStack(alignment:.leading,spacing:5) {
                        Text("Revision \(store.routingSnapshot?.routingRevision.prefix(12) ?? "—")").font(.caption.monospaced())
                        Text("Last used: \(lane.lastUsed?.provider ?? "No recent receipt") \(lane.lastUsed?.providerSymbol ?? "")").font(.caption)
                        Text("Attempts: \(lane.attemptState.count) of \(lane.attemptState.cap)\(lane.attemptState.boundary.map { " · \($0)" } ?? "")").font(.caption)
                        if let next=lane.attemptState.nextAction { Text("Next action: \(next.replacingOccurrences(of:"_",with:" ").capitalized)").font(.caption) }
                        if let reason=lane.operatorReason { Text("Override reason: \(reason)").font(.caption) }
                    }.frame(maxWidth:.infinity,alignment:.leading)
                }
            }.padding(.horizontal,18).padding(.bottom,20)
        }
    }

    private var providerCatalogue:some View {
        ScrollView {
            LazyVGrid(columns:[GridItem(.adaptive(minimum:310),spacing:14)],spacing:14) {
                ForEach(store.routingSnapshot?.providers ?? []) { provider in
                    GroupBox(provider.provider.replacingOccurrences(of:"_",with:" ")) {
                        VStack(alignment:.leading,spacing:7) {
                            Label(provider.enabled ? "Enabled estate-wide":"Disabled estate-wide",systemImage:provider.enabled ? "checkmark.circle.fill":"pause.circle.fill").foregroundStyle(provider.enabled ? .green:.orange)
                            Text("\(provider.activePrimaryLaneCount) primary · \(provider.activeFallbackLaneCount) fallback · \(provider.reviewedCandidateLaneCount) reviewed lanes").font(.caption)
                            Text("Timeframes: \(provider.supportedTimeframes.joined(separator:", "))").font(.caption)
                            Text("Current estate: \(provider.currentEstateSymbols.isEmpty ? "No reviewed symbols":provider.currentEstateSymbols.joined(separator:", "))").font(.caption).textSelection(.enabled)
                            ForEach(provider.bridgeNodes) { node in
                                VStack(alignment:.leading,spacing:3) {
                                    Text(node.displayName).font(.caption.bold())
                                    Text("\(node.availableLaneCount) available of \(node.reviewedLaneCount) reviewed lanes · \(node.currentEstateSymbols.joined(separator:", "))").font(.caption2).foregroundStyle(.secondary)
                                }.padding(.top,3)
                            }
                            if provider.additionalSymbolsAvailable { Text("Additional symbols may be available. Use Discover to review and admit them; the catalogue intentionally lists only the current Fragarach estate.").font(.caption).foregroundStyle(.secondary) }
                        }.frame(maxWidth:.infinity,alignment:.leading)
                    }
                }
            }
        }
    }

    private func loadEditor() {
        guard let lane=selected else{return}
        providerOrder=lane.candidates.sorted{$0.order<$1.order}.map(\.provider)
        disabled=Set(lane.disabledProviders)
        reason=""
        store.routingValidation=nil
    }
    private func move(_ index:Int,_ offset:Int) {
        let destination=index+offset
        guard providerOrder.indices.contains(index),providerOrder.indices.contains(destination) else{return}
        providerOrder.swapAt(index,destination);store.routingValidation=nil
    }
    private func acceptRequestedLane() {
        if let requested=store.routingRequestedLaneID,store.routingSnapshot?.lanes.contains(where:{$0.id==requested})==true { selectedLaneID=requested }
        else if selectedLaneID==nil { selectedLaneID=store.routingSnapshot?.lanes.first?.id }
    }
}
