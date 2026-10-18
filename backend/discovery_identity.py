"""Conservative public cross-reference evidence, independent of crawl permission."""
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .db import dump
from .extract import canonical_url, benefit_excerpt, geography


def observe_identity(db, page):
    soup = BeautifulSoup(page.body, 'html.parser')
    values = []
    for node in soup.select('script[type="application/ld+json"]')[:10]:
        try:
            value = json.loads(node.string or node.get_text())
            values.extend(value if isinstance(value, list) else [value])
        except (ValueError, TypeError):
            pass
    for value in list(values):
        if isinstance(value, dict):
            values.extend(value.get('@graph', []) if isinstance(value.get('@graph'), list) else [])
    for value in values[:100]:
        if not isinstance(value, dict) or value.get('@type') not in ('LocalBusiness', 'Restaurant', 'Store', 'Organization', 'CafeOrCoffeeShop'):
            continue
        name = str(value.get('name') or '')[:160]
        address = value.get('address') or {}
        location = str(address.get('addressLocality') or '')[:100] if isinstance(address, dict) else ''
        phone = re.sub(r'\D', '', str(value.get('telephone') or ''))
        if len(phone) < 8 or not name or not location:
            continue
        links = value.get('sameAs', [])
        links = [links] if isinstance(links, str) else links if isinstance(links, list) else []
        links += [a['href'] for a in soup.select('a[rel~="me"][href]')[:10]]
        normalized = []
        for link in links[:20]:
            try:
                normalized.append(canonical_url(urljoin(page.url, link)).rstrip('/'))
            except Exception:
                pass
        excerpt = f'{name}; locality {location}; public identity cross-reference in structured business metadata'
        evidence = dict(field='issuer_identity', url=page.url, excerpt=excerpt, retrieved=page.retrieved, content_hash=page.content_hash)
        db.execute('INSERT OR REPLACE INTO identity_observations VALUES (?,?,?,?,?,?,?)',
                   (canonical_url(page.url).rstrip('/'), name, location, phone, dump(normalized), dump(evidence), page.retrieved))


def issuer_support(db, page):
    soup = BeautifulSoup(page.body, 'html.parser')
    profiles = [canonical_url(page.url).rstrip('/')]
    for link in soup.select('a[rel~="author"][href]')[:3]:
        try:
            profile = canonical_url(urljoin(page.url, link['href'])).rstrip('/')
            if urlsplit(profile).hostname == urlsplit(page.url).hostname:
                profiles.append(profile)
        except Exception:
            pass
    for profile in profiles:
        own = db.rows('SELECT * FROM identity_observations WHERE url=?', (profile,))
        if not own:
            continue
        own = own[0]
        for target in json.loads(own['links']):
            if urlsplit(target).hostname == urlsplit(profile).hostname:
                continue
            other = db.rows('SELECT * FROM identity_observations WHERE url=?', (target,))
            if not other:
                continue
            other = other[0]
            # Name similarity alone never supplies identity. Require reciprocal
            # exact URLs, same public phone and locality, with exact normalized name.
            if (profile in json.loads(other['links']) and own['phone'] == other['phone'] and
                own['name'].casefold().strip() == other['name'].casefold().strip() and
                own['location'].casefold().strip() == other['location'].casefold().strip()):
                return {'name': own['name'], 'location': own['location'], 'profile': profile,
                        'evidence': [json.loads(own['evidence']), json.loads(other['evidence'])]}
    return None


def apply_issuer_support(item, support, page, text):
    if not support:
        return item
    benefit = benefit_excerpt(text)
    if not benefit:
        return item
    item.update(provider=support['name'], issuer_status='Supported public cross-references',
                verification='Issuer-posted; redemption not independently confirmed', confidence=55,
                geography='Unclear', geography_reason='Merchant identity evidence does not establish geographic eligibility',
                confidence_reasons=['Reciprocal profile/directory links with matching public name, phone and locality; redemption unconfirmed'])
    item['evidence'].extend(support['evidence'])
    item['evidence'].append(dict(field='issuer_posted_benefit', url=page.url, excerpt=benefit[:280], retrieved=page.retrieved, content_hash=page.content_hash))
    item['summary'] = f"{support['name']}: {benefit}\nIssuer-posted; redemption not independently confirmed.\n" + '; '.join(item['restrictions'])[:300] + (f" Deadline: {item['deadline']} ({item['deadline_precision']})." if item.get('deadline') else ' Source publication date and redemption availability may be unknown.')
    # A shop's identity locality cannot locate every repost/branch-specific offer.
    if not item.get('published_at'):
        item['risk_flags'].append('Source publication date unknown; this may be an old post or repost')
    return item
