SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(
        N'dbo.wait_recheck_consumption_claims',
        N'U'
    ) IS NOT NULL
        THROW 54000, 'dbo.wait_recheck_consumption_claims already exists.', 1;

    CREATE TABLE dbo.wait_recheck_consumption_claims (
        recheck_id NVARCHAR(256) NOT NULL,

        CONSTRAINT PK_wait_recheck_consumption_claims
            PRIMARY KEY CLUSTERED (recheck_id)
    );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;
