-- Candidate schema, NOT an applied migration. No existing table is modified.
-- Qualify with mssql-python 1.14.0 on an isolated SQL Server/Azure SQL engine
-- before assigning a migration number or deploying. Runtime never executes DDL.
-- Separate deployment principal owns schema; runtime needs INSERT and SELECT,
-- verifier SELECT only. No UPDATE/DELETE/schema/key/WORM rights are required.
CREATE TABLE dbo.f27_receipt_custody_v1 (
    logical_sha256 BINARY(32) NOT NULL,
    record_sha256 BINARY(32) NOT NULL,
    record_bytes VARBINARY(MAX) NOT NULL,
    inserted_utc DATETIME2(7) NOT NULL
        CONSTRAINT DF_f27_receipt_custody_v1_time DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_f27_receipt_custody_v1 PRIMARY KEY (logical_sha256),
    CONSTRAINT CK_f27_receipt_custody_v1_size
        CHECK (DATALENGTH(record_bytes) BETWEEN 1 AND 65536),
    CONSTRAINT CK_f27_receipt_custody_v1_digest
        CHECK (record_sha256 = HASHBYTES('SHA2_256', record_bytes))
);
