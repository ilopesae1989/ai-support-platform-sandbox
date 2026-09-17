SET XACT_ABORT ON;

DECLARE @runtimePrincipalName SYSNAME =
    N'$(RuntimePrincipalName)';

DECLARE @runtimePrincipalClientId UNIQUEIDENTIFIER =
    '$(RuntimePrincipalClientId)';

DECLARE @runtimePrincipalSid VARBINARY(16) =
    CONVERT(
        VARBINARY(16),
        @runtimePrincipalClientId
    );

IF (
    @runtimePrincipalName IS NULL
    OR LEN(@runtimePrincipalName) = 0
    OR @runtimePrincipalName <> LTRIM(RTRIM(@runtimePrincipalName))
)
    THROW 55000, 'Runtime principal name is invalid.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    DECLARE @existingPrincipalSid VARBINARY(85);
    DECLARE @existingPrincipalType CHAR(1);

    SELECT
        @existingPrincipalSid = sid,
        @existingPrincipalType = type
    FROM sys.database_principals
    WHERE name = @runtimePrincipalName;

    IF @existingPrincipalSid IS NULL
    BEGIN
        DECLARE @runtimePrincipalSidHex NVARCHAR(34) =
            CONVERT(
                VARCHAR(34),
                @runtimePrincipalSid,
                1
            );

        DECLARE @createRuntimePrincipalSql NVARCHAR(MAX) =
            N'CREATE USER '
            + QUOTENAME(@runtimePrincipalName)
            + N' WITH SID = '
            + @runtimePrincipalSidHex
            + N', TYPE = E;';

        EXEC sys.sp_executesql
            @createRuntimePrincipalSql;
    END
    ELSE
    BEGIN
        IF @existingPrincipalType <> 'E'
            THROW 55001, 'Existing runtime principal has unexpected type.', 1;

        IF @existingPrincipalSid <> @runtimePrincipalSid
            THROW 55002, 'Existing runtime principal SID does not match configured client ID.', 1;
    END;

    GRANT
        SELECT,
        INSERT,
        UPDATE,
        DELETE
    ON OBJECT::dbo.workflow_checkpoints
    TO [$(RuntimePrincipalName)];

    GRANT
        SELECT,
        INSERT,
        UPDATE
    ON OBJECT::dbo.teams_conversation_bindings
    TO [$(RuntimePrincipalName)];

    GRANT
        SELECT,
        INSERT,
        UPDATE
    ON OBJECT::dbo.pending_approvals
    TO [$(RuntimePrincipalName)];

    GRANT
        SELECT,
        INSERT,
        UPDATE
    ON OBJECT::dbo.incident_continuation_jobs
    TO [$(RuntimePrincipalName)];

    GRANT
        SELECT,
        INSERT
    ON OBJECT::dbo.operation_dispatch_claims
    TO [$(RuntimePrincipalName)];

    GRANT
        SELECT,
        INSERT,
        UPDATE,
        DELETE
    ON OBJECT::dbo.agent_sessions
    TO [$(RuntimePrincipalName)];

    GRANT
        SELECT,
        INSERT,
        UPDATE
    ON OBJECT::dbo.wait_recheck_consumption_claims
    TO [$(RuntimePrincipalName)];

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;