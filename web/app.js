const $ = (s) => document.querySelector(s);
const fmtInt = (n) => Number(n).toLocaleString();

async function loadInfo() {
  try {
    const r = await fetch("/api/info");
    const info = await r.json();
    if (info.error) throw new Error(info.error);
    const c = info.counts;
    $("#stats").innerHTML =
      `<b>${fmtInt(c.asteroids)}</b> asteroids · <b>${fmtInt(c.neo)}</b> near-Earth · ` +
      `<b>${fmtInt(c.pha)}</b> hazardous<br><b>${fmtInt(c.close_approaches)}</b> Earth flybys 1900–2200 · ` +
      `NASA/JPL data from ${info.dataset.fetched_utc || "?"}`;
    $("#model").textContent = info.model;
    const sel = $("#strategy");
    for (const [key, label] of Object.entries(info.strategies)) {
      const o = new Option(label.split(":")[0], key, false, key === info.default_strategy);
      o.title = label;
      sel.add(o);
    }
    try { const s = localStorage.getItem("strategy"); if (s && info.strategies[s]) sel.value = s; } catch {}
    for (const q of info.examples) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = q;
      b.onclick = () => { $("#question").value = q; ask(q); };
      $("#examples").append(b);
    }
  } catch (e) {
    $("#stats").textContent = "Could not load database info: " + e.message;
  }
}

function renderTable(table, columns, rows) {
  table.innerHTML = "";
  const thead = table.createTHead().insertRow();
  for (const c of columns) {
    const th = document.createElement("th");
    th.textContent = c;
    thead.append(th);
  }
  const tb = table.createTBody();
  for (const row of rows.slice(0, 200)) {
    const tr = tb.insertRow();
    for (const v of row) {
      const td = tr.insertCell();
      if (typeof v === "number") {
        td.className = "num";
        td.textContent = Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumSignificantDigits: 6 });
      } else {
        td.textContent = v === null ? "NULL" : v;
      }
    }
  }
}

let busy = false;
async function ask(question) {
  question = question.trim();
  if (!question || busy) return;
  busy = true;
  $("#ask-btn").disabled = true;

  const card = $("#card-tpl").content.firstElementChild.cloneNode(true);
  card.querySelector(".q").textContent = question;
  const a = card.querySelector(".a");
  a.textContent = "Writing SQL and querying the database";
  a.classList.add("loading");
  card.querySelectorAll("details").forEach((d) => (d.hidden = true));
  $("#thread").prepend(card);

  try {
    const strategy = $("#strategy").value;
    const r = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, strategy }),
    });
    const res = await r.json();
    a.classList.remove("loading");
    if (res.error && !res.sql) throw new Error(res.error);

    a.textContent = res.answer || "";
    if (res.error) a.classList.add("err");

    const sqlBox = card.querySelector(".sql-box");
    sqlBox.hidden = false;
    sqlBox.querySelector("code").textContent = res.sql || "";
    const secs = ((res.timings_ms?.total || 0) / 1000).toFixed(1);
    sqlBox.querySelector(".meta").textContent = `· ${res.strategy.replace("_", " ")} · ${secs}s`;
    const failed = (res.attempts || []).filter((t) => t.error);
    if (failed.length) {
      const div = sqlBox.querySelector(".attempts");
      const doubleCheck = failed.some((f) => f.error.startsWith("model said unanswerable"));
      div.textContent = res.error ? "Query failed:"
        : doubleCheck ? "The model first said this can't be answered from the data and was asked to double-check:"
        : "First attempt failed and was repaired:";
      for (const f of failed) {
        const pre = document.createElement("pre");
        pre.textContent = `${f.sql}\n\n${f.error}`;
        div.append(pre);
      }
    }
    if (res.rejected_answer) {
      const div = sqlBox.querySelector(".rejected");
      div.textContent = "Model's answer, rejected because it isn't backed by the data (" +
        res.grounding_problems.join("; ") + "):";
      const pre = document.createElement("pre");
      pre.textContent = res.rejected_answer;
      div.append(pre);
    }
    if (res.columns && res.columns.length && !res.unanswerable) {
      const tb = card.querySelector(".table-box");
      tb.hidden = false;
      const n = res.rows.length;
      tb.querySelector(".rowcount").textContent =
        `· ${fmtInt(n)}${res.truncated ? "+" : ""} row${n === 1 ? "" : "s"}${n > 200 ? " (showing 200)" : ""}`;
      renderTable(tb.querySelector("table"), res.columns, res.rows);
      if (n > 1 && n <= 25) tb.open = true;
    }
  } catch (e) {
    a.classList.remove("loading");
    a.classList.add("err");
    a.textContent = "Something went wrong: " + e.message;
  } finally {
    busy = false;
    $("#ask-btn").disabled = false;
  }
}

$("#ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  ask($("#question").value);
});
$("#strategy").addEventListener("change", (e) => {
  try { localStorage.setItem("strategy", e.target.value); } catch {}
});
loadInfo();
