-- Candidate schema following e3_execution_affinity_v1.sql.
CREATE TABLE dbo.incident_rejection_closures (
    execution_id NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL PRIMARY KEY
        REFERENCES dbo.incident_executions(execution_id),
    approval_id NVARCHAR(256) NOT NULL UNIQUE REFERENCES dbo.incident_affine_continuation_jobs(approval_id),
    worker_id NVARCHAR(256) NOT NULL,
    attempt INT NOT NULL CHECK(attempt > 0)
);
