from __future__ import annotations

import hashlib
import asyncio
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, urljoin

import feedparser
from bs4 import BeautifulSoup

from .fetch import FetchError, Page, validate_url
from .models import Source

TRACKING = {'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid'}


def canonical_url(url):
    u = validate_url(url)
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
    host = u.hostname.lower().encode('idna').decode()
    if ':' in host:
        host = '[' + host + ']'
    if u.port and not (u.scheme == 'https' and u.port == 443 or u.scheme == 'http' and u.port == 80):
        host += ':' + str(u.port)
    return urlunsplit((u.scheme.lower(), host, u.path or '/', urlencode(query), ''))


def official(url, domains):
    host = (urlsplit(url).hostname or '').lower().rstrip('.')
    return any(host == d or host.endswith('.' + d) for d in domains)


def text_html(body, selector='main'):
    soup = BeautifulSoup(body, 'html.parser')
    for node in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'svg']):
        node.decompose()
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    node = soup.select_one(selector) or soup.body or soup
    text = '\n'.join(x.strip() for x in node.get_text('\n', strip=True).splitlines() if x.strip())
    return title, text[:100000], soup


def excerpt_match(text, pattern):
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    # Preserve a short local span, not an entire page or unrelated navigation.
    start = max(text.rfind('\n', 0, match.start()) + 1, match.start() - 90)
    end = text.find('\n', match.end())
    if end == -1:
        end = len(text)
    return text[start:min(end, match.end() + 160)].strip()[:280]


def benefit_excerpt(text):
    pattern = r'\bfree (?:tier|plan|credits|access|trial|admission|workshop)|\bcredit(?:s)?\b(?!\s+card)|\b(?:discount|scholarship|fellowship|grant|hackathon|cashback|BOGO|coupon)\b|\bbuy (?:one|1) get (?:one|1)|\b\d+(?:\.\d+)?\s*%\s*(?:off|discount)|\$\s*0(?![\d.])\b|இலவச|தள்ளுபடி|சலுகை'
    choices = []
    for line in text.splitlines():
        excerpt = excerpt_match(line, pattern)
        if not excerpt:
            continue
        if not re.search(pattern, excerpt, re.I):
            continue
        score = 3 * bool(re.search(r'includes|provides|offers|receive|access|get|available', excerpt, re.I))
        score += 2 * bool(re.search(r'\$\d|\d+[,.\d]*\s*(?:requests|credits|hours|GB)', excerpt, re.I))
        score -= 5 * bool(re.search(r'upgrade|paid plan|billing history|refund', excerpt, re.I))
        score -= 3 * (len(excerpt) < 25)
        choices.append((score, excerpt))
    return max(choices, key=lambda choice: choice[0])[1] if choices else None


def geography(text):
    exclusion = excerpt_match(text, r'(?:not (?:available|eligible)|exclud(?:es|ing)|except)[^\n.]{0,70}\bIndia\b|\b(?:US|U\.S\.|United States)[ -](?:students?[- ]only|only)|only (?:open|available|eligible)[^\n.]{0,40}(?:United States|US residents)|must (?:be|reside)[^\n.]{0,45}(?:United States|US resident)')
    if exclusion:
        return 'Not eligible', exclusion
    india = excerpt_match(text, r'(?:available|eligible|open)[^\n.]{0,60}\bIndia\b|\bIndia\b[^\n.]{0,40}(?:eligible|supported)')
    if india:
        return 'India eligible', india
    worldwide = excerpt_match(text, r'(?:open|available|eligible)[^\n.]{0,40}(?:worldwide|globally|all countries)|(?:participants|applicants) (?:from )?(?:anywhere|around the world)')
    if worldwide:
        if re.search(r'exclud|except|restricted countr|sanction|selected countr', text, re.I):
            return 'Unclear', 'Global wording has exceptions; inspect geographic terms.'
        return 'India eligible', worldwide
    return 'Unclear', 'Geographic eligibility is not stated in the collected evidence.'


