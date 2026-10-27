// Motor testleri: node --test test/
const test = require("node:test");
const assert = require("node:assert");
const m = require("../motor.js");

const RSS = `<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Örnek</title>
<item><title><![CDATA[İstanbul'da <b>ilk</b> haber]]></title><link>https://ornek.test/haber/1</link>
<pubDate>Tue, 27 Oct 2026 10:00:00 +0300</pubDate></item>
<item><title>Saatsiz &amp; haber</title><link>/haber/2</link></item>
</channel></rss>`;
const ATOM = `<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom haberi</title><link rel="alternate" href="https://ornek.test/a/1"/><updated>2026-10-27T07:00:00Z</updated></entry>
<entry><title>Yalnız tarih</title><link href="https://ornek.test/a/2"/><published>2026-10-26</published></entry>
</feed>`;
const HTML_FEED = '<html><head><link rel="alternate" type="application/rss+xml" href="/akis.xml"></head><body></body></html>';
const HTML_PLAIN = `<html><body><script>var a = "<a href='/x'>yanlış bağlantı burada yazıyor uzun</a>";</script>
<a href="/">Ana sayfa</a>
<a href="/gundem/2026/10/uzun-bir-haber-basligi"><span>15:14</span> Uzun bir haber başlığı burada yer alıyor</a>
<a href="https://baska.test/gundem/2026/10/dis">Başka sitedeki uzun bir haber başlığı burada</a></body></html>`;

test("RSS ayrıştırma", () => {
  const items = m.parseFeed(RSS, "https://ornek.test/rss");
  assert.deepStrictEqual(items.map(i => i.title), ["İstanbul'da ilk haber", "Saatsiz & haber"]);
  assert.strictEqual(items[1].link, "https://ornek.test/haber/2");
  assert.ok(m.looksLikeFeed(RSS) && m.looksLikeFeed(ATOM) && !m.looksLikeFeed(HTML_FEED));
});

test("Atom ve tarihler", () => {
  const items = m.parseFeed(ATOM, "https://ornek.test/");
  assert.deepStrictEqual(items.map(i => i.link), ["https://ornek.test/a/1", "https://ornek.test/a/2"]);
  assert.strictEqual(m.parseDate(items[0].date).t, 1793084400);
  assert.strictEqual(m.parseDate(items[1].date).dateOnly, "2026-10-26");
  assert.strictEqual(m.parseDate("Tue, 27 Oct 2026 10:00:00 +0300").t, 1793084400);
  assert.strictEqual(m.parseDate("2026-10-27T10:00:00.123+0300").t, 1793084400.123);
  assert.strictEqual(m.parseDate("dün").t, null);
});

test("Türkçe karakter kodlamaları", () => {
  const bytes = Uint8Array.from([0x3c, 0x61, 0x3e, 0xfe, 0xf0, 0xdd]); // windows-1254: şğİ
  assert.strictEqual(m.decodeBody(bytes.buffer, "text/html; charset=windows-1254"), "<a>şğİ");
  assert.strictEqual(m.decodeEntities("&ccedil;&#305;&#x15F;&nbsp;&bilinmeyen;"), "çış &bilinmeyen;");
  assert.strictEqual(m.cleanText("Birinci &lt;b&gt;kalın&lt;/b&gt; haber &amp; 3 &lt; 5"), "Birinci kalın haber & 3 < 5");
});

test("RSS'i olmayan sayfadan başlık çıkarma", () => {
  const page = m.parsePage(HTML_PLAIN, "https://www.ornek.test/");
  assert.deepStrictEqual(m.pageHeadlines(page, "https://www.ornek.test/").map(i => i.title),
    ["Uzun bir haber başlığı burada yer alıyor"]);
  assert.deepStrictEqual(m.parsePage(HTML_FEED, "https://ornek.test/").feeds, ["/akis.xml"]);
});

test("Güvenli adresler", () => {
  assert.strictEqual(m.normalizeUrl("javascript:alert(1)"), null);
  assert.strictEqual(m.normalizeUrl("https://k:s@ornek.test/"), null);
  assert.strictEqual(m.normalizeUrl("https://ornek.test/a#b"), "https://ornek.test/a");
});

