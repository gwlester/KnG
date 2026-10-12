/* Shared "Order Information" result renderer -- used by the purchase flow
   (picker.js, after a FastSpring order is fulfilled) and the Test Drive
   flow (trial.html, after a trial is issued) so both present the same
   receipt: reference, key, and a pointer back up at the main download
   picker above, which picker.js has already pre-filled with this same
   reference+short_key (see picker.js's applyAccessCode). No picker of
   its own here -- "reuse the main picker" means literally reuse it, not
   build a second one. Pure DOM, no dependencies; exported for tests the
   same way picker.js is. */
(function (root) {
  "use strict";

  var PLATFORM_LABELS = { mac: "macOS", windows: "Windows", linux: "Linux", "raspberry-pi": "Raspberry Pi", android: "Android" };

  function platformLabel(id) {
    return PLATFORM_LABELS[id] || id;
  }

  // Builds the "Order Information" box as a DOM node -- callers append it
  // to their own container. `result` is whatever an order-fulfillment or
  // trial-request response gives: {reference, short_key, valid_to?}.
  function buildOrderResultBox(doc, result) {
    var box = doc.createElement("div");
    box.className = "order-info-box";

    var heading = doc.createElement("h3");
    heading.textContent = "Order Information";
    box.appendChild(heading);

    function field(label, value) {
      var p = doc.createElement("p");
      var strong = doc.createElement("strong");
      strong.textContent = label + ": ";
      p.appendChild(strong);
      p.appendChild(doc.createTextNode(value));
      box.appendChild(p);
    }

    field("Order reference", result.reference);
    field("Activation key", result.short_key);
    if (result.valid_to) field("Valid until", result.valid_to);

    var instructions = doc.createElement("p");
    instructions.textContent = "The picker above is filled in with these details -- choose your platform and click Download. " +
      "Keep this reference and key: you'll also enter them in the Admin app on first connection to license your Server/MIDI Player.";
    box.appendChild(instructions);

    return box;
  }

  function renderOrderResult(container, result) {
    container.innerHTML = "";
    container.appendChild(buildOrderResultBox(container.ownerDocument || document, result));
  }

  var api = { platformLabel: platformLabel, buildOrderResultBox: buildOrderResultBox, renderOrderResult: renderOrderResult };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
    return;
  }
  root.KnGOrderResult = api;
})(typeof window !== "undefined" ? window : this);
