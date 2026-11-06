const $ = id => document.getElementById(id);
const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
const svg = (t, a = {}) => { const e = document.createElementNS("http://www.w3.org/2000/svg", t); Object.entries(a).forEach(([k, v]) => e.setAttribute(k, v)); return e; };
const inr = n => "₹" + Number(n).toLocaleString("en-IN", {maximumFractionDigits: 2});
const COLORS = ["#1e40af", "#0e7490", "#7c3aed", "#d97706", "#be185d", "#15803d", "#b91c1c", "#64748b"];
const CSRF = document.querySelector('meta[name="csrf"]').content;
let META, month, editId = null, tt;
const toast = m => { const t = $("toast"); t.textContent = m; t.classList.add("show"); clearTimeout(tt); tt = setTimeout(() => t.classList.remove("show"), 2800); };
async function call(url, method = "GET", body) {
  const r = await fetch(url, {method, headers: {"Content-Type": "application/json", "X-CSRF-Token": CSRF}, body: body && JSON.stringify(body)});
  if (r.status === 401) { location.href = "/login"; return {ok: false, d: {}}; }
  return {ok: r.ok, d: await r.json()};
}
const monthLabel = k => new Date(+k.slice(0, 4), +k.slice(5) - 1).toLocaleString("en", {month: "short"});

function renderStats(s) {
  const box = $("stats"); box.innerHTML = "";
  [["Income", inr(s.income), "income"], ["Expenses", inr(s.expense), "expense"], ["Balance", inr(s.balance), s.balance < 0 ? "neg" : ""], ["Savings rate", s.savings_rate + "%", s.savings_rate < 0 ? "neg" : ""]].forEach(([l, v, c]) => {
    const d = el("div", "stat " + (c === "income" || c === "expense" ? c : "")); const sp = el("span", c === "neg" ? "neg" : "", v); d.append(el("small", "", l), sp); box.append(d); });
}

function renderDonut(cats) {
  const box = $("donut"), lg = $("legend"); box.innerHTML = lg.innerHTML = ""; $("noCats").hidden = cats.length > 0;
  if (!cats.length) return;
  const total = cats.reduce((a, c) => a + c.total, 0), s = svg("svg", {viewBox: "0 0 42 42", role: "img", "aria-label": "Spending by category"});
  s.append(svg("circle", {cx: 21, cy: 21, r: 15.9155, fill: "none", stroke: "#e9edf6", "stroke-width": 6}));
  let off = 0;
  cats.forEach((c, i) => {
    const pct = c.total / total * 100;
    s.append(svg("circle", {cx: 21, cy: 21, r: 15.9155, fill: "none", stroke: COLORS[i % COLORS.length], "stroke-width": 6, "stroke-dasharray": `${pct} ${100 - pct}`, "stroke-dashoffset": 25 - off}));
    off += pct;
    const li = el("li"), dot = el("i"); dot.style.background = COLORS[i % COLORS.length]; li.append(dot, el("span", "", c.category), el("b", "", inr(c.total))); lg.append(li);
  });
  const t = svg("text", {x: 21, y: 22.5, "text-anchor": "middle", "font-size": 4.2, "font-weight": 700, fill: "#16213a"}); t.textContent = inr(total); s.append(t);
  box.append(s);
}

function renderTrend(rows) {
  const box = $("trend"); box.innerHTML = "";
  const max = Math.max(1, ...rows.flatMap(r => [r.income, r.expense])), s = svg("svg", {viewBox: "0 0 360 170", role: "img", "aria-label": "Income and expenses for the last six months"});
  rows.forEach((r, i) => {
    const x = 12 + i * 58;
    [[r.income, "#16a34a", 0], [r.expense, "#1e40af", 20]].forEach(([v, c, dx]) => {
      const h = v / max * 120;
      const rect = svg("rect", {x: x + dx, y: 135 - h, width: 18, height: Math.max(h, v ? 2 : 0), rx: 3, fill: c}); const t = svg("title"); t.textContent = inr(v); rect.append(t); s.append(rect);
    });
    const lab = svg("text", {x: x + 19, y: 155, "text-anchor": "middle", "font-size": 11, fill: "#667089"}); lab.textContent = monthLabel(r.month); s.append(lab);
  });
  box.append(s);
}

