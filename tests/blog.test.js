const test = require("node:test");
const assert = require("node:assert/strict");
const { matches, filterPosts } = require("../www/blog.js");

const posts = [
  { month: "2026-09", search: "designing software that earns a place dependable" },
  { month: "2026-08", search: "release notes for the new beta android apps" },
  { month: "2026-08", search: "training videos for administrators" },
];

test("no query matches everything", () => assert.equal(filterPosts(posts, {}).length, 3));
test("text is case-insensitive and all words must match", () => {
  assert.equal(filterPosts(posts, { text: "RELEASE beta" }).length, 1);
  assert.equal(filterPosts(posts, { text: "release videos" }).length, 0);
});
test("month narrows the list", () => assert.equal(filterPosts(posts, { month: "2026-08" }).length, 2));
test("text and month combine", () => assert.equal(filterPosts(posts, { text: "training", month: "2026-08" }).length, 1));
test("matches ignores stray spaces", () => assert.equal(matches(posts[0], { text: "  software   dependable " }), true));
