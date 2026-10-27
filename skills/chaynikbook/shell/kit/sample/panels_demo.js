/* panels_demo.js: the sample book's one panel type. A slider moves the slope of y = a x; the axes stay fixed. */
(function () {
  "use strict";
  const V = window.VIZ;
  PANELS.register("demo", (host, o) => {
    V.div("controls", host);
    const out = V.div("", host), xs = [...Array(o.n).keys()].map((i) => (10 * i) / (o.n - 1));
    const draw = (a) => {
      out.innerHTML = "";
      const ys = xs.map((x) => a * x);
      const fr = V.frame(out, { xmin: 0, xmax: 10, ymin: 0, ymax: a * 10, xlabel: "input x", ylabel: "output y", label: "the line y = a x" });
      V.line(fr, xs, ys);
      V.dot(fr, o.x, a * o.x, 5);
      V.tag(fr, fr.sx(o.x) + 8, fr.sy(a * o.x), "y = " + V.fmt(a * o.x, "fix1"), "main");
      V.tableOf(host, "the line", ["input x", "output y"], xs.map((x, i) => [V.fmt(x, "fix1"), V.fmt(ys[i], "fix1")]));
    };
    V.slider(host, { label: "slope a", min: 0.5, max: 3, step: 0.1, value: o.a, show: (v) => v.toFixed(1) }, draw);
    draw(o.a);
  }, "Raise the slope and watch the line swing up while the axes stay where they are, so the scale never hides the change.");
})();