function renderBudgets(list) {
  const box = $("budgets"); box.innerHTML = ""; $("noBudgets").hidden = list.length > 0;
  list.forEach(b => {
    const row = el("div", "brow"), top = el("div", "top"), cls = b.pct >= 100 ? "over" : b.pct >= 80 ? "warn" : "";
    const rm = el("button", "link", "Remove"); rm.onclick = async () => { await call("/api/budgets/" + encodeURIComponent(b.category), "DELETE"); refresh(); };
    top.append(el("b", "", b.category), el("span", "", `${inr(b.spent)} of ${inr(b.limit)} (${b.pct}%)` + (b.pct >= 100 ? " · over budget" : b.pct >= 80 ? " · almost there" : "")), rm);
    const tr = el("div", "track"), i = el("i", cls); i.style.width = Math.min(b.pct, 100) + "%"; tr.append(i); row.append(top, tr); box.append(row);
  });
}

async function loadTx() {
  const p = new URLSearchParams({month, type: $("fType").value, category: $("fCat").value, q: $("q").value.trim()});
  $("exportLink").href = "/api/export?" + p;
  const rows = (await call("/api/transactions?" + p)).d, tb = $("rows"); tb.innerHTML = ""; $("noRows").hidden = rows.length > 0;
  rows.forEach(t => {
    const tr = el("tr"), cell = (l, ...k) => { const td = el("td"); td.dataset.l = l; td.append(...k); tr.append(td); return td; };
    cell("Date", t.tx_date); cell("Category", el("span", "tag", t.category)); cell("Note", t.note || "-");
    cell("Amount", el("span", "amt " + (t.type === "income" ? "in" : "out"), (t.type === "income" ? "+" : "-") + inr(t.amount))).classList.add("r");
    const td = el("td", "none"), a = el("div", "acts"), e = el("button", "", "Edit"), d = el("button", "del", "Delete");
    e.onclick = () => openForm(t); d.onclick = async () => { if (!confirm("Delete this transaction?")) return; await call("/api/transactions/" + t.id, "DELETE"); toast("Deleted"); refresh(); };
    a.append(e, d); td.append(a); tr.append(td); tb.append(tr);
  });
}

async function refresh() {
  const s = (await call("/api/summary?month=" + month)).d; if (!s.month) return;
  renderStats(s); renderDonut(s.by_category); renderTrend(s.trend); renderBudgets(s.budgets); loadTx();
}

function fillCategories(kind, value) {
  const sel = $("form").category; sel.innerHTML = ""; META[kind].forEach(c => sel.append(new Option(c, c))); if (value) sel.value = value;
}
function openForm(t) {
  editId = t ? t.id : null; const f = $("form"); f.reset(); $("formErr").textContent = ""; $("dlgTitle").textContent = t ? "Edit transaction" : "Add transaction";
  const today = new Date(), iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  f.tx_date.value = t ? t.tx_date : (iso.slice(0, 7) === month ? iso : month + "-01");
  if (t) { f.type.value = t.type; f.amount.value = t.amount; f.note.value = t.note; }
  fillCategories(f.type.value, t && t.category); $("dlg").showModal(); f.amount.focus();
}
document.querySelectorAll('#form input[name="type"]').forEach(r => r.addEventListener("change", () => fillCategories($("form").type.value)));
$("form").addEventListener("submit", async e => {
  e.preventDefault(); const f = e.target; if (!f.checkValidity()) return f.reportValidity();
  const body = {type: f.type.value, amount: f.amount.value, tx_date: f.tx_date.value, category: f.category.value, note: f.note.value};
  const r = await call(editId ? "/api/transactions/" + editId : "/api/transactions", editId ? "PUT" : "POST", body);
  if (!r.ok) { $("formErr").textContent = r.d.error; return; }
  $("dlg").close(); toast(editId ? "Transaction updated" : "Transaction added"); refresh();
});
$("budgetForm").addEventListener("submit", async e => {
  e.preventDefault(); const r = await call("/api/budgets/" + encodeURIComponent($("bCat").value), "PUT", {limit: $("bLimit").value});
  if (!r.ok) return toast(r.d.error); $("bLimit").value = ""; toast("Budget saved"); refresh();
});
$("addBtn").onclick = () => openForm(null); $("cancel").onclick = () => $("dlg").close();
$("month").onchange = e => { if (e.target.value) { month = e.target.value; refresh(); } };
let st; $("q").oninput = () => { clearTimeout(st); st = setTimeout(loadTx, 250); }; $("fType").onchange = $("fCat").onchange = loadTx;

(async () => {
  META = (await call("/api/meta")).d; month = META.month; $("month").value = month;
  META.expense.forEach(c => $("bCat").append(new Option(c, c)));
  [...new Set([...META.expense, ...META.income])].forEach(c => $("fCat").append(new Option(c, c)));
  refresh();
})();
