// Eklentiyi gerçek Chromium'da yükler ve varsayılan gerçek haber sitelerinden haber gelip gelmediğini denetler (CI).
// Kullanım: node test/gercek-siteler.js <eklenti-klasörü>
const { chromium } = require("playwright");
const os = require("os"), path = require("path"), fs = require("fs");

// Takılırsa CI'yı süresiz bekletmesin.
setTimeout(() => { console.error("Test 4 dakikada bitmedi."); process.exit(1); }, 240000).unref();

(async () => {
  const extension = path.resolve(process.argv[2] || ".");
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "haber-takip-"));
  const context = await chromium.launchPersistentContext(profile, {channel: "chromium", headless: true,
    args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]});
  let [worker] = context.serviceWorkers();
  if (!worker) worker = await context.waitForEvent("serviceworker");
  const errors = [];
  const page = await context.newPage();
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`chrome-extension://${worker.url().split("/")[2]}/app.html`);
  await page.waitForFunction(() => document.querySelectorAll(".chip").length > 0, null, {timeout: 20000});

  // Varsayılan siteler ilk turda taranır; hepsinin sonuçlanmasını en çok 2 dakika bekle.
  const deadline = Date.now() + 120000;
  let result;
  while (Date.now() < deadline) {
    result = await page.evaluate(() => chrome.runtime.sendMessage({path: "/api/status"}));
    const done = result.result.sources.filter(source => source.lastSuccess || source.errors).length;
    console.log(`${Math.round((deadline - Date.now()) / 1000)} sn kaldı · ${done}/${result.result.sources.length} kaynak sonuçlandı`);
    if (result.result.sources.every(source => source.lastSuccess || source.errors)) break;
    await page.waitForTimeout(3000);
  }
  const sources = result.result.sources;
  for (const source of sources) {
    console.log(`${source.url.padEnd(34)} ${String(source.count).padStart(4)}  ${source.lastSuccess ? "akış: " + source.feed : "HATA: " + source.error}`);
  }
  const rows = await page.locator(".row").count();
  console.log(`\nSayfada ${rows} haber · ilk başlık: ${rows ? await page.locator(".row .ti").first().textContent() : "-"}`);
  await page.screenshot({path: "ekran.png", fullPage: false});
  await context.close();

  const working = sources.filter(source => source.count > 0).length;
  if (errors.length) throw new Error("Sayfa hataları: " + errors.join(" | "));
  if (working < Math.ceil(sources.length / 2)) throw new Error(`Sitelerin yarısından azı okunabildi (${working}/${sources.length}).`);
  console.log(`TAMAM: ${working}/${sources.length} sitede haber bulundu.`);
})().catch(error => { console.error(error.message || error); process.exit(1); });
