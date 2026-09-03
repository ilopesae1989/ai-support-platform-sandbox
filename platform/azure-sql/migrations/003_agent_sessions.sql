SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.agent_sessions', N'U') IS NOT NULL
        THROW 53000, 'dbo.agent_sessions already exists.', 1;

    CREATE TABLE dbo.agent_sessions (
        session_store_id NVARCHAR(256) NOT NULL,
        payload_json NVARCHAR(MAX) NOT NULL,

        CONSTRAINT PK_agent_sessions
            PRIMARY KEY CLUSTERED (session_store_id),

        CONSTRAINT CK_agent_sessions_payload_json
            CHECK (
                ISJSON(payload_json) = 1
            )
    );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;
