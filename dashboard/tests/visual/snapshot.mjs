// Phase 5 visual verify: drives Chromium across {widths} × {themes} × {routes}
// and writes PNGs under tests/visual/output/. Used once per design pass to
// eyeball the dashboard at the three breakpoints in both light + dark mode.
//
// Usage:
//   node tests/visual/snapshot.mjs                      # production URL
//   node tests/visual/snapshot.mjs https://preview.url  # alternate target
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const TARGET = process.argv[2] ?? "https://mvm-dashboard.pages.dev";
const HERE = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(HERE, "output");

const WIDTHS = [375, 800, 1180];
const THEMES = ["light", "dark"];
const ROUTES = [
  { path: "/", slug: "home" },
  { path: "/monkeys", slug: "monkeys" },
  { path: "/aggregates", slug: "aggregates" },
  { path: "/ai", slug: "ai" },
  { path: "/journal", slug: "journal" },
  { path: "/about", slug: "about" },
];

await mkdir(OUT_DIR, { recursive: true });

const browser = await chromium.launch();
try {
  for (const width of WIDTHS) {
    for (const theme of THEMES) {
      const ctx = await browser.newContext({
        viewport: { width, height: 900 },
        colorScheme: theme, // hint, also seeded explicitly below
      });
      // Seed localStorage so the FOUC-prevention script picks the right theme
      // before paint. Without this we'd inherit prefers-color-scheme only.
      await ctx.addInitScript((t) => {
        try { localStorage.setItem("mvm-theme", t); } catch {}
      }, theme);

      const page = await ctx.newPage();
      for (const route of ROUTES) {
        const url = `${TARGET}${route.path}`;
        await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
        // Charts take a beat after networkidle to render. Wait for the canvas
        // to actually be drawn, or settle for the timeout.
        await page.waitForTimeout(800);

        const fname = `${route.slug}_${theme}_${width}.png`;
        const out = join(OUT_DIR, fname);
        await page.screenshot({ path: out, fullPage: true });
        console.log(`✓ ${fname}`);
      }
      await ctx.close();
    }
  }
} finally {
  await browser.close();
}
console.log(`\nAll screenshots in ${OUT_DIR}`);
