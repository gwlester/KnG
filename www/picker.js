/* Download picker. Pure helpers are exported for tests (node --test tests/picker.test.js);
   the DOM wiring at the bottom runs only in a browser. Options are public data. */
(function (root) {
  "use strict";

  var ORDER = ["android", "windows", "mac", "linux", "raspberry-pi"];

  // FastSpring product path (Popup Checkout, Add() takes this) for each
  // matrix_app id that's ever "purchase" type. Only two products, ever --
  // hardcoding this tiny map is simpler and more reliable than threading a
  // custom attribute through FastSpring's checkout, same reasoning as
  // src/order_fulfillment/handler.py's own _PRODUCT_TO_APP_ID (the inverse
  // of this map).
  var FASTSPRING_PRODUCT_PATHS = {
    "server": "virtual-church-musician-server",
    "midi-player": "virtual-church-musician-midi-player"
  };

  function fastspringProductPathFor(matrixAppId) {
    return FASTSPRING_PRODUCT_PATHS[matrixAppId] || null;
  }

  function detectPlatform(nav) {
    if (!nav) return null;
    var hint = (nav.userAgentData && nav.userAgentData.platform) || "";
    var ua = nav.userAgent || "";
    var text = (hint + " " + ua).toLowerCase();
    if (/iphone|ipad|ipod/.test(text)) return null;
    if (/android/.test(text)) return "android";
    if (/cros/.test(text)) return null;
    if (/windows|win32|win64/.test(text) || /^win/.test((nav.platform || "").toLowerCase())) return "windows";
    if (/macintosh|macos|mac os/.test(text) || /^mac/.test((nav.platform || "").toLowerCase())) return "mac";
    if (/linux|x11/.test(text)) return "linux";
    return null;
  }

  function findApp(options, appId) {
    for (var i = 0; i < options.apps.length; i++) {
      if (options.apps[i].id === appId) return options.apps[i];
    }
    return null;
  }

  function findPlatform(app, platformId) {
    if (!app) return null;
    for (var i = 0; i < app.platforms.length; i++) {
      if (app.platforms[i].id === platformId) return app.platforms[i];
    }
    return null;
  }

  function chooseDefault(app, selectedId, detectedId) {
    if (!app) return null;
    if (selectedId && findPlatform(app, selectedId)) return selectedId;
    if (detectedId && findPlatform(app, detectedId)) return detectedId;
    return null;
  }

  function describe(platform) {
    if (!platform) return { enabled: false, label: "Download", note: "Choose an app and a platform." };
    if (!platform.available) return { enabled: false, label: "Coming soon", note: "This download is not available yet." };
    if (platform.type === "store") return { enabled: true, label: "Get it on Google Play", note: "" };
    if (platform.type === "purchase") return { enabled: true, label: "Buy", note: "" };
    if (platform.type === "gated") {
      return { enabled: true, label: "Download", note: "Enter the access code you were given, then click Download." };
    }
    return { enabled: true, label: "Download", note: "" };
  }

  function buildUrl(endpoint, platform, extra) {
    extra = extra || {};
    var q = [
      "app=" + encodeURIComponent(platform.matrix_app),
      "platform=" + encodeURIComponent(platform.id),
      "version=" + encodeURIComponent(extra.version || "current"),
      "v=1"
    ];
    if (extra.format) q.push("format=" + encodeURIComponent(extra.format));
    if (extra.arch) q.push("arch=" + encodeURIComponent(extra.arch));
    return endpoint + (endpoint.indexOf("?") >= 0 ? "&" : "?") + q.join("&");
  }

  function otherFormat(platform) {
    if (!platform || !platform.formats || platform.formats.length < 2) return null;
    for (var i = 0; i < platform.formats.length; i++) {
      if (platform.formats[i] !== platform.default_format) return platform.formats[i];
    }
    return null;
  }

  function pick(status, which) {
    return status && status[which] ? status[which] : null;
  }

  // Returns a copy of options with availability taken from the Lambda's status
  // summary for "current" or "previous" (formats it actually has).
  function applyStatus(options, status, which) {
    var copy = JSON.parse(JSON.stringify(options));
    var release = pick(status, which);
    copy.apps.forEach(function (app) {
      app.platforms.forEach(function (p) {
        var formats = release && release.available ? release.available[p.matrix_app + ":" + p.id] : null;
        p.available = !!(formats && formats.length);
        if (!p.available) return;
        if (formats.indexOf("store") >= 0) { p.type = "store"; return; }
        if (formats.indexOf("purchase") >= 0) { p.type = "purchase"; return; }
        // A real file is published for a paid app, on any channel: the
        // Access code field (a purchase or an approved beta tester's
        // Test Drive credential) is the only way to get it, never a
        // plain download -- the backend enforces which credential kind
        // is accepted on which channel.
        p.type = (app.tier === "paid") ? "gated" : "download";
        if (p.formats) {
          p.formats = p.formats.filter(function (f) { return formats.indexOf(f) >= 0; });
          if (p.formats.indexOf(p.default_format) < 0) p.default_format = p.formats[0];
        }
      });
    });
    return copy;
  }

  function docFormats(status, which, kind) {
    var release = pick(status, which);
    return release && release.documents && release.documents[kind] ? release.documents[kind] : [];
  }

  function versionLabels(status, channelLabel) {
    var cur = pick(status, "current");
    var prev = pick(status, "previous");
    function name(r) {
      var tag = r.version + (r.channel === "beta" && channelLabel ? ", " + channelLabel : "") +
        (r.signed === false ? ", unsigned" : "");
      return "(" + tag + ")";
    }
    return {
      current: cur ? "Current release " + name(cur) : "Current release",
      previous: prev ? "Previous release " + name(prev) : "Previous release",
      hasPrevious: !!prev
    };
  }

  function docUrl(endpoint, kind, format, version) {
    return endpoint + (endpoint.indexOf("?") >= 0 ? "&" : "?") +
      "doc=" + encodeURIComponent(kind) + "&format=" + encodeURIComponent(format) +
      "&version=" + encodeURIComponent(version || "current") + "&v=1";
  }

  // The Access code field doubles as a purchase/Test Drive credential: a
  // "reference:short_key" pair (what onFSPopupClosed/the Test Drive
  // hand-off pre-fills it with) instead of the legacy beta-tester
  // password. A bare colon with nothing on one side is treated as a
  // literal password, not a malformed credential -- passwords are never
  // expected to contain one, so this only matters for a copy/paste slip.
  function parseAccessCode(raw) {
    var value = (raw || "").trim();
    if (!value) return null;
    var idx = value.indexOf(":");
    if (idx > 0 && idx < value.length - 1) {
      return { reference: value.slice(0, idx).trim(), short_key: value.slice(idx + 1).trim() };
    }
    return { password: value };
  }

  var api = {
    ORDER: ORDER,
    applyStatus: applyStatus,
    docFormats: docFormats,
    versionLabels: versionLabels,
    docUrl: docUrl,
    detectPlatform: detectPlatform,
    findApp: findApp,
    findPlatform: findPlatform,
    chooseDefault: chooseDefault,
    describe: describe,
    buildUrl: buildUrl,
    otherFormat: otherFormat,
    fastspringProductPathFor: fastspringProductPathFor,
    parseAccessCode: parseAccessCode
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
    return;
  }
  root.KnGPicker = api;

  function init() {
    var form = document.getElementById("download-picker");
    var data = document.getElementById("picker-options");
    if (!form || !data) return;
    var baseOptions = JSON.parse(data.textContent);
    var options = baseOptions;
    var status = null;
    var endpoint = form.getAttribute("data-endpoint") || "";
    var appSelect = document.getElementById("pick-app");
    var versionSelect = document.getElementById("pick-version");
    var group = document.getElementById("pick-platforms");
    var note = document.getElementById("pick-note");
    var go = document.getElementById("pick-go");
    var alt = document.getElementById("pick-alt");
    var passwordWrap = document.getElementById("pick-password-wrap");
    var passwordInput = document.getElementById("pick-password");
    var detected = detectPlatform(root.navigator);
    var selected = null;

    function currentPlatform() {
      return findPlatform(findApp(options, appSelect.value), selected);
    }

    function docLinks() {
      var anchors = document.querySelectorAll("a[data-doc-kind]");
      Array.prototype.forEach.call(anchors, function (a) {
        var formats = docFormats(status, versionSelect.value, a.getAttribute("data-doc-kind"));
        var format = a.getAttribute("data-doc-format");
        var label = a.getAttribute("data-label") || "";
        var span = a.querySelector(".doc-label") || a;
        if (endpoint && formats.indexOf(format) >= 0) {
          a.href = docUrl(endpoint, a.getAttribute("data-doc-kind"), format, versionSelect.value);
          a.removeAttribute("aria-disabled");
          a.removeAttribute("role");
          span.textContent = label;
        } else {
          a.removeAttribute("href");
          a.setAttribute("aria-disabled", "true");
          a.setAttribute("role", "link");
          span.textContent = label + " (coming soon)";
        }
      });
    }

    function render() {
      options = status ? applyStatus(baseOptions, status, versionSelect.value) : baseOptions;
      var app = findApp(options, appSelect.value);
      group.textContent = "";
      selected = chooseDefault(app, selected, detected);
      if (app) {
        var platforms = app.platforms.slice().sort(function (a, b) { return ORDER.indexOf(a.id) - ORDER.indexOf(b.id); });
        if (app.tier === "paid") platforms = app.platforms.slice();
        platforms.forEach(function (p) {
          var id = "plat-" + p.id;
          var wrap = document.createElement("label");
          wrap.className = "radio-pill";
          wrap.setAttribute("for", id);
          var input = document.createElement("input");
          input.type = "radio";
          input.name = "platform";
          input.id = id;
          input.value = p.id;
          input.checked = p.id === selected;
          input.addEventListener("change", function () { selected = p.id; render(); });
          wrap.appendChild(input);
          wrap.appendChild(document.createTextNode(" " + options.platforms[p.id].label));
          group.appendChild(wrap);
        });
      }
      var platform = currentPlatform();
      var info = describe(platform);
      go.textContent = info.label;
      go.disabled = !info.enabled;
      var text = info.note;
      if (platform && options.platforms[platform.id].note && info.enabled) text = options.platforms[platform.id].note;
      if (app && !platform && detected === null && root.navigator && /iphone|ipad|ipod/i.test(root.navigator.userAgent || "")) {
        text = "There is no iPhone or iPad version yet. Choose a platform for another device.";
      }
      note.textContent = text;
      note.classList.remove("is-error");
      if (passwordWrap) passwordWrap.hidden = !(platform && platform.type === "gated");
      var other = otherFormat(platform);
      if (other && info.enabled) {
        alt.hidden = false;
        alt.textContent = "Get the ." + other + " installer instead";
        alt.href = buildUrl(endpoint, platform, { version: versionSelect.value, format: other });
      } else {
        alt.hidden = true;
      }
      docLinks();
    }

    function loadStatus() {
      if (!endpoint || typeof root.fetch !== "function") return;
      root.fetch(endpoint + (endpoint.indexOf("?") >= 0 ? "&" : "?") + "status=1&v=1")
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (body) {
          if (!body || body.FormatVersion !== 1) return;
          status = body;
          var labels = versionLabels(status, baseOptions.channel_label);
          versionSelect.options[0].textContent = labels.current;
          versionSelect.options[1].textContent = labels.previous;
          versionSelect.options[1].disabled = !labels.hasPrevious;
          render();
        })
        .catch(function () { /* keep the built-in "coming soon" state */ });
    }

    // Never sent as a query string: that would land in browser history and
    // any request logging. The picker POSTs it in a JSON body instead, and
    // never computes or checks the checksum itself -- only the Lambda does.
    function requestGatedDownload(platform) {
      var raw = passwordInput && passwordInput.value ? passwordInput.value : "";
      var body = parseAccessCode(raw);
      if (!body) {
        note.textContent = "Enter the access code you were given.";
        note.classList.add("is-error");
        return;
      }
      var priorLabel = go.textContent;
      go.disabled = true;
      go.textContent = "Checking...";
      root.fetch(buildUrl(endpoint, platform, { version: versionSelect.value }), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      })
        .then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (json) {
            return { ok: r.ok, json: json };
          });
        })
        .then(function (result) {
          go.disabled = false;
          go.textContent = priorLabel;
          if (result.ok && result.json && result.json.ok && result.json.url) {
            root.location.assign(result.json.url);
          } else {
            note.textContent = (result.json && result.json.error) || "That access code didn't work.";
            note.classList.add("is-error");
          }
        })
        .catch(function () {
          go.disabled = false;
          go.textContent = priorLabel;
          note.textContent = "Could not reach the download service. Try again.";
          note.classList.add("is-error");
        });
    }

    var fulfillmentEndpoint = form.getAttribute("data-order-fulfillment-endpoint") || "";
    var purchaseResult = document.getElementById("purchase-result");

    // Pre-fills the Access code field (and selects the purchased/trialed
    // app, when known) after a purchase or a Test Drive hand-off --
    // "reuse the main picker" means the buyer never has to type or paste
    // the reference:short_key pair in by hand.
    function applyAccessCode(appId, reference, shortKey) {
      if (!reference || !shortKey) return;
      if (appId && findApp(baseOptions, appId)) appSelect.value = appId;
      if (passwordInput) passwordInput.value = reference + ":" + shortKey;
      render();
      // The buyer/tester lands on this page already scrolled past the
      // "Choose your download" picker (hero, beta callout, Test Drive
      // callout all come first) -- without this, the pre-filled Download
      // button is easy to miss entirely below the fold.
      var heading = document.getElementById("picker-heading");
      if (heading && heading.scrollIntoView) heading.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function startFastSpringCheckout(platform) {
      var productPath = fastspringProductPathFor(platform.matrix_app);
      if (!productPath || !root.fastspring || !root.fastspring.builder) {
        note.textContent = "Purchasing is not available right now. Please try again shortly.";
        note.classList.add("is-error");
        return;
      }
      root.fastspring.builder.add(productPath);
      root.fastspring.builder.checkout();
    }

    // Registered globally (data-popup-closed="onFSPopupClosed" on the
    // FastSpring script tag) so it exists before the popup can ever close.
    // orderReference is null on an incomplete/cancelled checkout.
    root.onFSPopupClosed = function (orderReference) {
      if (!orderReference || !orderReference.id || !purchaseResult) return;
      if (root.fastspring && root.fastspring.builder) root.fastspring.builder.reset();
      purchaseResult.innerHTML = "";
      purchaseResult.textContent = "Finishing up your order...";
      fetch(fulfillmentEndpoint + "?fulfill=1&order=" + encodeURIComponent(orderReference.id))
        .then(function (response) {
          return response.json().then(function (body) {
            return { ok: response.ok && body.ok, body: body };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            purchaseResult.textContent = (result.body && result.body.error) || "Could not finish your order. Contact inquiries@kng-consulting.com with your order reference.";
            return;
          }
          root.KnGOrderResult.renderOrderResult(purchaseResult, result.body);
          var kinds = result.body.kinds || [];
          applyAccessCode(kinds[0], result.body.reference, result.body.short_key);
        })
        .catch(function () {
          purchaseResult.textContent = "Could not reach the order service. Contact inquiries@kng-consulting.com with your order reference: " + orderReference.id;
        });
    };

    appSelect.addEventListener("change", render);
    versionSelect.addEventListener("change", render);
    go.addEventListener("click", function () {
      var platform = currentPlatform();
      if (!platform || !describe(platform).enabled) return;
      if (platform.type === "gated") {
        requestGatedDownload(platform);
        return;
      }
      if (platform.type === "purchase") {
        startFastSpringCheckout(platform);
        return;
      }
      if (!endpoint) return;
      root.location.assign(buildUrl(endpoint, platform, { version: versionSelect.value }));
    });
    render();
    loadStatus();

    // Test Drive hand-off: trial.html sends a successful Test Drive here
    // as ?app=<id>&ref=<reference>&key=<short_key> so this page can
    // pre-fill the same way a purchase does, without the visitor
    // re-typing anything. Scrubbed from the URL/history immediately
    // after reading, same reasoning as never putting an access code in
    // a query string the download endpoint itself would see.
    try {
      var params = new (root.URLSearchParams)(root.location.search);
      var ref = params.get("ref");
      var key = params.get("key");
      if (ref && key) {
        applyAccessCode(params.get("app"), ref, key);
        if (purchaseResult && root.KnGOrderResult) {
          root.KnGOrderResult.renderOrderResult(purchaseResult, {
            reference: ref,
            short_key: key,
            valid_to: params.get("until") || null
          });
        }
        if (root.history && root.history.replaceState) {
          root.history.replaceState(null, "", root.location.pathname);
        }
      }
    } catch (e) { /* no URLSearchParams, or no location -- skip the hand-off */ }
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
  }
})(typeof window !== "undefined" ? window : this);
