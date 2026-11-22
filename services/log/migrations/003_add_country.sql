ALTER TABLE hackathons ADD country NVARCHAR(100) NULL;
GO
UPDATE hackathons
SET country = NULLIF(LTRIM(RTRIM(RIGHT(location, CHARINDEX(',', REVERSE(location)) - 1))), '')
WHERE country IS NULL AND location LIKE '%,%';
