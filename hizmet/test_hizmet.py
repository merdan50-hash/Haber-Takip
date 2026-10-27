"""Haber Takip hizmeti testleri: python3 -m unittest discover -s hizmet"""
import hashlib
import http.server
import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile

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
<a href="/gundem/2026/10/uzun-bir-haber-basligi-burada-yer-aliyor"><span>15:14</span> Uzun bir haber başlığı burada yer alıyor</a>
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
        for server in (cls.api, cls.fixtures):
            server.shutdown()
            server.server_close()
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


def package(version, extra=None, service=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("HaberTakip/eklenti/manifest.json", json.dumps({"version": version}))
        archive.writestr("HaberTakip/eklenti/app.js", "// yeni")
        archive.writestr("HaberTakip/eklenti/icons/icon16.png", b"png")
        archive.writestr("HaberTakip/eklenti/bridge-config.js", "// paketteki boş ayar")
        archive.writestr("HaberTakip/hizmet/haber_takip_hizmeti.py", service or "VERSION = %r\n" % version)
        archive.writestr("HaberTakip/kur-macos.command", "#!/bin/bash")
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return buffer.getvalue()


class FakeGitHub(http.server.BaseHTTPRequestHandler):
    release = {}
    files = {}

    def do_GET(self):
        if self.path == "/repos/sahip/depo/releases/latest":
            body, kind = json.dumps(self.release).encode("utf-8"), "application/json"
        elif self.path in self.files:
            body, kind = self.files[self.path], "application/zip"
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class UpdaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.github = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
        threading.Thread(target=cls.github.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.github.server_port

    @classmethod
    def tearDownClass(cls):
        cls.github.shutdown()
        cls.github.server_close()

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.extension = os.path.join(self.root, "eklenti")
        os.makedirs(self.extension)
        with open(os.path.join(self.extension, "manifest.json"), "w") as stream:
            json.dump({"version": h.VERSION}, stream)
        with open(os.path.join(self.extension, "bridge-config.js"), "w") as stream:
            stream.write("// anahtar")
        self.updater = h.Updater(h.Store(os.path.join(self.root, "durum.json")), self.extension, self.root,
                                 repo="sahip/depo", api=self.base)
        self.updater.service_path = os.path.join(self.root, "haber_takip_hizmeti.py")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def publish(self, version, data, digest=None):
        name = "haber-takip-kurulum-%s.zip" % version
        FakeGitHub.files = {"/indir/" + name: data}
        FakeGitHub.release = {"tag_name": "v" + version, "assets": [{
            "name": name, "url": self.base + "/api/asset", "browser_download_url": self.base + "/indir/" + name,
            "digest": digest or "sha256:" + hashlib.sha256(data).hexdigest()}]}

    def read(self, *parts):
        with open(os.path.join(self.extension, *parts)) as stream:
            return stream.read()

    def test_installs_newer_release(self):
        self.publish("99.0.0", package("99.0.0"))
        self.assertTrue(self.updater.check())
        self.assertEqual(self.updater.extension_version, "99.0.0")
        self.assertEqual(self.read("app.js"), "// yeni")
        self.assertEqual(self.read("bridge-config.js"), "// anahtar", "erişim anahtarı korunmalı")
        self.assertTrue(os.path.exists(os.path.join(self.extension, "icons", "icon16.png")))
        with open(self.updater.service_path) as stream:
            self.assertIn("99.0.0", stream.read())

    def test_same_version_is_up_to_date(self):
        self.publish(h.VERSION, package(h.VERSION))
        self.assertFalse(self.updater.check())
        self.assertEqual(self.updater.state["state"], "güncel")

    def test_rejects_bad_digest(self):
        self.publish("99.0.0", package("99.0.0"), digest="sha256:" + "0" * 64)
        self.assertFalse(self.updater.check())
        self.assertIn("SHA-256", self.updater.state["error"])
        self.assertEqual(self.read("bridge-config.js"), "// anahtar")
        self.assertFalse(os.path.exists(os.path.join(self.extension, "app.js")))

    def test_rejects_path_traversal(self):
        self.publish("99.0.0", package("99.0.0", {"HaberTakip/eklenti/../../kotu.txt": "x"}))
        self.assertFalse(self.updater.check())
        self.assertFalse(os.path.exists(os.path.join(self.root, "kotu.txt")))
        self.assertFalse(os.path.exists(self.updater.service_path))

    def test_rejects_broken_service(self):
        self.publish("99.0.0", package("99.0.0", service="def bozuk(:\n"))
        self.assertFalse(self.updater.check())
        self.assertFalse(os.path.exists(self.updater.service_path))

    def test_version_compare(self):
        self.assertGreater(h.version_tuple("1.10.0"), h.version_tuple("1.9.9"))
        self.assertEqual(h.version_tuple("v1.4.0"), (1, 4, 0))


if __name__ == "__main__":
    unittest.main()
