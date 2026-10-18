import csv
import io
import json
from datetime import datetime, timedelta, timezone

from .models import Filters


def query_results(db, f: Filters, export=False):
    snapshot = f.snapshot or db.rows('SELECT snapshot_id FROM publication WHERE id=1')[0]['snapshot_id']
    if f.snapshot and not snapshot:
        return {'items': [], 'total': 0, 'snapshot': None, 'page': f.page, 'page_size': f.page_size}
    published = db.rows('SELECT published FROM snapshots WHERE id=?', (snapshot,))
    if f.snapshot and not published:
        return {'items': [], 'total': 0, 'snapshot': snapshot, 'page': f.page, 'page_size': f.page_size}
    where, args = (['m.snapshot_id=?'], [snapshot]) if f.snapshot else (['1=1'], [])
    fields = {'category': f.category, 'provider': f.provider, 'family': f.family, 'kind': f.kind,
              'geography': f.geography, 'verification': f.verification, 'location': f.location,
              'publication_state': f.publication_state, 'media_status': f.media_status, 'license_class': f.license_class}
    for field, value in fields.items():
        if value:
            where.append(f"json_extract(v.data,'$.{field}')=?")
            args.append(value)
    where.append("(json_extract(v.data,'$.kind')='news')=?")
    args.append(int(f.news))
    if not f.show_dismissed:
        where.append('coalesce(u.dismissed,0)=0')
    if not f.show_ineligible and not f.geography:
        where.append("json_extract(v.data,'$.geography')!='Not eligible'")
    if f.bookmarked:
        where.append('u.bookmarked=1')
    if f.near_me:
        where.append("distance_km(json_extract(v.data,'$.latitude'),json_extract(v.data,'$.longitude'),?,?)<=?")
        args.extend([f.latitude, f.longitude, f.radius_km])
    if f.q:
        has_fts = db.rows("SELECT name FROM sqlite_master WHERE name='version_search'")
        if has_fts:
            phrase = '"' + f.q.replace('"', '""') + '"'
            where.append('v.id IN (SELECT version_id FROM version_search WHERE version_search MATCH ?)')
            args.append(phrase)
        else:
            where.append("(json_extract(v.data,'$.title') LIKE ? OR json_extract(v.data,'$.summary') LIKE ?)")
            args.extend(['%' + f.q + '%'] * 2)
    where.append("json_extract(v.data,'$.confidence')>=?")
    args.append(f.min_confidence)
    if f.card:
        if f.card == 'unknown':
            where.append("json_extract(v.data,'$.card_required') IS NULL")
        else:
            where.append("json_extract(v.data,'$.card_required')=?")
            args.append(int(f.card == 'yes'))
    if f.min_discount is not None:
        where.append("json_extract(v.data,'$.discount')>=?")
        args.append(f.min_discount)
    if f.discovered_after:
        where.append('o.first_seen>=?')
        args.append(f.discovered_after)
    if f.new_only and published:
        prior = db.rows('SELECT id FROM snapshots WHERE published<? ORDER BY published DESC LIMIT 1', (published[0]['published'],))
        if prior:
            where.append('o.id NOT IN (SELECT opportunity_id FROM membership WHERE snapshot_id=?)')
            args.append(prior[0]['id'])
    # Date-only cutoffs never pass an exact deadline-window filter.
    if f.deadline_days:
        where.append("json_extract(v.data,'$.deadline_precision')='instant' AND julianday(json_extract(v.data,'$.deadline')) BETWEEN julianday(?) AND julianday(?)")
        current = datetime.now(timezone.utc)
        args.extend([current.isoformat(), (current + timedelta(days=f.deadline_days)).isoformat()])
    as_of = "(SELECT published FROM snapshots WHERE id=m.snapshot_id)" if f.snapshot else "'now'"
    life = "CASE WHEN json_extract(v.data,'$.lifecycle')='withdrawn' THEN 'withdrawn' WHEN json_extract(v.data,'$.deadline_precision')='instant' AND julianday(json_extract(v.data,'$.deadline'))<julianday(" + as_of + ") THEN 'expired' ELSE json_extract(v.data,'$.lifecycle') END"
    if f.lifecycle:
        where.append(f'({life})=?')
        args.append(f.lifecycle)
    sort = {'newest': 'o.first_seen DESC', 'deadline': "json_extract(v.data,'$.deadline') IS NULL, json_extract(v.data,'$.deadline') ASC",
            'confidence': "json_extract(v.data,'$.confidence') DESC", 'relevance': "(json_extract(v.data,'$.geography')='India eligible') DESC,json_extract(v.data,'$.confidence') DESC,o.first_seen DESC",
            'provider': "json_extract(v.data,'$.provider') COLLATE NOCASE", 'category': "json_extract(v.data,'$.category')"}[f.sort]
    base = ' FROM ' + ('membership' if f.snapshot else 'current_membership') + ' m JOIN versions v ON v.id=m.version_id JOIN opportunities o ON o.id=m.opportunity_id LEFT JOIN item_state u ON u.opportunity_id=o.id WHERE ' + ' AND '.join(where)
    with db.connect() as c:
        total = c.execute('SELECT count(*)' + base, args).fetchone()[0]
        sql = 'SELECT v.data,v.id version_id,o.first_seen,m.last_seen,m.stale,coalesce(u.bookmarked,0) bookmarked,coalesce(u.dismissed,0) dismissed,coalesce(u.notes,\'\') notes,(' + life + ') current_lifecycle' + base + ' ORDER BY ' + sort + ',o.id'
        if not export:
            sql += ' LIMIT ? OFFSET ?'
            args.extend([f.page_size, (f.page - 1) * f.page_size])
        rows = c.execute(sql, args).fetchall()
    items = []
    for row in rows:
        item = json.loads(row['data'])
        item.update({key: row[key] for key in ('version_id', 'first_seen', 'last_seen', 'stale', 'bookmarked', 'dismissed', 'notes')})
        item['lifecycle'] = row['current_lifecycle']
        item.pop('evidence', None)
        items.append(item)
    return {'items': items, 'total': total, 'snapshot': snapshot, 'published': published[0]['published'] if published else None, 'page': f.page, 'page_size': f.page_size}


def csv_export(items):
    out = io.StringIO(newline='')
    fields = ['title', 'provider', 'category', 'kind', 'summary', 'verification', 'geography', 'deadline', 'official_url', 'terms_url', 'notes']
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for item in items:
        safe = {}
        for key in fields:
            value = str(item.get(key) or '')
            if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')):
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)
    return out.getvalue()
