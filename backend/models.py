from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Source(StrictModel):
    id: str = Field(pattern=r'^[a-z0-9_-]{1,64}$')
    name: str = Field(min_length=1, max_length=160)
    adapter: Literal['html', 'feed', 'github', 'community', 'search']
    url: str = Field(max_length=2048)
    family: str = Field(default='official', max_length=60)
    category: Literal['AI', 'Cloud', 'Developer', 'Opportunities', 'Learning', 'Shopping', 'News', 'Food', 'Travel', 'Local services', 'Events', 'Jobs', 'Open source'] = 'AI'
    provider: str = Field(max_length=120)
    official_domains: list[str] = Field(default_factory=list, max_length=12)
    enabled: bool = True
    cadence_minutes: int = Field(default=1440, ge=15, le=43200)
    timeout: int = Field(default=20, ge=3, le=60)
    budget: int = Field(default=5, ge=1, le=30)
    interval_seconds: float = Field(default=2, ge=1, le=120)
    selector: str = Field(default='main', max_length=160)
    strategy: Literal['page', 'event_index'] = 'page'
    terms_url: str | None = None
    notes: str = Field(default='', max_length=2000)

    @field_validator('url', 'terms_url')
    @classmethod
    def public_syntax(cls, value):
        if value is None:
            return value
        u = urlsplit(value)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
            raise ValueError('Use a public HTTP(S) URL without credentials')
        if u.port not in (None, 80, 443):
            raise ValueError('Only web ports 80 and 443 are supported')
        return value

    @field_validator('official_domains')
    @classmethod
    def domains(cls, values):
        for v in values:
            if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', v) or '.' not in v:
                raise ValueError('Official domains must be lowercase hostnames, not URLs')
        return values


class Settings(StrictModel):
    mode: Literal['manual', 'daily', 'continuous'] = 'continuous'
    daily_time: str = '08:00'
    armed: bool = False
    continuous_minutes: int = Field(default=60, ge=15, le=10080)
    concurrency: int = Field(default=4, ge=1, le=8)
    run_budget_seconds: int = Field(default=600, ge=30, le=3600)
    retention_days: int = Field(default=90, ge=7, le=3650)
    event_retention_days: int = Field(default=90, ge=7, le=3650)
    alerts_enabled: bool = True
    min_alert_confidence: int = Field(default=75, ge=0, le=100)
    source_families: list[str] = Field(default_factory=list, max_length=30)
    student: bool | None = None
    founder: bool | None = None
    model_enabled: bool = False
    model_name: str = Field(default='', max_length=100)
    model_url: Literal['http://127.0.0.1:11434'] = 'http://127.0.0.1:11434'
    discovery_enabled: bool = True
    quiet_start: str = '22:00'
    quiet_end: str = '08:00'

    @field_validator('daily_time', 'quiet_start', 'quiet_end')
    @classmethod
    def time_format(cls, value):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
            raise ValueError('Expected HH:MM')
        return value


class ItemState(StrictModel):
    bookmarked: bool = False
    dismissed: bool = False
    notes: str = Field(default='', max_length=10000)


class Tracking(StrictModel):
    status: Literal['interested', 'preparing', 'applied', 'accepted', 'declined', 'archived'] = 'interested'
    reminder_date: str | None = None

    @field_validator('reminder_date')
    @classmethod
    def reminder_format(cls, value):
        if value:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('Use YYYY-MM-DD for the personal reminder')
            datetime.strptime(value, '%Y-%m-%d')
        return value or None


class Filters(StrictModel):
    q: str = Field(default='', max_length=200)
    category: str = ''
    provider: str = ''
    family: str = ''
    kind: str = ''
    geography: str = ''
    verification: str = ''
    lifecycle: str = ''
    location: str = ''
    publication_state: Literal['', 'provisional', 'evidence_reviewed'] = ''
    media_status: str = ''
    license_class: str = ''
    near_me: bool = False
    latitude: float = Field(default=13.0827, ge=-90, le=90)
    longitude: float = Field(default=80.2707, ge=-180, le=180)
    radius_km: float = Field(default=10, ge=.1, le=500)
    card: Literal['', 'yes', 'no', 'unknown'] = ''
    min_discount: float | None = Field(default=None, ge=0, le=100)
    min_confidence: int = Field(default=0, ge=0, le=100)
    deadline_days: int | None = Field(default=None, ge=1, le=365)
    discovered_after: str = ''
    new_only: bool = False
    bookmarked: bool = False
    show_dismissed: bool = False
    show_ineligible: bool = False
    news: bool = False
    snapshot: str = ''
    sort: Literal['relevance', 'newest', 'deadline', 'confidence', 'provider', 'category'] = 'relevance'
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=24, ge=1, le=100)

    @field_validator('discovered_after')
    @classmethod
    def valid_date(cls, value):
        if value:
            datetime.strptime(value, '%Y-%m-%d')
        return value
