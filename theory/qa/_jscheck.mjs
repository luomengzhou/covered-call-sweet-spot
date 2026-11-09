import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const html = fs.readFileSync(new URL("../AB_explorer.html", import.meta.url), "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script, "AB_explorer.html must contain one inline script");

// Execute the current production model, stopping before DOM initialization.
const model = script.split("/* ---------- build sliders")[0];
const checks = `
const base = solve({...BASE});
if (Math.abs(base.yA - 0.0329455) > 5e-6) throw new Error("y_A anchor failed");
if (Math.abs(base.yB - 0.0533824) > 5e-6) throw new Error("y_B anchor failed");
if (Math.abs(base.fB - 0.61716) > 5e-5) throw new Error("f_B anchor failed");
if (Math.abs(base.D(0.05) - 0.030858) > 5e-6) throw new Error("D peak failed");
if (Math.abs(base.D(base.rss)) > 1e-12) throw new Error("crossover identity failed");
if (Math.abs(base.p.fA * base.ytA - base.fB * base.ytB) > 1e-12)
  throw new Error("premium match failed");
const wing = solve({...BASE, wing: -0.0052});
if (Math.abs(wing.sigA - 0.4448) > 1e-12) throw new Error("additive wing failed");
if (!base.valid) throw new Error("base case unexpectedly invalid");
if (Math.abs(base.dq - Math.expm1(base.p.q*base.tau)) > 1e-15)
  throw new Error("toy dividend proxy failed");
const actualDiv = solve({...BASE, q: 0.06, dividendReturn: 0.0123});
if (!actualDiv.valid || Math.abs(actualDiv.dq - 0.0123) > 1e-15)
  throw new Error("actual period dividend override failed");

const expectInvalid = (p,code) => {
  const s=solve({...BASE,...p});
  if(s.valid || s.code!==code) throw new Error(\`expected invalid \${code}, got \${s.code}\`);
  return s;
};
expectInvalid({cA:0.04,cB:0.05},"cap-order");
expectInvalid({sig:0.10,wing:-0.10,cA:0.05,cB:0},"vol-floor");
expectInvalid({q:1000,rf:0},"premium");
expectInvalid({wing:0.50},"fB-bounds");
const ordering=expectInvalid({wing:0.20,fA:0.50},"ordering");
if (!(ordering.fB>=ordering.p.fA && ordering.fB<=1))
  throw new Error("ordering fixture must isolate f_B >= f_A within coverage bounds");

// Joint boundary: cap-order wins deterministically even when the raw A vol also hits the floor.
const joint=expectInvalid(
  {sig:0.10,wing:-0.20,cA:0.04,cB:0.05},
  "cap-order"
);
if (joint.sigA>MIN_VOL+1e-12) throw new Error("joint boundary did not reach vol floor");

const equalCaps=solve({...BASE,cA:0,cB:0});
if(!equalCaps.valid || Math.abs(equalCaps.fB-equalCaps.p.fA)>1e-12)
  throw new Error("c_A = c_B identity boundary should remain valid");

// ---- desk/distribution layer (00_theory_dashboard_desk_view.md) ----
// Exercise probabilities: flat-smile N(d2) anchors, and the smile-consistent
// digital must match ab_core.call_prob_q on the same inputs.
if (Math.abs(base.probBsA - 0.3391153) > 5e-6) throw new Error("N(d2) A anchor failed");
if (Math.abs(base.probBsB - 0.4843288) > 5e-6) throw new Error("N(d2) B anchor failed");
if (base.probA !== base.probBsA) throw new Error("wing=0 digital must equal N(d2)");
const smile = solve({...BASE, wing:-0.02});
if (Math.abs(smile.probA - 0.3783589) > 5e-6) throw new Error("smile digital A anchor failed");
if (Math.abs(smile.probB - 0.5303592) > 5e-6) throw new Error("smile digital B anchor failed");
if (!(smile.probA > smile.probBsA && smile.probB > smile.probBsB))
  throw new Error("negative wing must lift the smile-consistent digitals");

// Wing feasibility domain: mirrors ab_core.wing_bounds on the binding case.
const wr = wingRange({...BASE, sig:0.20, cA:0.20});
if (Math.abs(wr[0] - (-0.017102)) > 5e-4) throw new Error("wing lower bound anchor failed");
if (Math.abs(wr[1] - 0.05) > 1e-12) throw new Error("wing upper bound should not bind here");
if (!solve({...BASE, sig:0.20, cA:0.20, wing:wr[0]}).valid)
  throw new Error("wing lower edge must solve");
if (solve({...BASE, sig:0.20, cA:0.20, wing:wr[0]-1e-3}).valid)
  throw new Error("below the wing lower edge must be invalid");
const wrBase = wingRange({...BASE});
if (wrBase[0] !== -0.05 || wrBase[1] !== 0.05)
  throw new Error("base params should not clamp the wing slider");

// Notional helpers: parse robustness and the equal-dollar-premium identity.
if (parseNotional("10,000,000") !== 1e7) throw new Error("notional parse failed");
if (parseNotional("0") !== 1e7 || parseNotional("junk") !== 1e7)
  throw new Error("notional fallback failed");
if (fmtMoney(329455.0) !== "$329,455") throw new Error("money format failed");
const premA = base.p.fA*base.yA*1e7, premB = base.fB*base.yB*1e7;
if (Math.abs(premA - premB) > 1e-6) throw new Error("equal dollar premium failed");
if (Math.abs(premA - 329454.99) > 1) throw new Error("$10mm premium anchor failed");

console.log("AB_explorer current-model numerical checks passed");
`;

vm.runInNewContext(`${model}\n${checks}`, {console, Math, Number, Object, Array});
