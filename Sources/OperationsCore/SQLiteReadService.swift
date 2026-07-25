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
        guard tables == foundationTables else { throw AuthorityReadError.incompatibleDatabase("exact ten-table identity failed") }
        let migrations = try int(db, "SELECT count(*) FROM schema_migrations")
        guard (6...9).contains(migrations) else { throw AuthorityReadError.incompatibleDatabase("expected six through nine recognized migrations") }
        let registrations = try queryRegistrations(db)
        let lanes = try queryLanes(db)
        let authorityEvents = try queryAuthorityEvents(db)
        let operations = try queryOperations(db, limit: max(1, min(operationLimit, 500)))
        return AuthoritySnapshot(databasePath: path, registrations: registrations, lanes: lanes, operations: operations, authorityEvents: authorityEvents, readAt: Date())
    }

    /// Reads the operational Price History projection only. This deliberately
    /// returns one aggregate row, actual discontinuities, and a bounded price
    /// profile; it never reads provenance or materialises a governed lane.
    public func loadPriceHistory(path: String, symbol: String, timeframe: String, profilePointLimit: Int = 1_200) throws -> PriceHistoryOverview {
        guard FileManager.default.fileExists(atPath: path) else { throw AuthorityReadError.missingDatabase(path) }
        var db: OpaquePointer?
        let uri = "file:\(URL(fileURLWithPath: path).standardizedFileURL.path)?mode=ro"
        let rc = sqlite3_open_v2(uri, &db, SQLITE_OPEN_READONLY | SQLITE_OPEN_URI | SQLITE_OPEN_NOMUTEX, nil)
        guard rc == SQLITE_OK, let db else { throw AuthorityReadError.sqlite("open failed (\(rc))") }
        defer { sqlite3_close(db) }
        guard sqlite3_db_readonly(db, "main") == 1 else { throw AuthorityReadError.sqlite("SQLite did not enforce read-only mode") }
        try exec(db, "PRAGMA query_only=ON")

        let metadata = try queryPriceHistoryMetadata(db, symbol: symbol, timeframe: timeframe)
        let expectedCadence = expectedCadenceSeconds(for: timeframe)
        let summary = priceHistoryValidationSummary(metadata.validationSummary)
        let gaps = try queryPriceHistoryGaps(
            db, symbol: symbol, timeframe: timeframe, expectedCadence: expectedCadence,
            assetClass: metadata.assetClass
        )
        let continuity = makeContinuity(
            observationCount: metadata.totalBarCount,
            gaps: gaps,
            expectedCadence: expectedCadence,
            latestExpectedPresent: summary.latestExpectedPresent,
            metadataWarning: summary.warning
        )
        let profile = try queryPriceHistoryProfile(
            db,
            symbol: symbol,
            timeframe: timeframe,
            pointLimit: max(500, min(profilePointLimit, 2_000))
        )
        let revision = [metadata.stateVersion.map(String.init), metadata.lastIngestRunID]
            .compactMap { $0 }
            .joined(separator: " · ")
        return PriceHistoryOverview(
            symbol: symbol,
            timeframe: timeframe,
            authority: "GOVERNED_BARS",
            governedInputRevision: revision.isEmpty ? "Unavailable" : revision,
            latestGovernedObservation: metadata.latestBar,
            earliestGovernedObservation: metadata.earliestBar,
            totalBarCount: metadata.totalBarCount,
            validationState: summary.state,
            continuity: continuity,
            profile: profile,
            metadataWarning: summary.warning
        )
    }

    private struct PriceHistoryMetadata {
        let stateVersion: Int?
        let lastIngestRunID: String?
        let validationSummary: String?
        let assetClass: String?
        let totalBarCount: Int
        let earliestBar: Int64?
        let latestBar: Int64?
    }

    private func queryPriceHistoryMetadata(_ db: OpaquePointer, symbol: String, timeframe: String) throws -> PriceHistoryMetadata {
        let sql = """
        SELECT l.state_version,l.last_ingest_run_id,l.validation_summary,r.asset_class,
               count(b.open_time_utc),min(b.open_time_utc),max(b.open_time_utc)
        FROM lane_state l
        LEFT JOIN instrument_registrations r ON r.asset=l.asset AND r.timeframe='D1'
        LEFT JOIN bars b ON b.asset=l.asset AND b.timeframe=l.timeframe
        WHERE l.asset=? AND l.timeframe=?
        GROUP BY l.asset,l.timeframe
        LIMIT 1
        """
        var statement: OpaquePointer?; try prepare(db, sql, &statement); defer { sqlite3_finalize(statement) }
        bind(statement, index: 1, value: symbol); bind(statement, index: 2, value: timeframe)
        guard sqlite3_step(statement) == SQLITE_ROW else {
            return .init(stateVersion: nil, lastIngestRunID: nil, validationSummary: nil, assetClass: nil, totalBarCount: 0, earliestBar: nil, latestBar: nil)
        }
        return .init(
            stateVersion: Int(sqlite3_column_int64(statement, 0)),
            lastIngestRunID: optionalText(statement, 1),
            validationSummary: optionalText(statement, 2),
            assetClass: optionalText(statement, 3),
            totalBarCount: Int(sqlite3_column_int64(statement, 4)),
            earliestBar: optionalInt(statement, 5),
            latestBar: optionalInt(statement, 6)
        )
    }

    private func queryPriceHistoryGaps(_ db: OpaquePointer, symbol: String, timeframe: String, expectedCadence: Int64, assetClass: String?) throws -> [GovernedObservationGap] {
        // D1 permits the normal Friday-to-Monday interval; intraday lanes
        // surface every missing run longer than two expected bars.
        let threshold = expectedCadence >= 86_400 ? expectedCadence * 3 : expectedCadence * 2
        let sql = """
        WITH intervals AS (
            SELECT open_time_utc AS next_timestamp,
                   lag(open_time_utc) OVER (ORDER BY open_time_utc) AS previous_timestamp
            FROM bars
            WHERE asset=? AND timeframe=?
        )
        SELECT previous_timestamp,next_timestamp,next_timestamp-previous_timestamp
        FROM intervals
        WHERE previous_timestamp IS NOT NULL
          AND next_timestamp-previous_timestamp > ?
        ORDER BY next_timestamp ASC
        """
        var statement: OpaquePointer?; try prepare(db, sql, &statement); defer { sqlite3_finalize(statement) }
        bind(statement, index: 1, value: symbol); bind(statement, index: 2, value: timeframe)
        sqlite3_bind_int64(statement, 3, threshold)
        var result: [GovernedObservationGap] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            let previous = sqlite3_column_int64(statement, 0)
            let next = sqlite3_column_int64(statement, 1)
            let duration = sqlite3_column_int64(statement, 2)
            let expectedClosure = assetClass?.uppercased() == "FX"
                && isExpectedFXWeekendClosure(previous: previous, next: next, duration: duration)
            result.append(.init(
                previousObservationTimestamp: previous,
                nextObservationTimestamp: next,
                gapDuration: duration,
                expectedCadence: expectedCadence,
                classification: expectedClosure ? "EXPECTED_MARKET_CLOSURE" : "OBSERVED_INTERVAL_GAP",
                reason: expectedClosure ? "FX_WEEKEND_CLOSURE" : nil
            ))
        }
        return result
    }

    private func isExpectedFXWeekendClosure(previous: Int64, next: Int64, duration: Int64) -> Bool {
        // FX normally closes late Friday and reopens late Sunday UTC.  A 49h
        // interval is common around the broker/session boundary; allow the
        // daylight-saving variation while leaving Thu→Sun and Fri→Tue holes
        // visible as true missing observations.
        guard duration >= 44 * 3_600, duration <= 76 * 3_600 else { return false }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0) ?? .gmt
        let previousDate = Date(timeIntervalSince1970: TimeInterval(previous))
        let nextDate = Date(timeIntervalSince1970: TimeInterval(next))
        let previousWeekday = calendar.component(.weekday, from: previousDate)
        let nextWeekday = calendar.component(.weekday, from: nextDate)
        return previousWeekday == 6 && (nextWeekday == 1 || nextWeekday == 2)
    }

    private func queryPriceHistoryProfile(_ db: OpaquePointer, symbol: String, timeframe: String, pointLimit: Int) throws -> [PriceHistoryProfilePoint] {
        // The grouped result is bounded by pointLimit even when a lane holds
        // millions of bars. SQLite does the aggregation before Swift sees it.
        let sql = """
        WITH bounds AS (
            SELECT min(open_time_utc) AS first_timestamp,max(open_time_utc) AS last_timestamp
            FROM bars
            WHERE asset=? AND timeframe=?
        ), bucketed AS (
            SELECT b.open_time_utc,
                   cast(b.high AS REAL) AS high,
                   cast(b.low AS REAL) AS low,
                   cast(b.close AS REAL) AS close,
                   cast((b.open_time_utc-bounds.first_timestamp)*? /
                        max(bounds.last_timestamp-bounds.first_timestamp+1,1) AS INTEGER) AS bucket
            FROM bars b CROSS JOIN bounds
            WHERE b.asset=? AND b.timeframe=?
        ), ranked AS (
            SELECT *,row_number() OVER (PARTITION BY bucket ORDER BY open_time_utc DESC) AS newest_in_bucket
            FROM bucketed
        )
        SELECT min(open_time_utc),max(high),min(low),
               max(CASE WHEN newest_in_bucket=1 THEN close END)
        FROM ranked
        GROUP BY bucket
        ORDER BY min(open_time_utc)
        """
        var statement: OpaquePointer?; try prepare(db, sql, &statement); defer { sqlite3_finalize(statement) }
        bind(statement, index: 1, value: symbol); bind(statement, index: 2, value: timeframe)
        sqlite3_bind_int(statement, 3, Int32(pointLimit))
        bind(statement, index: 4, value: symbol); bind(statement, index: 5, value: timeframe)
        var result: [PriceHistoryProfilePoint] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            result.append(.init(
                timestamp: sqlite3_column_int64(statement, 0),
                high: sqlite3_column_double(statement, 1),
                low: sqlite3_column_double(statement, 2),
                close: sqlite3_column_double(statement, 3)
            ))
        }
        return result
    }

    private func priceHistoryValidationSummary(_ text: String?) -> (state: String, latestExpectedPresent: Bool?, warning: String?) {
        guard let text, let data = text.data(using: .utf8),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              value["validator_version"] as? String != nil else {
            return ("METADATA_UNAVAILABLE", nil, "Validation metadata is unavailable or malformed; governed observations remain readable.")
        }
        guard let latestPresent = value["latest_expected_session_present"] as? Bool ?? value["latest_expected_closed_interval_present"] as? Bool else {
            return ("METADATA_INCOMPLETE", nil, "Validation metadata does not declare the latest expected boundary.")
        }
        return latestPresent ? ("VALIDATED_CURRENT", true, nil) : ("VALIDATED_DELAYED", false, nil)
    }

    private func makeContinuity(observationCount: Int, gaps: [GovernedObservationGap], expectedCadence: Int64, latestExpectedPresent: Bool?, metadataWarning: String?) -> GovernedContinuity {
        let warnings = metadataWarning.map { [$0] } ?? []
        let latestState: String
        if observationCount == 0 { latestState = "UNAVAILABLE" }
        else if latestExpectedPresent == true { latestState = "CURRENT" }
        else { latestState = "LAST_AVAILABLE" }
        return .init(expectedCadence: expectedCadence, observedCadence: nil, gaps: gaps, latestState: latestState, warnings: warnings)
    }

    private func expectedCadenceSeconds(for timeframe: String) -> Int64 {
        switch timeframe.uppercased() {
        case "M1": 60; case "M5": 300; case "M15": 900; case "M30": 1_800
        case "H1": 3_600; case "H4": 14_400; case "D1": 86_400; case "W1": 604_800
        default: 86_400
        }
    }

    private func queryRegistrations(_ db: OpaquePointer) throws -> [InstrumentRegistrationRecord] {
        let sql = """
        SELECT r.asset,r.timeframe,r.display_name,r.asset_class,r.representation_type,
               coalesce(r.provider_id,(SELECT json_extract(i.detail,'$.provider') FROM ingest_runs i WHERE i.status='committed' AND json_extract(i.detail,'$.asset')=r.asset AND json_extract(i.detail,'$.mapping_state')='CONFIRMED_BY_VALID_EVIDENCE' ORDER BY i.finished_at_utc DESC LIMIT 1),''),
               coalesce(r.provider_contract,(SELECT json_extract(i.detail,'$.provider_contract') FROM ingest_runs i WHERE i.status='committed' AND json_extract(i.detail,'$.asset')=r.asset AND json_extract(i.detail,'$.mapping_state')='CONFIRMED_BY_VALID_EVIDENCE' ORDER BY i.finished_at_utc DESC LIMIT 1),''),
               coalesce(r.provider_symbol,(SELECT json_extract(i.detail,'$.provider_symbol') FROM ingest_runs i WHERE i.status='committed' AND json_extract(i.detail,'$.asset')=r.asset AND json_extract(i.detail,'$.mapping_state')='CONFIRMED_BY_VALID_EVIDENCE' ORDER BY i.finished_at_utc DESC LIMIT 1),''),r.registration_status,r.registered_at_utc,
               EXISTS(SELECT 1 FROM authority_events e
                 WHERE json_extract(e.canonical_payload,'$.body.asset')=r.asset
                 AND json_extract(e.canonical_payload,'$.body.timeframe')=r.timeframe
                 AND (json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'RETIRED%'
                   OR json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'QUARANTINED%'
                   OR json_extract(e.canonical_payload,'$.body.lifecycle_state')='PERMANENTLY_REMOVED')
                 AND NOT EXISTS(SELECT 1 FROM authority_events successor WHERE successor.supersedes_event_id=e.authority_event_id))
        FROM instrument_registrations r ORDER BY r.display_name,r.asset,r.timeframe
        """
        var statement: OpaquePointer?; try prepare(db,sql,&statement); defer{sqlite3_finalize(statement)}
        var result:[InstrumentRegistrationRecord]=[]
        while sqlite3_step(statement)==SQLITE_ROW {
            result.append(.init(asset:text(statement,0),timeframe:text(statement,1),displayName:text(statement,2),assetClass:text(statement,3),representationType:text(statement,4),providerID:text(statement,5),providerContract:text(statement,6),providerSymbol:text(statement,7),registrationStatus:text(statement,8),registeredAt:text(statement,9),retired:sqlite3_column_int(statement,10) != 0))
        }
        return result
    }

    private func queryAuthorityEvents(_ db: OpaquePointer) throws -> [AuthorityEventRecord] {
        let sql = """
        SELECT authority_event_id,entity_kind,entity_id,event_kind,supersedes_event_id,
               effective_from_utc,effective_to_utc,
               json_extract(canonical_payload,'$.compatibility_state'),
               json_extract(canonical_payload,'$.compatibility_reasons'),
               payload_checksum_sha256,event_checksum_sha256,recorded_at_utc,recorded_by
        FROM authority_events
        ORDER BY entity_kind,entity_id,effective_from_utc,recorded_at_utc,authority_event_id
        LIMIT 500
        """
        var statement: OpaquePointer?; try prepare(db,sql,&statement); defer{sqlite3_finalize(statement)}
        var result:[AuthorityEventRecord]=[]
        while sqlite3_step(statement)==SQLITE_ROW {
            result.append(.init(id:text(statement,0),entityKind:text(statement,1),entityID:text(statement,2),eventKind:text(statement,3),supersedesEventID:optionalText(statement,4),effectiveFrom:text(statement,5),effectiveTo:optionalText(statement,6),compatibilityState:text(statement,7),compatibilityReasonsJSON:text(statement,8),payloadChecksum:text(statement,9),eventChecksum:text(statement,10),recordedAt:text(statement,11),recordedBy:text(statement,12)))
        }
        return result
    }

    private func queryLanes(_ db: OpaquePointer) throws -> [LaneRecord] {
        let sql = """
        SELECT l.asset,l.timeframe,l.high_watermark_open_time_utc,l.state_version,l.last_ingest_run_id,l.updated_at_utc,
               count(b.open_time_utc),min(b.open_time_utc),max(b.open_time_utc),l.validation_summary
        FROM lane_state l LEFT JOIN bars b ON b.asset=l.asset AND b.timeframe=l.timeframe
        WHERE NOT EXISTS (SELECT 1 FROM authority_events e WHERE json_extract(e.canonical_payload,'$.body.asset')=l.asset AND json_extract(e.canonical_payload,'$.body.timeframe')=l.timeframe
          AND (json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'RETIRED%' OR json_extract(e.canonical_payload,'$.body.lifecycle_state') LIKE 'QUARANTINED%' OR json_extract(e.canonical_payload,'$.body.lifecycle_state')='PERMANENTLY_REMOVED')
          AND NOT EXISTS(SELECT 1 FROM authority_events successor WHERE successor.supersedes_event_id=e.authority_event_id))
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
               sum(CASE WHEN p.merge_action='CORRECTED' THEN 1 ELSE 0 END),
               coalesce(min(p.symbol),'—'),coalesce(min(p.timeframe),'—'),
               coalesce(json_extract(r.detail,'$.provider'),json_extract(r.detail,'$.source_name'),upper(r.kind)),
               coalesce(json_extract(r.detail,'$.warnings'),'[]')
        FROM ingest_runs r LEFT JOIN provenance p ON p.ingest_run_id=r.ingest_run_id
        GROUP BY r.ingest_run_id ORDER BY r.started_at_utc DESC LIMIT ?
        """
        var statement: OpaquePointer?; try prepare(db, sql, &statement); sqlite3_bind_int(statement,1,Int32(limit)); defer { sqlite3_finalize(statement) }
        var result: [OperationRecord] = []
        while sqlite3_step(statement) == SQLITE_ROW {
            result.append(OperationRecord(id:text(statement,0),kind:text(statement,1),status:text(statement,2),startedAt:text(statement,3),finishedAt:optionalText(statement,4),rawBlockID:optionalText(statement,5),detailJSON:optionalText(statement,6),provenanceTotal:Int(sqlite3_column_int64(statement,7)),inserted:Int(sqlite3_column_int64(statement,8)),unchanged:Int(sqlite3_column_int64(statement,9)),conflicts:Int(sqlite3_column_int64(statement,10)),corrected:Int(sqlite3_column_int64(statement,11)),instrument:text(statement,12),timeframe:text(statement,13),source:text(statement,14),warningsJSON:text(statement,15)))
        }
        return result
    }

    private func prepare(_ db: OpaquePointer, _ sql: String, _ statement: inout OpaquePointer?) throws { if sqlite3_prepare_v2(db,sql,-1,&statement,nil) != SQLITE_OK { throw AuthorityReadError.sqlite(String(cString:sqlite3_errmsg(db))) } }
    private func bind(_ statement: OpaquePointer?, index: Int32, value: String) {
        _ = value.withCString { pointer in
            sqlite3_bind_text(statement, index, pointer, -1, unsafeBitCast(-1, to: sqlite3_destructor_type.self))
        }
    }
    private func exec(_ db: OpaquePointer, _ sql: String) throws { if sqlite3_exec(db,sql,nil,nil,nil) != SQLITE_OK { throw AuthorityReadError.sqlite(String(cString:sqlite3_errmsg(db))) } }
    private func strings(_ db: OpaquePointer, _ sql: String) throws -> [String] { var s: OpaquePointer?; try prepare(db,sql,&s); defer{sqlite3_finalize(s)}; var a:[String]=[]; while sqlite3_step(s)==SQLITE_ROW { a.append(text(s,0)) }; return a }
    private func int(_ db: OpaquePointer, _ sql: String) throws -> Int { var s: OpaquePointer?; try prepare(db,sql,&s); defer{sqlite3_finalize(s)}; guard sqlite3_step(s)==SQLITE_ROW else { throw AuthorityReadError.sqlite("missing scalar") }; return Int(sqlite3_column_int64(s,0)) }
    private func text(_ s: OpaquePointer?, _ i:Int32)->String { String(cString:sqlite3_column_text(s,i)) }
    private func optionalText(_ s: OpaquePointer?, _ i:Int32)->String? { sqlite3_column_type(s,i)==SQLITE_NULL ? nil : text(s,i) }
    private func optionalInt(_ s: OpaquePointer?, _ i:Int32)->Int64? { sqlite3_column_type(s,i)==SQLITE_NULL ? nil : sqlite3_column_int64(s,i) }
}
