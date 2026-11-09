import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../AB_explorer.html", import.meta.url), "utf8");
const builder = fs.readFileSync(new URL("../_build_nb.py", import.meta.url), "utf8");

for (const text of [
  'data-slider="wing"',
  "σ_IV(c) = σ_ATM + wing·(c/5%)",
  "equal-premium solve",
  "premium match residual",
  "A leads on",
  "Pricing yield q (annualized)",
  "Stock-borrow / carry (pricing)",
  "toy period-dividend proxy",
  "INVALID — ",
  "peak and r** suppressed",
]) {
  assert.ok(html.includes(text), `missing current explorer text: ${text}`);
}

assert.ok(!html.includes('data-slider="k"'), "obsolete multiplicative k slider returned");
assert.ok(!html.includes("sigAtm*(1+(k-1)"), "obsolete multiplicative skew model returned");
assert.ok(!html.includes("Borrow / repo spread"), "obsolete borrow label returned");

for (const text of [
  "used **only in option pricing**",
  "stock-borrow / carry adjustment used only in option pricing",
  "toy proxy exp(q·τ)−1",
  "higher *relative price elasticity* to IV",
  "$y_A/y_B$ and $f_B$ rise",
  "INVALID —",
  "No return curves, D_peak, or r** are drawn",
]) {
  assert.ok(builder.includes(text), `missing builder contract text: ${text}`);
}
assert.ok(!builder.includes("raises $y_B$ faster than"),
  "obsolete IV explanation returned");
assert.ok(!builder.includes('description="borrow / repo"'),
  "obsolete notebook borrow label returned");

console.log("AB_explorer current text/model contract checks passed");
