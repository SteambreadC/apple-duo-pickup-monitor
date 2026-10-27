import json
import socketserver
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import monitor as m
import notify as n
from test_monitor import NOW, KEY, payload


class HTTPHandler(BaseHTTPRequestHandler):
    received = []
    reply = b'{"ok": true, "id": "test"}'
    def do_POST(self):
        self.received.append((self.path, self.rfile.read(int(self.headers['Content-Length'])), dict(self.headers)))
        self.send_response(200); self.end_headers(); self.wfile.write(self.reply)
    def log_message(self, *args):
        pass


class SMTPHandler(socketserver.StreamRequestHandler):
    messages = []
    def handle(self):
        self.wfile.write(b'220 localhost test SMTP\r\n')
        while line := self.rfile.readline():
            cmd = line.decode().upper()
            if cmd.startswith('EHLO') or cmd.startswith('HELO'):
                self.wfile.write(b'250 localhost\r\n')
            elif cmd.startswith('DATA'):
                self.wfile.write(b'354 send data\r\n')
                data = b''
                while (line := self.rfile.readline()) != b'.\r\n':
                    if not line: return
                    data += line
                self.messages.append(data); self.wfile.write(b'250 accepted\r\n')
            elif cmd.startswith('QUIT'):
                self.wfile.write(b'221 bye\r\n'); return
            else:
                self.wfile.write(b'250 ok\r\n')


class NotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), HTTPHandler)
        cls.smtp = socketserver.ThreadingTCPServer(('127.0.0.1', 0), SMTPHandler)
        for server in [cls.server, cls.smtp]:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()
        cls.smtp.shutdown(); cls.smtp.server_close()

    def setUp(self):
        HTTPHandler.received.clear(); SMTPHandler.messages.clear()
        HTTPHandler.reply = b'{"ok": true, "id": "test"}'
        self.event = m.parse_payload(payload(), NOW)[KEY]

    def test_ntfy_local_http_and_message_fields(self):
        n.send_ntfy(self.event, self.url, 'local-test', allow_local=True)
        data = json.loads(HTTPHandler.received[0][1])
        for expected in ['Pioneer Place', 'Night Sky', '512GB', '2026-10-27', '19:30', 'apple.com']:
            self.assertIn(expected, data['message'])
        self.assertEqual(data['click'], self.event['url'])
        self.assertEqual(data['topic'], 'local-test')

    def test_telegram_local_http_and_rejection(self):
        n.send_telegram(self.event, 'test-token', 'test-chat', base_url=self.url, allow_local=True)
        data = json.loads(HTTPHandler.received[0][1])
        self.assertEqual(data['chat_id'], 'test-chat')
        self.assertIn('Pioneer Place', data['text'])
        HTTPHandler.reply = b'{"ok": false}'
        with self.assertRaises(n.DeliveryError):
            n.send_telegram(self.event, 'test-token', 'test-chat', base_url=self.url, allow_local=True)

    def test_smtp_real_local_protocol(self):
        n.send_email(self.event, {'SMTP_HOST': '127.0.0.1', 'SMTP_PORT': str(self.smtp.server_address[1]),
                     'SMTP_SECURITY': 'local-test', 'MAIL_FROM': 'sender@example.invalid',
                     'MAIL_TO': 'receiver@example.invalid'}, allow_local=True)
        self.assertEqual(len(SMTPHandler.messages), 1)
        self.assertIn(b'Pioneer Place', SMTPHandler.messages[0])
        self.assertIn(b'Night Sky', SMTPHandler.messages[0])

    def test_unsafe_notification_url_and_incomplete_config(self):
        with self.assertRaises(n.DeliveryError):
            n.send_ntfy(self.event, 'http://example.invalid', 'topic')
        for env in [{'TELEGRAM_BOT_TOKEN': 'x'}, {'SMTP_HOST': 'x'}, {'MAIL_TO': 'x'}]:
            with self.assertRaises(n.DeliveryError): n.configured_channels(env)

    def test_test_label(self):
        title, text, url = n.render({'kind': 'test', 'message': 'TEST ONLY, no inventory', 'checked_at': NOW.isoformat()})
        self.assertIn('TEST', title)
        self.assertIn('TEST ONLY', text)


class ClientTests(unittest.TestCase):
    def test_429_and_541_stop_without_inline_retry(self):
        for code in (429, 541):
            calls = []
            def opener(request, timeout):
                calls.append(request)
                raise urllib.error.HTTPError(request.full_url, code, 'blocked', {'Retry-After': '7200'}, None)
            with self.assertRaises(m.CheckError) as caught:
                m.fetch_location('98033', opener)
            self.assertEqual(caught.exception.retry_after, 7200)
            self.assertEqual(len(calls), 1)

    def test_transient_available_not_sent(self):
        a = m.parse_payload(payload(), NOW)
        u = m.parse_payload(payload('unavailable'), NOW)
        sequence = iter([a, a, u, u])
        self.assertEqual(m.collect(lambda loc: next(sequence), lambda delay: None)[KEY]['status'], 'unknown')

    def test_complete_confirmation_retains_timestamp(self):
        a = m.parse_payload(payload(), NOW)
        result = m.collect(lambda loc: a, lambda delay: None)
        self.assertEqual(result[KEY]['status'], 'available')

    def test_bad_state_fails_closed(self):
        for value in [{}, {'schema': 1, 'items': []}, {**m.new_state(), 'next_check': 'bad'}]:
            with self.assertRaises(m.CheckError): m.validate_state(value)


if __name__ == '__main__':
    unittest.main()
