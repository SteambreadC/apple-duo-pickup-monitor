import copy
import unittest
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime

import monitor as m

NOW = datetime(2026, 10, 27, 2, 30, tzinfo=timezone.utc)
PART = 'MK1H4LL/A'
KEY = 'R077|' + PART


def payload(display='available', title='iPhone Duo 512GB Night Sky'):
    return {'head': {'status': '200'}, 'body': {'stores': [{
        'storeNumber': 'R077', 'storeName': 'Pioneer Place',
        'partsAvailability': {PART: {
            'partNumber': PART, 'pickupDisplay': display,
            'storePickEligible': True, 'pickupType': 'In-Store Pickup',
            'pickupSearchQuote': 'Available Tomorrow' if display == 'available' else 'Currently unavailable',
            'messageTypes': {'regular': {
                'storeSelectionEnabled': display == 'available',
                'storePickupProductTitle': title,
                'storePickupQuote': 'Tomorrow at Apple Pioneer Place' if display == 'available' else 'Currently unavailable at Apple Pioneer Place'
            }}
        }}
    }]}}


class ParseTests(unittest.TestCase):
    def test_exact_available(self):
        o = m.parse_payload(payload(), NOW)
        self.assertEqual(o[KEY]['status'], 'available')
        self.assertEqual(o[KEY]['pickup_quote'], 'Tomorrow at Apple Pioneer Place')
        self.assertEqual(o[KEY]['pickup_date'], '2026-10-27')
        self.assertIn('apple.com/shop/buy-iphone/iphone-duo/', o[KEY]['url'])

    def test_shipping_is_never_pickup(self):
        p = payload('unavailable')
        p['body']['shippingMessage'] = {'availability': 'available', 'deliveryDate': 'Tomorrow'}
        self.assertEqual(m.parse_payload(p, NOW)[KEY]['status'], 'unavailable')

    def test_wrong_product_is_unknown(self):
        for title in ['iPhone Duo 256GB Night Sky', 'iPhone 18 Pro 512GB Night Sky', 'iPhone Duo 512GB Star White']:
            self.assertEqual(m.parse_payload(payload(title=title), NOW)[KEY]['status'], 'unknown')

    def test_mismatched_part_store_eligibility_and_missing_date(self):
        for field, value in [('partNumber', 'MK1F4LL/A'), ('storePickEligible', False), ('pickupType', 'Delivery'), ('pickupSearchQuote', '')]:
            p = payload(); p['body']['stores'][0]['partsAvailability'][PART][field] = value
            if field == 'pickupSearchQuote':
                p['body']['stores'][0]['partsAvailability'][PART]['messageTypes']['regular']['storePickupQuote'] = ''
            self.assertEqual(m.parse_payload(p, NOW)[KEY]['status'], 'unknown')
        p = payload(); p['body']['stores'][0]['storeName'] = 'Another Store'
        self.assertEqual(m.parse_payload(p, NOW)[KEY]['status'], 'unknown')

    def test_missing_and_duplicate_store_are_unknown(self):
        p = payload(); p['body']['stores'] *= 2
        self.assertEqual(m.parse_payload(p, NOW)[KEY]['status'], 'unknown')
        self.assertTrue(all(x['status'] == 'unknown' for x in m.parse_payload({'head': {'status': '200'}, 'body': {'stores': []}}, NOW).values()))

    def test_freshness(self):
        m.validate_freshness({'Date': format_datetime(NOW), 'Age': '0'}, NOW)
        for headers in [{}, {'Date': format_datetime(NOW - timedelta(minutes=5))}, {'Date': format_datetime(NOW), 'Age': '1'}, {'Date': format_datetime(NOW), 'Warning': '110 stale'}]:
            with self.assertRaises(m.CheckError):
                m.validate_freshness(headers, NOW)

    def test_merge_conflict_is_unknown(self):
        a = m.parse_payload(payload(), NOW)
        b = m.parse_payload(payload('unavailable'), NOW)
        self.assertEqual(m.merge_observations([a,b])[KEY]['status'], 'unknown')

    def test_schema_drift_fails_safely(self):
        for p in [None, [], {'head': [], 'body': {}}, {'head': {'status': '200'}, 'body': []}]:
            with self.assertRaises(m.CheckError): m.parse_payload(p, NOW)
        for field in ['messageTypes', 'partsAvailability']:
            p = payload()
            if field == 'messageTypes': p['body']['stores'][0]['partsAvailability'][PART][field] = []
            else: p['body']['stores'][0][field] = None
            self.assertEqual(m.parse_payload(p, NOW)[KEY]['status'], 'unknown')


class StateTests(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.channels = {'phone': lambda event: self.sent.append(event)}
        self.state = m.new_state()
        self.a = m.parse_payload(payload(), NOW)
        self.u = m.parse_payload(payload('unavailable'), NOW)
        self.x = copy.deepcopy(self.a); self.x[KEY]['status'] = 'unknown'

    def test_first_available_once_and_rearm_after_two_misses(self):
        for obs in [self.a, self.a, self.u, self.a]:
            m.process(self.state, obs, self.channels, NOW)
        self.assertEqual(len(self.sent), 1)
        for obs in [self.u, self.u, self.a]:
            m.process(self.state, obs, self.channels, NOW)
        self.assertEqual(len(self.sent), 2)

    def test_unknown_breaks_consecutive_misses(self):
        for obs in [self.a, self.u, self.x, self.u, self.a]:
            m.process(self.state, obs, self.channels, NOW)
        self.assertEqual(len(self.sent), 1)

    def test_delivery_failure_does_not_ack_or_resend_successful_channel(self):
        failures = []
        def fail(event):
            failures.append(event); raise RuntimeError('unavailable')
        channels = {**self.channels, 'mail': fail}
        self.assertTrue(m.process(self.state, self.a, channels, NOW))
        m.process(self.state, self.x, channels, NOW)
        m.process(self.state, self.a, channels, NOW)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(len(failures), 2)

    def test_changed_date_notifies(self):
        m.process(self.state, self.a, self.channels, NOW)
        a = copy.deepcopy(self.a); a[KEY]['pickup_quote'] = 'Friday at Apple Pioneer Place'
        m.process(self.state, a, self.channels, NOW)
        self.assertEqual(len(self.sent), 2)


if __name__ == '__main__':
    unittest.main()
