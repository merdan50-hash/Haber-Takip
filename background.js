// Uygulama sekmesi zaten açıksa onu öne getirir, değilse yeni sekmede açar.
// chrome.runtime.getContexts "tabs" izni istemeden eklentinin kendi sayfalarını bulur.
chrome.action.onClicked.addListener(async () => {
  const url = chrome.runtime.getURL("app.html");
  try {
    const [context] = await chrome.runtime.getContexts({contextTypes: ["TAB"], documentUrls: [url]});
    if (context && context.tabId >= 0) {
      await chrome.tabs.update(context.tabId, {active: true});
      if (context.windowId >= 0) await chrome.windows.update(context.windowId, {focused: true});
      return;
    }
  } catch (error) {
    console.warn("Açık Haber Takip sekmesi bulunamadı:", error);
  }
  await chrome.tabs.create({url});
});
