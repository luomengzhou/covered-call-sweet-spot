import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const html = fs.readFileSync(new URL("../AB_explorer.html", import.meta.url), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script, "AB_explorer.html must contain one inline script");

let canvasCalls = 0;
function contextStub() {
  return new Proxy({}, {
    get(_target, prop) {
      if (prop === "measureText") return () => ({width: 20});
      return (...args) => {
        canvasCalls += 1;
        for (const value of args) {
          if (typeof value === "number" && !Number.isFinite(value)) {
            throw new Error(`non-finite canvas coordinate in ${String(prop)}`);
          }
        }
      };
    },
    set() { return true; },
  });
}

class Element {
  constructor(id = "") {
    this.id = id;
    this.dataset = {};
    this.style = {};
    this.checked = false;
    this.value = "0";
    this.clientWidth = 800;
    this.listeners = {};
    this.attrs = {};
    this.html = "";
    this.text = "";
  }
  get innerHTML() { return this.html; }
  set innerHTML(value) { this.html = String(value); this.text = ""; }
  get textContent() { return this.text; }
  set textContent(value) { this.text = String(value); this.html = ""; }
  getAttribute(name) { return this.attrs[name] ?? (name === "height" ? "300" : null); }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  getContext() { return contextStub(); }
  querySelector(selector) { return this.children?.[selector] ?? new Element(); }
}

const registry = new Map();
const get = id => {
  if (!registry.has(id)) registry.set(id, new Element(id));
  return registry.get(id);
};
for (const id of [
  "verdict", "cards", "skewNote", "presetNote", "tbl", "checks",
  "showExcess", "showMarks", "c1", "c2", "c3", "c4", "c5",
  "sweepNote", "grid", "gridNote", "gridQty", "notional", "notionalOut",
]) get(id);
get("showMarks").checked = true;

const sliderRows = [...html.matchAll(/<div class="row" ([^>]*data-slider[^>]*)><\/div>/g)]
  .map(([, attrs]) => {
    const data = Object.fromEntries(
      [...attrs.matchAll(/data-([a-z]+)="([^"]+)"/g)].map(([, key, value]) => [key, value])
    );
    const row = new Element();
    row.dataset = data;
    const input = new Element();
    const output = new Element();
    row.children = {input, output};
    return row;
  });
const presetButtons = [...html.matchAll(/data-preset="([^"]+)"/g)].map(([, preset]) => {
  const button = new Element();
  button.dataset = {preset};
  return button;
});

const document = {
  getElementById: get,
  querySelectorAll: selector => selector.includes("data-slider") ? sliderRows
    : selector.includes("data-preset") ? presetButtons : [],
};
const window = {devicePixelRatio: 2, addEventListener() {}};

vm.runInNewContext(script, {console, document, window, Math, Number, Object, Array, isFinite});

let renders = 1;
for (const row of sliderRows) {
  const input = row.children.input;
  for (const value of [row.dataset.min, row.dataset.max]) {
    input.value = value;
    for (const fn of input.listeners.input ?? []) fn();
    renders += 1;
  }
}
for (const button of presetButtons) {
  for (const fn of button.listeners.click ?? []) fn();
  renders += 1;
}

const setSlider = (key,value) => {
  const row=sliderRows.find(r=>r.dataset.slider===key);
  assert.ok(row, `missing slider ${key}`);
  row.children.input.value=String(value);
  for (const fn of row.children.input.listeners.input ?? []) fn();
  renders += 1;
};

// Hostile drive: the same sequence that used to reach the INVALID branch
// (reversed caps plus a floored raw volatility) must now be normalized away —
// sliders clamp to the feasible domain, so no slider-reachable state is invalid.
setSlider("sig",0.10);
setSlider("wing",-0.05);      // clamped up to the feasible wing lower edge
setSlider("cA",0.00);         // pulls c_B down with it
setSlider("cB",0.15);         // clamped back to c_A
assert.ok(!get("verdict").textContent.startsWith("INVALID —"),
  "slider-reachable state rendered INVALID despite clamping");
assert.ok(get("verdict").textContent.includes("identical"),
  "c_A = c_B = 0 should render the identical-strategies verdict");
assert.ok(get("skewNote").innerHTML.includes("Feasible here"),
  "skew note does not report the feasible wing range");

// Wing clamp alone: a low-vol wide cap must tighten the wing's lower edge.
setSlider("cA",0.20);
setSlider("sig",0.20);
setSlider("wing",-0.05);
assert.ok(!get("verdict").textContent.startsWith("INVALID —"),
  "wing clamp failed at sig=20%, cap=20%");
assert.ok(get("cards").innerHTML.includes("f_B"), "clamped state did not render cards");

setSlider("sig",0.45);
setSlider("wing",0.00);
setSlider("cB",0.00);
setSlider("cA",0.05);
assert.ok(!get("verdict").textContent.startsWith("INVALID —"), "valid render did not recover");
assert.ok(get("cards").innerHTML.includes("f_B"), "valid cards did not recover");

// New desk/distribution surfaces render.
assert.ok(get("cards").innerHTML.includes("P(A called)"), "probability cards missing");
assert.ok(get("cards").innerHTML.includes("premium $"), "dollar premium card missing");
assert.ok(get("tbl").innerHTML.includes("P(called)"), "leg table lacks P(called) column");
assert.ok(get("tbl").innerHTML.includes("premium $"), "leg table lacks premium $ column");
assert.ok(get("tbl").innerHTML.includes("$/contract"), "leg table lacks $/contract column");
assert.ok(get("tbl").innerHTML.includes("100 shares"), "leg table lacks the contract-size footnote");
assert.ok(get("grid").innerHTML.includes("<thead"), "term grid did not render");
assert.ok(get("grid").innerHTML.includes("12M"), "term grid lacks tenor columns");
assert.ok(get("gridNote").textContent.includes("anchor c_B"), "term grid note missing");
assert.ok(get("notionalOut").textContent.startsWith("$"), "notional readout missing");

// Sweep charts (00_theory_dashboard_desk_view.md §5.1): at short tenor,
// D_peak(c) has a real interior maximum inside the cap window; the
// sweet-spot note must say so, not the boundary language. The earlier
// full-slider sweep (min/max pass above) left tau parked at its max (12), so
// set it back to the 1-month default explicitly before asserting.
setSlider("tau",1);
assert.ok(get("sweepNote").innerHTML.includes("sweet-spot cap"),
  "short-tenor sweep should report an interior sweet-spot cap");
assert.ok(!get("sweepNote").innerHTML.includes("still rising at the right edge"),
  "short-tenor sweep incorrectly reported a boundary-pinned optimum");

// Push tenor past the ~5.5-month threshold: the interior max should vanish
// and the note should switch to the boundary-pinned explanation.
setSlider("tau",12);
assert.ok(get("sweepNote").innerHTML.includes("still rising at the right edge"),
  "12-month sweep should report the optimum has moved past the cap window");
assert.ok(!get("sweepNote").innerHTML.includes("sweet-spot cap"),
  "12-month sweep incorrectly still reported an interior sweet-spot cap");
setSlider("tau",1);   // restore the default before the remaining assertions

assert.ok(canvasCalls > 0, "render did not exercise canvas");
canvasCalls = 0; setSlider("tau",1); // re-render (all 5 canvases, incl. c5)
assert.ok(canvasCalls > 0, "re-render did not exercise canvas (tenor-sweep chart included)");

assert.ok(canvasCalls > 0, "render did not exercise canvas");
assert.ok(get("cards").innerHTML.includes("f_B"), "cards did not render");
console.log(`AB_explorer rendered ${renders} current-model scenarios`);
