SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.workflow_checkpoints', N'U') IS NOT NULL
        THROW 52000, 'dbo.workflow_checkpoints already exists.', 1;

    CREATE TABLE dbo.workflow_checkpoints (
        checkpoint_id NVARCHAR(256) NOT NULL,
        workflow_name NVARCHAR(256) NOT NULL,
        checkpoint_timestamp DATETIMEOFFSET(7) NOT NULL,
        payload_json NVARCHAR(MAX) NOT NULL,

        CONSTRAINT PK_workflow_checkpoints
            PRIMARY KEY CLUSTERED (checkpoint_id),

        CONSTRAINT CK_workflow_checkpoints_payload_json
            CHECK (
                ISJSON(payload_json) = 1
            )
    );

    CREATE INDEX IX_workflow_checkpoints_workflow_order
        ON dbo.workflow_checkpoints
        (
            workflow_name ASC,
            checkpoint_timestamp DESC,
            checkpoint_id DESC
        );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;