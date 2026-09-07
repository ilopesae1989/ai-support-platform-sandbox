SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(
        N'dbo.wait_recheck_consumption_claims',
        N'U'
    ) IS NULL
        THROW 54001, 'dbo.wait_recheck_consumption_claims does not exist.', 1;

    IF COL_LENGTH(
        N'dbo.wait_recheck_consumption_claims',
        N'status'
    ) IS NOT NULL
        THROW 54002, 'status already exists on dbo.wait_recheck_consumption_claims.', 1;

    ALTER TABLE dbo.wait_recheck_consumption_claims
    ADD status NVARCHAR(32) NOT NULL
        CONSTRAINT DF_wait_recheck_consumption_claims_status
        DEFAULT N'completed'
        WITH VALUES;

    ALTER TABLE dbo.wait_recheck_consumption_claims
    ADD CONSTRAINT CK_wait_recheck_consumption_claims_status
        CHECK (
            status IN (
                N'in_progress',
                N'completed'
            )
        );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;
