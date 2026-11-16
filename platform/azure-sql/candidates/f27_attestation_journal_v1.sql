-- Candidate DDL; NOT executed or assigned an applied migration number.
-- Private evidence may contain provider responses/tool output. Never export
-- record_bytes in a sanitized report. Separate reader and writer principals.
-- Runtime: INSERT only for writer, SELECT for independent reader. No DELETE,
-- UPDATE, ALTER, key administration, role management or dispatch permissions.
-- Validate on a real isolated SQL engine before production application.
CREATE TABLE dbo.f27_attestation_journal_v1 (
    claim_sha256 BINARY(32) NOT NULL,
    owner_sha256 BINARY(32) NOT NULL,
    record_sha256 BINARY(32) NOT NULL,
    record_bytes VARBINARY(MAX) NOT NULL,
    inserted_utc DATETIME2(7) NOT NULL
        CONSTRAINT DF_f27_attestation_journal_v1_time DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_f27_attestation_journal_v1 PRIMARY KEY (claim_sha256),
    CONSTRAINT CK_f27_attestation_journal_v1_size
        CHECK (DATALENGTH(record_bytes) BETWEEN 1 AND 1048576),
    CONSTRAINT CK_f27_attestation_journal_v1_digest
        CHECK (record_sha256 = HASHBYTES('SHA2_256', record_bytes))
);
