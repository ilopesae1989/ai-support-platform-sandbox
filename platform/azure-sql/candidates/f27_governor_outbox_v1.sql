-- Candidate only. Apply once through the existing private SQL administration path.
-- Core principal: INSERT + SELECT. Attestor principal: SELECT only.
-- Neither backend may read or write this table. No runtime UPDATE/DELETE/ALTER.
CREATE TABLE dbo.f27_governor_outbox_v1 (
    operation_sha256 BINARY(32) NOT NULL CONSTRAINT PK_f27_governor_outbox_v1 PRIMARY KEY,
    record_sha256 BINARY(32) NOT NULL,
    record_bytes VARBINARY(MAX) NOT NULL,
    inserted_utc DATETIME2(7) NOT NULL CONSTRAINT DF_f27_governor_outbox_v1_time DEFAULT SYSUTCDATETIME(),
    CONSTRAINT CK_f27_governor_outbox_v1_size CHECK (DATALENGTH(record_bytes) BETWEEN 1 AND 65536),
    CONSTRAINT CK_f27_governor_outbox_v1_digest CHECK (record_sha256 = HASHBYTES('SHA2_256', record_bytes))
);