function setup(pages) {
  const data = {};
  const storage = {get: async key => ({[key]: data[key] && JSON.parse(JSON.stringify(data[key]))}),
    set: async obj => Object.assign(data, JSON.parse(JSON.stringify(obj)))};
  let now = 1793084400 + 3600;
  const fetcher = async url => {
    if (!(url in pages)) throw new Error("Site HTTP 404 yanıtı verdi.");
    return {text: pages[url], url};
  };
  const engine = new m.Engine(storage, fetcher, () => now);
  return {engine, storage, data, advance: s => { now += s; }};
}

test("Tarama, yeni haberler, okundu ve kaldırma", async () => {
  const pages = {"https://ornek.test/": HTML_FEED, "https://ornek.test/akis.xml": RSS};
  const {engine, storage, advance} = setup(pages);
  const api = (path, method, body) => engine.handle({path, method, body});

  assert.deepStrictEqual(await api("/api/import", "POST", {sites: ["https://ornek.test/"], poll: 30}), {ok: true, imported: true});
  assert.strictEqual((await api("/api/import", "POST", {sites: ["https://baska.test/"]})).imported, false);
  await engine.tick();
  let status = await api("/api/status");
  assert.strictEqual(status.sources[0].feed, "https://ornek.test/akis.xml");
  assert.strictEqual(status.sources[0].count, 2);
  assert.strictEqual(status.unread, 0, "ilk taramadaki haberler yeni sayılmaz");

  const found = await api("/api/articles?query=%C4%B0stanbul&offset=0&limit=50");
  assert.deepStrictEqual(found.articles.map(a => a.title), ["İstanbul'da ilk haber"]);
  assert.strictEqual((await api("/api/articles?query=saatsiz")).articles[0].a, true);

  await assert.rejects(api("/api/sources", "POST", {url: "https://www.ornek.test/x"}), /zaten ekli/);

  // Yeni eklenen kaynak, sırasını beklemeden hemen taranır.
  pages["https://yeni.test/"] = RSS.replace(/ornek\.test/g, "yeni.test");
  await api("/api/sources", "POST", {url: "https://yeni.test/"});
  await engine.idle();
  assert.strictEqual((await api("/api/articles?site=yeni.test")).total, 2);
  await api("/api/sources", "DELETE", {url: "https://yeni.test/"});
  await assert.rejects(api("/api/config", "PATCH", {poll: 7}), /Geçersiz/);

  // Süre dolmadan yeniden taranmaz; dolunca yeni haber okunmamış sayılır.
  pages["https://ornek.test/akis.xml"] = RSS.replace("<channel><title>Örnek</title>",
    "<channel><item><title>Son dakika</title><link>https://ornek.test/haber/3</link></item>");
  assert.strictEqual(await engine.tick(), false);
  advance(31);
  await engine.tick();
  assert.strictEqual((await api("/api/status")).unread, 1);
  const [fresh] = (await api("/api/articles?unread=1")).articles;
  assert.strictEqual(fresh.title, "Son dakika");
  await api("/api/read", "POST", {keys: [fresh.k]});
  assert.strictEqual((await api("/api/status")).unread, 0);

  // Kayıtlar kalıcı: yeni bir motor aynı depodan okur.
  const again = new m.Engine(storage, async () => { throw new Error("yok"); });
  assert.strictEqual((await again.handle({path: "/api/status"})).sources[0].count, 3);

  await api("/api/sources", "DELETE", {url: "https://ornek.test/"});
  assert.strictEqual((await api("/api/articles")).total, 0);
});

test("Hata sonrası bekleme süresi artar", async () => {
  const {engine, advance} = setup({});
  await engine.handle({path: "/api/sources", method: "POST", body: {url: "https://kapali.test/"}});
  await engine.idle();
  let source = (await engine.handle({path: "/api/status"})).sources[0];
  assert.strictEqual(source.errors, 1);
  assert.match(source.error, /404/);
  advance(30);
  assert.strictEqual(await engine.tick(), false, "60 sn dolmadan yeniden denenmez");
  advance(31);
  await engine.tick();
  source = (await engine.handle({path: "/api/status"})).sources[0];
  assert.strictEqual(source.errors, 2);
});

test("RSS'i olmayan site", async () => {
  const {engine} = setup({"https://www.ornek.test/": HTML_PLAIN});
  await engine.handle({path: "/api/sources", method: "POST", body: {url: "https://www.ornek.test/"}});
  await engine.idle();
  const page = await engine.handle({path: "/api/articles"});
  assert.deepStrictEqual(page.articles.map(a => [a.title, a.a]), [["Uzun bir haber başlığı burada yer alıyor", true]]);
});