def build_item(source: Source, page: Page, title=None, text=None, url=None, news=False, published=None):
    timer = time.perf_counter()
    if text is None:
        page_title, text, _ = text_html(page.body, source.selector)
        title = title or page_title or source.name
    title = re.sub(r'\s+', ' ', title or source.name)[:240]
    extracted = time.perf_counter()
    url = canonical_url(url or page.url)
    is_official = official(page.url, source.official_domains) and official(url, source.official_domains)
    evidence = []

    def add(field, excerpt):
        if excerpt and is_official:
            evidence.append(dict(field=field, url=page.url, excerpt=excerpt[:280],
                                 retrieved=page.retrieved, content_hash=page.content_hash))
        return excerpt

    benefit = benefit_excerpt(text)
    if news:
        kind = 'news'
        benefit = re.sub(r'\s+', ' ', text)[:240] or title
    elif benefit:
        low = benefit.lower()
        kind = ('cashback' if 'cashback' in low else 'BOGO' if re.search(r'bogo|buy (?:one|1) get (?:one|1)', low) else
                'coupon' if 'coupon' in low else 'trial' if 'trial' in low else 'credits' if 'credit' in low else
                'discount' if 'discount' in low or re.search(r'%\s*off', low) else
                'competition/event' if 'hackathon' in low else
                'application-based' if re.search(r'grant|scholarship|fellowship', low) else 'free tier')
    else:
        kind = 'application-based'
    add('benefit', benefit)
    geo, geo_reason = geography(text) if is_official else ('Unclear', 'Discovery lead; official geography evidence required.')
    if geo != 'Unclear':
        add('geography', geo_reason)
    no_card = excerpt_match(text, r'no (?:credit |payment )?card (?:is )?required|without (?:a )?(?:credit|payment) card')
    yes_card = excerpt_match(text, r'(?:credit|payment) card (?:is )?required')
    card = False if no_card else True if yes_card else None
    add('card_required', no_card or yes_card)
    conditions = []
    for label, pattern in [
        ('Student eligibility', r'(?:must be|eligible|only|verified)[^\n.]{0,35}\bstudent|\bstudents? only'),
        ('Startup eligibility', r'\b(?:eligible startups?|startup[s]? must|founders? only|funding stage)\b'),
        ('New customers', r'\bnew (?:users?|customers?|accounts?) only\b'),
        ('Approval required', r'\b(?:subject to approval|application required|apply for|approval required)\b'),
        ('Automatic renewal', r'\b(?:auto(?:matic(?:ally)?)?[- ]renew|automatically charged)\b'),
        ('Limits / costs', r'\b(?:limited to|per (?:day|month)|usage limits|overage|shipping costs|delivery fee)\b'),
        ('Coupon restrictions', r'\b(?:coupon|promo code)[^\n.]{0,90}'),
        ('Minimum spend', r'\b(?:minimum spend|minimum purchase|orders? (?:over|above)|min\.? order)[^\n]{0,90}'),
        ('Bank / card condition', r'\b(?:only with|valid on|using)[^\n]{0,60}(?:bank|credit card|debit card)[^\n]{0,50}'),
        ('Stock uncertainty', r'\b(?:while stocks? last|subject to availability)[^\n]{0,60}'),
        ('Taxes / fees', r'\b(?:taxes? extra|excluding taxes|booking fee|service charge)[^\n]{0,70}'),
    ]:
        found = excerpt_match(text, pattern)
        if found:
            conditions.append(label + ': ' + found)
            add(label, found)
    deadline_match = re.search(r'(?:deadline|ends|apply by|applications close)\s*:?\s*(\d{4}-\d{2}-\d{2})([T ][0-2]\d:[0-5]\d(?::[0-5]\d)?(?:Z|[+-]\d{2}:\d{2}))?', text, re.I)
    deadline, precision = None, None
    if deadline_match:
        candidate_date = ''.join(x or '' for x in deadline_match.groups())
        try:
            datetime.fromisoformat(candidate_date.replace('Z', '+00:00'))
            deadline = candidate_date
            precision = 'instant' if deadline_match[2] else 'date (cutoff and timezone not stated)'
            add('deadline', deadline_match[0])
        except ValueError:
            pass
    withdrawn = excerpt_match(text, r'\b(?:this (?:offer|program|promotion) (?:has ended|is (?:closed|discontinued))|no longer accepting applications)\b')
    add('withdrawn', withdrawn)
    verification = 'Partially verified' if is_official and benefit else 'Unverified'
    reasons = ['Official domain and claim-specific benefit excerpt'] if is_official and benefit else ['No substantiated official benefit; manual review needed']
    # Broad pages do not establish completeness of terms. Verified requires all
    # explicit gates, and a narrow offer page rather than arbitrary news.
    terms_present = bool(source.terms_url and canonical_url(source.terms_url) == url)
    if is_official and benefit and geo != 'Unclear' and card is not None and terms_present and conditions and not news:
        verification = 'Verified'
        reasons.append('Geography, payment requirement and material conditions evidenced on registered terms page')
    if no_card and re.search(r'(?<!no )\b(?:a credit card is required|requires a credit card)\b', text, re.I):
        verification = 'Contradicted'
        card = None
        reasons.append('Conflicting payment-card statements')
    score = 90 if verification == 'Verified' else 65 if verification == 'Partially verified' else 20
    if verification == 'Contradicted':
        score = 10
    discount = re.search(r'\b(\d{1,2}(?:\.\d+)?)\s*%\s*(?:off|discount)', benefit or '', re.I)
    money = re.search(r'(USD|\$|INR|₹|Rs\.?)\s*([\d,]+(?:\.\d+)?)', benefit or '', re.I)
    location_excerpt = excerpt_match(text, r'\b(?:venue|location)\s*:?[^\n]{0,70}\bChennai\b')
    online = excerpt_match(text, r'\b(?:online (?:event|course|hackathon)|remote participation|virtual event)\b')
    add('location', location_excerpt or online)
    restrictions = '; '.join(conditions) or 'Personal eligibility, limits and costs: not fully stated.'
    summary = f'{source.provider}: {"Discovery claim: " if not is_official else ""}{benefit or "Offer benefit not substantiated; review the source."}\n{geo}. {restrictions[:220]}\n' + (f'Deadline: {deadline} ({precision}).' if deadline else 'Deadline not stated. Check official terms before applying.')
    if kind == 'credits':
        summary += ' Advertised credits are not a guaranteed award.'
    return dict(
        id=hashlib.sha256(url.encode()).hexdigest()[:24], title=title, provider=source.provider,
        category=source.category, family=source.family, source_id=source.id, tags=[source.category, kind],
        kind=kind, summary=summary, official_url=url if is_official else None,
        discovery_url=url, terms_url=source.terms_url, benefit=benefit, currency=('USD' if money[1].upper() in ('USD', '$') else 'INR') if money else None,
        amount=float(money[2].replace(',', '')) if money and is_official else None,
        value_qualifier='advertised, not guaranteed' if money else None,
        discount=float(discount[1]) if discount and is_official else None,
        card_required=card if is_official else None, restrictions=conditions,
        account_required=None, auto_renewal=True if any(c.startswith('Automatic renewal') for c in conditions) else None,
        geography=geo, geography_reason=geo_reason, personal_eligibility='Unknown; check student/startup/new-user conditions',
        location='Chennai' if location_excerpt else 'Online' if online else 'Unknown', shipping=None,
        verification=verification, confidence=score, confidence_reasons=reasons,
        risk_flags=[] if verification == 'Verified' else ['Material conditions may be incomplete; review official terms'],
        supported_claims=[e['field'] for e in evidence], unsupported_claims=['Any benefit, condition, or eligibility not explicitly evidenced'],
        start_date=None, deadline=deadline, deadline_precision=precision,
        lifecycle='withdrawn' if withdrawn and is_official else 'uncertain',
        published_at=published, last_verified=page.retrieved if evidence else None,
        evidence=evidence, provenance=[{'source_id': source.id, 'url': url}],
        _timings={'extraction_seconds': extracted - timer, 'verification_seconds': time.perf_counter() - extracted},
    )


