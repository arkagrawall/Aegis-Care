/* A simplified outline of India drawn from about a hundred border points (lat, lon), and city markers placed on
   it: each city is a small donut sized by how many people the service watches there, split by priority.
   Works offline (no tiles, no library). Accurate enough to read "where", not for navigation. */
(function () {
  const OUTLINE = [
    [23.6, 68.4], [24.3, 68.8], [24.6, 71.1], [25.4, 70.6], [26.0, 70.2], [27.0, 70.0], [27.9, 70.6], [28.6, 72.0],
    [29.9, 73.4], [30.9, 74.0], [31.6, 74.6], [32.3, 75.0], [32.8, 74.5], [33.6, 74.0], [34.4, 73.8], [35.4, 74.3],
    [36.3, 74.8], [36.9, 75.3], [36.2, 76.9], [35.7, 77.9], [35.6, 79.4], [35.1, 80.2], [34.3, 79.0], [33.2, 79.4],
    [32.5, 79.4], [31.7, 78.8], [31.0, 79.0], [30.3, 80.2], [30.2, 81.0], [28.9, 80.1], [28.6, 81.2], [27.9, 82.7],
    [27.4, 83.9], [27.4, 85.2], [26.6, 86.8], [26.4, 88.0], [27.3, 88.1], [28.1, 88.8], [27.4, 88.9], [27.1, 89.0],
    [26.8, 89.5], [26.8, 91.0], [26.8, 92.0], [27.8, 92.2], [28.2, 93.4], [29.0, 94.0], [29.3, 95.4], [29.4, 96.1],
    [28.4, 97.3], [27.2, 97.0], [26.6, 96.0], [25.8, 95.4], [24.9, 94.7], [24.0, 94.2], [23.4, 93.4], [22.4, 93.2],
    [21.9, 92.6], [22.9, 92.3], [23.8, 91.9], [24.1, 91.4], [23.4, 91.2], [23.9, 91.6], [24.4, 92.2], [25.1, 92.4],
    [25.2, 90.0], [25.3, 89.8], [26.1, 89.1], [25.6, 88.4], [25.0, 88.4], [24.2, 88.7], [23.2, 88.9], [22.0, 89.0],
    [21.6, 88.5], [21.6, 87.5], [20.8, 87.0], [20.2, 86.5], [19.3, 84.9], [18.3, 84.0], [17.7, 83.3], [16.9, 82.3],
    [16.4, 81.7], [15.8, 80.3], [14.5, 80.2], [13.6, 80.3], [13.0, 80.3], [12.0, 79.9], [11.0, 79.8], [10.3, 79.3],
    [9.3, 79.1], [8.8, 78.2], [8.1, 77.5], [8.9, 76.5], [10.0, 76.2], [11.2, 75.8], [12.9, 74.8], [14.8, 74.1],
    [15.6, 73.7], [17.0, 73.3], [18.9, 72.8], [20.5, 72.8], [21.1, 72.6], [22.2, 72.6], [21.6, 72.2], [21.0, 71.1],
    [20.8, 70.8], [21.6, 69.3], [22.3, 68.9], [22.8, 70.3], [23.0, 69.6], [22.9, 68.7],
  ];
  // the cities the service runs in (coordinates of the city centre)
  const CITIES = {
    "delhi ncr": [28.61, 77.21], delhi: [28.61, 77.21], lucknow: [26.85, 80.95], jaipur: [26.91, 75.79],
    varanasi: [25.32, 82.97], indore: [22.72, 75.86], mumbai: [19.08, 72.88], bengaluru: [12.97, 77.59],
    kolkata: [22.57, 88.36], chennai: [13.08, 80.27], hyderabad: [17.39, 78.49], pune: [18.52, 73.86],
    ahmedabad: [23.02, 72.57], patna: [25.59, 85.14], bhopal: [23.26, 77.41], chandigarh: [30.73, 76.78],
    noida: [28.54, 77.39], "greater noida": [28.47, 77.5], gurugram: [28.46, 77.03], ghaziabad: [28.67, 77.45],
    mathura: [27.49, 77.67], agra: [27.18, 78.01], kanpur: [26.45, 80.33], bihar: [25.59, 85.14], "uttar pradesh": [26.85, 80.95],
  };
  const LAT0 = 22, K = Math.cos((LAT0 * Math.PI) / 180);
  const W = 400, H = 440, PAD = 10;
  const lons = OUTLINE.map((p) => p[1]), lats = OUTLINE.map((p) => p[0]);
  const minX = Math.min(...lons) * K, maxX = Math.max(...lons) * K, minY = Math.min(...lats), maxY = Math.max(...lats);
  const s = Math.min((W - 2 * PAD) / (maxX - minX), (H - 2 * PAD) / (maxY - minY));
  const P = (lat, lon) => [PAD + (lon * K - minX) * s, PAD + (maxY - lat) * s];
  const PATH = OUTLINE.map(([la, lo], i) => { const [x, y] = P(la, lo); return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`; }).join(" ") + " Z";
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* A projection that fits the given lat/lon box into W x H (same east-west correction as the full map). */
  function fit(la0, la1, lo0, lo1, w, h, pad) {
    const x0 = lo0 * K, x1 = lo1 * K, sc = Math.min((w - 2 * pad) / (x1 - x0), (h - 2 * pad) / (la1 - la0));
    const ox = (w - (x1 - x0) * sc) / 2, oy = (h - (la1 - la0) * sc) / 2;
    return (lat, lon) => [ox + (lon * K - x0) * sc, oy + (la1 - lat) * sc];
  }
  const pathWith = (proj) => OUTLINE.map(([la, lo], i) => { const [x, y] = proj(la, lo); return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`; }).join(" ") + " Z";

  /* cities: [{name, total, parts:[{label, value, color}], href, tip, sub}]   pins: [{lat, lon, label}] (SOS)
     When the cities sit in one part of the country the map zooms to them and shows all of India as a small inset. */
  function render({ cities = [], pins = [], label = "" }) {
    const max = Math.max(1, ...cities.map((c) => c.total || 0));
    const placed = cities.map((c) => ({ c, at: CITIES[String(c.name).toLowerCase()] })).filter((x) => x.at);
    const pts = placed.map((x) => x.at).concat(pins.map((p) => [p.lat, p.lon]));
    let proj = P, zoom = null;
    if (pts.length) {
      let la0 = Math.min(...pts.map((p) => p[0])) - 2.2, la1 = Math.max(...pts.map((p) => p[0])) + 2.2;
      let lo0 = Math.min(...pts.map((p) => p[1])) - 3, lo1 = Math.max(...pts.map((p) => p[1])) + 3;
      const grow = (a, b, min) => { const m = (a + b) / 2, half = Math.max((b - a) / 2, min / 2); return [m - half, m + half]; };
      [la0, la1] = grow(la0, la1, 9); [lo0, lo1] = grow(lo0, lo1, 10);
      if (la1 - la0 < (maxY - minY) * 0.7) { proj = fit(la0, la1, lo0, lo1, W, H, 6); zoom = [la0, la1, lo0, lo1]; }
    }
    // circles first, so labels never sit on another city's circle
    const geo = placed.sort((a, b) => (b.c.total || 0) - (a.c.total || 0)).map(({ c, at }) => {
      const [x, y] = proj(at[0], at[1]);
      return { c, x, y, r: 6 + 14 * Math.sqrt((c.total || 0) / max) };
    });
    const taken = geo.map((g) => [g.x - g.r, g.y - g.r, g.x + g.r, g.y + g.r]);
    const free = (b) => b[0] >= 0 && b[2] <= W && b[1] >= 0 && b[3] <= H && !taken.some((t) => b[0] < t[2] && b[2] > t[0] && b[1] < t[3] && b[3] > t[1]);
    const marks = geo.map(({ c, x, y, r }) => {
      const w = r > 10 ? 7 : 4, rr = r - w / 2, circ = 2 * Math.PI * rr;
      let off = 0;
      const segs = c.parts.filter((p) => p.value > 0).map((p) => {
        const len = (p.value / (c.total || 1)) * circ, dash = Math.max(len - 1.5, 0.5);
        const el = `<circle r="${rr.toFixed(1)}" fill="none" stroke="${p.color}" stroke-width="${w}" stroke-dasharray="${dash.toFixed(2)} ${(circ - dash).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90)"></circle>`;
        off += len; return el;
      }).join("");
      const tw = Math.max(String(c.name).length * 7.8, String(c.sub || "").length * 6.4) + 4, th = 30;
      const spots = [[x + r + 5, y - 15, "start"], [x - r - 5 - tw, y - 15, "end"], [x - tw / 2, y + r + 3, "middle"], [x - tw / 2, y - r - th - 3, "middle"],
                     [x + r + 5, y - 2, "start"], [x - r - 5 - tw, y - 2, "end"], [x + r + 5, y - th + 2, "start"], [x - r - 5 - tw, y - th + 2, "end"]];
      const spot = spots.find(([sx, sy]) => free([sx, sy, sx + tw, sy + th]));
      let lab = "";
      if (spot) {
        taken.push([spot[0], spot[1], spot[0] + tw, spot[1] + th]);
        const ax = spot[2] === "start" ? spot[0] - x : spot[2] === "end" ? spot[0] + tw - x : spot[0] + tw / 2 - x, ay = spot[1] - y + 12;
        lab = `<text class="cn" x="${ax.toFixed(1)}" y="${ay.toFixed(1)}" text-anchor="${spot[2]}">${esc(c.name)}</text>
        <text class="cv" x="${ax.toFixed(1)}" y="${(ay + 15).toFixed(1)}" text-anchor="${spot[2]}">${esc(c.sub || "")}</text>`;
      }
      return `<a class="city" href="${esc(c.href || "#")}" data-tip="${esc(c.tip || c.name)}" aria-label="${esc(c.tip || c.name)}" transform="translate(${x.toFixed(1)},${y.toFixed(1)})">
        <circle r="${(r + 2).toFixed(1)}" class="halo"></circle>${segs}<circle r="${Math.max(1, rr - w / 2 - 0.5).toFixed(1)}" class="core"></circle>
        ${lab}</a>`;
    }).reverse().join("");      // small towns drawn last, on top
    const pinEls = pins.map((p) => {
      const [x, y] = proj(p.lat, p.lon);
      return `<g class="pin" transform="translate(${x.toFixed(1)},${y.toFixed(1)})" tabindex="0" data-tip="${esc(p.label)}"><circle r="9" class="pulse"></circle><circle r="5"></circle></g>`;
    }).join("");
    let inset = "";
    if (zoom) {
      const iw = 92, ih = 100, ip = fit(minY, maxY, Math.min(...lons), Math.max(...lons), iw, ih, 4);
      const [ax, ay] = ip(zoom[1], zoom[2]), [bx, by] = ip(zoom[0], zoom[3]);
      inset = `<g class="inset" transform="translate(${W - iw - 6},${H - ih - 6})" aria-hidden="true"><rect width="${iw}" height="${ih}" rx="8"></rect>
        <path class="land" d="${pathWith(ip)}"></path><rect class="zoom" x="${ax.toFixed(1)}" y="${ay.toFixed(1)}" width="${(bx - ax).toFixed(1)}" height="${(by - ay).toFixed(1)}"></rect></g>`;
    }
    return `<svg class="india" viewBox="0 0 ${W} ${H}" role="group" aria-label="${esc(label)}"><path class="land" d="${zoom ? pathWith(proj) : PATH}"></path>${marks}${pinEls}${inset}</svg>`;
  }

  window.IndiaMap = { render, known: (name) => !!CITIES[String(name || "").toLowerCase()] };
})();
