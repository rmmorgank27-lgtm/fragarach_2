import CSQLite
import Foundation

public enum AuthorityReadError: Error, LocalizedError, Sendable {
    case missingDatabase(String), incompatibleDatabase(String), sqlite(String)
    public var errorDescription: String? {
        switch self { case .missingDatabase(let p): "Database does not exist: \(p)"; case .incompatibleDatabase(let m): "Incompatible Fragarach II database: \(m)"; case .sqlite(let m): "Read-only database error: \(m)" }
    }
}

public final class SQLiteReadService: @unchecked Sendable {
    public init() {}

    public func load(path: String, operationLimit: Int = 100) throws -> AuthoritySnapshot {
        guard FileManager.default.fileExists(atPath: path) else { throw AuthorityReadError.missingDatabase(path) }
        var db: OpaquePointer?
        let uri = "file:\(URL(fileURLWithPath: path).standardizedFileURL.path)?mode=ro"
        let rc = sqlite3_open_v2(uri, &db, SQLITE_OPEN_READONLY | SQLITE_OPEN_URI | SQLITE_OPEN_NOMUTEX, nil)
        guard rc == SQLITE_OK, let db else { throw AuthorityReadError.sqlite("open failed (\(rc))") }
        defer { sqlite3_close(db) }
        guard sqlite3_db_readonly(db, "main") == 1 else { throw AuthorityReadError.sqlite("SQLite did not enforce read-only mode") }
        try exec(db, "PRAGMA query_only=ON")
        let tables = Set(try strings(db, "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
        guard tables == foundationTables else { throw AuthorityReadError.incompatibleDatabase("exact nine-table identity failed") }
        let migrations = try int(db, "SELECT count(*) FROM schema_migrations")
        guard migrations == 5 else { throw AuthorityReadError.incompatibleDatabase("expected five recognized migrations") }
        let lanes = try queryLanes(db)
        let operations = try queryOperations(db, limit: max(1, min(operationLimit, 500)))
        return AuthoritySnapshot(databasePath: path, lanes: lanes, operations: operations, readAt: Date())
    }

    private func queryLanes(_ db: OpaquePointer) throws -> [LaneRecord] {
        let sql = """
        SELECT l.asset,l.timeframe,l.high_watermark_open_time_utc,l.state_version,l.last_ingest_run_id,l.updated_at_utc,
               count(b.open_time_utc),min(b.open_time_utc),max(b.open_time_utc),l.validation_summary
        FROM lane_state l LEFT JOIN bars b ON b.asset=l.asset AND b.timeframe=l.timeframe
        GROUP BY l.asset,l.timeframe ORDER BY l.asset,l.timeframe
        """
        var statement: OpaquePointer?; try prepare(db, sql, &statement); defer { sqlite3_finalize(statement) }
        var result: [LaneRecord] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            let summaryText = optionalText(statement, 9)
            let summary = summaryText.flatMap { try? JSONDecoder().decode(ValidationSummary.self, from: Data($0.utf8)) }
            result.append(LaneRecord(asset: text(statement,0), timeframe: text(statement,1), highWatermark: optionalInt(statement,2), stateVersion: Int(sqlite3_column_int64(statement,3)), lastIngestRunID: optionalText(statement,4), updatedAt: text(statement,5), barCount: Int(sqlite3_column_int64(statement,6)), earliestBar: optionalInt(statement,7), latestBar: optionalInt(statement,8), validation: summary))
        }
        return result
    }

    private func queryOperations(_ db: OpaquePointer, limit: Int) throws -> [OperationRecord] {
        let sql = """
        SELECT r.ingest_run_id,r.kind,r.status,r.started_at_utc,r.finished_at_utc,r.raw_block_id,r.detail,
               count(p.provenance_event_id),
               sum(CASE WHEN p.merge_action='INSERT' THEN 1 ELSE 0 END),
               sum(CASE WHEN p.merge_action='UNCHANGED' THEN 1 ELSE 0 END),
               sum(CASE WHEN p.merge_action='CONFLICT_PRESERVED' THEN 1 ELSE 0 END),
               sum(CASE WHEN p.merge_action='CORRECTED' THEN 1 ELSE 0 END)
        FROM ingest_runs r LEFT JOIN provenance p ON p.ingest_run_id=r.ingest_run_id
        GROUP BY r.ingest_run_id ORDER BY r.started_at_utc DESC LIMIT ?
        """
        var statement: OpaquePointer?; try prepare(db, sql, &statement); sqlite3_bind_int(statement,1,Int32(limit)); defer { sqlite3_finalize(statement) }
        var result: [OperationRecord] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            result.append(OperationRecord(id:text(statement,0),kind:text(statement,1),status:text(statement,2),startedAt:text(statement,3),finishedAt:optionalText(statement,4),rawBlockID:optionalText(statement,5),detailJSON:optionalText(statement,6),provenanceTotal:Int(sqlite3_column_int64(statement,7)),inserted:Int(sqlite3_column_int64(statement,8)),unchanged:Int(sqlite3_column_int64(statement,9)),conflicts:Int(sqlite3_column_int64(statement,10)),corrected:Int(sqlite3_column_int64(statement,11))))
        }
        return result
    }

    private func prepare(_ db: OpaquePointer, _ sql: String, _ statement: inout OpaquePointer?) throws { if sqlite3_prepare_v2(db,sql,-1,&statement,nil) != SQLITE_OK { throw AuthorityReadError.sqlite(String(cString:sqlite3_errmsg(db))) } }
    private func exec(_ db: OpaquePointer, _ sql: String) throws { if sqlite3_exec(db,sql,nil,nil,nil) != SQLITE_OK { throw AuthorityReadError.sqlite(String(cString:sqlite3_errmsg(db))) } }
    private func strings(_ db: OpaquePointer, _ sql: String) throws -> [String] { var s: OpaquePointer?; try prepare(db,sql,&s); defer{sqlite3_finalize(s)}; var a:[String]=[]; while sqlite3_step(s)==SQLITE_ROW { a.append(text(s,0)) }; return a }
    private func int(_ db: OpaquePointer, _ sql: String) throws -> Int { var s: OpaquePointer?; try prepare(db,sql,&s); defer{sqlite3_finalize(s)}; guard sqlite3_step(s)==SQLITE_ROW else { throw AuthorityReadError.sqlite("missing scalar") }; return Int(sqlite3_column_int64(s,0)) }
    private func text(_ s: OpaquePointer?, _ i:Int32)->String { String(cString:sqlite3_column_text(s,i)) }
    private func optionalText(_ s: OpaquePointer?, _ i:Int32)->String? { sqlite3_column_type(s,i)==SQLITE_NULL ? nil : text(s,i) }
    private func optionalInt(_ s: OpaquePointer?, _ i:Int32)->Int64? { sqlite3_column_type(s,i)==SQLITE_NULL ? nil : sqlite3_column_int64(s,i) }
}
