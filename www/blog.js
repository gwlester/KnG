/* Blog page filter: shows or hides the "Earlier posts" by text and by month. Works without scripts (all posts stay listed). */
(function (root) {
  "use strict";

  function matches(post, query) {
    var text = String((query && query.text) || "").trim().toLowerCase();
    var month = String((query && query.month) || "");
    if (month && post.month !== month) return false;
    if (!text) return true;
    return text.split(/\s+/).every(function (word) { return post.search.indexOf(word) !== -1; });
  }

  function filterPosts(posts, query) {
    return posts.filter(function (p) { return matches(p, query); });
  }

  var api = { matches: matches, filterPosts: filterPosts };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.BlogFilter = api;

  if (typeof document === "undefined") return;
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("blog-filter");
    if (!form || form.hidden) return;
    var items = Array.prototype.slice.call(document.querySelectorAll(".blog-item"));
    var text = document.getElementById("blog-text"), month = document.getElementById("blog-month");
    var count = document.getElementById("blog-count"), clear = document.getElementById("blog-clear");
    var data = items.map(function (el) { return { el: el, month: el.getAttribute("data-month"), search: el.getAttribute("data-search") }; });
    function apply() {
      var q = { text: text.value, month: month.value }, shown = 0;
      data.forEach(function (d) { var ok = matches(d, q); d.el.hidden = !ok; if (ok) shown++; });
      count.textContent = (q.text || q.month) ? shown + " of " + data.length + " earlier posts match" : "";
    }
    text.addEventListener("input", apply);
    month.addEventListener("change", apply);
    clear.addEventListener("click", function () { text.value = ""; month.value = ""; apply(); text.focus(); });
    form.addEventListener("submit", function (e) { e.preventDefault(); });
    apply();
  });
})(typeof window !== "undefined" ? window : globalThis);
