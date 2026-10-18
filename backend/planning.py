"""Local planning tools. Personal reminder dates never become offer deadlines."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .models import now

ZONE = ZoneInfo('Asia/Kolkata')


def tracked_items(db):
    rows = db.rows('''SELECT t.*,v.data,m.stale,u.notes FROM item_tracking t
        JOIN current_membership m ON m.opportunity_id=t.opportunity_id
        JOIN versions v ON v.id=m.version_id
        LEFT JOIN item_state u ON u.opportunity_id=t.opportunity_id
        ORDER BY t.reminder_date IS NULL,t.reminder_date,t.updated DESC''')
    return [{**json.loads(r['data']), 'tracking': {k: r[k] for k in ('status', 'reminder_date', 'updated')},
             'stale': bool(r['stale']), 'notes': r['notes'] or ''} for r in rows]


def reminder_alerts(db, current=None):
    current = current or datetime.now(timezone.utc)
    if not db.settings().alerts_enabled:
        return
    today = current.astimezone(ZONE).date().isoformat()
    for item in tracked_items(db):
        tracking = item['tracking']
        due = tracking['reminder_date']
        if due and due <= today and tracking['status'] not in ('accepted', 'declined', 'archived'):
            alert_id = f'{item["id"]}:personal-reminder:{due}'
            db.execute('INSERT OR IGNORE INTO alerts(id,opportunity_id,type,title,created) VALUES (?,?,?,?,?)',
                       (alert_id, item['id'], 'personal reminder', f'Your reminder: {item["title"]}', now()))


def weekly_digest(db, days=7, current=None):
    current = current or datetime.now(timezone.utc)
    cutoff = (current - timedelta(days=days)).isoformat()
    # Committed live publications and archives only; legacy staged rows stay private.
    rows = db.rows('''SELECT v.data,v.id version_id,o.first_seen,m.stale,m.last_seen,
        coalesce(u.bookmarked,0) bookmarked FROM current_membership m
        JOIN versions v ON v.id=m.version_id JOIN opportunities o ON o.id=m.opportunity_id
        LEFT JOIN item_state u ON u.opportunity_id=o.id
        WHERE coalesce(u.dismissed,0)=0
          AND json_extract(v.data,'$.geography')!='Not eligible'
          AND json_extract(v.data,'$.kind')!='news'
        ORDER BY o.first_seen DESC,o.id''')
    items = [{**json.loads(r['data']), **{k: r[k] for k in ('version_id', 'first_seen', 'stale', 'last_seen', 'bookmarked')}} for r in rows]
    fresh = [i for i in items if i['first_seen'] >= cutoff]
    changes = db.rows('''WITH observations AS (
        SELECT m.opportunity_id,m.version_id,s.published,s.id
        FROM membership m JOIN snapshots s ON s.id=m.snapshot_id
        UNION ALL
        SELECT opportunity_id,version_id,committed,campaign_id FROM live_versions
    ), history AS (
        SELECT opportunity_id,version_id,published,
          lag(version_id) OVER (PARTITION BY opportunity_id ORDER BY published,id) previous
        FROM observations
    ) SELECT h.opportunity_id,h.published created,json_extract(v.data,'$.title') title,
        CASE WHEN json_extract(v.data,'$.lifecycle')='withdrawn' THEN 'withdrawal' ELSE 'material change' END type
        FROM history h JOIN versions v ON v.id=h.version_id
        WHERE h.published>=? AND h.previous IS NOT NULL AND h.previous!=h.version_id
          AND json_extract(v.data,'$.kind')!='news'
          AND json_extract(v.data,'$.geography')!='Not eligible'
          AND NOT EXISTS (SELECT 1 FROM item_state u WHERE u.opportunity_id=h.opportunity_id AND u.dismissed=1)
        ORDER BY h.published DESC''', (cutoff,))
    expiring = []
    for item in items:
        if item.get('deadline') and item.get('deadline_precision') == 'instant':
            deadline = datetime.fromisoformat(item['deadline'].replace('Z', '+00:00'))
            if current <= deadline <= current + timedelta(days=7):
                expiring.append(item)
    publication = db.rows('SELECT s.* FROM publication p JOIN snapshots s ON s.id=p.snapshot_id')
    return dict(generated_at=current.isoformat(), days=days, snapshot=publication[0] if publication else None,
                new_items=fresh, changes=changes, expiring=expiring,
                reminders=[i for i in tracked_items(db) if i['tracking']['reminder_date'] and i['tracking']['status'] not in ('accepted', 'declined', 'archived')],
                counts={'new': len(fresh), 'changes': len(changes), 'expiring': len(expiring)},
                note='Published results only. Exact deadline windows exclude unknown cutoffs. Personal reminders are your dates, not official deadlines.')


def digest_markdown(digest):
    def plain(value):
        # No raw HTML or injected Markdown links from page content in exports.
        text = str(value or '').replace('\r', ' ').replace('\n', ' ')
        for ch in '\\`*_{}[]<>()!#|':
            text = text.replace(ch, '\\' + ch)
        return text
    lines = ['# Your opportunity digest', '', f'Generated {digest["generated_at"]}; last {digest["days"]} days.', '', digest['note']]
    for key, title in [('new_items', 'New discoveries'), ('expiring', 'Confirmed deadlines in the next 7 days')]:
        lines.extend(['', '## ' + title, ''])
        if not digest[key]:
            lines.append('No matching published opportunities.')
        for item in digest[key]:
            lines += ['- **' + plain(item['title']) + '** — ' + plain(item['verification']) + '; ' + plain(item['geography']),
                      '  ' + plain(item['summary']), '  Source: ' + plain(item.get('official_url') or item.get('discovery_url'))]
    lines += ['', '## Material changes', '']
    lines += ['- ' + plain(i['title']) + ': ' + plain(i['type']) for i in digest['changes']] or ['No recorded changes.']
    lines += ['', '## Personal reminders (not official deadlines)', '']
    lines += ['- ' + plain(i['tracking']['reminder_date']) + ': ' + plain(i['title']) for i in digest['reminders']] or ['No personal reminders.']
    return '\n'.join(lines) + '\n'


def calendar_export(db):
    def escape(value):
        return str(value).replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')
    events = []
    for item in tracked_items(db):
        tracking = item['tracking']
        if tracking['status'] in ('accepted', 'declined', 'archived'):
            continue
        if tracking['reminder_date']:
            events.append((item, 'personal reminder', tracking['reminder_date'].replace('-', ''), True))
        if item.get('deadline') and item.get('deadline_precision') == 'instant':
            deadline = datetime.fromisoformat(item['deadline'].replace('Z', '+00:00')).astimezone(timezone.utc)
            events.append((item, 'official deadline', deadline.strftime('%Y%m%dT%H%M%SZ'), False))
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Opportunity Radar//Local planning//EN', 'CALSCALE:GREGORIAN']
    for item, kind, start, all_day in events:
        uid = hashlib.sha256((item['id'] + kind + start).encode()).hexdigest()[:32]
        lines += ['BEGIN:VEVENT', 'UID:' + uid + '@opportunity-radar.local',
                  'DTSTAMP:' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
                  ('DTSTART;VALUE=DATE:' if all_day else 'DTSTART:') + start,
                  'SUMMARY:' + escape(kind.title() + ': ' + item['title']),
                  'DESCRIPTION:' + escape('Personal date set by you; not an official deadline.' if all_day else 'Exact published deadline; recheck official terms. ' + (item.get('official_url') or '')),
                  'END:VEVENT']
    lines += ['END:VCALENDAR']
    # RFC 5545 folding: at most 75 UTF-8 octets per physical line.
    folded = []
    for line in lines:
        part = ''
        for char in line:
            if len((part + char).encode('utf-8')) > 75:
                folded.append(part)
                part = ' '
            part += char
        folded.append(part)
    return '\r\n'.join(folded) + '\r\n'
