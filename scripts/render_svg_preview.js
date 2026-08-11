#!/usr/bin/env node
"use strict";

// Local Chromium renderer for EY selection-message PNG previews. The SVG is
// loaded from a temporary HTML wrapper prepared beside its source file. The
// governed SVG boundary permits only embedded data assets and local fragments.
// This script never reads from or writes to svg_output/.

const fs = require("fs");
const os = require("os");
const path = require("path");
const { pathToFileURL } = require("url");

const RENDERER = "ey-deck-playwright-chromium";
const SCHEMA_VERSION = "ey-deck-preview-renderer.v3";

function fail(message, code = 2) {
  process.stderr.write(String(message).trim() + "\n");
  process.exit(code);
}

function parseArgs(argv) {
  const result = { version: false, request: null };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--version") result.version = true;
    else if (token === "--request") result.request = argv[++index];
    else fail(`unknown renderer argument: ${token}`);
  }
  return result;
}

function playwrightVersion() {
  try {
    return require("playwright/package.json").version;
  } catch (error) {
    fail(`Playwright package is unavailable: ${error.message}`, 3);
  }
}

function identity(executablePath = preferredExecutable()) {
  return {
    renderer: RENDERER,
    renderer_version: `${SCHEMA_VERSION}/playwright-${playwrightVersion()}`,
    chromium_executable: executablePath,
  };
}

function executableFile(candidate) {
  try {
    fs.accessSync(candidate, fs.constants.X_OK);
    return fs.statSync(candidate).isFile();
  } catch (_) {
    return false;
  }
}

function preferredExecutable() {
  if (process.env.EY_PREVIEW_CHROMIUM) {
    const override = path.resolve(process.env.EY_PREVIEW_CHROMIUM);
    if (!executableFile(override)) {
      fail(`EY_PREVIEW_CHROMIUM is not an executable file: ${override}`, 3);
    }
    return override;
  }

  const cacheRoots = process.platform === "darwin"
    ? [path.join(os.homedir(), "Library", "Caches", "ms-playwright")]
    : [path.join(os.homedir(), ".cache", "ms-playwright")];
  const candidates = [];
  for (const root of cacheRoots) {
    if (!fs.existsSync(root)) continue;
    const entries = fs.readdirSync(root)
      .filter((entry) => /^chromium_headless_shell-\d+$/.test(entry))
      .sort((left, right) => Number(right.split("-").pop()) - Number(left.split("-").pop()));
    for (const entry of entries) {
      const revision = path.join(root, entry);
      for (const platformDir of fs.readdirSync(revision).sort()) {
        const platformRoot = path.join(revision, platformDir);
        if (!fs.statSync(platformRoot).isDirectory()) continue;
        for (const executable of [
          "chrome-headless-shell",
          "headless_shell.exe",
          "chrome-headless-shell.exe",
        ]) {
          const candidate = path.join(platformRoot, executable);
          if (executableFile(candidate)) candidates.push(candidate);
        }
      }
    }
  }
  if (candidates.length === 0) {
    fail(
      "No Playwright Chromium headless shell was found; install it or set EY_PREVIEW_CHROMIUM. " +
      "System browsers are never used as fallbacks.",
      3,
    );
  }
  return candidates[0];
}

