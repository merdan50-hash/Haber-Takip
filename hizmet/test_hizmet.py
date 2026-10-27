"""Haber Takip hizmeti testleri: python3 -m unittest discover -s hizmet"""
import http.server
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

import haber_takip_hizmeti as h

RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Örnek</title>
<item><title><![CDATA[İstanbul'da <b>ilk</b> haber]]></title><link>https://ornek.test/haber/1</link>
<pubDate>Tue, 27 Oct 2026 10:00:00 +0300</pubDate></item>
<item><title>Saatsiz haber</title><link>/haber/2</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom haberi</title><link rel="alternate" href="https://ornek.test/a/1"/><updated>2026-10-27T07:00:00Z</updated></entry>
<entry><title>Yalnız tarih</title><link href="https://ornek.test/a/2"/><published>2026-10-26</published></entry>
</feed>"""

BROKEN = """<rss><channel><item><title>Bozuk &nbsp; akış</title><link>https://ornek.test/b/1</link>
<pubDate>Tue, 27 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>"""

HTML_WITH_FEED = '<html><head><link rel="alternate" type="application/rss+xml" href="/akis.xml"></head><body></body></html>'
HTML_NO_FEED = """<html><body><a href="/">Ana sayfa</a>
<a href="/gundem/2026/10/uzun-bir-haber-basligi-burada-yer-aliyor">Uzun bir haber başlığı burada yer alıyor</a>
<a href="https://baska.test/gundem/2026/10/dis-baglanti">Başka sitedeki uzun bir haber başlığı burada</a></body></html>"""


class ParsingTests(unittest.TestCase):
    def test_rss(self):
        items = h.parse_feed(RSS, "https://ornek.test/rss")
        self.assertEqual([i["title"] for i in items], ["İstanbul'da ilk haber", "Saatsiz haber"])
        self.assertEqual(items[1]["link"], "https://ornek.test/haber/2")

    def test_atom_and_dates(self):
        items = h.parse_feed(ATOM, "https://ornek.test/")
        self.assertEqual([i["link"] for i in items], ["https://ornek.test/a/1", "https://ornek.test/a/2"])
        self.assertEqual(h.parse_date(items[0]["date"]), (1793084400.0, None))
        self.assertEqual(h.parse_date(items[1]["date"])[1], "2026-10-26")
        self.assertEqual(h.parse_date("Tue, 27 Oct 2026 10:00:00 +0300")[0], 1793084400.0)
        self.assertEqual(h.parse_date("2026-10-27T10:00:00.123+0300")[0], 1793084400.0)
        self.assertEqual(h.parse_date("dün"), (None, None))

    def test_broken_feed_fallback(self):
        self.assertEqual(h.parse_feed(BROKEN, "https://ornek.test/")[0]["title"], "Bozuk akış")

    def test_doctype_entities_are_not_expanded(self):
        bomb = '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa">]><rss><channel><item><title>&a;</title><link>https://ornek.test/x</link></item></channel></rss>'
        self.assertNotIn("aaaaaaaaaa", json.dumps(h.parse_feed(bomb, "https://ornek.test/")))

    def test_page_headlines(self):
        page = h.PageParser()
        page.feed(HTML_NO_FEED)
        found = h.page_headlines(page, "https://www.ornek.test/")
        self.assertEqual([i["title"] for i in found], ["Uzun bir haber başlığı burada yer alıyor"])

    def test_helpers(self):
        self.assertEqual(h.tr_lower("IĞDIR İZMİR"), "ığdır izmir")
        self.assertEqual(h.host_of("https://www.bianet.org/x"), "bianet.org")
        self.assertIsNone(h.normalize_url("javascript:alert(1)"))
        self.assertIsNone(h.normalize_url("https://kullanici:sifre@ornek.test/"))
        self.assertTrue(h.is_private_host("http://127.0.0.1:8080/"))
        self.assertTrue(h.is_private_host("http://192.168.1.1/"))
        self.assertFalse(h.is_private_host("https://bianet.org/"))


class Fixtures(http.server.BaseHTTPRequestHandler):
    pages = {"/": (HTML_WITH_FEED, "text/html"), "/akis.xml": (RSS, "application/rss+xml"),
             "/duz/": (HTML_NO_FEED, "text/html; charset=utf-8")}

    def do_GET(self):
        body, kind = self.pages.get(self.path, ("yok", "text/plain"))
        self.send_response(200 if self.path in self.pages else 404)
        self.send_header("Content-Type", kind)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):
        pass


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.ALLOW_PRIVATE_HOSTS = True
        cls.fixtures = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fixtures)
        threading.Thread(target=cls.fixtures.serve_forever, daemon=True).start()
        cls.site = "http://127.0.0.1:%d/" % cls.fixtures.server_port
        cls.data = tempfile.mkdtemp()
        cls.store = h.Store(os.path.join(cls.data, "durum.json"))
        cls.scanner = h.Scanner(cls.store)
        threading.Thread(target=cls.scanner.run, daemon=True).start()
        cls.token = "t" * 32
        cls.api = http.server.ThreadingHTTPServer(("127.0.0.1", 0), None)
        cls.api.RequestHandlerClass = h.make_handler(cls.store, cls.scanner, cls.token, cls.api.server_port)
        threading.Thread(target=cls.api.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        h.ALLOW_PRIVATE_HOSTS = False
        cls.api.shutdown()
        cls.fixtures.shutdown()
        shutil.rmtree(cls.data, ignore_errors=True)

    def call(self, path, method="GET", body=None, token=None, host=None):
        request = urllib.request.Request("http://127.0.0.1:%d%s" % (self.api.server_port, path), method=method,
                                         data=None if body is None else json.dumps(body).encode("utf-8"))
        request.add_header("Authorization", "Bearer " + (token or self.token))
        if host:
            request.add_header("Host", host)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def wait_for(self, check):
        for _ in range(100):
            if check():
                return
            time.sleep(0.1)
        self.fail("zaman aşımı")

    def test_flow(self):
        self.assertEqual(self.call("/api/status", token="yanlis")[0], 401)
        self.assertEqual(self.call("/api/status", host="kotu.test:%d" % self.api.server_port)[0], 403)

        self.assertEqual(self.call("/api/import", "POST", {"sites": [self.site], "poll": 30, "articles": []}),
                         (200, {"ok": True, "imported": True}))
        self.assertEqual(self.call("/api/import", "POST", {"sites": ["https://bianet.org"]})[1]["imported"], False)
        self.wait_for(lambda: self.call("/api/status")[1]["sources"][0]["lastSuccess"])
        status = self.call("/api/status")[1]
        self.assertEqual(status["poll"], 30)
        self.assertEqual(status["sources"][0]["feed"], self.site + "akis.xml")
        self.assertEqual(status["unread"], 0, "ilk taramadaki haberler yeni sayılmamalı")

        page = self.call("/api/articles?query=%C4%B0stanbul&offset=0&limit=50")[1]
        self.assertEqual([a["title"] for a in page["articles"]], ["İstanbul'da ilk haber"])
        self.assertFalse(page["articles"][0]["a"])
        self.assertTrue(self.call("/api/articles?query=saatsiz")[1]["articles"][0]["a"])

        self.assertEqual(self.call("/api/sources", "POST", {"url": self.site})[0], 409)
        self.assertEqual(self.call("/api/sources", "POST", {"url": "ftp://x"})[0], 400)
        self.assertEqual(self.call("/api/config", "PATCH", {"poll": 7})[0], 400)
        self.assertEqual(self.call("/api/config", "PATCH", {"poll": 60})[0], 200)

        # Sonraki taramada yeni çıkan haber okunmamış sayılır.
        Fixtures.pages["/akis.xml"] = (RSS.replace("<channel><title>Örnek</title>",
            "<channel><item><title>Son dakika</title><link>https://ornek.test/haber/3</link></item>"), "application/rss+xml")
        with self.store.lock:
            self.store.runtime[self.site]["due"] = 0
        self.scanner.wake.set()
        self.wait_for(lambda: self.call("/api/status")[1]["unread"] == 1)
        key = self.call("/api/articles?unread=1")[1]["articles"][0]["k"]
        self.call("/api/read", "POST", {"keys": [key]})
        self.assertEqual(self.call("/api/status")[1]["unread"], 0)

        self.store.save()
        self.assertEqual(len(h.Store(self.store.path).data["articles"]), 3)

        self.assertEqual(self.call("/api/sources", "DELETE", {"url": self.site})[0], 200)
        self.assertEqual(self.call("/api/articles")[1]["total"], 0)

    def test_page_without_feed(self):
        store = h.Store(os.path.join(self.data, "duz.json"))
        store.add_site(self.site + "duz/")
        h.Scanner(store).scan(dict(store.data["sites"][0]))
        self.assertIsNone(store.runtime[self.site + "duz/"]["error"])
        self.assertEqual([a["title"] for a in store.data["articles"].values()], ["Uzun bir haber başlığı burada yer alıyor"])


if __name__ == "__main__":
    unittest.main()
