const test = require("node:test");
const assert = require("node:assert");
const R = require("../www/order-result.js");

test("platformLabel maps known platform ids to display names", () => {
  assert.equal(R.platformLabel("mac"), "macOS");
  assert.equal(R.platformLabel("windows"), "Windows");
  assert.equal(R.platformLabel("linux"), "Linux");
  assert.equal(R.platformLabel("raspberry-pi"), "Raspberry Pi");
  assert.equal(R.platformLabel("android"), "Android");
});

test("platformLabel falls back to the raw id for an unknown platform", () => {
  assert.equal(R.platformLabel("unknown-platform"), "unknown-platform");
});
