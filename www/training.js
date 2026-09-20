/* Training page finder. Pure helpers are exported for tests (node --test tests/training.test.js);
   the DOM wiring at the bottom runs only in a browser. No cookies, no storage: the choice lives in the address (#role=...). */
(function (root) {
  "use strict";

  function has(list, value) {
    return Array.isArray(list) && list.indexOf(value) !== -1;
  }

  // Which videos does this choice show? A video is {roles: [], platforms: [], task}; a choice is {role, platform, task}.
  function matches(video, choice) {
    if (!choice || !choice.role) return true;
    var platform = choice.platform && choice.platform !== "both" ? choice.platform : null;
    if (platform && !has(video.platforms, platform)) return false;
    if (has(video.roles, "everyone")) return true;
    if (!has(video.roles, choice.role)) return false;
    if (choice.role === "admin" && choice.task && choice.task !== "all") return video.task === choice.task;
    return true;
  }

  function filterVideos(videos, choice) {
    var out = [];
    for (var i = 0; i < videos.length; i++) {
      if (videos[i].always || matches(videos[i], choice)) out.push(videos[i]);
    }
    return out;
  }

  function parseHash(hash) {
    var choice = { role: "", platform: "", task: "" };
    var text = String(hash || "").replace(/^#/, "");
    if (!text) return choice;
    var parts = text.split("&");
    for (var i = 0; i < parts.length; i++) {
      var kv = parts[i].split("=");
      var key = kv[0];
      if (key in choice) choice[key] = decodeURIComponent(kv[1] || "");
    }
    return choice;
  }

  function buildHash(choice) {
    var parts = [];
    ["role", "platform", "task"].forEach(function (key) {
      if (choice[key]) parts.push(key + "=" + encodeURIComponent(choice[key]));
    });
    return parts.length ? "#" + parts.join("&") : "";
  }

  var api = { matches: matches, filterVideos: filterVideos, parseHash: parseHash, buildHash: buildHash };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  if (typeof document === "undefined") return;

  function init() {
    var finder = document.getElementById("finder");
    if (!finder) return;
    var role = document.getElementById("finder-role");
    var platform = document.getElementById("finder-platform");
    var task = document.getElementById("finder-task");
    var taskWrap = document.getElementById("finder-task-wrap");
    var panel = document.getElementById("your-videos");
    var list = document.getElementById("your-videos-list");
    var title = document.getElementById("your-videos-title");
    var reset = document.getElementById("finder-reset");
    var cards = Array.prototype.slice.call(document.querySelectorAll(".video-card"));
    var sections = Array.prototype.slice.call(document.querySelectorAll(".video-section"));
    var videos = cards.map(function (el) {
      return {
        id: el.id,
        roles: (el.getAttribute("data-roles") || "").split(","),
        platforms: (el.getAttribute("data-platforms") || "").split(","),
        task: el.getAttribute("data-task") || "",
        always: el.getAttribute("data-always") === "true",
        title: (el.querySelector("h3") || {}).textContent || el.id,
        use: el.getAttribute("data-use") || "",
        meta: el.getAttribute("data-status") || "",
        el: el
      };
    });
    finder.hidden = false;

    function read() {
      return { role: role.value, platform: platform.value, task: task.value };
    }

    function apply(push) {
      var choice = read();
      taskWrap.hidden = choice.role !== "admin";
      if (choice.role !== "admin") choice.task = "";
      var shown = filterVideos(videos, choice);
      var ids = {};
      shown.forEach(function (v) { ids[v.id] = true; });
      var filtering = !!choice.role;
      videos.forEach(function (v) { v.el.hidden = filtering && !ids[v.id]; });
      sections.forEach(function (s) {
        var any = Array.prototype.some.call(s.querySelectorAll(".video-card"), function (c) { return !c.hidden; });
        s.hidden = !any;
      });
      list.innerHTML = "";
      panel.hidden = !filtering;
      if (filtering) {
        var label = role.options[role.selectedIndex].text;
        title.textContent = "Your videos: " + label;
        shown.filter(function (v) { return !v.always; }).forEach(function (v) {
          var li = document.createElement("li");
          var a = document.createElement("a");
          a.href = "#" + v.id;
          a.textContent = v.title;
          li.appendChild(a);
          if (v.use) { var s = document.createElement("span"); s.className = "your-use"; s.textContent = " Use it when " + v.use + "."; li.appendChild(s); }
          if (v.meta) { var m = document.createElement("span"); m.className = "video-tag"; m.textContent = v.meta; li.appendChild(m); }
          list.appendChild(li);
        });
      }
      if (push !== false && window.history && history.replaceState) {
        history.replaceState(null, "", location.pathname + location.search + buildHash(choice));
      }
    }

    var start = parseHash(location.hash);
    if (start.role) role.value = start.role;
    if (start.platform) platform.value = start.platform;
    if (start.task) task.value = start.task;
    [role, platform, task].forEach(function (el) { el.addEventListener("change", function () { apply(true); }); });
    reset.addEventListener("click", function () { role.value = ""; platform.value = ""; task.value = ""; apply(true); });
    apply(false);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})(typeof window !== "undefined" ? window : this);