async function render(requestPath) {
  let playwright;
  try {
    playwright = require("playwright");
  } catch (error) {
    fail(`Playwright package is unavailable: ${error.message}`, 3);
  }
  const request = JSON.parse(fs.readFileSync(requestPath, "utf8"));
  if (!request || !Array.isArray(request.items) || request.items.length === 0) {
    fail("render request needs a non-empty items array");
  }

  const executablePath = preferredExecutable();
  let browser;
  try {
    browser = await playwright.chromium.launch({
      headless: true,
      executablePath,
      args: ["--force-color-profile=srgb"],
    });
  } catch (error) {
    fail(
      `Playwright Chromium headless shell launch failed (${executablePath}): ${error.message}. ` +
      "No system-browser fallback was attempted.",
      3,
    );
  }

  const records = [];
  const browserVersion = browser.version();
  try {
    for (const item of request.items) {
      const record = { version: item.version, ok: false };
      let context;
      try {
        const width = Number(item.width);
        const height = Number(item.height);
        if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
          throw new Error(`invalid viewport ${item.width}x${item.height}`);
        }
        context = await browser.newContext({
          viewport: { width, height },
          deviceScaleFactor: 1,
          colorScheme: "light",
        });
        const page = await context.newPage();
        const failedRequests = [];
        page.on("requestfailed", (req) => failedRequests.push(`${req.url()}: ${req.failure()?.errorText || "failed"}`));
        await page.route(/^https?:\/\//, (route) => route.abort("blockedbyclient"));
        await page.goto(pathToFileURL(path.resolve(item.html_path)).href, { waitUntil: "networkidle" });
        await page.evaluate(() => document.fonts ? document.fonts.ready : Promise.resolve());
        await page.waitForTimeout(100);
        if (failedRequests.length) {
          throw new Error(`asset load failed: ${failedRequests.join("; ")}`);
        }
        const stage = page.locator("#stage");
        const box = await stage.boundingBox();
        if (!box || Math.round(box.width) !== width || Math.round(box.height) !== height) {
          throw new Error(`rendered stage has wrong size: ${box ? `${box.width}x${box.height}` : "missing"}`);
        }
        let visibleCopy = null;
        if (item.copy_contract) {
          visibleCopy = await page.evaluate((contract) => {
            const normalize = (value) => String(value || "")
              .normalize("NFC")
              .replace(/\u00A0/gu, " ")
              .replace(/\s+/gu, " ")
              .trim()
              .replace(/(?<=[\u2E80-\u9FFF\uF900-\uFAFF\uFF01-\uFF60]) (?=[\u2E80-\u9FFF\uF900-\uFAFF\uFF01-\uFF60])/gu, "");
            const stageElement = document.querySelector("#stage");
            const stageRect = stageElement.getBoundingClientRect();
            const errors = [];
            const evidence = [];
            const allBound = Array.from(document.querySelectorAll("[data-copy-id]"));
            for (const expected of contract.items || []) {
              const matches = allBound.filter((node) => node.getAttribute("data-copy-id") === expected.id);
              if (matches.length === 0) {
                if (expected.required) errors.push(`${expected.id}: missing DOM binding`);
                continue;
              }
              if (matches.length !== 1) {
                errors.push(`${expected.id}: ${matches.length} DOM bindings`);
                continue;
              }
              const element = matches[0];
              const style = getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              const observed = normalize(element.textContent);
              const approved = normalize(expected.text);
              const intersects = rect.right > stageRect.left && rect.left < stageRect.right
                && rect.bottom > stageRect.top && rect.top < stageRect.bottom;
              const contained = rect.left >= stageRect.left - 1
                && rect.top >= stageRect.top - 1
                && rect.right <= stageRect.right + 1
                && rect.bottom <= stageRect.bottom + 1;
              const displayed = style.display !== "none"
                && style.visibility !== "hidden"
                && style.visibility !== "collapse"
                && Number(style.opacity || "1") > 0.01;
              const sized = rect.width > 0.5 && rect.height > 0.5;
              if (observed !== approved) errors.push(`${expected.id}: DOM text changed`);
              if (!displayed) errors.push(`${expected.id}: hidden by computed style`);
              if (!sized) errors.push(`${expected.id}: empty rendered bounds`);
              if (!intersects) errors.push(`${expected.id}: outside the preview canvas`);
              else if (!contained) errors.push(`${expected.id}: extends outside the preview canvas`);
              evidence.push({
                id: expected.id,
                normalized_character_count: Array.from(observed).length,
                bounds: {
                  x: Math.round((rect.x - stageRect.x) * 1000) / 1000,
                  y: Math.round((rect.y - stageRect.y) * 1000) / 1000,
                  width: Math.round(rect.width * 1000) / 1000,
                  height: Math.round(rect.height * 1000) / 1000,
                },
                displayed,
                intersects,
                contained,
              });
            }
            return { status: errors.length ? "FAIL" : "PASS", items: evidence, errors };
          }, item.copy_contract);
          if (visibleCopy.errors.length) {
            throw new Error(`visible-copy gate failed: ${visibleCopy.errors.join("; ")}`);
          }
        }
        fs.mkdirSync(path.dirname(item.output_path), { recursive: true });
        await stage.screenshot({ path: item.output_path, type: "png", omitBackground: false });
        record.ok = true;
        record.output_path = item.output_path;
        record.width = width;
        record.height = height;
        if (visibleCopy) record.visible_copy = visibleCopy;
      } catch (error) {
        record.error = `${error.name || "Error"}: ${error.message || String(error)}`;
      } finally {
        if (context) await context.close();
      }
      records.push(record);
    }
  } finally {
    await browser.close();
  }

  const summary = {
    ...identity(executablePath),
    browser_version: browserVersion,
    chromium_executable: executablePath,
    records,
  };
  process.stdout.write(JSON.stringify(summary) + "\n");
  if (records.some((record) => !record.ok)) process.exit(4);
}

(async () => {
  const args = parseArgs(process.argv.slice(2));
  if (args.version) {
    process.stdout.write(JSON.stringify(identity()) + "\n");
    return;
  }
  if (!args.request) fail("--request is required");
  await render(args.request);
})().catch((error) => fail(`${error.name || "Error"}: ${error.message || String(error)}`, 4));
