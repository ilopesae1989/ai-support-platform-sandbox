IF OBJECT_ID(N'dbo.incident_admission_drains', N'U') IS NULL
    CREATE TABLE dbo.incident_admission_drains (
        installation_id varchar(128) COLLATE Latin1_General_100_BIN2 NOT NULL,
        release_id varchar(128) COLLATE Latin1_General_100_BIN2 NOT NULL,
        PRIMARY KEY (installation_id, release_id)
    );
