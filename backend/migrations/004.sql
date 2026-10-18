CREATE TABLE campaigns(id TEXT PRIMARY KEY,status TEXT NOT NULL,created TEXT NOT NULL,finished TEXT,heartbeat REAL NOT NULL,config TEXT NOT NULL,metrics TEXT NOT NULL DEFAULT '{}',error TEXT,generation INTEGER NOT NULL DEFAULT 1);
CREATE UNIQUE INDEX one_active_campaign ON campaigns((1)) WHERE status IN ('running','paused');
CREATE TABLE discovery_events(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id TEXT,task_id TEXT,created TEXT NOT NULL,stage TEXT NOT NULL,resource TEXT,metadata TEXT NOT NULL,code TEXT,duration REAL);
CREATE INDEX event_campaign ON discovery_events(campaign_id,id);
CREATE TABLE queries(id TEXT PRIMARY KEY,signature TEXT NOT NULL UNIQUE,query TEXT NOT NULL,category TEXT NOT NULL,region TEXT NOT NULL,language TEXT NOT NULL,engine TEXT NOT NULL,last_attempt TEXT,status TEXT,diagnostics TEXT);
CREATE TABLE search_hits(id TEXT PRIMARY KEY,campaign_id TEXT NOT NULL,query_id TEXT NOT NULL,engine TEXT NOT NULL,rank INTEGER NOT NULL,url TEXT NOT NULL,snippet TEXT,observed TEXT NOT NULL);
CREATE TABLE frontier(id TEXT PRIMARY KEY,url TEXT NOT NULL UNIQUE,domain TEXT NOT NULL,parent TEXT,category TEXT NOT NULL,region TEXT,language TEXT,priority REAL NOT NULL,depth INTEGER NOT NULL,policy TEXT NOT NULL DEFAULT 'unchecked',first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,next_due TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,lease_until REAL NOT NULL DEFAULT 0,owner TEXT,status TEXT NOT NULL DEFAULT 'queued',bytes INTEGER NOT NULL DEFAULT 0,last_error TEXT,novel INTEGER NOT NULL DEFAULT 1);
CREATE INDEX frontier_due ON frontier(next_due,status,priority DESC);
CREATE TABLE provenance_edges(id INTEGER PRIMARY KEY AUTOINCREMENT,child TEXT NOT NULL,parent TEXT NOT NULL,relation TEXT NOT NULL,campaign_id TEXT,created TEXT NOT NULL,UNIQUE(child,parent,relation));
CREATE TABLE entities(id TEXT PRIMARY KEY,domain TEXT NOT NULL UNIQUE,name TEXT NOT NULL,issuer_status TEXT NOT NULL DEFAULT 'unassessed',evidence TEXT NOT NULL DEFAULT '[]',first_seen TEXT NOT NULL,last_seen TEXT NOT NULL);
CREATE TABLE live_membership(opportunity_id TEXT PRIMARY KEY REFERENCES opportunities(id),version_id TEXT NOT NULL REFERENCES versions(id),last_seen TEXT NOT NULL,stale INTEGER NOT NULL DEFAULT 0,campaign_id TEXT NOT NULL);
CREATE TABLE live_versions(version_id TEXT PRIMARY KEY REFERENCES versions(id),opportunity_id TEXT NOT NULL,campaign_id TEXT NOT NULL,committed TEXT NOT NULL,publication_state TEXT NOT NULL);
CREATE VIEW current_membership AS
 SELECT NULL snapshot_id,opportunity_id,version_id,last_seen,stale FROM live_membership
 UNION ALL
 SELECT m.* FROM membership m JOIN publication p ON p.snapshot_id=m.snapshot_id WHERE NOT EXISTS(SELECT 1 FROM live_membership l WHERE l.opportunity_id=m.opportunity_id);
CREATE TABLE repository_observations(repo_id TEXT NOT NULL,observed TEXT NOT NULL,stars INTEGER NOT NULL,forks INTEGER NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(repo_id,observed));
CREATE TABLE media_jobs(id TEXT PRIMARY KEY,campaign_id TEXT,frontier_id TEXT,url TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL,language TEXT,evidence TEXT NOT NULL DEFAULT '[]',error TEXT);
CREATE TABLE alert_rules(id TEXT PRIMARY KEY,name TEXT NOT NULL,filters TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,min_confidence INTEGER NOT NULL DEFAULT 65,provisional INTEGER NOT NULL DEFAULT 0,cooldown_hours INTEGER NOT NULL DEFAULT 24);
CREATE TABLE alert_deliveries(rule_id TEXT NOT NULL,opportunity_id TEXT NOT NULL,version_id TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(rule_id,opportunity_id,version_id));
CREATE TABLE pending_alerts(id TEXT PRIMARY KEY,opportunity_id TEXT NOT NULL,type TEXT NOT NULL,title TEXT NOT NULL,due TEXT NOT NULL,created TEXT NOT NULL);
