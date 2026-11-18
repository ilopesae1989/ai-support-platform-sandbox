-- CANDIDATE ONLY: not installed or granted to a runtime by this package.
-- Requires 001_persistence.sql. No backfill/adoption of historical executions.
SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRANSACTION;
    IF OBJECT_ID(N'dbo.incident_executions', N'U') IS NOT NULL
        THROW 51000, 'incident_executions already exists; inspect version before retry.', 1;
    IF OBJECT_ID(N'dbo.incident_affine_continuation_jobs', N'U') IS NOT NULL
        THROW 51001, 'incident_affine_continuation_jobs already exists.', 1;

    CREATE TABLE dbo.incident_executions (
        execution_id NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL PRIMARY KEY,
        input_sha256 CHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
        affinity_sha256 CHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
        affinity_json NVARCHAR(MAX) NOT NULL CHECK(ISJSON(affinity_json)=1)
    );
    CREATE INDEX IX_incident_execution_affinity
        ON dbo.incident_executions(affinity_sha256, execution_id);

    CREATE TABLE dbo.incident_affine_continuation_jobs (
        approval_id NVARCHAR(256) NOT NULL PRIMARY KEY
            REFERENCES dbo.pending_approvals(approval_id),
        payload_json NVARCHAR(MAX) NOT NULL CHECK(ISJSON(payload_json)=1),
        status NVARCHAR(32) NOT NULL CHECK(status IN ('pending','claimed','completed','failed')),
        attempt_count INT NOT NULL CHECK(attempt_count >= 0),
        claimed_by NVARCHAR(256) NULL,
        last_error NVARCHAR(MAX) NULL,
        created_at FLOAT(53) NOT NULL,
        updated_at FLOAT(53) NOT NULL,
        execution_id NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL
            REFERENCES dbo.incident_executions(execution_id),
        CHECK((status='claimed' AND claimed_by IS NOT NULL)
            OR (status<>'claimed' AND claimed_by IS NULL))
    );
    CREATE INDEX IX_incident_affine_queue
        ON dbo.incident_affine_continuation_jobs(status, created_at, approval_id);
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
