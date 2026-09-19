const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const P = require("../www/picker.js");

const options = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "downloads", "options.json"), "utf8"));

test("detects platforms, with Android before Linux", () => {
  assert.equal(P.detectPlatform({ userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 8)" }), "android");
  assert.equal(P.detectPlatform({ userAgent: "Mozilla/5.0 (X11; Linux x86_64)" }), "linux");
  assert.equal(P.detectPlatform({ userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" }), "windows");
  assert.equal(P.detectPlatform({ userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)" }), "mac");
  assert.equal(P.detectPlatform({ userAgent: "", userAgentData: { platform: "macOS" } }), "mac");
});

test("iOS, ChromeOS, and unknown platforms get no default", () => {
  assert.equal(P.detectPlatform({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)" }), null);
  assert.equal(P.detectPlatform({ userAgent: "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0)" }), null);
  assert.equal(P.detectPlatform({ userAgent: "curl/8" }), null);
  assert.equal(P.detectPlatform(null), null);
});

test("selection is kept when still valid, else detected, else none", () => {
  const server = P.findApp(options, "server");
  const editor = P.findApp(options, "template-editor");
  assert.equal(P.chooseDefault(editor, "android", "windows"), "android");
  assert.equal(P.chooseDefault(server, "android", "windows"), "windows");
  assert.equal(P.chooseDefault(server, null, "android"), null);
  assert.equal(P.chooseDefault(null, null, "windows"), null);
});

test("Admin and Security maps Android to Security and desktops to Admin", () => {
  const app = P.findApp(options, "admin-security");
  assert.equal(P.findPlatform(app, "android").matrix_app, "security");
  for (const p of ["windows", "mac", "linux"]) assert.equal(P.findPlatform(app, p).matrix_app, "admin");
});

test("button state and label follow the entry", () => {
  assert.deepEqual(P.describe(null).enabled, false);
  assert.equal(P.describe({ available: false, type: "download" }).label, "Coming soon");
  assert.equal(P.describe({ available: true, type: "download" }).label, "Download");
  assert.equal(P.describe({ available: true, type: "store" }).label, "Get it on Google Play");
  assert.equal(P.describe({ available: true, type: "purchase" }).label, "Buy");
  assert.equal(P.describe({ available: true, type: "download" }).enabled, true);
});

test("download URLs encode parameters and never carry a target", () => {
  const p = { id: "windows", matrix_app: "template-editor" };
  const url = P.buildUrl("https://x.example/", p, { version: "previous", format: "msi" });
  assert.equal(url, "https://x.example/?app=template-editor&platform=windows&version=previous&v=1&format=msi");
  assert.ok(!/key=|url=|target=/.test(url));
  assert.ok(P.buildUrl("https://x.example/?a=1", p).includes("&app=template-editor"));
});

test("an alternative installer format is offered only when there is one", () => {
  assert.equal(P.otherFormat(P.findPlatform(P.findApp(options, "template-editor"), "windows")), "msi");
  assert.equal(P.otherFormat(P.findPlatform(P.findApp(options, "server"), "windows")), "exe");
  assert.equal(P.otherFormat(P.findPlatform(P.findApp(options, "template-editor"), "mac")), null);
});

const status = {
  FormatVersion: 1,
  current: {
    version: "v1.0.1-b.7", channel: "beta", published: "2026-09-11",
    available: {
      "template-editor:windows": ["exe", "msi"],
      "template-editor:android": ["apk"],
      "security:android": ["apk"],
      "admin:mac": ["dmg"]
    },
    documents: { "user-manual": ["html", "pdf"] }
  },
  previous: { version: "v1.0.1-b.6", channel: "beta", published: "2026-09-01", available: {}, documents: {} }
};

test("status marks only what is published as available", () => {
  const o = P.applyStatus(options, status, "current");
  assert.equal(P.findPlatform(P.findApp(o, "template-editor"), "windows").available, true);
  assert.equal(P.findPlatform(P.findApp(o, "template-editor"), "linux").available, false);
  assert.equal(P.findPlatform(P.findApp(o, "admin-security"), "android").available, true);
  assert.equal(P.findPlatform(P.findApp(o, "admin-security"), "mac").available, true);
  assert.equal(P.findPlatform(P.findApp(o, "server"), "linux").available, false);
  assert.equal(options.apps[0].platforms[1].available, false, "the input is not mutated");
});

test("published formats narrow the alternative-installer choice", () => {
  const o = P.applyStatus(options, { FormatVersion: 1, current: { version: "v1", channel: "beta", available: { "template-editor:windows": ["msi"] }, documents: {} } }, "current");
  const win = P.findPlatform(P.findApp(o, "template-editor"), "windows");
  assert.deepEqual(win.formats, ["msi"]);
  assert.equal(win.default_format, "msi");
  assert.equal(P.otherFormat(win), null);
});

test("a store link switches the entry to Get it on Google Play", () => {
  const o = P.applyStatus(options, { FormatVersion: 1, current: { version: "v1", channel: "beta", available: { "template-editor:android": ["store"] }, documents: {} } }, "current");
  assert.equal(P.describe(P.findPlatform(P.findApp(o, "template-editor"), "android")).label, "Get it on Google Play");
});

test("no status, or an empty previous release, means nothing is available", () => {
  const none = P.applyStatus(options, null, "current");
  assert.ok(none.apps.every((a) => a.platforms.every((p) => !p.available)));
  const prev = P.applyStatus(options, status, "previous");
  assert.ok(prev.apps.every((a) => a.platforms.every((p) => !p.available)));
});

test("version labels and document lookups", () => {
  const labels = P.versionLabels(status, "Beta");
  assert.equal(labels.current, "Current release (v1.0.1-b.7, Beta)");
  assert.equal(labels.hasPrevious, true);
  assert.equal(P.versionLabels({ FormatVersion: 1, current: status.current, previous: null }, "Beta").hasPrevious, false);
  assert.deepEqual(P.docFormats(status, "current", "user-manual"), ["html", "pdf"]);
  assert.deepEqual(P.docFormats(status, "current", "system-admin-guide"), []);
  assert.equal(P.docUrl("https://x.example/", "user-manual", "pdf", "previous"),
    "https://x.example/?doc=user-manual&format=pdf&version=previous&v=1");
});

test("an unsigned release is labelled as such", () => {
  const labels = P.versionLabels({ FormatVersion: 1, current: { version: "v1.0.1-b.6", channel: "beta", signed: false }, previous: null }, "Beta");
  assert.equal(labels.current, "Current release (v1.0.1-b.6, Beta, unsigned)");
  const signed = P.versionLabels({ FormatVersion: 1, current: { version: "v1.1.0", channel: "stable", signed: true }, previous: null }, "Beta");
  assert.equal(signed.current, "Current release (v1.1.0)");
});
