CREATE SCHEMA dw;

CREATE TABLE dw.schema_migration (
    version text PRIMARY KEY,
    file_sha256 char(64) NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dw.load_run (
    run_id uuid PRIMARY KEY,
    data_version uuid NOT NULL UNIQUE,
    staging_batch_id uuid NOT NULL REFERENCES staging.load_batch(batch_id),
    source_set_fingerprint char(64) NOT NULL CHECK (source_set_fingerprint ~ '^[0-9a-f]{64}$'),
    build_fingerprint char(64) NOT NULL CHECK (build_fingerprint ~ '^[0-9a-f]{64}$'),
    contract_version text NOT NULL CHECK (btrim(contract_version) <> ''),
    code_version text NOT NULL CHECK (btrim(code_version) <> ''),
    mapping_versions jsonb NOT NULL CHECK (jsonb_typeof(mapping_versions) = 'object'),
    config_sha256 char(64) NOT NULL CHECK (config_sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('loading', 'published', 'failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    row_counts jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(row_counts) = 'object'),
    error_summary text,
    CONSTRAINT ck_run_finished CHECK (
        (status = 'loading' AND finished_at IS NULL)
        OR (status IN ('published', 'failed') AND finished_at IS NOT NULL AND finished_at >= started_at)
    )
);
CREATE INDEX ix_load_run_staging_batch ON dw.load_run(staging_batch_id);
CREATE INDEX ix_load_run_build_fingerprint ON dw.load_run(build_fingerprint);

CREATE TABLE dw.active_dataset (
    singleton_id smallint PRIMARY KEY CHECK (singleton_id = 1),
    run_id uuid NOT NULL UNIQUE REFERENCES dw.load_run(run_id),
    published_at timestamptz NOT NULL DEFAULT now()
);

-- Publication references another row, so a CHECK expression cannot enforce it.
CREATE FUNCTION dw.check_active_run_published() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM dw.load_run WHERE run_id = NEW.run_id AND status = 'published' FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active dataset requires a published DW run' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER check_active_run_published BEFORE INSERT OR UPDATE ON dw.active_dataset
    FOR EACH ROW EXECUTE FUNCTION dw.check_active_run_published();

CREATE FUNCTION dw.protect_active_run_status() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status <> 'published' AND EXISTS (SELECT 1 FROM dw.active_dataset WHERE run_id = OLD.run_id) THEN
        RAISE EXCEPTION 'Serving DW run must remain published' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER protect_active_run_status BEFORE UPDATE OF status ON dw.load_run
    FOR EACH ROW EXECUTE FUNCTION dw.protect_active_run_status();

CREATE TABLE dw.source_coverage (
    run_id uuid NOT NULL REFERENCES dw.load_run(run_id),
    source_id text NOT NULL CHECK (source_id IN ('booking', 'holiday', 'weather')),
    local_date date NOT NULL CHECK (isfinite(local_date)),
    coverage_status text NOT NULL CHECK (coverage_status IN ('COMPLETE', 'PARTIAL', 'MISSING', 'UNKNOWN')),
    evidence_ref text,
    evidence_sha256 char(64) CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    reason text,
    PRIMARY KEY (run_id, source_id, local_date),
    CONSTRAINT ck_coverage_evidence CHECK (
        (evidence_ref IS NULL AND evidence_sha256 IS NULL)
        OR (evidence_ref IS NOT NULL AND btrim(evidence_ref) <> '' AND evidence_sha256 IS NOT NULL)
    )
);

CREATE TABLE dw.row_issue (
    issue_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES dw.load_run(run_id),
    source_id text NOT NULL CHECK (source_id IN ('booking', 'holiday', 'weather', 'derived')),
    source_file_sha256 char(64) CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    source_row_id bigint CHECK (source_row_id >= 1),
    local_date date CHECK (isfinite(local_date)),
    field_name text NOT NULL CHECK (btrim(field_name) <> ''),
    rule_code text NOT NULL CHECK (btrim(rule_code) <> ''),
    issue_type text NOT NULL CHECK (issue_type IN ('missing', 'invalid', 'mapping', 'coverage', 'warning')),
    severity text NOT NULL CHECK (severity IN ('info', 'warning', 'error')),
    disposition text NOT NULL CHECK (disposition IN (
        'REJECT_FACT', 'NULL_MEASURE', 'UNKNOWN_DIMENSION', 'WARN_ONLY', 'BLOCK_PUBLISH')),
    raw_value jsonb,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (source_row_id IS NULL OR source_file_sha256 IS NOT NULL),
    CHECK (source_id NOT IN ('booking', 'holiday') OR source_row_id IS NULL OR source_row_id >= 2)
);
CREATE INDEX ix_row_issue_run_source ON dw.row_issue(run_id, source_id);
CREATE INDEX ix_row_issue_source_row ON dw.row_issue(source_file_sha256, source_row_id);

CREATE TABLE dw.booking_rejection (
    run_id uuid NOT NULL REFERENCES dw.load_run(run_id),
    source_file_sha256 char(64) NOT NULL CHECK (source_file_sha256 ~ '^[0-9a-f]{64}$'),
    source_row_id bigint NOT NULL CHECK (source_row_id >= 2),
    arrival_date date CHECK (isfinite(arrival_date)),
    reason_codes text[] NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, source_file_sha256, source_row_id),
    FOREIGN KEY (source_file_sha256, source_row_id)
        REFERENCES staging.stg_booking(_source_file_sha256, _source_row_id),
    CHECK (cardinality(reason_codes) > 0 AND array_ndims(reason_codes) = 1
           AND array_position(reason_codes, NULL) IS NULL AND NOT ('' = ANY(reason_codes)))
);
CREATE INDEX ix_booking_rejection_source ON dw.booking_rejection(source_file_sha256, source_row_id);
