ALTER TABLE scan_runs ADD COLUMN config_snapshot TEXT NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS version_category ON versions(json_extract(data,'$.category'));
CREATE INDEX IF NOT EXISTS version_provider ON versions(json_extract(data,'$.provider'));
CREATE INDEX IF NOT EXISTS version_kind ON versions(json_extract(data,'$.kind'));
CREATE INDEX IF NOT EXISTS version_confidence ON versions(json_extract(data,'$.confidence'));
