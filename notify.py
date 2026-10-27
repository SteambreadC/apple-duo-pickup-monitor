"""Notification adapters. Secrets are supplied only through environment variables."""
import json
import os
import re
import smtplib
import ssl
import urllib.parse
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo


class DeliveryError(Exception):
    pass


def render(event):
    when = datetime.fromisoformat(event['checked_at']).astimezone(ZoneInfo('America/Los_Angeles'))
    stamp = when.strftime('%Y-%m-%d %H:%M:%S %Z')
    if event.get('kind') in ('test', 'health'):
        title = 'TEST - Apple Duo monitor' if event['kind'] == 'test' else 'Apple monitor - CHECK FAILED'
        return title, event['message'] + '\nChecked: ' + stamp, 'https://www.apple.com/shop/buy-iphone/iphone-duo'
    title = f"Apple pickup: {event['store']} - {event['color']} 512GB"
    text = '\n'.join([
        'Apple official pickup signal (rechecked; not a reservation)',
        f"Store: {event['store']} ({event['store_id']})",
        f"iPhone Duo 512GB {event['color']} | {event['part']}",
        f"Pickup: {event['pickup_quote']}",
        'Pickup date: ' + (event['pickup_date'] or 'See Apple quote above; exact calendar date unverified'),
        'Verified: ' + stamp,
        event['url'], event['store_url'],
        'Availability can change. Select this store and confirm pickup at Apple before ordering.',
    ])
    return title, text, event['url']


def secure_url(url, allow_local=False):
    parsed = urllib.parse.urlsplit(url)
    local = parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if (parsed.scheme != 'https' and not (allow_local and local and parsed.scheme == 'http')) or not parsed.hostname or parsed.username or parsed.password:
        raise DeliveryError('Notification URL must use HTTPS without embedded credentials')
    return url.rstrip('/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise DeliveryError('Notification redirects are refused')


def post_json(url, body, headers=None):
    request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'),
                                    headers={'Content-Type': 'application/json', **(headers or {})}, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            result = json.loads(response.read(100_000))
            if response.status != 200:
                raise DeliveryError('Provider did not acknowledge message')
            return result
    except DeliveryError:
        raise
    except Exception:
        raise DeliveryError('Notification provider failed') from None


def send_ntfy(event, server, topic, token='', allow_local=False):
    server = secure_url(server, allow_local)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', topic):
        raise DeliveryError('Invalid ntfy topic')
    title, text, url = render(event)
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    result = post_json(server, {'topic': topic, 'title': title, 'message': text,
                               'priority': 4, 'click': url}, headers)
    if not isinstance(result, dict) or not result.get('id'):
        raise DeliveryError('ntfy did not return a message ID')


def send_telegram(event, token, chat_id, base_url='https://api.telegram.org', allow_local=False):
    base_url = secure_url(base_url, allow_local)
    title, text, url = render(event)
    result = post_json(base_url + '/bot' + urllib.parse.quote(token, safe=':') + '/sendMessage',
                       {'chat_id': chat_id, 'text': title + '\n' + text, 'disable_web_page_preview': True})
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise DeliveryError('Telegram did not acknowledge message')


def send_email(event, env, allow_local=False):
    title, text, url = render(event)
    message = EmailMessage()
    message['Subject'] = title; message['From'] = env['MAIL_FROM']; message['To'] = env['MAIL_TO']
    message.set_content(text)
    host = env['SMTP_HOST']; security = env.get('SMTP_SECURITY') or 'starttls'
    port = int(env.get('SMTP_PORT', '') or ('465' if security == 'ssl' else '587'))
    context = ssl.create_default_context()
    if security == 'ssl':
        client = smtplib.SMTP_SSL(host, port, timeout=20, context=context)
    elif security == 'starttls' or (allow_local and security == 'local-test' and host in ('127.0.0.1', 'localhost')):
        client = smtplib.SMTP(host, port, timeout=20)
    else:
        raise DeliveryError('SMTP must use starttls or ssl')
    with client:
        if security == 'starttls':
            client.ehlo(); client.starttls(context=context); client.ehlo()
        if env.get('SMTP_USER'):
            client.login(env['SMTP_USER'], env['SMTP_PASSWORD'])
        refused = client.send_message(message)
        if refused:
            raise DeliveryError('SMTP refused recipient')


def configured_channels(env=None):
    env = os.environ if env is None else env
    channels = {}
    if env.get('NTFY_TOPIC'):
        topic = env['NTFY_TOPIC']; server = env.get('NTFY_SERVER') or 'https://ntfy.sh'
        secure_url(server)
        if not re.fullmatch(r'[A-Za-z0-9_-]{20,128}', topic):
            raise DeliveryError('Use a random ntfy topic with at least 20 characters')
        channels['ntfy'] = lambda event: send_ntfy(event, server, topic, env.get('NTFY_TOKEN', ''))
    if env.get('TELEGRAM_BOT_TOKEN') or env.get('TELEGRAM_CHAT_ID'):
        if not env.get('TELEGRAM_BOT_TOKEN') or not env.get('TELEGRAM_CHAT_ID'):
            raise DeliveryError('Configure both Telegram token and chat ID')
        channels['telegram'] = lambda event: send_telegram(event, env['TELEGRAM_BOT_TOKEN'], env['TELEGRAM_CHAT_ID'])
    mail_keys = ('SMTP_HOST', 'MAIL_FROM', 'MAIL_TO', 'SMTP_USER', 'SMTP_PASSWORD')
    if any(env.get(key) for key in mail_keys):
        if not all(env.get(key) for key in mail_keys):
            raise DeliveryError('Configure SMTP_HOST, SMTP_USER, SMTP_PASSWORD, MAIL_FROM, MAIL_TO together')
        if (env.get('SMTP_SECURITY') or 'starttls') not in ('ssl', 'starttls'):
            raise DeliveryError('SMTP security must be ssl or starttls')
        port = env.get('SMTP_PORT')
        if port and (not port.isdigit() or not 1 <= int(port) <= 65535):
            raise DeliveryError('Invalid SMTP port')
        channels['email'] = lambda event: send_email(event, env)
    return channels
