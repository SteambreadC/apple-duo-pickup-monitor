import unittest
from verify_catalog import verify_html
from monitor import CheckError

class CatalogTests(unittest.TestCase):
    def test_correct_sku_and_capacity(self):
        html = '<script type="application/ld+json">{"@type":"Product","name":"iPhone Duo 512GB Night Sky","color":"Night Sky","offers":[{"sku":"MK1H4LL/A+unlocked","priceCurrency":"USD"}]}</script>defaultOnloadPart: "MK1H4LL/A"'
        self.assertEqual(verify_html(html, 'MK1H4LL/A', 'Night Sky')['part'], 'MK1H4LL/A')
        for bad in [html.replace('512GB', '256GB'), html.replace('MK1H4', 'MK1F4'), html.replace('USD', 'CAD')]:
            with self.assertRaises(CheckError): verify_html(bad, 'MK1H4LL/A', 'Night Sky')
