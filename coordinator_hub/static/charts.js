/* Aegis Saathi charts: small, dependency-free SVG/HTML charts drawn from the portal's CSS tokens, so light and
   dark mode both work. Every chart is a string of markup; Charts.bind(root) adds the hover / focus tooltips.
   Rules kept everywhere: one axis, thin marks, 2px gaps between fills, text in ink colours (never the series
   colour), an aria-label that says what the chart shows, and a "Table" view for anything with more than a
   handful of numbers. Nothing animates on the 8-second refresh. */
(function () {
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (v) => v !== null && v !== undefined && v !== "" && !Number.isNaN(Number(v));
  const f = (n, d = 0) => (num(n) ? Number(n).toLocaleString(document.documentElement.lang === "hi" ? "hi-IN" : "en-IN", { maximumFractionDigits: d, minimumFractionDigits: d }) : "–");
  let uid = 0;

  /* ---------------------------------------------------------------- donut (parts of a whole, ≤ 5 parts) */
  // segments: [{label, value, color}]   color is a CSS colour, e.g. "var(--viz-crit)"
  function donut({ segments, size = 168, thick = 22, center = "", centerSub = "", label = "" }) {
    const total = segments.reduce((a, s) => a + (Number(s.value) || 0), 0);
    const r = (size - thick) / 2, c = 2 * Math.PI * r, gap = total ? 2 : 0;   // 2px surface gap between segments
    let at = 0;
    const arcs = segments.filter((s) => s.value > 0).map((s) => {
      const len = (s.value / total) * c, dash = Math.max(len - gap, 0.5);
      const el = `<circle class="seg" cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${s.color}" stroke-width="${thick}"
        stroke-dasharray="${dash.toFixed(2)} ${(c - dash).toFixed(2)}" stroke-dashoffset="${(-at).toFixed(2)}"
        tabindex="0" data-tip="${esc(s.label)}: ${f(s.value)} (${Math.round((s.value / total) * 100)}%)"></circle>`;
      at += len;
      return el;
    }).join("");
    const aria = label || segments.map((s) => `${s.label} ${s.value}`).join(", ");
    return `<div class="donut" style="width:${size}px;height:${size}px">
      <svg viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(aria)}"><g transform="rotate(-90 ${size / 2} ${size / 2})">
        <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="var(--viz-track)" stroke-width="${thick}"></circle>${arcs}</g></svg>
      ${center !== "" ? `<div class="donut-c"><b class="num">${center}</b>${centerSub ? `<span>${esc(centerSub)}</span>` : ""}</div>` : ""}</div>`;
  }

  /* ------------------------------------------------- legend with counts (identity is never colour alone) */
  function legend(items, cls = "") {
    return `<ul class="viz-legend ${cls}">${items.map((s) => `<li>${s.icon || `<i class="sw" style="background:${s.color}"></i>`}
      <span class="lbl">${esc(s.label)}</span>${s.value !== undefined ? `<b class="num">${f(s.value)}</b>` : ""}</li>`).join("")}</ul>`;
  }

  /* ---------------------------------------------------- horizontal bar list (ranked magnitudes, labels) */
  // rows: [{label, value, color?, note?, href?}]
  function bars(rows, { max, unit = "", digits = 0, label = "" } = {}) {
    const m = max || Math.max(1, ...rows.map((r) => Number(r.value) || 0));
    return `<ul class="viz-bars" role="list" aria-label="${esc(label)}">${rows.map((r) => {
      const w = Math.max(0, Math.min(100, ((Number(r.value) || 0) / m) * 100));
      const inner = `<span class="bl">${esc(r.label)}${r.note ? `<small>${esc(r.note)}</small>` : ""}</span>
        <span class="bt" aria-hidden="true"><i style="width:${w.toFixed(1)}%;${r.color ? `background:${r.color}` : ""}"></i></span>
        <b class="bv num">${f(r.value, digits)}${unit ? `<small>${esc(unit)}</small>` : ""}</b>`;
      return `<li>${r.href ? `<a href="${esc(r.href)}">${inner}</a>` : `<div>${inner}</div>`}</li>`;
    }).join("")}</ul>`;
  }

  /* --------------------------------------------- stacked horizontal bars (composition per row + total) */
  // rows: [{label, href?, parts:[{label, value, color}]}]
  function stacks(rows, { label = "", target = null } = {}) {
    const m = Math.max(1, target || 0, ...rows.map((r) => r.parts.reduce((a, p) => a + (p.value || 0), 0)));
    return `<ul class="viz-stacks" aria-label="${esc(label)}">${rows.map((r) => {
      const tot = r.parts.reduce((a, p) => a + (p.value || 0), 0);
      const segs = r.parts.filter((p) => p.value > 0).map((p) => `<i tabindex="0" style="width:${((p.value / m) * 100).toFixed(2)}%;background:${p.color}"
        data-tip="${esc(r.label)} · ${esc(p.label)}: ${f(p.value)}"></i>`).join("");
      const tip = r.parts.map((p) => `${p.label} ${p.value}`).join(", ");
      const name = r.href ? `<a href="${esc(r.href)}">${esc(r.label)}</a>` : esc(r.label);
      return `<li><span class="bl">${name}</span><span class="st" role="img" aria-label="${esc(r.label)}: ${esc(tip)}">${segs}
        ${target ? `<em class="target" style="left:${((target / m) * 100).toFixed(1)}%" title="target"></em>` : ""}</span><b class="bv num">${f(tot)}</b></li>`;
    }).join("")}</ul>`;
  }

  /* ------------------------------------------- line over days (one series, optional usual-range band) */
  // values: numbers or null (gap); labels: same length; band: [lo, hi] shaded "usual" range; ref: [lo, hi] dashed lines
  function line(values, { labels = [], band = null, ref = null, unit = "", digits = 0, height = 140, width = 460, color = "var(--viz-brand)", label = "", second = null } = {}) {
    const W = width, H = height, P = { l: 38, r: 10, t: 10, b: 22 };   // scales with its box; kept narrow so text stays readable on phones
    const all = values.concat(second ? second.values : []).filter(num).map(Number);
    if (all.length < 2) return `<p class="viz-empty">${esc(label)}</p>`;
    let lo = Math.min(...all, ...(band || []), ...(ref || [])), hi = Math.max(...all, ...(band || []), ...(ref || []));
    const pad = (hi - lo) * 0.12 || Math.max(1, Math.abs(hi) * 0.1); lo -= pad; hi += pad;
    const n = Math.max(values.length - 1, 1);
    const X = (i) => P.l + (i / n) * (W - P.l - P.r), Y = (v) => P.t + (1 - (v - lo) / (hi - lo)) * (H - P.t - P.b);
    const path = (vals) => { let d = "", pen = false; vals.forEach((v, i) => { if (!num(v)) { return; } d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)} `; pen = true; }); return d; };
    const ticks = [lo + pad, (lo + hi) / 2, hi - pad].map((v) => `<g class="tick"><line x1="${P.l}" x2="${W - P.r}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"></line>
      <text x="${P.l - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end">${f(v, digits)}</text></g>`).join("");
    const xl = labels.length ? [0, Math.floor(n / 2), n].map((i) => `<text class="xl" x="${X(i).toFixed(1)}" y="${H - 6}" text-anchor="${i === 0 ? "start" : i === n ? "end" : "middle"}">${esc(labels[i] || "")}</text>`).join("") : "";
    const bandEl = band ? `<rect class="band" x="${P.l}" width="${W - P.l - P.r}" y="${Y(band[1]).toFixed(1)}" height="${Math.max(1, Y(band[0]) - Y(band[1])).toFixed(1)}"></rect>` : "";
    const refEl = ref ? ref.map((v) => `<line class="ref" x1="${P.l}" x2="${W - P.r}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"></line>`).join("") : "";
    const dots = (vals, col) => vals.map((v, i) => (num(v) ? `<circle class="pt" cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="${i === vals.length - 1 || vals.filter(num).length < 8 ? 4.5 : 0}" fill="${col}"></circle>` : "")).join("");
    // one invisible column per day: hover / keyboard focus shows that day's value
    const colW = (W - P.l - P.r) / (n || 1);
    const hits = values.map((v, i) => {
      const parts = [num(v) ? `${f(v, digits)}${unit ? " " + unit : ""}` : "–"];
      if (second && num(second.values[i])) parts.push(`${second.label} ${f(second.values[i], digits)}`);
      return `<rect class="hit" tabindex="0" x="${(X(i) - colW / 2).toFixed(1)}" y="0" width="${colW.toFixed(1)}" height="${H}" data-x="${X(i).toFixed(1)}"
        data-tip="${esc(labels[i] || "")}: ${esc(parts.join(" · "))}"></rect>`;
    }).join("");
    const id = "ln" + ++uid;
    return `<div class="viz-line" id="${id}"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">
      ${bandEl}${ticks}${refEl}
      ${second ? `<path class="ln ln2" d="${path(second.values)}" stroke="${second.color || "var(--viz-brand-2)"}"></path>${dots(second.values, second.color || "var(--viz-brand-2)")}` : ""}
      <path class="ln" d="${path(values)}" stroke="${color}"></path>${dots(values, color)}
      <line class="xh" x1="0" x2="0" y1="${P.t}" y2="${H - P.b}"></line>${xl}${hits}</svg></div>`;
  }

  /* ---------------------------------------------------------- small trend (KPI tiles, trend cards) */
  function mini(values, { color = "var(--viz-brand)", labels = [], unit = "", label = "" } = {}) {
    const vals = values.map((v) => (num(v) ? Number(v) : null));
    const ys = vals.filter((v) => v !== null);
    if (ys.length < 2) return "";
    const W = 120, H = 32, lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1, n = vals.length - 1;
    const pts = vals.map((v, i) => (v === null ? null : [(i / n) * W, H - 3 - ((v - lo) / span) * (H - 6)])).filter(Boolean);
    const d = pts.map((p, k) => `${k ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
    const area = `${d} L${pts[pts.length - 1][0].toFixed(1)},${H} L${pts[0][0].toFixed(1)},${H} Z`;
    const last = pts[pts.length - 1];
    return `<svg class="viz-mini" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(label || ys.join(", "))}">
      <path d="${area}" fill="${color}" opacity=".12"></path><path d="${d}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"></path>
      <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3" fill="${color}"></circle></svg>`;
  }

  /* --------------------------------------------------------------- half-circle gauge (one number of 100) */
  function gauge(value, { max = 100, color = "var(--viz-brand)", label = "", sub = "" } = {}) {
    const v = Math.max(0, Math.min(max, Number(value) || 0)), r = 70, cx = 90, cy = 86, c = Math.PI * r;
    const len = (v / max) * c;
    return `<div class="viz-gauge"><svg viewBox="0 0 180 100" role="img" aria-label="${esc(label)}: ${f(v)} / ${max}">
      <path d="M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}" fill="none" stroke="var(--viz-track)" stroke-width="14" stroke-linecap="round"></path>
      <path d="M${cx - r},${cy} A${r},${r} 0 0 1 ${cx + r},${cy}" fill="none" stroke="${color}" stroke-width="14" stroke-linecap="round"
        stroke-dasharray="${len.toFixed(1)} ${c.toFixed(1)}"></path></svg>
      <div class="gv"><b class="num">${f(v)}</b><span>${esc(sub)}</span></div></div>`;
  }

  /* ------------------------------------------------------------ calendar heat strip (doses per day) */
  // rows: [{label, sub, cells:[{state, tip}]}]  state: taken | skipped | missed | due | none
  function heat(rows, cols, { label = "" } = {}) {
    const sym = { taken: "✓", skipped: "–", missed: "×", due: "", none: "" };
    return `<div class="viz-heat" role="table" aria-label="${esc(label)}">
      <div class="hr hh" role="row"><span role="columnheader"></span>${cols.map((c) => `<span role="columnheader">${esc(c)}</span>`).join("")}</div>
      ${rows.map((r) => `<div class="hr" role="row"><span class="hl" role="rowheader">${esc(r.label)}${r.sub ? `<small>${esc(r.sub)}</small>` : ""}</span>
        ${r.cells.map((c) => `<span role="cell" class="hc ${c.state}" tabindex="0" data-tip="${esc(c.tip)}" aria-label="${esc(c.tip)}">${c.parts || sym[c.state] || ""}</span>`).join("")}</div>`).join("")}
    </div>`;
  }

  /* ------------------------------------------------------- figure: title, chart, and a "Table" toggle */
  function figure({ title = "", sub = "", body = "", table = null, actions = "", cls = "" }) {
    const id = "fig" + ++uid;
    return `<figure class="viz ${cls}" data-fig="${id}">
      ${title || table ? `<figcaption><div class="grow">${title ? `<h3>${title}</h3>` : ""}${sub ? `<p class="sm muted">${sub}</p>` : ""}</div>${actions}
        ${table ? `<button type="button" class="tbl-toggle" aria-expanded="false" aria-controls="${id}-t">${esc(window.__vizTableLabel || "Table")}</button>` : ""}</figcaption>` : ""}
      <div class="viz-body">${body}</div>
      ${table ? `<div class="viz-table" id="${id}-t" hidden><div class="table-wrap"><table class="tbl"><thead><tr>${table.head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>
        <tbody>${table.rows.map((r) => `<tr>${r.map((c, i) => `<td${i ? ' class="n"' : ""}>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div>` : ""}
    </figure>`;
  }

  /* ----------------------------------------------------------------------- tooltips + table toggles */
  let tipEl = null;
  function tip() {
    if (!tipEl) { tipEl = document.createElement("div"); tipEl.className = "viz-tip"; tipEl.setAttribute("role", "tooltip"); document.body.appendChild(tipEl); }
    return tipEl;
  }
  function show(target, x, y) {
    const t = tip(); t.textContent = target.getAttribute("data-tip"); t.style.display = "block";
    const r = t.getBoundingClientRect();
    t.style.left = Math.min(window.innerWidth - r.width - 8, Math.max(8, x - r.width / 2)) + "px";
    t.style.top = Math.max(8, y - r.height - 12) + "px";
    const svg = target.closest(".viz-line svg");
    if (svg && target.dataset.x) { const xh = svg.querySelector(".xh"); xh.setAttribute("x1", target.dataset.x); xh.setAttribute("x2", target.dataset.x); xh.style.opacity = 1; }
  }
  function hide(target) {
    if (tipEl) tipEl.style.display = "none";
    const xh = target && target.closest && target.closest(".viz-line svg") && target.closest(".viz-line svg").querySelector(".xh");
    if (xh) xh.style.opacity = 0;
  }
  function bind(root) {
    root.querySelectorAll("[data-tip]").forEach((el) => {
      if (el.__tip) return; el.__tip = 1;
      el.addEventListener("pointermove", (e) => show(el, e.clientX, e.clientY));
      el.addEventListener("pointerleave", () => hide(el));
      el.addEventListener("focus", () => { const r = el.getBoundingClientRect(); show(el, r.left + r.width / 2, r.top); });
      el.addEventListener("blur", () => hide(el));
    });
    root.querySelectorAll(".tbl-toggle").forEach((b) => {
      if (b.__t) return; b.__t = 1;
      b.addEventListener("click", () => {
        const t = document.getElementById(b.getAttribute("aria-controls")), open = b.getAttribute("aria-expanded") !== "true";
        b.setAttribute("aria-expanded", open); t.hidden = !open;
        b.closest("figure").querySelector(".viz-body").hidden = open;
      });
    });
  }
  window.addEventListener("scroll", () => hide(null), { passive: true });

  window.Charts = { donut, legend, bars, stacks, line, mini, gauge, heat, figure, bind, fmt: f };
})();
