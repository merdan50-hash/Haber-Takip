#!/usr/bin/env python3
"""Haber Takip yerel hizmeti.

Eklenen sitelerin RSS/Atom akışlarını (yoksa ana sayfadaki haber bağlantılarını) düzenli
aralıklarla tarar ve Haber Takip Chrome eklentisine yalnızca 127.0.0.1 üzerinden sunar.
Yalnızca Python standart kütüphanesini kullanır (Python 3.8+).
"""
import argparse
import email.utils
import hashlib
import hmac
import html
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.3.0"
POLLS = (5, 10, 15, 30, 60, 120, 300)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) HaberTakip/" + VERSION
MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_BODY = 16 * 1024 * 1024
MAX_ARTICLES = 20000
KEEP_SECONDS = 30 * 24 * 3600
MAX_PER_SCAN = 150
MAX_BACKOFF = 1800
FEED_PATHS = ("/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml")

ALLOW_PRIVATE_HOSTS = False  # yalnızca testler için


def log(*parts):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *parts, file=sys.stderr, flush=True)


def host_of(url):
    try:
        name = urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return ""
    return name[4:] if name.startswith("www.") else name


def tr_lower(text):
    return text.replace("I", "ı").replace("İ", "i").lower()


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize_url(value, base=None):
    """Güvenli bir http(s) adresi döndürür; geçersizse None."""
    try:
        if base:
            value = urllib.parse.urljoin(base, value.strip())
        parts = urllib.parse.urlsplit(value.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        return None
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", parts.query, ""))


def is_private_host(url):
    name = urllib.parse.urlsplit(url).hostname or ""
    if name == "localhost" or name.endswith(".localhost") or name.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(name.strip("[]"))
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local or address.is_reserved


# --- İndirme -----------------------------------------------------------------

class FetchError(Exception):
    pass


CURL_ERRORS = {
    5: "Vekil sunucu adresi çözülemedi.",
    6: "Site adresi bulunamadı (DNS). Adresi ve internet bağlantısını kontrol edin.",
    7: "Siteye bağlanılamadı.",
    28: "Site zamanında yanıt vermedi.",
    35: "Güvenli bağlantı (SSL) kurulamadı.",
    47: "Site çok fazla yönlendirme yaptı.",
    52: "Site boş yanıt döndürdü.",
    56: "Bağlantı yarıda kesildi.",
    60: "Sitenin güvenlik sertifikası doğrulanamadı.",
    63: "Sayfa çok büyük.",
}


def fetch(url, timeout=20):
    """(gövde, son adres, içerik türü) döndürür. macOS'ta sistem sertifikalarını kullanan curl tercih edilir."""
    curl = shutil.which("curl")
    if curl:
        handle, path = tempfile.mkstemp(prefix="habertakip-")
        os.close(handle)
        try:
            result = subprocess.run(
                [curl, "-sS", "-L", "--compressed", "--max-redirs", "5", "--max-time", str(timeout),
                 "--max-filesize", str(MAX_DOWNLOAD), "-A", USER_AGENT,
                 "-H", "Accept: application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.5",
                 "-o", path, "-w", "%{http_code} %{url_effective} %{content_type}", "--", url],
                capture_output=True, text=True, timeout=timeout + 5)
            if result.returncode != 0:
                raise FetchError(CURL_ERRORS.get(result.returncode, "Site okunamadı (curl hata kodu %d)." % result.returncode))
            status, final, *rest = result.stdout.split(" ", 2) + [""]
            if not status.startswith("2"):
                raise FetchError("Site HTTP %s yanıtı verdi." % status)
            with open(path, "rb") as stream:
                return stream.read(MAX_DOWNLOAD + 1)[:MAX_DOWNLOAD], final or url, (rest[0] if rest else "").strip()
        except subprocess.TimeoutExpired:
            raise FetchError("Site %d saniyede yanıt vermedi." % timeout)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(MAX_DOWNLOAD), response.geturl(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        raise FetchError("Site HTTP %d yanıtı verdi." % error.code)
    except (urllib.error.URLError, OSError) as error:
        raise FetchError("Siteye bağlanılamadı: %s" % getattr(error, "reason", error))


def decode(body, content_type=""):
    match = re.search(r"charset=([\w-]+)", content_type, re.I) or \
        re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.I)
    charset = match.group(1) if match else "utf-8"
    if isinstance(charset, bytes):
        charset = charset.decode("ascii", "ignore")
    try:
        return body.decode(charset, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


# --- Tarih ------------------------------------------------------------------

def parse_date(value):
    """(unix zamanı, yalnız tarih) döndürür; anlaşılamazsa (None, None)."""
    value = (value or "").strip()
    if not value:
        return None, None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            stamp = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
            return stamp, value
        except ValueError:
            return None, None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed:
            return (parsed if parsed.tzinfo else parsed.astimezone()).timestamp(), None
    except (TypeError, ValueError, IndexError):
        pass
    iso = re.sub(r"(\.\d+)", "", value.replace("Z", "+00:00").replace(" ", "T", 1))
    iso = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", iso)
    try:
        parsed = datetime.fromisoformat(iso)
        return (parsed if parsed.tzinfo else parsed.astimezone()).timestamp(), None
    except ValueError:
        return None, None


# --- Akış ve sayfa ayrıştırma ------------------------------------------------

def looks_like_feed(text):
    head = text.lstrip()[:2000].lower()
    return head.startswith("<?xml") and ("<rss" in head or "<feed" in head or "<rdf" in head) or \
        head.startswith("<rss") or head.startswith("<feed")


def local(tag):
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def parse_feed(text, base):
    """Akıştaki haberleri [{title, link, date}] olarak döndürür."""
    items = []
    try:
        # XML bildirimi metin olarak ayrıştırmayı engeller; DOCTYPE ise varlık genişletme saldırılarına kapı açar.
        cleaned = re.sub(r"^\s*<\?xml[^>]*\?>", "", text, count=1)
        root = ET.fromstring(re.sub(r"<!DOCTYPE[^>\[]*(\[.*?\])?\s*>", "", cleaned, count=1, flags=re.S).strip())
        for node in root.iter():
            if local(node.tag) not in ("item", "entry"):
                continue
            fields, link = {}, None
            for child in node:
                name = local(child.tag)
                if name == "link":
                    href = child.get("href")
                    if href and child.get("rel", "alternate") == "alternate":
                        link = link or href
                    elif not href and (child.text or "").strip():
                        link = link or child.text.strip()
                elif name in ("title", "pubdate", "date", "published", "updated", "issued", "guid") and name not in fields:
                    fields[name] = "".join(child.itertext())
                    if name == "guid" and child.get("isPermaLink", "true") == "false":
                        fields.pop("guid")
            items.append({"title": fields.get("title", ""), "link": link or fields.get("guid"),
                          "date": fields.get("pubdate") or fields.get("published") or fields.get("date")
                          or fields.get("issued") or fields.get("updated")})
    except (ET.ParseError, ValueError):
        # Geçersiz XML yayınlayan siteler için hoşgörülü yedek ayrıştırıcı.
        for block in re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", text, re.S | re.I):
            def field(*names):
                for name in names:
                    found = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (name, name), block, re.S | re.I)
                    if found:
                        return re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", found.group(1).strip(), flags=re.S)
                return None
            href = re.search(r"<link\b[^>]*href=[\"']([^\"']+)", block, re.I)
            items.append({"title": field("title") or "", "link": field("link") or (href.group(1) if href else None) or field("guid"),
                          "date": field("pubDate", "dc:date", "published", "updated")})
    result = []
    for item in items:
        link = normalize_url(html.unescape(item["link"] or ""), base)
        title = clean_text(item["title"])
        if link and title:
            result.append({"title": title[:500], "link": link, "date": item["date"]})
    return result


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.feeds, self.links, self._href, self._text = [], [], None, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "alternate" in (attrs.get("rel") or "").lower() and \
                (attrs.get("type") or "").lower() in ("application/rss+xml", "application/atom+xml") and attrs.get("href"):
            self.feeds.append(attrs["href"])
        elif tag == "a":
            self._href, self._text = attrs.get("href"), []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href = None


def page_headlines(page, base):
    """RSS'i olmayan siteler için ana sayfadaki haber başlığına benzeyen bağlantılar."""
    site, seen, result = host_of(base), set(), []
    for href, text in page.links:
        link, title = normalize_url(href or "", base), clean_text(text)
        if not link or link in seen or not (25 <= len(title) <= 300):
            continue
        path = urllib.parse.urlsplit(link).path
        if not host_of(link).endswith(site) or len(path) < 8 or not re.search(r"[-_]|\d", path):
            continue
        seen.add(link)
        result.append({"title": title, "link": link, "date": None})
    return result


# --- Durum -------------------------------------------------------------------

class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.dirty = False
        self.revision = 1
        self.data = {"imported": False, "poll": 60, "sites": [], "articles": {}}
        self.runtime = {}  # kaynak adresi -> çalışma zamanı durumu (diske yazılmaz)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as stream:
                    loaded = json.load(stream)
                self.data.update(loaded)
                self.data["articles"] = {item["k"]: item for item in loaded.get("articles", [])}
            except (OSError, ValueError, KeyError, TypeError) as error:
                backup = path + ".bozuk-%d" % int(time.time())
                log("Kayıt dosyası okunamadı, yedeklenip boş başlatılıyor:", error)
                try:
                    os.replace(path, backup)
                except OSError:
                    pass
        for site in self.data["sites"]:
            self._runtime(site["url"])

    def _runtime(self, url):
        return self.runtime.setdefault(url, {"lastSuccess": None, "error": None, "partialError": None,
                                             "errors": 0, "due": 0, "busy": False, "baseline": None})

    def changed(self):
        self.revision += 1
        self.dirty = True

    def save(self):
        with self.lock:
            if not self.dirty:
                return
            payload = dict(self.data, articles=list(self.data["articles"].values()), version=VERSION)
            self.dirty = False
        directory = os.path.dirname(self.path)
        handle, temp = tempfile.mkstemp(dir=directory, prefix=".durum-")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False)
            os.replace(temp, self.path)
        except OSError as error:
            log("Kayıt yazılamadı:", error)
            with self.lock:
                self.dirty = True
            try:
                os.unlink(temp)
            except OSError:
                pass

    def site(self, url):
        return next((site for site in self.data["sites"] if site["url"] == url), None)

    def add_site(self, url, feed=None):
        if any(host_of(site["url"]) == host_of(url) for site in self.data["sites"]):
            return False
        self.data["sites"].append({"url": url, "feed": feed, "scanned": False})
        self._runtime(url)
        self.changed()
        return True

    def remove_site(self, url):
        before = len(self.data["sites"])
        self.data["sites"] = [site for site in self.data["sites"] if site["url"] != url]
        if len(self.data["sites"]) == before:
            return False
        self.runtime.pop(url, None)
        self.data["articles"] = {k: item for k, item in self.data["articles"].items() if item.get("src") != url}
        self.changed()
        return True

    def sort_key(self, item):
        if item.get("a"):
            return item["seen"]
        return min(item["t"], item["seen"]) if not item.get("dateOnly") else item["t"]

    def prune(self):
        limit = time.time() - KEEP_SECONDS
        articles = self.data["articles"]
        stale = [k for k, item in articles.items() if item["seen"] < limit and not item.get("f")]
        for k in stale:
            del articles[k]
        if len(articles) > MAX_ARTICLES:
            for item in sorted(articles.values(), key=self.sort_key)[:len(articles) - MAX_ARTICLES]:
                del articles[item["k"]]


