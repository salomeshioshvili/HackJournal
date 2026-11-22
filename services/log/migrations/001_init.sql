CREATE TABLE hackathons (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(255) NOT NULL,
    location NVARCHAR(255) NULL,
    mode NVARCHAR(32) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    application_deadline DATE NULL,
    status NVARCHAR(32) NOT NULL DEFAULT 'interested',
    travel_funded BIT NOT NULL DEFAULT 0,
    notes NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE teammates (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE hackathon_teammates (
    hackathon_id INT NOT NULL,
    teammate_id INT NOT NULL,
    PRIMARY KEY (hackathon_id, teammate_id),
    FOREIGN KEY (hackathon_id) REFERENCES hackathons(id),
    FOREIGN KEY (teammate_id) REFERENCES teammates(id)
);

CREATE TABLE projects (
    id INT IDENTITY(1,1) PRIMARY KEY,
    hackathon_id INT NOT NULL,
    name NVARCHAR(255) NOT NULL,
    result NVARCHAR(32) NOT NULL DEFAULT 'participated',
    FOREIGN KEY (hackathon_id) REFERENCES hackathons(id)
);

CREATE TABLE project_technologies (
    project_id INT NOT NULL,
    technology NVARCHAR(128) NOT NULL,
    PRIMARY KEY (project_id, technology),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
