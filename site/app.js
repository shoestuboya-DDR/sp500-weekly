(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const yen = (n) => n.toLocaleString("ja-JP") + " 円";
  const md = (iso) => {
    const [, m, d] = iso.split("-").map(Number);
    return `${m}/${d}`;
  };
  const pct = (x) => (x > 0 ? "+" : "") + x.toFixed(2) + "%";
  const arrow = (x) => (x >= 0 ? "▲" : "▼");
  const daysBetween = (a, b) => Math.floor((b - a) / 86400000);

  function render(data) {
    const weeks = data.weeks;
    const latest = weeks[0];
    const th = data.alert_threshold_pct;

    // ---- ヘッダー
    const gen = new Date(data.generated_at);
    $("meta").textContent =
      `最終更新 ${gen.toLocaleString("ja-JP", { dateStyle: "short", timeStyle: "short" })}` +
      `（データ ${data.source_latest_date} まで）`;
    $("fund").textContent = `${data.fund.name}（ISIN: ${data.fund.isin}）`;

    // ---- データが古い
    const age = daysBetween(new Date(data.source_latest_date + "T00:00:00+09:00"), new Date());
    if (age >= data.stale_days) {
      const el = $("stale");
      el.textContent = `⚠ 最新データが ${data.source_latest_date} のままで、更新が止まっている可能性あり`;
      el.hidden = false;
    }

    // ---- 今週のサマリー
    $("cur-label").textContent = `今週末 (${md(latest.date)})`;
    $("cur-price").textContent = yen(latest.price);
    if (latest.prev_price != null) {
      $("prev-label").textContent = `前週末 (${md(latest.prev_date)})`;
      $("prev-price").textContent = yen(latest.prev_price);
      const ch = $("change");
      ch.textContent = `${pct(latest.change_pct)} ${arrow(latest.change_pct)}`;
      ch.className = "change " + (latest.change_pct >= 0 ? "up" : "down");
    }
    if (latest.is_partial) {
      const b = $("partial-badge");
      b.textContent = `速報（${md(latest.date)} 時点）`;
      b.hidden = false;
    }
    const prefix = latest.is_partial ? "【暫定】" : "";
    if (latest.alert) {
      const el = $("alert");
      el.textContent = `⚠ ${prefix}前週比 ${pct(latest.change_pct)}（${th}% 以下）の下落`;
      el.hidden = false;
      document.querySelector(".summary").classList.add("is-alert");
    } else if (latest.caution) {
      const el = $("caution");
      el.textContent =
        `⚠ ${prefix}注意：前週比 ${pct(latest.change_pct)}（${data.caution_threshold_pct}% 以下）の下落`;
      el.hidden = false;
      document.querySelector(".summary").classList.add("is-caution");
    }

    // ---- 表
    const shown = weeks.slice(0, data.display_weeks);
    const tbody = $("rows");
    for (const w of shown) {
      const tr = document.createElement("tr");
      if (w.alert) tr.className = "alert";
      else if (w.caution) tr.className = "caution";
      const changeText = w.change_pct == null ? "-" : `${pct(w.change_pct)} ${arrow(w.change_pct)}`;
      const cls = w.change_pct == null ? "" : w.change_pct >= 0 ? "up" : "down";
      tr.innerHTML =
        `<td class="col-week"></td><td></td><td class="num"></td>` +
        `<td class="num ${cls}"></td>`;
      tr.children[0].textContent = w.week;
      tr.children[1].textContent = w.date + (w.is_partial ? "（速報）" : "");
      tr.children[2].textContent = w.price.toLocaleString("ja-JP");
      tr.children[3].textContent = changeText;
      if (w.alert || w.caution) {
        const flag = document.createElement("span");
        flag.className = "flag";
        flag.textContent = w.alert ? "⚠" : "△";
        flag.setAttribute("aria-label", w.alert ? "アラート" : "注意");
        tr.children[3].appendChild(flag);
      }
      tbody.appendChild(tr);
    }

    // ---- グラフ（古い順に並べ直す）
    if (window.Chart) drawChart(shown.slice().reverse());
  }

  function drawChart(series) {
    const css = getComputedStyle(document.documentElement);
    const lineColor = css.getPropertyValue("--line").trim();
    const downColor = css.getPropertyValue("--down").trim();
    const cautionColor = css.getPropertyValue("--caution").trim();
    const pointColor = (w) => (w.alert ? downColor : w.caution ? cautionColor : lineColor);
    const muted = css.getPropertyValue("--muted").trim();
    const border = css.getPropertyValue("--border").trim();

    new Chart($("chart"), {
      type: "line",
      data: {
        labels: series.map((w) => md(w.date)),
        datasets: [
          {
            data: series.map((w) => w.price),
            borderColor: lineColor,
            borderWidth: 2,
            tension: 0.2,
            pointRadius: series.map((w) => (w.alert ? 6 : w.caution ? 5 : 0)),
            pointHoverRadius: 5,
            pointBackgroundColor: series.map(pointColor),
            pointBorderColor: series.map(pointColor),
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => series[items[0].dataIndex].date,
              label: (item) => {
                const w = series[item.dataIndex];
                const c = w.change_pct == null ? "" : `（${pct(w.change_pct)}）`;
                return `${yen(w.price)}${c}${w.alert ? " ⚠" : w.caution ? " △" : ""}`;
              },
            },
          },
        },
        scales: {
          x: { ticks: { color: muted, maxTicksLimit: 8 }, grid: { color: border } },
          y: {
            ticks: { color: muted, callback: (v) => v.toLocaleString("ja-JP") },
            grid: { color: border },
          },
        },
      },
    });
  }

  fetch("data/data.json", { cache: "no-store" })
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(render)
    .catch((e) => {
      $("meta").textContent = `データの読み込みに失敗: ${e.message}`;
    });
})();
