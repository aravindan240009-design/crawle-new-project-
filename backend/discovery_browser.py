"""Browser rendering with no direct browser network access."""
import hashlib

from .fetch import Page
from .models import now


async def render(fetcher, original, emit):
    from playwright.async_api import async_playwright
    emit('browser_started')
    blocked, fulfilled = 0, 0
    async with async_playwright() as p:
        # Defense in depth: if a browser feature escapes routing, its connection
        # hits a closed local proxy instead of opening an unchecked remote socket.
        browser = await p.chromium.launch(headless=True, proxy={'server': 'http://127.0.0.1:9'},
            args=['--proxy-bypass-list=<-loopback>', '--disable-quic', '--force-webrtc-ip-handling-policy=disable_non_proxied_udp'])
        try:
            context = await browser.new_context(service_workers='block', accept_downloads=False)
            # Every HTTP(S) request is fulfilled by our DNS-pinned transport.
            # No route.continue(), browser cookies, workers, WebRTC or downloads.
            await context.route_web_socket('**/*', lambda ws: ws.close())
            async def route_request(route):
                nonlocal blocked, fulfilled
                req = route.request
                if fulfilled+blocked >= 30 or req.method != 'GET' or req.resource_type not in ('document', 'script', 'stylesheet', 'xhr', 'fetch'):
                    blocked += 1
                    await route.abort()
                    return
                try:
                    page = original if req.url == original.url else await fetcher.get(req.url, timeout=10)
                    fulfilled += 1
                    # CSP also disables alternate browser network primitives.
                    await route.fulfill(status=200, body=page.body, headers={'content-type': page.content_type,
                        'content-security-policy': "default-src 'none'; script-src http: https: 'unsafe-inline'; style-src http: https: 'unsafe-inline'; connect-src http: https:; worker-src 'none'; frame-src 'none'; media-src 'none'; object-src 'none'; form-action 'none'"})
                except Exception:
                    blocked += 1
                    await route.abort()
            await context.route('**/*', route_request)
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(window, 'RTCPeerConnection', {value: undefined}); Object.defineProperty(window, 'webkitRTCPeerConnection', {value: undefined});")
            await page.goto(original.url, wait_until='domcontentloaded', timeout=30000)
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)
            except Exception:
                pass
            body = (await page.content())[:2_000_000]
            emit('browser_completed', metadata={'fulfilled_requests': fulfilled, 'blocked_requests': blocked})
            return Page(page.url, body, 'text/html', 200, hashlib.sha256(body.encode()).hexdigest(), now())
        finally:
            await browser.close()
