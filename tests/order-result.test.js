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

test("the order box links to the offline license page", () => {
  const made = [];
  const doc = {
    createElement: (tag) => {
      const el = { tag, children: [], className: "", textContent: "", appendChild(c) { this.children.push(c); } };
      made.push(el);
      return el;
    },
    createTextNode: (text) => ({ text })
  };
  R.buildOrderResultBox(doc, { reference: "R1", short_key: "K1" });
  const link = made.find((el) => el.tag === "a");
  assert.ok(link);
  assert.equal(link.href, "activate.html");
});
