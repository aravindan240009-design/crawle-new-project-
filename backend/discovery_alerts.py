"""Local-only rules, cooldowns, corrections and IST quiet hours."""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pydantic import Field

from .db import dump
from .models import StrictModel, now

ZONE = ZoneInfo('Asia/Kolkata')


class Rule(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default='', max_length=80)
    location: str = Field(default='', max_length=80)
    query: str = Field(default='', max_length=200)
    enabled: bool = True
    min_confidence: int = Field(default=65, ge=0, le=100)
    provisional: bool = False
    cooldown_hours: int = Field(default=24, ge=0, le=8760)


def delivery_time(settings, current=None):
    current = current or datetime.now(timezone.utc)
    local = current.astimezone(ZONE)
    start, end = settings.quiet_start, settings.quiet_end
    clock = local.strftime('%H:%M')
    quiet = start <= clock < end if start < end else clock >= start or clock < end if start != end else False
    if not quiet:
        return current.isoformat()
    hour, minute = map(int, end.split(':'))
    due = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due <= local:
        due += timedelta(days=1)
    return due.astimezone(timezone.utc).isoformat()


def match_rules(c, item, vid, settings):
    if not settings.alerts_enabled:
        return
    current = now()
    for row in c.execute('SELECT * FROM alert_rules WHERE enabled=1').fetchall():
        filters = json.loads(row['filters'])
        if item['confidence'] < row['min_confidence'] or (item['publication_state'] == 'provisional' and not row['provisional']):
            continue
        if any(filters.get(k) and filters[k] != item.get(k) for k in ('category', 'location')):
            continue
        if filters.get('query', '').lower() not in (item['title']+' '+item['summary']).lower():
            continue
        if item.get('deadline_precision') == 'instant' and item.get('deadline'):
            deadline = datetime.fromisoformat(item['deadline'].replace('Z', '+00:00'))
            instant = datetime.now(timezone.utc)
            if deadline > instant:
                aid = f"expiry:{row['id']}:{item['id']}:{item['deadline']}"
                due = delivery_time(settings, max(instant, deadline-timedelta(days=7)))
                c.execute('INSERT OR IGNORE INTO pending_alerts SELECT ?,?,?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM alerts WHERE id=?)',
                          (aid, item['id'], 'deadline reminder', item['title'] + ' — deadline ' + item['deadline'], due, current, aid))
        cutoff = (datetime.now(timezone.utc)-timedelta(hours=row['cooldown_hours'])).isoformat()
        if c.execute('SELECT 1 FROM alert_deliveries WHERE rule_id=? AND opportunity_id=? AND (created>? OR version_id=?)', (row['id'], item['id'], cutoff, vid)).fetchone():
            continue
        aid = f"rule:{row['id']}:{item['id']}:{vid}"
        c.execute('INSERT OR IGNORE INTO alert_deliveries VALUES (?,?,?,?)', (row['id'], item['id'], vid, current))
        c.execute('INSERT OR IGNORE INTO pending_alerts VALUES (?,?,?,?,?,?)', (aid, item['id'], 'matched rule', row['name'] + ': ' + item['title'], delivery_time(settings), current))
    if item['verification'] == 'Contradicted' or item['lifecycle'] == 'withdrawn':
        c.execute('UPDATE alerts SET resolved=1 WHERE opportunity_id=?', (item['id'],))
        c.execute('DELETE FROM pending_alerts WHERE opportunity_id=?', (item['id'],))
        aid = f"correction:{item['id']}:{vid}"
        c.execute('INSERT OR IGNORE INTO pending_alerts VALUES (?,?,?,?,?,?)', (aid, item['id'], 'correction', item['title'] + ': ' + item['verification'] + ' / ' + item['lifecycle'], delivery_time(settings), current))


def deliver_pending(db):
    settings = db.settings()
    if not settings.alerts_enabled:
        return
    current = datetime.now(timezone.utc)
    due = delivery_time(settings, current)
    with db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if due > current.isoformat():
            c.execute('UPDATE pending_alerts SET due=? WHERE due<=?', (due, current.isoformat()))
            return
        c.execute('INSERT OR IGNORE INTO alerts(id,opportunity_id,type,title,created) SELECT id,opportunity_id,type,title,? FROM pending_alerts WHERE due<=?', (now(), now()))
        c.execute('DELETE FROM pending_alerts WHERE due<=?', (now(),))


def list_rules(db):
    return [{**r, **json.loads(r['filters'])} for r in db.rows('SELECT * FROM alert_rules ORDER BY name')]


def save_rule(db, rid, rule):
    filters = {k: getattr(rule, k) for k in ('category', 'location', 'query')}
    db.execute('INSERT OR REPLACE INTO alert_rules VALUES (?,?,?,?,?,?,?)', (rid, rule.name, dump(filters), rule.enabled, rule.min_confidence, rule.provisional, rule.cooldown_hours))