# --- Tarayıcı ----------------------------------------------------------------

class Scanner:
    def __init__(self, store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.wake = threading.Event()

    def run(self):
        while True:
            now = time.time()
            with self.store.lock:
                due = []
                for site in self.store.data["sites"]:
                    state = self.store._runtime(site["url"])
                    if not state["busy"] and state["due"] <= now:
                        state["busy"] = True
                        due.append(dict(site))
            for site in due:
                self.pool.submit(self.scan, site)
            self.wake.wait(1)
            self.wake.clear()

    def discover(self, url):
        """Kaynağın akış adresini bulur. (akış adresi veya None, haberler) döndürür."""
        body, final, content_type = fetch(url)
        text = decode(body, content_type)
        if looks_like_feed(text):
            return url, parse_feed(text, final)
        page = PageParser()
        try:
            page.feed(text)
        except Exception:  # bozuk HTML taramayı durdurmamalı
            pass
        candidates = [normalize_url(href, final) for href in page.feeds]
        root = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(final))
        candidates += [root + path for path in FEED_PATHS]
        for candidate in dict.fromkeys(filter(None, candidates)):
            try:
                feed_body, feed_final, feed_type = fetch(candidate, timeout=12)
            except FetchError:
                continue
            feed_text = decode(feed_body, feed_type)
            if looks_like_feed(feed_text):
                items = parse_feed(feed_text, feed_final)
                if items:
                    return candidate, items
        return None, page_headlines(page, final)

    def scan(self, site):
        url, feed, error, items = site["url"], site.get("feed"), None, []
        try:
            if feed:
                try:
                    body, final, content_type = fetch(feed)
                    text = decode(body, content_type)
                    if not looks_like_feed(text):
                        raise FetchError("RSS adresi artık akış döndürmüyor.")
                    items = parse_feed(text, final)
                except FetchError:
                    with self.store.lock:
                        failures = self.store._runtime(url)["errors"]
                    if failures < 2:
                        raise
                    feed, items = self.discover(url)  # akış birkaç kez başarısızsa yeniden ara
            else:
                feed, items = self.discover(url)
            if not items:
                raise FetchError("Sitede haber bulunamadı. RSS adresini doğrudan eklemeyi deneyin.")
        except FetchError as failure:
            error = str(failure)
        except Exception as failure:  # beklenmedik hata: hizmet çalışmaya devam etmeli
            log("Tarama hatası", url, repr(failure))
            error = "Site okunamadı: %s" % failure.__class__.__name__
        self.finish(url, feed, items, error)

    def finish(self, url, feed, items, error):
        now = time.time()
        store = self.store
        with store.lock:
            site = store.site(url)
            state = store.runtime.get(url)
            if not site or not state:
                return  # tarama sürerken kaynak kaldırıldı
            state["busy"] = False
            poll = store.data["poll"]
            if error:
                state["errors"] += 1
                state["error"] = error
                state["due"] = now + min(MAX_BACKOFF, max(poll, 15 * 2 ** (state["errors"] - 1)))
                store.changed()
                return
            state.update(error=None, errors=0, lastSuccess=now, due=now + poll)
            if site.get("feed") != feed:
                site["feed"] = feed
            baseline = not site.get("scanned")
            site["scanned"] = True
            name, articles, added = host_of(url), store.data["articles"], 0
            for item in items[:MAX_PER_SCAN]:
                key = hashlib.sha1(item["link"].encode("utf-8")).hexdigest()[:20]
                existing = articles.get(key)
                if existing:
                    if existing["title"] != item["title"]:
                        existing["title"] = item["title"]
                        added += 1
                    continue
                stamp, date_only = parse_date(item["date"])
                articles[key] = {"k": key, "src": url, "site": name, "title": item["title"], "link": item["link"],
                                 "t": stamp if stamp else now, "seen": now, "a": stamp is None,
                                 "dateOnly": date_only, "f": not baseline}
                added += 1
            if added:
                store.prune()
            store.changed()