async def collect(source, fetcher):
    if source.adapter == 'search':
        if urlsplit(source.url).hostname != 'hn.algolia.com' or not urlsplit(source.url).path.startswith('/api/v1/search'):
            raise FetchError('Supported search interface: public HN Algolia /api/v1/search only', 'disabled')
        page = await fetcher.get(source.url, timeout=source.timeout, interval=source.interval_seconds)
        try:
            rows = json.loads(page.body)['hits']
            untrusted = source.model_copy(update={'official_domains': []})
            items = [build_item(untrusted, page, row.get('title') or 'Community search lead',
                                row.get('story_text') or row.get('title') or '', row['url'], news=True,
                                published=row.get('created_at')) for row in rows[:source.budget] if row.get('url')]
            return items, page
        except (ValueError, KeyError, TypeError) as exc:
            raise FetchError('Malformed public search response', 'parse_error') from exc
    page = await fetcher.get(source.url, timeout=source.timeout, interval=source.interval_seconds)
    if source.adapter == 'html':
        page_title, text, soup = await asyncio.to_thread(text_html, page.body, source.selector)
        if len(text) < 40:
            raise FetchError('Page has insufficient extractable text (possibly JavaScript-only)', 'parse_error', page.status)
        if source.strategy == 'event_index':
            cards = soup.select('[itemtype="https://schema.org/Event"]')
            if not cards:
                raise FetchError('No structured event cards found; extraction needs review', 'parse_error')
            items = []
            for card in cards[:source.budget]:
                link = card.get('href') or (card.select_one('a[href]') or {}).get('href')
                if not link:
                    continue
                link = canonical_url(urljoin(page.url, link))
                heading = card.select_one('[itemprop="name"],h2,h3,h4')
                title = heading.get_text(' ', strip=True) if heading else card.get_text(' ', strip=True)[:120]
                # Hidden location metadata can also use itemprop=name: prefer visible headings.
                visible_heading = card.select_one('h2,h3,h4')
                if visible_heading:
                    title = visible_heading.get_text(' ', strip=True)
                text = card.get_text('\n', strip=True)
                item = build_item(source, page, title, text, link)
                item['kind'] = 'competition/event'
                item['benefit'] = 'Hackathon/event listed by ' + source.provider
                item['verification'] = 'Partially verified' if official(page.url, source.official_domains) else 'Unverified'
                item['confidence'] = 50
                item['confidence_reasons'] = ['Event listing found; organizer rules and personal eligibility require review']
                item['evidence'] = []
                if official(page.url, source.official_domains):
                    item['evidence'].append(dict(field='event listing', url=page.url, excerpt=title[:280], retrieved=page.retrieved, content_hash=page.content_hash))
                for prop, field in [('startDate', 'start_date'), ('endDate', 'end_date')]:
                    node = card.select_one(f'[itemprop="{prop}"]')
                    value = node.get('content') if node else None
                    if value:
                        try:
                            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            if dt.tzinfo:
                                item[field] = dt.astimezone(timezone.utc).isoformat()
                                item['evidence'].append(dict(field=field, url=page.url, excerpt=f'{prop}: {value}', retrieved=page.retrieved, content_hash=page.content_hash))
                        except ValueError:
                            pass
                mode = card.select_one('[itemprop="eventAttendanceMode"]')
                city = card.select_one('[itemprop="addressLocality"]')
                if mode and 'OnlineEventAttendanceMode' in mode.get('content', ''):
                    item['location'] = 'Online'
                elif city and city.get('content', '').lower() == 'chennai':
                    item['location'] = 'Chennai'
                current = datetime.now(timezone.utc)
                if item.get('end_date') and datetime.fromisoformat(item['end_date']) < current:
                    item['lifecycle'] = 'expired'
                elif item.get('start_date') and datetime.fromisoformat(item['start_date']) > current:
                    item['lifecycle'] = 'upcoming'
                elif item.get('start_date') and item.get('end_date'):
                    item['lifecycle'] = 'active'
                item['supported_claims'] = [e['field'] for e in item['evidence']]
                item['summary'] = f'{title}: event listed by {source.provider}.\n{item["location"]} availability. Geographic and personal eligibility require organizer rules.\n' + (f'Event starts {item["start_date"]}; application deadline not stated.' if item.get('start_date') else 'Dates and application deadline not confirmed.')
                item['provenance'].append({'source_id': source.id, 'url': page.url})
                items.append(item)
            return items, page
        item = await asyncio.to_thread(build_item, source, page, page_title, text)
        if source.terms_url and canonical_url(source.terms_url) != canonical_url(page.url):
            try:
                terms = await fetcher.get(source.terms_url, timeout=source.timeout, interval=source.interval_seconds)
                terms_item = await asyncio.to_thread(build_item, source, terms)
                if official(terms.url, source.official_domains):
                    for field in ('geography', 'card_required', 'deadline'):
                        old, new = item.get(field), terms_item.get(field)
                        if new not in (None, 'Unclear'):
                            if old not in (None, 'Unclear') and old != new:
                                item['verification'] = 'Contradicted'
                                item['confidence'] = 10
                                item['risk_flags'].append('Conflicting offer/terms field: ' + field)
                            # Terms are the stronger source for explicit exclusions/conditions.
                            item[field] = 'Not eligible' if field == 'geography' and 'Not eligible' in (old, new) else new
                    if terms_item['geography'] != 'Unclear':
                        item['geography_reason'] = terms_item['geography_reason']
                    if terms_item['deadline']:
                        item['deadline_precision'] = terms_item['deadline_precision']
                    item['restrictions'] = list(dict.fromkeys(item['restrictions'] + terms_item['restrictions']))
                    item['evidence'].extend(e for e in terms_item['evidence'] if e['field'] != 'benefit')
                    item['supported_claims'] = list(dict.fromkeys(e['field'] for e in item['evidence']))
                    item['summary'] = f'{source.provider}: {item["benefit"] or "Benefit not substantiated."}\n{item["geography"]}. ' + ('; '.join(item['restrictions'])[:220] or 'Personal conditions not stated.') + '\n' + (f'Deadline: {item["deadline"]} ({item["deadline_precision"]}).' if item['deadline'] else 'Deadline not stated. Read the official offer and terms.')
                    if item['verification'] == 'Contradicted':
                        item['summary'] += ' Conflicting evidence: review both pages.'
            except Exception as exc:
                item['risk_flags'].append('Terms page could not be checked: ' + str(exc))
        return [item], page
    if source.adapter in ('feed', 'community'):
        feed = await asyncio.to_thread(feedparser.parse, page.body)
        if feed.bozo and not feed.entries:
            raise FetchError('Malformed RSS/Atom feed', 'parse_error', page.status)
        if not feed.entries and not feed.get('version'):
            raise FetchError('Response is not an RSS/Atom feed', 'parse_error', page.status)
        items = []
        for entry in feed.entries[:source.budget]:
            url = entry.get('link')
            if not url:
                continue
            try:
                canonical_url(url)
            except (ValueError, FetchError):
                continue
            _, text, _ = text_html(entry.get('summary', ''))
            # Feeds are news/discovery evidence, never a Verified offer shortcut.
            items.append(build_item(source, page, entry.get('title'), text, url, news=True,
                                    published=entry.get('published') or entry.get('updated')))
        return items, page
    if source.adapter == 'github':
        try:
            rows = json.loads(page.body)
            if not isinstance(rows, list):
                raise ValueError('Expected releases array')
            return [build_item(source, page, r.get('name') or r['tag_name'], r.get('body') or '',
                               r['html_url'], news=True, published=r.get('published_at'))
                    for r in rows[:source.budget] if not r.get('draft')], page
        except (ValueError, KeyError, TypeError) as exc:
            raise FetchError('Invalid GitHub release response', 'parse_error', page.status) from exc
    raise FetchError('Unsupported adapter', 'disabled')
