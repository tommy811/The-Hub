// scripts/harvester/page_function.js
// Page function for apify/puppeteer-scraper.
// Loaded into Python as a string and passed via actor input.
//
// Strategy:
// 1. Hook window.open and location.assign / location.href setters BEFORE
//    page scripts run — capture URLs without actually navigating.
// 2. Wait for hydration (networkidle).
// 3. Extract every <a href> from rendered DOM.
// 4. Iterate every <button>, [role=button], [onclick] — click each.
// 5. After each click, scan for "Open link" / "Continue" / "I am over 18" /
//    "Sensitive Content" interstitial buttons; auto-click them.
// 6. Dump __NEXT_DATA__ + <script type="application/json"> URL strings.
// 7. Return deduped URL list with raw_text labels.

async function pageFunction(context) {
    const { page, request, log } = context;

    const captured = new Set();
    const labels = new Map();  // url → label text

    // STEP 1: install URL interception BEFORE any other script runs
    await page.evaluateOnNewDocument(() => {
        window.__capturedUrls = [];

        const origOpen = window.open;
        window.open = function (url, ...args) {
            if (url) window.__capturedUrls.push(String(url));
            return null;  // suppress popup so it doesn't navigate
        };

        const origAssign = window.location.assign?.bind(window.location);
        if (origAssign) {
            window.location.assign = function (url) {
                if (url) window.__capturedUrls.push(String(url));
            };
        }

        // Override location.href setter
        try {
            const origDescriptor = Object.getOwnPropertyDescriptor(
                window.Location.prototype, "href"
            );
            Object.defineProperty(window.location, "href", {
                set(url) {
                    if (url) window.__capturedUrls.push(String(url));
                },
                get() { return origDescriptor?.get?.call(this); },
                configurable: true,
            });
        } catch (e) { /* some browsers won't allow this — fall back */ }
    });

    // STEP 2: navigate and wait for hydration
    try {
        await page.goto(request.url, { waitUntil: "networkidle2", timeout: 20000 });
    } catch (e) {
        log.warning(`navigation timeout on ${request.url}: ${e.message}`);
    }

    // STEP 3: extract anchors from rendered DOM
    const anchors = await page.$$eval("a[href]", (els) =>
        els.map((a) => ({ url: a.href, text: (a.innerText || "").trim().slice(0, 200) }))
    );
    for (const { url, text } of anchors) {
        if (url && !url.startsWith("javascript:") && !url.startsWith("#")) {
            captured.add(url);
            if (text) labels.set(url, text);
        }
    }

    // STEP 4: click every button-style element + chase interstitials
    const clickables = await page.$$(
        "button, [role='button'], [onclick]"
    );

    for (let i = 0; i < clickables.length; i++) {
        const btn = clickables[i];
        let label = "";
        try {
            label = await btn.evaluate((el) => (el.innerText || "").trim().slice(0, 200));
            await btn.click({ delay: 50 }).catch(() => null);
            await new Promise((r) => setTimeout(r, 400));

            // Look for an interstitial action button that appeared after the click.
            const continueBtns = await page.$$(
                "xpath/.//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'open link') or " +
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'continue') or " +
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'i am over 18') or " +
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'i agree') or " +
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'i confirm') or " +
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'18+') or " +
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'enter')]"
            );
            if (continueBtns.length > 0) {
                await continueBtns[0].click({ delay: 50 }).catch(() => null);
                await new Promise((r) => setTimeout(r, 400));
            }
        } catch (e) { /* skip this button */ }

        // Drain captured URLs from this iteration's window.open hook
        const newUrls = await page.evaluate(() => {
            const arr = window.__capturedUrls || [];
            window.__capturedUrls = [];
            return arr;
        });
        for (const u of newUrls) {
            captured.add(u);
            if (label && !labels.has(u)) labels.set(u, label);
        }
    }

    // STEP 5: scrape embedded JSON for URLs
    const jsonUrls = await page.evaluate(() => {
        const out = [];
        const re = /https?:\/\/[^\s"']{8,}/g;
        document.querySelectorAll("script[type='application/json']").forEach((s) => {
            const matches = (s.textContent || "").match(re);
            if (matches) out.push(...matches);
        });
        return out;
    });
    for (const u of jsonUrls) captured.add(u);

    return {
        urls: [...captured].map((url) => ({
            url,
            text: labels.get(url) || "",
        })),
    };
}
