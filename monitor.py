"""Read-only Apple pickup monitor. No account, checkout, or order operations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ENDPOINT = 'https://www.apple.com/shop/retail/pickup-message'
TZ = ZoneInfo('America/Los_Angeles')
PARTS = {
    'MK1G4LL/A': ('Star White', 'star-white'),
    'MK1H4LL/A': ('Night Sky', 'night-sky'),
}
STORES = {
    'R003': 'Bellevue Square', 'R072': 'University Village',
    'R100': 'Alderwood', 'R106': 'Southcenter', 'R339': 'Tacoma Mall',
    'R077': 'Pioneer Place', 'R090': 'Washington Square', 'R134': 'Bridgeport Village',
}
LOCATIONS = ('98033', '97204')


class CheckError(Exception):
    def __init__(self, reason, retry_after=0):
        super().__init__(reason)
        self.retry_after = retry_after


def utcnow():
    return datetime.now(timezone.utc)


def new_state():
    return {'schema': 1, 'items': {}, 'failures': 0, 'next_check': 0,
            'last_success': None, 'health_delivered': {}}


def validate_state(state):
    if not isinstance(state, dict) or state.get('schema') != 1 or not isinstance(state.get('items'), dict):
        raise CheckError('Invalid persistent state; restore it instead of silently resetting deduplication')
    for item in state['items'].values():
        if (not isinstance(item, dict) or not isinstance(item.get('delivered', {}), dict)
                or not isinstance(item.get('misses', 0), int)):
            raise CheckError('Invalid persistent item state')
    for key in ('failures', 'next_check'):
        if not isinstance(state.get(key), (int, float)) or state[key] < 0:
            raise CheckError('Invalid persistent health state')
    if not isinstance(state.get('health_delivered'), dict):
        raise CheckError('Invalid persistent delivery state')
    return state


def validate_freshness(headers, now):
    h = {k.lower(): v for k, v in headers.items()}
    try:
        date = parsedate_to_datetime(h['date'])
        if date.tzinfo is None or not -30 <= (now - date).total_seconds() <= 120:
            raise ValueError('Date')
        if float(h.get('age', '0')) != 0:
            raise ValueError('Age')
        if re.search(r'\b(110|111|112|113)\b', h.get('warning', '')):
            raise ValueError('Warning')
        if 'hit' in h.get('x-cache', '').lower():
            raise ValueError('cache hit')
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise CheckError('Stale or unverifiable HTTP response; availability is unknown') from exc


def blank_observations():
    return {f'{store}|{part}': {'status': 'unknown'} for store in STORES for part in PARTS}


def normalized(text):
    return ' '.join(str(text).split())


def pickup_date(quote, now):
    local = now.astimezone(TZ).date()
    if re.search(r'\btomorrow\b', quote, re.I):
        return (local + timedelta(days=1)).isoformat()
    if re.search(r'\btoday\b', quote, re.I):
        return local.isoformat()
    # Do not invent an exact date for ambiguous localized/weekday/range quotes.
    return None


def parse_payload(payload, checked_at):
    out = blank_observations()
    if not isinstance(payload, dict) or not isinstance(payload.get('head'), dict) or str(payload['head'].get('status')) != '200':
        raise CheckError('Unexpected Apple application status')
    if not isinstance(payload.get('body'), dict):
        raise CheckError('Apple pickup schema changed')
    stores = payload['body'].get('stores')
    if not isinstance(stores, list):
        raise CheckError('Apple pickup schema changed')
    seen = set()
    for store in stores:
        if not isinstance(store, dict):
            continue
        sid = store.get('storeNumber')
        if sid not in STORES:
            continue
        if sid in seen:
            for part in PARTS:
                out[f'{sid}|{part}'] = {'status': 'unknown'}
            continue
        seen.add(sid)
        if normalized(store.get('storeName')) != STORES[sid]:
            continue
        availability = store.get('partsAvailability', {})
        if not isinstance(availability, dict):
            continue
        for part, (color, slug) in PARTS.items():
            data = availability.get(part)
            if not isinstance(data, dict):
                continue
            messages = data.get('messageTypes')
            if not isinstance(messages, dict):
                continue
            regular = messages.get('regular', {})
            if not isinstance(regular, dict):
                continue
            if (data.get('partNumber') != part
                    or normalized(regular.get('storePickupProductTitle')) != f'iPhone Duo 512GB {color}'
                    or data.get('pickupType') != 'In-Store Pickup'):
                continue
            display = data.get('pickupDisplay')
            if display == 'unavailable':
                out[f'{sid}|{part}'] = {'status': 'unavailable'}
                continue
            quote = normalized(regular.get('storePickupQuote', ''))
            search_quote = normalized(data.get('pickupSearchQuote', ''))
            if (display != 'available' or data.get('storePickEligible') is not True
                    or regular.get('storeSelectionEnabled') is not True
                    or not quote or not search_quote
                    or re.search(r'unavailable|not available|check back', quote + ' ' + search_quote, re.I)):
                continue
            out[f'{sid}|{part}'] = {
                'status': 'available', 'store_id': sid, 'store': STORES[sid],
                'part': part, 'color': color, 'capacity': '512GB',
                'pickup_quote': quote, 'pickup_date': pickup_date(quote, checked_at),
                'checked_at': checked_at.isoformat(),
                'url': f'https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-{slug}-unlocked',
                'store_url': 'https://www.apple.com/retail/' + {
                    'R003': 'bellevuesquare', 'R072': 'universityvillage', 'R100': 'alderwood',
                    'R106': 'southcenter', 'R339': 'tacomamall', 'R077': 'pioneerplace',
                    'R090': 'washingtonsquare', 'R134': 'bridgeportvillage'}[sid] + '/',
            }
    return out


def merge_observations(rounds):
    merged = blank_observations()
    for key in merged:
        values = [r[key] for r in rounds if r[key]['status'] != 'unknown']
        if values and len({v['status'] for v in values}) == 1:
            if values[0]['status'] == 'available' and len({v['pickup_quote'] for v in values}) > 1:
                continue
            merged[key] = values[-1]
    return merged


def retry_delay(value, now):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        try:
            return max(0, int((parsedate_to_datetime(value) - now).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 0


def fetch_location(location, opener=urllib.request.urlopen):
    query = {'pl': 'true', 'location': location, '_': uuid.uuid4().hex}
    query.update({f'parts.{i}': part for i, part in enumerate(PARTS)})
    request = urllib.request.Request(ENDPOINT + '?' + urllib.parse.urlencode(query), headers={
        'User-Agent': 'Mozilla/5.0 (compatible; PersonalPickupMonitor/1.0)',
        'Accept': 'application/json', 'Cache-Control': 'no-cache, no-store', 'Pragma': 'no-cache',
    })
    try:
        with opener(request, timeout=20) as response:
            now = utcnow()
            if response.status != 200 or not response.geturl().startswith(ENDPOINT + '?'):
                raise CheckError('Unexpected Apple response or redirect')
            validate_freshness(response.headers, now)
            if 'json' not in response.headers.get('Content-Type', '').lower():
                raise CheckError('Apple returned non-JSON content')
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise CheckError('Oversized Apple response')
            return parse_payload(json.loads(body), now)
    except urllib.error.HTTPError as exc:
        delay = retry_delay(exc.headers.get('Retry-After'), utcnow())
        if exc.code in (403, 429, 541):
            delay = max(delay, 3600)
        raise CheckError(f'Apple HTTP {exc.code}; availability unknown', delay) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise CheckError(f'Apple network/JSON failure ({type(exc).__name__}); availability unknown') from None


def collect(fetcher=fetch_location, sleeper=time.sleep):
    rounds = []
    # A hard failure aborts the round, avoiding more requests after a block/limit.
    for i, location in enumerate(LOCATIONS):
        if i:
            sleeper(1)
        rounds.append(fetcher(location))
    observations = merge_observations(rounds)
    if any(v['status'] == 'available' for v in observations.values()):
        sleeper(2)
        confirm = []
        for i, location in enumerate(LOCATIONS):
            if i:
                sleeper(1)
            confirm.append(fetcher(location))
        confirmed = merge_observations(confirm)
        for key, value in list(observations.items()):
            if value['status'] == 'available':
                check = confirmed[key]
                if check['status'] == 'available' and check['pickup_quote'] == value['pickup_quote']:
                    observations[key] = check
                else:
                    observations[key] = {'status': 'unknown'}
    return observations


def process(state, observations, channels, now, checkpoint=None, budget_seconds=180, clock=time.monotonic):
    delivery_errors = False
    failed_channels = set()
    deadline = clock() + budget_seconds
    for key, obs in observations.items():
        item = state['items'].setdefault(key, {'misses': 0, 'delivered': {}})
        if obs['status'] == 'unknown':
            item['misses'] = 0
            continue
        if obs['status'] == 'unavailable':
            item['misses'] = min(2, item.get('misses', 0) + 1)
            if item['misses'] >= 2:
                item['delivered'] = {}
            continue
        item['misses'] = 0
        # Exclude observation timestamp. Relative date must be normalized across midnight.
        signature = hashlib.sha256(json.dumps([key, obs['pickup_date'] or obs['pickup_quote']]).encode()).hexdigest()
        for name, send in channels.items():
            if item['delivered'].get(name) == signature:
                continue
            if name in failed_channels:
                delivery_errors = True
                continue
            if clock() >= deadline:
                print('Notification time budget reached; remaining channels stay pending.')
                return True
            try:
                send(obs)
                item['delivered'][name] = signature
            except Exception as exc:
                # Never log exception text: SMTP addresses/tokens or provider URLs may be in it.
                print(f'Notification failed: {name} ({type(exc).__name__})')
                delivery_errors = True
                failed_channels.add(name)
                continue
            # Persistence errors must stop delivery; do not treat them as provider failures.
            if checkpoint:
                checkpoint()
    return delivery_errors


def health(state, channels, now):
    if state['failures'] < 3:
        return
    event = {'kind': 'health', 'checked_at': now.isoformat(),
             'message': 'Apple pickup monitor has failed or has incomplete coverage for at least 3 checks. Stock is UNKNOWN. Check GitHub Actions. Last complete success: ' + str(state.get('last_success'))}
    for name, send in channels.items():
        if now.timestamp() - state['health_delivered'].get(name, 0) < 21600:
            continue
        try:
            send(event); state['health_delivered'][name] = now.timestamp()
        except Exception as exc:
            print(f'Health notification failed: {name} ({type(exc).__name__})')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Fresh Apple query; no state or notifications')
    parser.add_argument('--test-notifications', action='store_true', help='Send labelled tests; no Apple stock claim')
    parser.add_argument('--github-state', action='store_true')
    parser.add_argument('--state', default='work/state.json')
    parser.add_argument('--report', default='work/latest.json')
    args = parser.parse_args()
    from notify import configured_channels
    channels = configured_channels() if not args.dry_run else {}
    if args.test_notifications:
        if not channels:
            raise CheckError('No notification channels configured')
        failed = False
        for name, send in channels.items():
            try:
                send({'kind': 'test', 'checked_at': utcnow().isoformat(),
                      'message': 'TEST ONLY: Apple Duo pickup monitor notification test. This is NOT a stock alert.'})
                print(f'Test accepted by provider: {name}')
            except Exception as exc:
                print(f'Test failed: {name} ({type(exc).__name__})'); failed = True
        return 1 if failed else 0
    if not args.dry_run and not channels:
        raise CheckError('Configure at least one notification channel before enabling monitoring')
    storage = None
    if args.github_state and not args.dry_run:
        from github_state import GitHubState
        storage = GitHubState()
        state = storage.load()
    elif not args.dry_run and Path(args.state).exists():
        state = validate_state(json.loads(Path(args.state).read_text(encoding='utf-8')))
    else:
        state = new_state()
    now = utcnow()
    if state['next_check'] > now.timestamp():
        print('Apple backoff active; no request made. State is unknown until next successful check.')
        return 0
    errors = []
    try:
        observations = collect()
        unknown = sum(v['status'] == 'unknown' for v in observations.values())
        if unknown:
            errors.append(f'{unknown}/16 store/color combinations unknown')
    except CheckError as exc:
        observations = blank_observations()
        errors.append(str(exc))
        state['next_check'] = now.timestamp() + max(exc.retry_after, min(21600, 300 * 2 ** min(state['failures'], 6)))
    now = utcnow()
    if errors:
        state['failures'] += 1
    else:
        state['failures'] = 0; state['next_check'] = 0
        state['last_success'] = now.isoformat(); state['health_delivered'] = {}
    report = {'checked_at': now.isoformat(), 'errors': errors, 'observations': observations}
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding='utf-8')
    counts = {s: sum(v['status'] == s for v in observations.values()) for s in ('available', 'unavailable', 'unknown')}
    print(json.dumps({'checked_at': now.isoformat(), 'counts': counts, 'errors': errors}))
    if args.dry_run:
        for obs in observations.values():
            if obs['status'] == 'available':
                print(json.dumps(obs, ensure_ascii=False))
        return 1 if errors else 0
    def save():
        if storage:
            storage.save(state)
            return
        dest = Path(args.state); dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix('.tmp'); temp.write_text(json.dumps(state, indent=2), encoding='utf-8'); temp.replace(dest)
    failed_delivery = process(state, observations, channels, now, checkpoint=save)
    health(state, channels, now)
    save()
    return 1 if errors or failed_delivery else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (CheckError, ValueError, OSError) as exc:
        print(f'Monitor stopped safely ({type(exc).__name__}). Inspect configuration/state; no stock inference.')
        raise SystemExit(2)
