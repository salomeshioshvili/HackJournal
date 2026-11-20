CREATE TABLE reflections (
    id INT IDENTITY(1,1) PRIMARY KEY,
    hackathon_id INT NOT NULL,
    went_well NVARCHAR(MAX) NULL,
    went_badly NVARCHAR(MAX) NULL,
    lesson NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE checklist_rules (
    id INT IDENTITY(1,1) PRIMARY KEY,
    condition_field NVARCHAR(64) NOT NULL,
    condition_value NVARCHAR(64) NOT NULL,
    item NVARCHAR(255) NOT NULL,
    CONSTRAINT uq_checklist_rule UNIQUE (condition_field, condition_value, item)
);
