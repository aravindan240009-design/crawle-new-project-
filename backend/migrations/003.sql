CREATE TABLE IF NOT EXISTS item_tracking (
  opportunity_id TEXT PRIMARY KEY REFERENCES opportunities(id),
  status TEXT NOT NULL DEFAULT 'interested' CHECK(status IN ('interested','preparing','applied','accepted','declined','archived')),
  reminder_date TEXT,
  updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS tracking_reminder ON item_tracking(reminder_date);
