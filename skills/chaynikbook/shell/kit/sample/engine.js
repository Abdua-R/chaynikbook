/* engine.js of the sample book: the one formula the page recomputes, y = a x (see page.js for the contract). */
(function (root) {
  "use strict";
  const y = (s) => s.a * s.x;
  root.ENGINE = {
    selfTest(D) { const ok = y(D.inputs) === D.outputs.y ? 1 : 0; return { ok, total: 1, failed: ok ? [] : ["y"] }; },
    applyChanges(changes, check, D) { return Object.assign({}, D.inputs, changes); },
    checkValue(out, s) { if (out === "y") return y(s); throw new Error("unknown check output " + out); },
    CHECK_BASE: { y: "outputs.y" },
  };
})(window);
