import AppKit
import OperationsCore
import SwiftUI

struct ReadOnlyClientsView:View {
    @EnvironmentObject var store:ConsoleStore
    @State private var clientID="macbook-pro"
    @State private var displayName="Ray's MacBook Pro"
    @State private var revokeTarget:ReadOnlyClientRecord?
    @State private var advancedControls=false

    var body:some View {
        ScrollView {
            VStack(alignment:.leading,spacing:18) {
                header
                if let error=store.readOnlyClientsError { errorPanel(error) }
                ReplicaSystemOverviewView(
                    snapshot: store.readOnlyClientsSnapshot,
                    busy: store.readOnlyClientsBusy,
                    onRefresh: { clientID in Task { await store.refreshReplicaClient(clientID) } },
                    onSetPaused: { clientID, paused in Task { await store.setReplicaSyncPaused(clientID, paused: paused) } }
                )
                clientsCard
                transportCard
                publicationCard
                DisclosureGroup("Advanced access recovery",isExpanded:$advancedControls) { addClientCard.padding(.top,8) }
            }.padding(24).frame(maxWidth:1050,alignment:.leading)
        }
        .task {
            await store.refreshReadOnlyClients()
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                await store.refreshReadOnlyClients(silently:true)
            }
        }
        .sheet(isPresented:Binding(get:{store.readOnlyIssuedToken != nil},set:{if !$0{store.clearReadOnlyIssuedToken()}})) { tokenSheet }
        .confirmationDialog("Revoke this read-only client?",isPresented:Binding(get:{revokeTarget != nil},set:{if !$0{revokeTarget=nil}}),titleVisibility:.visible) {
            if let target=revokeTarget {
                Button("Revoke \(target.displayName)",role:.destructive){Task{await store.revokeReadOnlyClient(target.clientID);revokeTarget=nil}}
            }
            Button("Cancel",role:.cancel){revokeTarget=nil}
        } message:{Text("Revocation disables access and destroys the stored token hash. A revoked client cannot be re-enabled.")}
    }

    private var header:some View {
        VStack(alignment:.leading,spacing:5) {
            Text("Fragarach Estate Overview").font(.largeTitle.bold())
            Text("One operational view of the Studio, MacBook Lite, data lanes, and the flow between them.").foregroundStyle(.secondary)
        }
    }

    private var transportCard:some View {
        GroupBox("Replica link") {
            VStack(alignment:.leading,spacing:12) {
                HStack {
                    statusDot(enabled:store.readOnlyClientsSnapshot?.publisherEnabled == true)
                    VStack(alignment:.leading) {
                        Text(store.readOnlyClientsSnapshot?.publisherEnabled == true ? "Studio publisher ready":"Studio publisher paused").font(.headline)
                        Text(serviceDescription).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button(store.readOnlyClientsSnapshot?.publisherEnabled == true ? "Disable Access":"Enable Access") {
                        Task{await store.setReadOnlyPublisherEnabled(!(store.readOnlyClientsSnapshot?.publisherEnabled ?? false))}
                    }.disabled(store.readOnlyClientsBusy)
                    serviceButton
                    Button("Refresh"){Task{await store.refreshReadOnlyClients()}}.disabled(store.readOnlyClientsBusy)
                }
                Divider()
                HStack {
                    Label("Private Tailscale HTTPS transport is commissioned and tested.",systemImage:"checkmark.shield.fill").font(.caption).foregroundStyle(.secondary)
                    Spacer()
                    if store.readOnlyClientsSnapshot?.service.installed == true {
                        Button("Remove Service",role:.destructive){Task{await store.uninstallReadOnlyPublisherService()}}.buttonStyle(.borderless).disabled(store.readOnlyClientsBusy)
                    }
                }
            }.padding(8)
        }
    }

    private var publicationCard:some View {
        GroupBox("Replica publication") {
            VStack(alignment:.leading,spacing:12) {
                if let publication=store.readOnlyClientsSnapshot?.latestPublication {
                    LabeledContent("Latest publication",value:publication.publicationID)
                    LabeledContent("Generated",value:publication.generatedAtUTC)
                    LabeledContent("Authority revision",value:short(publication.authorityRevision))
                    LabeledContent("Payload",value:ByteCountFormatter.string(fromByteCount:Int64(publication.payload.bytes),countStyle:.file))
                    LabeledContent("Lanes",value:"\(publication.lanes.count)")
                    if let latest=publication.lanes.map(\.caodt).compactMap({$0}).max() { LabeledContent("Latest lane CAODT",value:formatEpoch(latest)) }
                    Label("Payload and lane fingerprints verified; signing upgrade remains optional commissioning work.",systemImage:"checkmark.seal").foregroundStyle(.secondary).font(.caption)
                } else { Text("No replica snapshot has been published.").foregroundStyle(.secondary) }
                HStack {
                    if advancedControls {Button("Publish v1 compatibility snapshot"){Task{await store.publishReadOnlySnapshot()}}.disabled(store.readOnlyClientsBusy)}
                    if store.readOnlyClientsBusy { ProgressView().controlSize(.small) }
                    Spacer()
                    Text("Reads canonical evidence; writes only to the replica sidecar.").font(.caption).foregroundStyle(.secondary)
                }
            }.padding(8)
        }
    }

    private var clientsCard:some View {
        GroupBox("Fragarach Lite estate") {
            VStack(alignment:.leading,spacing:10) {
                let clients=store.readOnlyClientsSnapshot?.clients ?? []
                if clients.isEmpty { Text("No Fragarach Lite client is connected.").foregroundStyle(.secondary).padding(8) }
                ForEach(clients) { client in
                    VStack(alignment:.leading,spacing:10) {
                        HStack {
                            statusDot(enabled:client.report?.state == "READY")
                            VStack(alignment:.leading) {
                                Text(client.displayName).font(.headline)
                                Text(client.clientID).font(.caption.monospaced()).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text(client.report?.state ?? "WAITING FOR CHECK-IN").font(.caption.bold()).foregroundStyle(client.report?.state == "READY" ? .green:.orange)
                        }
                        if let report=client.report {
                            HStack(spacing:20) {
                                LabeledContent("Last seen",value:report.receivedAtUTC)
                                LabeledContent("Last sync",value:report.service.lastSyncOutcome ?? "—")
                                LabeledContent("Lanes",value:"\(report.lanes.count)")
                                LabeledContent("Revision",value:report.replica.map{short($0.originAuthorityRevision)} ?? "—")
                            }.font(.caption)
                            if let requests=report.requests,!requests.isEmpty {
                                Label("Lite requests: \(requests.map{"\($0.symbol)/\($0.timeframe)"}.joined(separator:", "))",systemImage:"arrow.up.message.fill").foregroundStyle(.blue).font(.caption)
                            }
                            HStack {
                                Button("Refresh Now"){Task{await store.refreshReplicaClient(client.clientID)}}.buttonStyle(.borderedProminent)
                                Button(client.control?.syncPaused == true ? "Resume Sync":"Pause Sync"){Task{await store.setReplicaSyncPaused(client.clientID,paused:client.control?.syncPaused != true)}}
                                Spacer()
                            }
                            Text("Pause Sync stops new lane artifacts. Verified active lanes remain stored and readable on the MacBook.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Divider()
                            Label("SELECTIVE V2 · active status and progress come from the authoritative per-client request registry.",systemImage:"checkmark.shield.fill")
                                .font(.caption)
                                .foregroundStyle(.green)
                            estateGrid(client:client,report:report)
                        } else {
                            Text("Lite has not checked in yet. The MacBook update will populate service, sync, revision, lane and CAODT status here.").font(.caption).foregroundStyle(.secondary)
                        }
                        if let paused=client.control?.pausedLanes,!paused.isEmpty {Text("Paused: \(paused.map{"\($0.symbol)/\($0.timeframe)"}.joined(separator:", "))").font(.caption).foregroundStyle(.orange)}
                        if advancedControls {
                            HStack {
                                Button(client.enabled ? "Disable Client":"Enable Client"){Task{await store.setReadOnlyClientEnabled(client.clientID,enabled:!client.enabled)}}
                                Button("Rotate Token"){Task{await store.rotateReadOnlyClientToken(client.clientID)}}
                                Button("Revoke",role:.destructive){revokeTarget=client}
                                Spacer()
                                if let issued=client.tokenIssuedAtUTC {Text("Token issued \(issued)").font(.caption2).foregroundStyle(.tertiary)}
                            }
                        }
                    }.padding(10).background(.quaternary.opacity(0.35),in:RoundedRectangle(cornerRadius:8)).disabled(store.readOnlyClientsBusy)
                }
            }.padding(8)
        }
    }

    private var addClientCard:some View {
        GroupBox("Add or recover a replica client") {
            VStack(alignment:.leading,spacing:10) {
                HStack { TextField("Client ID",text:$clientID);TextField("Display name",text:$displayName) }
                HStack {
                    Button("Add Client and Issue Token") {Task{await store.addReadOnlyClient(clientID:clientID,displayName:displayName,symbols:"*",timeframes:"*")}}.disabled(store.readOnlyClientsBusy || clientID.trimmingCharacters(in:.whitespaces).isEmpty || displayName.trimmingCharacters(in:.whitespaces).isEmpty)
                    Spacer()
                    Text("The token is displayed once and is never stored in readable form.").font(.caption).foregroundStyle(.secondary)
                }
            }.padding(8)
        }
    }

    private var tokenSheet:some View {
        VStack(alignment:.leading,spacing:15) {
            Text("Save Client Token Now").font(.title2.bold())
            Text("This token is displayed once. Store it securely on the client Mac. Fragarach retains only its SHA-256 digest.").foregroundStyle(.secondary)
            Text(store.readOnlyIssuedToken ?? "").textSelection(.enabled).font(.system(.body,design:.monospaced)).padding().background(.quaternary,in:RoundedRectangle(cornerRadius:8))
            HStack {
                Button("Copy Token") {NSPasteboard.general.clearContents();NSPasteboard.general.setString(store.readOnlyIssuedToken ?? "",forType:.string)}
                Spacer()
                Button("Done"){store.clearReadOnlyIssuedToken()}.keyboardShortcut(.defaultAction)
            }
        }.padding(24).frame(width:620)
    }

    private func errorPanel(_ value:String)->some View {Label(value,systemImage:"exclamationmark.triangle.fill").foregroundStyle(.red).padding(12).frame(maxWidth:.infinity,alignment:.leading).background(.red.opacity(0.08),in:RoundedRectangle(cornerRadius:8))}
    private func statusDot(enabled:Bool)->some View {Circle().fill(enabled ? Color.green:Color.secondary).frame(width:10,height:10)}
    private var serviceDescription:String {
        guard let service=store.readOnlyClientsSnapshot?.service,let state=service.state else{return "Publisher process not started"}
        let endpoint=[service.host,service.port.map(String.init)].compactMap{$0}.joined(separator:":")
        return endpoint.isEmpty ? state:"\(state) · \(endpoint)"
    }
    @ViewBuilder private var serviceButton:some View {
        let service=store.readOnlyClientsSnapshot?.service
        if service?.installed != true {
            Button("Install Local Service"){Task{await store.installReadOnlyPublisherService()}}.disabled(store.readOnlyClientsBusy)
        } else if service?.running == true {
            Button("Stop Service"){Task{await store.stopReadOnlyPublisherService()}}.disabled(store.readOnlyClientsBusy)
        } else {
            Button("Start Service"){Task{await store.startReadOnlyPublisherService()}}.disabled(store.readOnlyClientsBusy)
        }
    }
    private func short(_ value:String)->String {value.count > 24 ? String(value.prefix(21))+"…":value}
    private func formatEpoch(_ value:Int)->String {Date(timeIntervalSince1970:TimeInterval(value)).formatted(date:.abbreviated,time:.shortened)}
    private func estateGrid(client:ReadOnlyClientRecord,report:ReplicaLiteReport)->some View {
        let authority=store.estateTruth?.truthMatrix ?? []
        let paused=client.control?.pausedLanes ?? []
        let requests=client.requests ?? report.requests ?? []
        return ReplicaEstateGridView(authority:authority,available:client.control?.availableLanes ?? [],actual:report.lanes,paused:paused,requests:requests) { symbol,timeframe,state in
            handleLaneClick(clientID:client.clientID,symbol:symbol,timeframe:timeframe,state:state)
        }
    }
    private func handleLaneClick(clientID:String,symbol:String,timeframe:String,state:ReplicaLaneSyncState) {
        Task {
            switch state {
            case .paused:
                await store.setReplicaLanePaused(clientID,symbol:symbol,timeframe:timeframe,paused:false)
                await store.refreshReplicaClient(clientID)
            case .macbookLocal,.stale:
                await store.setReplicaLanePaused(clientID,symbol:symbol,timeframe:timeframe,paused:true)
            case .requested,.incoming,.error:
                await store.setReplicaLanePaused(clientID,symbol:symbol,timeframe:timeframe,paused:false)
                await store.refreshReplicaClient(clientID)
            case .studioOnly:
                return
            }
        }
    }
}
