"""Public feeds and bounded robots-aware JSON-LD discovery. No browser bypass."""
import ipaddress
import json
import socket
from urllib.parse import urlparse, urljoin, quote
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from .core import normalize

class DiscoveryError(ValueError):
    pass

BLOCKED = ('glassdoor.com', 'glassdoor.co.in', 'ambitionbox.com', 'linkedin.com')

def validate_url(url):
    p = urlparse(url)
    host = (p.hostname or '').lower()
    if p.scheme != 'https' or not host or p.username or p.password or p.port not in (None, 443):
        raise DiscoveryError('Use a public HTTPS careers URL without credentials or a custom port.')
    if any(host == d or host.endswith('.' + d) for d in BLOCKED):
        raise DiscoveryError('Protected job/review sites are not supported. Use the company careers page.')
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise DiscoveryError('Private and local network addresses are not allowed.')
    except socket.gaierror as exc:
        raise DiscoveryError('Company hostname could not be resolved.') from exc
    return url

class Client:
    def __init__(self):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers['User-Agent'] = 'CareerPilot/2.0 (personal public job discovery)'
        self.robots = {}

    def get(self, url):
        for _ in range(5):
            validate_url(url)
            try:
                with self.session.get(url, timeout=(8, 20), allow_redirects=False, stream=True) as r:
                    if r.is_redirect:
                        url = urljoin(url, r.headers['Location'])
                        continue
                    r.raise_for_status()
                    chunks, size = [], 0
                    for chunk in r.iter_content(65536):
                        size += len(chunk)
                        if size > 8_000_000:
                            raise DiscoveryError('Source exceeds the 8 MB response limit.')
                        chunks.append(chunk)
                    return b''.join(chunks).decode('utf-8', errors='replace')
            except requests.RequestException as exc:
                raise DiscoveryError(f'Source unavailable ({type(exc).__name__}). No demo jobs substituted.') from exc
        raise DiscoveryError('Too many redirects.')

    def page(self, url):
        p = urlparse(validate_url(url))
        origin = f'{p.scheme}://{p.netloc}'
        if origin not in self.robots:
            try:
                rp = RobotFileParser()
                rp.parse(self.get(origin + '/robots.txt').splitlines())
                self.robots[origin] = rp
            except DiscoveryError as exc:
                raise DiscoveryError('Could not verify robots.txt; use a direct supported ATS board URL.') from exc
        if not self.robots[origin].can_fetch('CareerPilot', url):
            raise DiscoveryError('This page disallows automated access.')
        return self.get(url)


def ats(url):
    p = urlparse(url)
    parts = p.path.strip('/').split('/')
    if p.hostname in ('boards.greenhouse.io', 'job-boards.greenhouse.io') and parts[0]:
        return 'greenhouse', parts[0]
    if p.hostname in ('jobs.lever.co', 'jobs.eu.lever.co') and parts[0]:
        return 'lever-eu' if 'eu.' in p.hostname else 'lever', parts[0]
    return None

def feed(company, kind, slug, client):
    slug = quote(slug, safe='')
    if kind == 'greenhouse':
        payload = json.loads(client.get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true'))
        if not isinstance(payload.get('jobs'), list):
            raise DiscoveryError('Unexpected Greenhouse response.')
        return [normalize(company, f'greenhouse:{slug}', j['id'], j['title'], j.get('content',''), j.get('location',{}).get('name',''), j.get('absolute_url','')) for j in payload['jobs']]
    host = 'api.eu.lever.co' if kind == 'lever-eu' else 'api.lever.co'
    jobs = []
    for skip in range(0, 2000, 100):
        batch = json.loads(client.get(f'https://{host}/v0/postings/{slug}?mode=json&limit=100&skip={skip}'))
        if not isinstance(batch, list):
            raise DiscoveryError('Unexpected Lever response.')
        for j in batch:
            desc = j.get('description','') + ' ' + ' '.join(x.get('text','') + ' ' + x.get('content','') for x in j.get('lists',[])) + ' ' + j.get('additional','')
            c = j.get('categories',{})
            jobs.append(normalize(company, f'{kind}:{slug}', j['id'], j['text'], desc, c.get('location',''), j.get('hostedUrl',''), c.get('commitment','')))
        if len(batch) < 100:
            return jobs
    raise DiscoveryError('Board exceeds the 2,000-job limit; scan not saved as complete.')

def jsonld_jobs(html, company, url):
    jobs = []
    def walk(obj):
        if isinstance(obj, list):
            for value in obj: walk(value)
        elif isinstance(obj, dict):
            types = obj.get('@type', [])
            if types == 'JobPosting' or isinstance(types, list) and 'JobPosting' in types:
                locations = obj.get('jobLocation', [])
                if isinstance(locations, dict): locations = [locations]
                loc = []
                for location in locations:
                    a = location.get('address', {}) if isinstance(location, dict) else {}
                    if isinstance(a, str): loc.append(a)
                    else: loc.extend(str(a[k]) for k in ('addressLocality','addressRegion','addressCountry') if a.get(k))
                if obj.get('jobLocationType') == 'TELECOMMUTE': loc.append('Remote')
                link = urljoin(url, obj.get('url') or url)
                ident = obj.get('identifier', {})
                ident = ident.get('value') if isinstance(ident, dict) else ident
                if obj.get('title') and obj.get('description'):
                    jobs.append(normalize(company, urlparse(url).hostname, ident or link + '#' + obj['title'], obj['title'], obj['description'], ', '.join(loc), link, obj.get('employmentType','')))
            for key, value in obj.items():
                if key != '@context' and isinstance(value, (dict, list)): walk(value)
    for script in BeautifulSoup(html, 'html.parser').find_all('script', type='application/ld+json'):
        try: walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError): continue
    return jobs

def discover(company, url, client=None):
    if not url:
        raise DiscoveryError('Company saved. Add its official careers URL to enable discovery; names alone are ambiguous.')
    client = client or Client()
    detected = ats(url)
    if detected: return feed(company, *detected, client), 'Complete public ATS feed'
    html = client.page(url)
    jobs = jsonld_jobs(html, company, url)
    soup = BeautifulSoup(html, 'html.parser')
    links = list(dict.fromkeys(urljoin(url, a.get('href') or a.get('src') or '') for a in soup.select('a[href],iframe[src]')))
    for link in links:
        detected = ats(link)
        if detected: return feed(company, *detected, client), 'Complete linked ATS feed'
    candidates = [l for l in links if urlparse(l).hostname == urlparse(url).hostname and re_job(l) and l != url][:10]
    failures = 0
    for link in candidates:
        try: jobs.extend(jsonld_jobs(client.page(link), company, link))
        except DiscoveryError: failures += 1
    if not jobs:
        raise DiscoveryError('No accessible structured jobs found. This page may require JavaScript or another adapter. Try a direct Greenhouse/Lever URL.')
    return list({j['id']: j for j in jobs}.values()), f'Partial page scan (up to 10 detail pages; {failures} inaccessible). Not a full company inventory.'

def re_job(url):
    import re
    return bool(re.search(r'/(jobs?|careers?|positions?|openings?)/', urlparse(url).path, re.I))
