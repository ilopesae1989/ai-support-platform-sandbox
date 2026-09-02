SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET NUMERIC_ROUNDABORT OFF;
SET QUOTED_IDENTIFIER ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.operation_dispatch_claims', N'U') IS NOT NULL
        THROW 51000, 'dbo.operation_dispatch_claims already exists.', 1;

    IF OBJECT_ID(N'dbo.teams_conversation_bindings', N'U') IS NOT NULL
        THROW 51001, 'dbo.teams_conversation_bindings already exists.', 1;

    IF OBJECT_ID(N'dbo.pending_approvals', N'U') IS NOT NULL
        THROW 51002, 'dbo.pending_approvals already exists.', 1;

    IF OBJECT_ID(N'dbo.incident_continuation_jobs', N'U') IS NOT NULL
        THROW 51003, 'dbo.incident_continuation_jobs already exists.', 1;

    CREATE TABLE dbo.operation_dispatch_claims (
        operation_id NVARCHAR(256) NOT NULL,

        CONSTRAINT PK_operation_dispatch_claims
            PRIMARY KEY CLUSTERED (operation_id)
    );

    CREATE TABLE dbo.teams_conversation_bindings (
        tenant_id NVARCHAR(256) NOT NULL,
        conversation_id NVARCHAR(256) NOT NULL,
        service_url NVARCHAR(2048) NOT NULL,

        CONSTRAINT PK_teams_conversation_bindings
            PRIMARY KEY NONCLUSTERED (tenant_id, conversation_id)
    );

    CREATE TABLE dbo.pending_approvals (
        approval_id NVARCHAR(256) NOT NULL,
        workflow_id NVARCHAR(256) NOT NULL,
        request_id NVARCHAR(256) NOT NULL,
        checkpoint_id NVARCHAR(256) NOT NULL,

        consumption_status NVARCHAR(32) NOT NULL
            CONSTRAINT DF_pending_approvals_consumption_status
            DEFAULT ('pending'),

        approved_decision BIT NULL,

        CONSTRAINT PK_pending_approvals
            PRIMARY KEY CLUSTERED (approval_id),

        CONSTRAINT UQ_pending_approvals_request_id
            UNIQUE (request_id),

        CONSTRAINT CK_pending_approvals_status
            CHECK (
                consumption_status IN (
                    'pending',
                    'claimed',
                    'completed'
                )
            ),

        CONSTRAINT CK_pending_approvals_decision_state
            CHECK (
                (
                    consumption_status = 'pending'
                    AND approved_decision IS NULL
                )
                OR
                (
                    consumption_status IN (
                        'claimed',
                        'completed'
                    )
                    AND approved_decision IS NOT NULL
                )
            )
    );

    CREATE TABLE dbo.incident_continuation_jobs (
        approval_id NVARCHAR(256) NOT NULL,
        payload_json NVARCHAR(MAX) NOT NULL,
        status NVARCHAR(32) NOT NULL,
        attempt_count INT NOT NULL,
        claimed_by NVARCHAR(256) NULL,
        last_error NVARCHAR(MAX) NULL,
        created_at FLOAT(53) NOT NULL,
        updated_at FLOAT(53) NOT NULL,

        CONSTRAINT PK_incident_continuation_jobs
            PRIMARY KEY CLUSTERED (approval_id),

        CONSTRAINT CK_incident_continuation_jobs_status
            CHECK (
                status IN (
                    'pending',
                    'claimed',
                    'completed',
                    'failed'
                )
            ),

        CONSTRAINT CK_incident_continuation_jobs_attempt_count
            CHECK (
                attempt_count >= 0
            ),

        CONSTRAINT CK_incident_continuation_jobs_claim_owner
            CHECK (
                (
                    status = 'claimed'
                    AND claimed_by IS NOT NULL
                )
                OR
                (
                    status <> 'claimed'
                    AND claimed_by IS NULL
                )
            ),

        CONSTRAINT CK_incident_continuation_jobs_payload_json
            CHECK (
                ISJSON(payload_json) = 1
            )
    );

    CREATE INDEX IX_incident_continuation_pending_queue
        ON dbo.incident_continuation_jobs
        (
            status,
            created_at,
            approval_id
        )
        WHERE status = 'pending';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;