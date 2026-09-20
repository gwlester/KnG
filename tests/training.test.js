const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const T = require("../www/training.js");

const data = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "content", "videos", "videos.json"), "utf8"));
const all = data.sections.flatMap((s) => s.videos.map((v) => Object.assign({ always: s.id === "see-it" }, v)));
const ids = (choice) => T.filterVideos(all, choice).filter((v) => !v.always).map((v) => v.id);

test("no role chosen shows everything", () => {
  assert.equal(T.filterVideos(all, {}).length, all.length);
  assert.equal(T.filterVideos(all, { role: "", platform: "android" }).length, all.length);
});

test("everyone sees only the Start here videos for their platform", () => {
  const desktop = ids({ role: "everyone", platform: "computer" });
  assert.deepEqual(desktop, ["install-apps", "connecting", "password-and-locking"]);
  const phone = ids({ role: "everyone", platform: "android" });
  assert.deepEqual(phone, ["android-install"]);
});

test("a planner on a computer gets Start here plus the planner video, nothing for other roles", () => {
  assert.deepEqual(ids({ role: "planner", platform: "computer" }), ["install-apps", "connecting", "password-and-locking", "planner"]);
});

test("a planner on Android gets the Android videos only", () => {
  assert.deepEqual(ids({ role: "planner", platform: "android" }), ["android-install", "planner-android"]);
});

test("any device shows both platforms", () => {
  const list = ids({ role: "runner", platform: "both" });
  assert.ok(list.includes("runner") && list.includes("runner-android") && list.includes("connecting") && list.includes("android-install"));
});

test("an administrator can narrow to one task, keeping Start here", () => {
  const list = ids({ role: "admin", platform: "computer", task: "approve" });
  assert.deepEqual(list, ["install-apps", "connecting", "password-and-locking", "admin-approving"]);
  const phone = ids({ role: "admin", platform: "android", task: "approve" });
  assert.deepEqual(phone, ["android-install", "android-security"]);
});

test("an administrator with no task sees every administrator video for the platform", () => {
  const list = ids({ role: "admin", platform: "computer", task: "" });
  assert.ok(["admin-approving", "admin-devices", "admin-loading", "admin-catalog", "admin-backup", "admin-health", "admin-settings", "admin-trouble"].every((id) => list.includes(id)));
  assert.ok(!list.includes("android-security"));
});

test("the technical contact gets the one-time setup videos", () => {
  const list = ids({ role: "tech", platform: "computer" });
  assert.ok(list.includes("install-server-linux") && list.includes("first-administrator") && list.includes("install-midi-mac"));
});

test("the demo and the commercial are always shown", () => {
  const shown = T.filterVideos(all, { role: "planner", platform: "android" }).map((v) => v.id);
  assert.ok(shown.includes("overview") && shown.includes("ready-when-you-are"));
});

test("the address round-trips and ignores junk", () => {
  const choice = { role: "admin", platform: "android", task: "approve" };
  assert.deepEqual(T.parseHash(T.buildHash(choice)), choice);
  assert.equal(T.buildHash({ role: "", platform: "", task: "" }), "");
  assert.deepEqual(T.parseHash("#nothing=here&role=planner"), { role: "planner", platform: "", task: "" });
  assert.deepEqual(T.parseHash(""), { role: "", platform: "", task: "" });
});
