"""Manually revalidate the configured US product identities against official pages."""
import json
import re
import urllib.request

from monitor import PARTS, CheckError, utcnow


def verify_html(html, part, color):
    for raw in re.findall(r'<script\b[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html, re.S | re.I):
        data = json.loads(raw)
        if data.get('@type') != 'Product':
            continue
        offers = data.get('offers', [])
        if isinstance(offers, dict): offers = [offers]
        if (data.get('name') == f'iPhone Duo 512GB {color}' and data.get('color') == color
                and any(o.get('sku') == part + '+unlocked' and o.get('priceCurrency') == 'USD' for o in offers)
                and re.search(r'defaultOnloadPart:\s*"' + re.escape(part) + '"', html)):
            return {'part': part, 'name': data['name'], 'color': color, 'url': data.get('url')}
    raise CheckError('Official product identity does not match configured part/capacity/finish')


if __name__ == '__main__':
    for part, (color, slug) in PARTS.items():
        url = f'https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-{slug}-unlocked'
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=20) as response:
            result = verify_html(response.read(3_000_000).decode('utf-8'), part, color)
            print(json.dumps({'verified_at': utcnow().isoformat(), **result}))
