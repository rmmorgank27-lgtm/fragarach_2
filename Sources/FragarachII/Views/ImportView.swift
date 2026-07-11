import CryptoKit
import Foundation
import OperationsCore
import SwiftUI

struct ImportView:View {
    @EnvironmentObject var store:ConsoleStore;@State private var file:URL?;@State private var symbol="AUDUSD";@State private var timeframe="D1";@State private var mode=ConflictMode.preserve;@State private var reviewing=false
    var checksum:String{guard let file,let data=try? Data(contentsOf:file) else{return "—"};return SHA256.hash(data:data).map{String(format:"%02x",$0)}.joined()}
    var body:some View{ScrollView{VStack(alignment:.leading,spacing:18){Text("Import Evidence").font(.largeTitle);Text("Manual CSV evidence remains unchanged; the existing SPEC-002 pipeline preserves immutable raw bytes.").foregroundStyle(.secondary);Button("Choose CSV…"){file=PanelService.chooseCSV()};if let file{GroupBox("Selected evidence"){Facts([("File",file.lastPathComponent),("Bytes","\((try? file.resourceValues(forKeys:[.fileSizeKey]).fileSize) ?? 0)"),("SHA-256",checksum)])}};Form{Picker("Asset",selection:$symbol){ForEach(["AUDUSD","XAUUSD","BTCUSD"],id:\.self){Text($0)}};TextField("Timeframe",text:$timeframe);Picker("Conflict mode",selection:$mode){ForEach(ConflictMode.allCases,id:\.self){Text($0.rawValue.capitalized)}}};Button("Review Import"){reviewing=true}.buttonStyle(.borderedProminent).disabled(file==nil || store.activeOperationID != nil);ResultPanel()}.padding().frame(maxWidth:760,alignment:.leading)}.confirmationDialog("Review Import",isPresented:$reviewing,titleVisibility:.visible){Button("Run Import"){if let file{Task{await store.run(.importCSV(file:file.path,symbol:symbol,timeframe:timeframe,mode:mode))}}};Button("Cancel",role:.cancel){}}message:{Text("File: \(file?.path ?? "")\nAsset: \(symbol) \(timeframe)\nMode: \(mode.rawValue)\nDatabase: \(store.databasePath)")}}
}