# --- HTTP API ----------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def make_handler(store, scanner, token, port):
    allowed_hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}

    def status():
        sites = store.data["sites"]
        counts = {}
        unread = 0
        for item in store.data["articles"].values():
            counts[item["src"]] = counts.get(item["src"], 0) + 1
            unread += 1 if item.get("f") else 0
        sources = []
        for site in sites:
            state = store._runtime(site["url"])
            sources.append({"url": site["url"], "feed": site.get("feed"), "count": counts.get(site["url"], 0),
                            "lastSuccess": state["lastSuccess"], "error": state["error"],
                            "partialError": state["partialError"], "errors": state["errors"],
                            "next": int(state["due"] * 1000) if state["error"] else None})
        return {"sites": [site["url"] for site in sites], "sources": sources, "revision": store.revision,
                "poll": store.data["poll"], "unread": unread, "version": VERSION}

    def articles(params):
        query = tr_lower(params.get("query", [""])[0].strip())
        site = params.get("site", [""])[0]
        unread = params.get("unread", [""])[0] == "1"
        try:
            offset = max(0, int(params.get("offset", ["0"])[0]))
            limit = min(500, max(1, int(params.get("limit", ["200"])[0])))
        except ValueError:
            raise ApiError(400, "Geçersiz sayfa bilgisi.")
        found = [item for item in store.data["articles"].values()
                 if (not site or item["site"] == site) and (not unread or item.get("f"))
                 and (not query or query in tr_lower(item["title"]) or query in item["site"])]
        found.sort(key=store.sort_key, reverse=True)
        page = [{key: item[key] for key in ("k", "site", "title", "link", "t", "seen", "a", "dateOnly", "f")}
                for item in found[offset:offset + limit]]
        return {"articles": page, "total": len(found), "revision": store.revision}

    def import_legacy(body):
        if store.data["imported"]:
            return {"ok": True, "imported": False}
        sites = body.get("sites") if isinstance(body.get("sites"), list) else []
        feeds = body.get("feeds") if isinstance(body.get("feeds"), dict) else {}
        for value in sites:
            url = normalize_url(value) if isinstance(value, str) else None
            if url and (ALLOW_PRIVATE_HOSTS or not is_private_host(url)):
                feed = feeds.get(value) if isinstance(feeds.get(value), str) else None
                store.add_site(url, normalize_url(feed) if feed else None)
        if body.get("poll") in POLLS:
            store.data["poll"] = body["poll"]
        now = time.time()
        for old in body.get("articles") if isinstance(body.get("articles"), list) else []:
            if not isinstance(old, dict):
                continue
            link = normalize_url(old.get("link") or old.get("url") or "") if isinstance(old.get("link") or old.get("url"), str) else None
            title = clean_text(old.get("title") if isinstance(old.get("title"), str) else "")
            if not link or not title:
                continue
            stamp = old.get("t") or old.get("time") or old.get("date")
            stamp = stamp / 1000 if isinstance(stamp, (int, float)) and stamp > 1e12 else stamp
            stamp = stamp if isinstance(stamp, (int, float)) and 0 < stamp < now + 86400 else None
            owner = next((site["url"] for site in store.data["sites"] if host_of(link).endswith(host_of(site["url"]))), None)
            if not owner:
                continue
            key = hashlib.sha1(link.encode("utf-8")).hexdigest()[:20]
            store.data["articles"].setdefault(key, {"k": key, "src": owner, "site": host_of(owner), "title": title[:500],
                                                    "link": link, "t": stamp or now, "seen": stamp or now,
                                                    "a": stamp is None, "dateOnly": None, "f": False})
        for site in store.data["sites"]:
            site["scanned"] = site["scanned"] or any(item["src"] == site["url"] for item in store.data["articles"].values())
        store.data["imported"] = True
        store.prune()
        store.changed()
        scanner.wake.set()
        return {"ok": True, "imported": True}

    def add_source(body):
        url = normalize_url(body.get("url") if isinstance(body.get("url"), str) else "")
        if not url:
            raise ApiError(400, "Geçerli bir HTTP veya HTTPS adresi girin.")
        if not ALLOW_PRIVATE_HOSTS and is_private_host(url):
            raise ApiError(400, "Yerel ağ adresleri kaynak olarak eklenemez.")
        if not store.add_site(url):
            raise ApiError(409, "%s zaten ekli." % host_of(url))
        scanner.wake.set()
        return {"ok": True}

    def remove_source(body):
        if not store.remove_site(body.get("url")):
            raise ApiError(404, "Kaynak bulunamadı.")
        return {"ok": True}

    def mark_read(body):
        changed = 0
        if isinstance(body.get("keys"), list):
            for key in body["keys"][:5000]:
                item = store.data["articles"].get(key) if isinstance(key, str) else None
                if item and item.get("f"):
                    item["f"] = False
                    changed += 1
        elif isinstance(body.get("before"), (int, float)):
            for item in store.data["articles"].values():
                if item.get("f") and store.sort_key(item) <= body["before"]:
                    item["f"] = False
                    changed += 1
        else:
            raise ApiError(400, "Okundu bilgisi eksik.")
        if changed:
            store.changed()
        return {"ok": True, "changed": changed}

    def config(body):
        poll = body.get("poll")
        if poll not in POLLS:
            raise ApiError(400, "Geçersiz tarama aralığı.")
        store.data["poll"] = poll
        now = time.time()
        for state in store.runtime.values():
            if not state["error"]:
                state["due"] = min(state["due"], now + poll)
        store.changed()
        return {"ok": True}

    routes = {
        ("GET", "/api/status"): lambda params, body: status(),
        ("GET", "/api/articles"): lambda params, body: articles(params),
        ("POST", "/api/import"): lambda params, body: import_legacy(body),
        ("POST", "/api/sources"): lambda params, body: add_source(body),
        ("DELETE", "/api/sources"): lambda params, body: remove_source(body),
        ("POST", "/api/read"): lambda params, body: mark_read(body),
        ("PATCH", "/api/config"): lambda params, body: config(body),
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = "HaberTakip/" + VERSION
        sys_version = ""

        def log_message(self, *args):
            pass

        def reply(self, code, payload):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def handle_any(self):
            try:
                # Başka sitelerin DNS yeniden bağlama yoluyla hizmete ulaşmasını engeller.
                if self.headers.get("Host") not in allowed_hosts:
                    raise ApiError(403, "İzin verilmeyen adres.")
                header = self.headers.get("Authorization", "")
                if not hmac.compare_digest(header.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
                    raise ApiError(401, "Erişim anahtarı geçersiz.")
                parts = urllib.parse.urlsplit(self.path)
                route = routes.get((self.command, parts.path))
                if not route:
                    raise ApiError(404, "Bilinmeyen istek.")
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    raise ApiError(413, "İstek çok büyük.")
                body = {}
                if length:
                    try:
                        body = json.loads(self.rfile.read(length).decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        raise ApiError(400, "Geçersiz JSON.")
                    if not isinstance(body, dict):
                        raise ApiError(400, "Geçersiz istek gövdesi.")
                with store.lock:
                    result = route(urllib.parse.parse_qs(parts.query), body)
                self.reply(200, result)
            except ApiError as error:
                self.reply(error.status, {"error": str(error)})
            except Exception as error:
                log("İstek hatası", self.command, self.path, repr(error))
                self.reply(500, {"error": "Hizmette beklenmeyen bir hata oluştu."})

        do_GET = do_POST = do_DELETE = do_PATCH = handle_any

    return Handler


def main():
    global ALLOW_PRIVATE_HOSTS
    parser = argparse.ArgumentParser(description="Haber Takip yerel hizmeti")
    parser.add_argument("--data", required=True, help="kayıt klasörü")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--token-file", help="erişim anahtarı dosyası (varsayılan: <data>/token)")
    parser.add_argument("--allow-private-hosts", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    ALLOW_PRIVATE_HOSTS = args.allow_private_hosts

    os.makedirs(args.data, exist_ok=True)
    with open(args.token_file or os.path.join(args.data, "token"), encoding="utf-8") as stream:
        token = stream.read().strip()
    if len(token) < 16:
        sys.exit("Erişim anahtarı çok kısa veya boş.")

    store = Store(os.path.join(args.data, "durum.json"))
    scanner = Scanner(store)
    threading.Thread(target=scanner.run, daemon=True).start()

    def saver():
        while True:
            time.sleep(2)
            store.save()
    threading.Thread(target=saver, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(store, scanner, token, args.port))
    server.daemon_threads = True
    log("Haber Takip hizmeti %s, http://127.0.0.1:%d adresinde çalışıyor." % (VERSION, args.port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        store.save()


if __name__ == "__main__":
    main()
