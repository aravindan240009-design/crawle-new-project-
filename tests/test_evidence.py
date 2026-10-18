import hashlib
import json

import pytest

from backend.extract import canonical_url, official, geography, build_item, collect, benefit_excerpt
from backend.fetch import Page, FetchError
from backend.fixtures import demo_sources
from backend.models import now
from backend.summary import validate_model_output, summarize
from backend.models import Settings


def page(text, url='https://example.com/cloud'):
    return Page(url, text, 'text/html', 200, hashlib.sha256(text.encode()).hexdigest(), now())


def test_canonical_identity():
    assert canonical_url('https://EXAMPLE.com/a?utm_source=foo&coupon=INDIA&tier=2#fragment') == 'https://example.com/a?coupon=INDIA&tier=2'
    assert canonical_url('https://example.com/a?region=IN') != canonical_url('https://example.com/a?region=US')
    assert canonical_url('https://example.com/?ref=program') == 'https://example.com/?ref=program'


def test_payment_prices_are_not_free_benefits():
    assert benefit_excerpt('$0.01344 per branch per hour') is None
    assert benefit_excerpt('A credit card is required') is None
    assert benefit_excerpt('The Free plan includes limited usage') == 'The Free plan includes limited usage'


@pytest.mark.parametrize('url,expected', [('https://example.com/a', True), ('https://docs.example.com/a', True), ('https://example.com.evil.net/a', False), ('https://examp1e.com/a', False)])
def test_official_domains(url, expected):
    assert official(url, ['example.com']) == expected


@pytest.mark.parametrize('text,state', [
    ('Available worldwide.', 'India eligible'), ('Available worldwide, except India.', 'Not eligible'),
    ('Free trial for US-student-only applicants.', 'Not eligible'),
    ('Available worldwide. Restricted countries apply.', 'Unclear'),
    ('Available in India. Eligible startups must apply.', 'India eligible'), ('Website loads in India', 'Unclear')])
def test_geographic_gates(text, state):
    assert geography(text)[0] == state


def test_evidence_and_unknowns():
    source = demo_sources()[0]
    text = 'Free tier provides 100 requests per day.\nAvailable worldwide.\nNo credit card required.\nUsage limits apply.'
    item = build_item(source, page(text), text=text)
    assert item['verification'] == 'Verified'
    assert item['card_required'] is False
    assert item['deadline'] is None
    assert item['personal_eligibility'].startswith('Unknown')
    assert {'benefit', 'geography', 'card_required'} <= set(item['supported_claims'])
    assert all(e['excerpt'] in text and len(e['content_hash']) == 64 for e in item['evidence'])
    unknown = build_item(source, page('Our great homepage'), text='Our great homepage')
    assert unknown['verification'] == 'Unverified' and unknown['card_required'] is None


def test_conflicting_terms_and_dates():
    source = demo_sources()[0]
    text = 'Free trial.\nNo credit card required.\nA credit card is required.\nDeadline: 2027-01-02'
    item = build_item(source, page(text), text=text)
    assert item['verification'] == 'Contradicted'
    assert item['card_required'] is None
    assert item['deadline'] == '2027-01-02'
    assert item['deadline_precision'].startswith('date')


def test_leads_never_verify():
    source = demo_sources()[0].model_copy(update={'official_domains': []})
    text = 'Free tier. Available worldwide. No credit card required. Usage limits apply.'
    item = build_item(source, page(text), text=text)
    assert item['verification'] == 'Unverified'
    assert not item['evidence'] and item['geography'] == 'Unclear'


def test_summary_rejects_hallucinations():
    sentences = ['Benefit from Provider', 'Conditions are unknown', 'Deadline not stated']
    assert validate_model_output('{"sentence_indexes":[0,1,2]}', sentences) == '\n'.join(sentences)
    for raw in ['{"summary":"$100000 free"}', '{"sentence_indexes":[0]}', '{"sentence_indexes":[0,1,99]}']:
        with pytest.raises(ValueError):
            validate_model_output(raw, sentences)


async def test_model_disabled():
    assert await summarize({'summary': 'Faithful baseline'}, Settings()) == ('Faithful baseline', 'disabled')


async def test_feed_and_github_parsing():
    class Fake:
        body = '<rss version="2.0"><channel><title>Feed</title><item><title>Launch</title><link>https://example.com/launch</link><description>Free tier announced</description></item></channel></rss>'
        async def get(self, *args, **kwargs):
            return page(self.body)
    fake = Fake()
    source = demo_sources()[0].model_copy(update={'adapter': 'feed'})
    items, _ = await collect(source, fake)
    assert len(items) == 1 and items[0]['kind'] == 'news'
    fake.body = json.dumps([{'tag_name': 'v1', 'body': 'Release notes', 'html_url': 'https://example.com/releases/1'}])
    items, _ = await collect(source.model_copy(update={'adapter': 'github'}), fake)
    assert items[0]['title'] == 'v1'
    fake.body = '<html>Not a feed</html>'
    with pytest.raises(FetchError):
        await collect(source, fake)


async def test_event_index_candidates_and_exact_dates():
    html = '''<main><h1>Official events</h1><a href="https://organizer.example/event" itemtype="https://schema.org/Event"><h3>Demo Hackathon</h3><meta itemprop="startDate" content="2027-01-02T10:00:00Z"><meta itemprop="endDate" content="2027-01-03T10:00:00Z"><meta itemprop="eventAttendanceMode" content="https://schema.org/OnlineEventAttendanceMode">Event information</a></main>'''
    class Fake:
        async def get(self, *args, **kwargs):
            return page(html)
    source = demo_sources()[0].model_copy(update={'strategy': 'event_index'})
    items, _ = await collect(source, Fake())
    item = items[0]
    assert item['title'] == 'Demo Hackathon' and item['kind'] == 'competition/event'
    assert item['deadline'] is None and item['start_date'] == '2027-01-02T10:00:00+00:00'
    assert item['official_url'] is None  # External organizer not auto-trusted.
    assert item['location'] == 'Online' and item['geography'] == 'Unclear'


async def test_terms_exclusion_and_conflict():
    source = demo_sources()[0].model_copy(update={'terms_url': 'https://example.com/terms'})
    class Fake:
        async def get(self, url, **kwargs):
            text = '<main>Free tier with usage limits. Available worldwide. No credit card required.</main>' if url == source.url else '<main>This free tier is not available in India. A credit card is required.</main>'
            return page(text, url)
    items, _ = await collect(source, Fake())
    assert items[0]['geography'] == 'Not eligible'
    assert items[0]['verification'] == 'Contradicted'
    assert any(e['url'].endswith('/terms') for e in items[0]['evidence'])


async def test_public_search_never_trusts_discovered_domains():
    source = demo_sources()[0].model_copy(update={'adapter': 'search', 'url': 'https://hn.algolia.com/api/v1/search?query=credits'})
    class Fake:
        async def get(self, *args, **kwargs):
            return page(json.dumps({'hits': [{'title': 'Free credits', 'url': 'https://new-provider.example/offer', 'created_at': '2026-10-09T00:00:00Z'}]}))
    items, _ = await collect(source, Fake())
    assert items[0]['verification'] == 'Unverified' and not items[0]['evidence']
