const COLORS = {
  orange: "#c2410c",
  teal: "#0f766e",
  sky: "#0369a1",
  rose: "#be123c",
  slate: "#334155",
  amber: "#d97706",
};

const STATE_NAMES = ["stable", "infiltrative", "angiogenic", "aggressive", "terminal"];
const EVENT_NAMES = ["seizure", "edema_flare", "cognitive_drop", "radiographic_progression", "intervention"];
const STATE_COLORS = {
  stable: "#4d7c0f",
  infiltrative: "#0f766e",
  angiogenic: "#0369a1",
  aggressive: "#d97706",
  terminal: "#be123c",
};

function mulberry32(seed) {
  let t = seed >>> 0;
  return function next() {
    t += 0x6d2b79f5;
    let x = Math.imul(t ^ t >>> 15, 1 | t);
    x ^= x + Math.imul(x ^ x >>> 7, 61 | x);
    return ((x ^ x >>> 14) >>> 0) / 4294967296;
  };
}

function sigmoid(value) {
  return 1 / (1 + Math.exp(-value));
}

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/).filter(Boolean);
  if (!lines.length) return [];
  const headers = lines[0].split(",").map((item) => item.trim());
  return lines.slice(1).map((line) => {
    const values = line.split(",").map((item) => item.trim());
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
  });
}

function fitLongitudinalRows(rows) {
  const stateCounts = Object.fromEntries(STATE_NAMES.map((name) => [name, 0]));
  const grouped = {};
  rows.forEach((row) => {
    const patientId = Number(row.patient_id || 0);
    grouped[patientId] ||= [];
    grouped[patientId].push(row);
    stateCounts[row.state] = (stateCounts[row.state] || 0) + 1;
  });
  return {
    rows: rows.length,
    patients: Object.keys(grouped).length,
    state_prevalence_order: Object.entries(stateCounts).sort((a, b) => b[1] - a[1]),
  };
}

function createMetricCard(label, value) {
  const template = document.getElementById("metric-card-template");
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".metric-label").textContent = label;
  node.querySelector(".metric-value").textContent = value;
  return node;
}

function createPanel(title, subtitle = "") {
  const panel = document.createElement("section");
  panel.className = "panel";
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = subtitle || "Visualization";
  const heading = document.createElement("h2");
  heading.textContent = title;
  panel.append(kicker, heading);
  return panel;
}

function svgEl(name, attrs = {}) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, String(value)));
  return el;
}

function renderBarChart(data, options = {}) {
  const width = options.width || 520;
  const height = options.height || 280;
  const padding = { top: 30, right: 20, bottom: 44, left: 44 };
  const maxValue = Math.max(...data.map((item) => item.count || item.value || 0), 1);
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const barWidth = chartWidth / Math.max(data.length, 1) * 0.62;
  const gap = chartWidth / Math.max(data.length, 1) * 0.38;
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, class: options.className || "chart" });

  svg.appendChild(svgEl("line", { x1: padding.left, y1: padding.top, x2: padding.left, y2: padding.top + chartHeight, stroke: "#334155", "stroke-width": 2 }));
  svg.appendChild(svgEl("line", { x1: padding.left, y1: padding.top + chartHeight, x2: width - padding.right, y2: padding.top + chartHeight, stroke: "#334155", "stroke-width": 2 }));

  data.forEach((item, index) => {
    const value = item.count ?? item.value ?? 0;
    const x = padding.left + index * (barWidth + gap) + gap / 2;
    const barHeight = (value / maxValue) * chartHeight;
    const y = padding.top + chartHeight - barHeight;

    const rect = svgEl("rect", {
      x,
      y,
      width: barWidth,
      height: barHeight,
      rx: 10,
      fill: item.color || options.color || COLORS.orange,
    });
    if (item.tooltip) {
      const title = svgEl("title");
      title.textContent = item.tooltip;
      rect.appendChild(title);
    }
    if (item.onClick) {
      rect.style.cursor = "pointer";
      rect.addEventListener("click", item.onClick);
    }
    svg.appendChild(rect);

    const valueLabel = svgEl("text", {
      x: x + barWidth / 2,
      y: y - 8,
      "text-anchor": "middle",
      "font-size": 12,
      fill: "#1a2233",
      "font-family": "Trebuchet MS, Segoe UI, sans-serif",
    });
    valueLabel.textContent = value;
    svg.appendChild(valueLabel);

    const label = svgEl("text", {
      x: x + barWidth / 2,
      y: height - 12,
      "text-anchor": "middle",
      "font-size": 12,
      fill: "#5f6b7a",
      "font-family": "Trebuchet MS, Segoe UI, sans-serif",
    });
    label.textContent = item.label;
    svg.appendChild(label);
  });

  return svg;
}

function renderComparisonChart(data) {
  const width = 540;
  const height = 300;
  const padding = { top: 34, right: 20, bottom: 52, left: 54 };
  const maxValue = Math.max(
    ...data.flatMap((item) => [item.observed, item.simulated]),
    1,
  );
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const groupWidth = chartWidth / Math.max(data.length, 1);
  const barWidth = Math.min(42, groupWidth / 3);
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart" });

  svg.appendChild(svgEl("line", { x1: padding.left, y1: padding.top, x2: padding.left, y2: padding.top + chartHeight, stroke: "#334155", "stroke-width": 2 }));
  svg.appendChild(svgEl("line", { x1: padding.left, y1: padding.top + chartHeight, x2: width - padding.right, y2: padding.top + chartHeight, stroke: "#334155", "stroke-width": 2 }));

  data.forEach((item, index) => {
    const origin = padding.left + index * groupWidth + groupWidth / 2;
    const observedHeight = (item.observed / maxValue) * chartHeight;
    const simulatedHeight = (item.simulated / maxValue) * chartHeight;

    svg.appendChild(svgEl("rect", {
      x: origin - barWidth - 6,
      y: padding.top + chartHeight - observedHeight,
      width: barWidth,
      height: observedHeight,
      rx: 10,
      fill: COLORS.teal,
    }));
    svg.appendChild(svgEl("rect", {
      x: origin + 6,
      y: padding.top + chartHeight - simulatedHeight,
      width: barWidth,
      height: simulatedHeight,
      rx: 10,
      fill: COLORS.orange,
    }));

    const label = svgEl("text", {
      x: origin,
      y: height - 14,
      "text-anchor": "middle",
      "font-size": 12,
      fill: "#5f6b7a",
      "font-family": "Trebuchet MS, Segoe UI, sans-serif",
    });
    label.textContent = item.label;
    svg.appendChild(label);
  });

  return svg;
}

function renderPolicyChart(data) {
  return renderBarChart(
    data.map((item, index) => ({
      label: item.policy,
      value: Number(item.mean_total_reward.toFixed(2)),
      color: [COLORS.orange, COLORS.sky, COLORS.rose][index % 3],
    })),
    { width: 480, height: 260, className: "mini-chart" },
  );
}

function renderHorizontalBars(data, key, color) {
  const width = 520;
  const height = 250;
  const padding = { top: 24, right: 24, bottom: 20, left: 120 };
  const maxValue = Math.max(...data.map((item) => item[key]), 1);
  const chartWidth = width - padding.left - padding.right;
  const rowHeight = 34;
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart" });

  data.forEach((item, index) => {
    const y = padding.top + index * (rowHeight + 12);
    const barWidth = (item[key] / maxValue) * chartWidth;
    const label = svgEl("text", {
      x: 12,
      y: y + 20,
      "font-size": 13,
      fill: "#334155",
      "font-family": "Trebuchet MS, Segoe UI, sans-serif",
    });
    label.textContent = item.label;
    svg.appendChild(label);
    svg.appendChild(svgEl("rect", { x: padding.left, y, width: chartWidth, height: rowHeight, rx: 10, fill: "#e2e8f0" }));
    const bar = svgEl("rect", { x: padding.left, y, width: barWidth, height: rowHeight, rx: 10, fill: color });
    if (item.tooltip) {
      const title = svgEl("title");
      title.textContent = item.tooltip;
      bar.appendChild(title);
    }
    svg.appendChild(bar);
    const value = svgEl("text", {
      x: padding.left + chartWidth + 8,
      y: y + 20,
      "font-size": 12,
      fill: "#5f6b7a",
      "font-family": "Trebuchet MS, Segoe UI, sans-serif",
    });
    value.textContent = item[key];
    svg.appendChild(value);
  });

  return svg;
}

function renderLineTrajectory(states) {
  const width = 620;
  const height = 250;
  const padding = { top: 24, right: 20, bottom: 34, left: 84 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart" });
  const severity = Object.fromEntries(STATE_NAMES.map((name, index) => [name, index]));

  STATE_NAMES.forEach((stateName, index) => {
    const y = padding.top + chartHeight - (index / (STATE_NAMES.length - 1)) * chartHeight;
    const label = svgEl("text", { x: 8, y: y + 4, "font-size": 12, fill: "#5f6b7a", "font-family": "Trebuchet MS, Segoe UI, sans-serif" });
    label.textContent = stateName;
    svg.appendChild(label);
    svg.appendChild(svgEl("line", { x1: padding.left, y1: y, x2: width - padding.right, y2: y, stroke: "#dbe4ee", "stroke-dasharray": "4,4" }));
  });

  const points = states.map((state, index) => {
    const x = padding.left + (index / Math.max(states.length - 1, 1)) * chartWidth;
    const y = padding.top + chartHeight - (severity[state] / (STATE_NAMES.length - 1)) * chartHeight;
    return { x, y, state, index };
  });
  svg.appendChild(svgEl("polyline", {
    fill: "none",
    stroke: COLORS.orange,
    "stroke-width": 4,
    points: points.map((point) => `${point.x},${point.y}`).join(" "),
  }));
  points.forEach((point) => {
    const circle = svgEl("circle", { cx: point.x, cy: point.y, r: 4, fill: STATE_COLORS[point.state] });
    const title = svgEl("title");
    title.textContent = `Step ${point.index}: ${point.state}`;
    circle.appendChild(title);
    svg.appendChild(circle);
  });
  return svg;
}

function simulatePatient(profile, config, policyMode, seed = 11, horizon = 18) {
  const rng = mulberry32(seed);
  const eventCounts = Object.fromEntries(EVENT_NAMES.map((name) => [name, 0]));
  const states = [];
  let currentState = "stable";

  for (let step = 0; step < horizon; step += 1) {
    const severeScore =
      0.02 * (profile.age - 50) +
      0.04 * (profile.tumorVolume - 45) -
      1.2 * (profile.resectionExtent - 0.55) +
      (profile.grade === 4 ? 0.9 : 0.15) +
      (profile.methylated ? -0.4 : 0.2) +
      config.age_weight_scale * 0.25 +
      config.progression_weight_scale * 0.2 +
      config.terminal_bias * 0.35;
    const treatmentEffect = policyMode === "none" ? 0 : policyMode === "reactive" ? 0.25 : 0.45;
    const nextIndex = Math.max(
      0,
      Math.min(
        STATE_NAMES.length - 1,
        Math.round(sigmoid(severeScore - treatmentEffect + (rng() - 0.5)) * (STATE_NAMES.length - 1)),
      ),
    );
    currentState = STATE_NAMES[nextIndex];
    states.push(currentState);

    if (rng() < sigmoid(-1.8 + nextIndex * 0.25)) eventCounts.seizure += 1;
    if (rng() < sigmoid(-1.5 + nextIndex * 0.3)) eventCounts.edema_flare += 1;
    if (rng() < sigmoid(-1.4 + nextIndex * 0.28)) eventCounts.cognitive_drop += 1;
    if (rng() < sigmoid(-1.3 + nextIndex * 0.35 + config.progression_weight_scale * 0.1)) eventCounts.radiographic_progression += 1;
    if (policyMode !== "none" && nextIndex >= 2 && rng() < 0.45) eventCounts.intervention += 1;
  }

  return { states, eventCounts, finalState: states[states.length - 1] };
}

function buildTable(rows, filterLabel = "Click an age bar to filter this table.") {
  const wrapper = document.createElement("section");
  wrapper.className = "table-panel";
  const kicker = document.createElement("p");
  kicker.className = "section-kicker";
  kicker.textContent = "Sample Records";
  const title = document.createElement("h2");
  title.textContent = "Flattened GDC Case Preview";
  const banner = document.createElement("p");
  banner.className = "filter-banner";
  banner.textContent = filterLabel;
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  ["submitter_id", "project_id", "age_years", "vital_status", "days_to_death", "progression_or_recurrence"].forEach((key) => {
    const th = document.createElement("th");
    th.textContent = key;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    ["submitter_id", "project_id", "age_years", "vital_status", "days_to_death", "progression_or_recurrence"].forEach((key) => {
      const td = document.createElement("td");
      td.textContent = row[key] ?? "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  wrapper.append(kicker, title, banner, table);
  return wrapper;
}

function buildLegend(items) {
  const legend = document.createElement("div");
  legend.className = "legend";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = item.color;
    const label = document.createElement("span");
    label.textContent = item.label;
    row.append(swatch, label);
    legend.appendChild(row);
  });
  return legend;
}

function renderDashboard(data, state) {
  const app = document.getElementById("app");
  app.innerHTML = "";

  const aboutPanel = createPanel("About", "Project Overview");
  const aboutCallout = document.createElement("div");
  aboutCallout.className = "callout";
  aboutCallout.innerHTML = `
    <p><strong>What this is:</strong> a neuro-oncology modeling lab that combines public TCGA glioma metadata, temporal disease-state simulation, intervention comparison, and longitudinal-fit summaries.</p>
    <p><strong>Live site:</strong> <a href="https://glioma-event-dynamics-dashboard.vercel.app/webapp" target="_blank" rel="noreferrer">glioma-event-dynamics-dashboard.vercel.app/webapp</a></p>
    <p><strong>GitHub:</strong> <a href="https://github.com/pranavc80/glioma-event-dynamics-dashboard" target="_blank" rel="noreferrer">github.com/pranavc80/glioma-event-dynamics-dashboard</a></p>
  `;
  aboutPanel.appendChild(aboutCallout);
  app.appendChild(aboutPanel);

  const metrics = document.createElement("section");
  metrics.className = "metrics-grid";
  metrics.append(
    createMetricCard("Cases Fetched", data.summary.cases_fetched),
    createMetricCard("Mean Age", data.summary.mean_age),
    createMetricCard("Observed 1Y Mortality", data.summary.observed_one_year_mortality),
    createMetricCard("Simulated Terminal Rate", data.summary.simulated_terminal_rate),
  );
  app.appendChild(metrics);

  const panelsA = document.createElement("section");
  panelsA.className = "panel-grid two-up";

  const agePanel = createPanel("Age Distribution", "Observed Cases");
  agePanel.appendChild(
    renderBarChart(
      data.age_buckets.map((item, idx) => ({
        ...item,
        color: [COLORS.orange, COLORS.amber, COLORS.sky, COLORS.teal, COLORS.rose][idx],
        tooltip: `${item.label}: ${item.count} cases`,
        onClick: () => {
          state.activeAgeLabel = state.activeAgeLabel === item.label ? null : item.label;
          state.render();
        },
      })),
      { width: 540, height: 280 },
    ),
  );
  const ageNote = document.createElement("p");
  ageNote.className = "chart-note";
  ageNote.textContent = "Click a bar to filter the case preview table.";
  agePanel.appendChild(ageNote);

  const mixPanel = createPanel("Project Mix", "Observed Cases");
  mixPanel.appendChild(
    renderBarChart(
      data.project_mix.map((item, idx) => ({ ...item, color: [COLORS.rose, COLORS.sky][idx] })),
      { width: 540, height: 280 },
    ),
  );

  panelsA.append(agePanel, mixPanel);
  app.appendChild(panelsA);

  const panelsB = document.createElement("section");
  panelsB.className = "panel-grid three-up";

  const calibrationPanel = createPanel("Observed vs Simulated", "Calibration Check");
  calibrationPanel.appendChild(
    renderComparisonChart([
      {
        label: "Mortality",
        observed: data.summary.observed_one_year_mortality,
        simulated: data.summary.simulated_terminal_rate,
      },
      {
        label: "Progression",
        observed: data.summary.observed_progression_prevalence,
        simulated: data.summary.simulated_progression_prevalence,
      },
    ]),
  );
  calibrationPanel.appendChild(
    buildLegend([
      { label: "Observed", color: COLORS.teal },
      { label: "Simulated", color: COLORS.orange },
    ]),
  );

  const policyPanel = createPanel("Policy Rewards", "Treatment Environment");
  policyPanel.appendChild(renderPolicyChart(data.policy_results));

  const configPanel = createPanel("Calibrated Config", "Fitted Parameters");
  const callout = document.createElement("div");
  callout.className = "callout";
  callout.innerHTML = `
    <p><strong>Terminal Bias:</strong> ${data.fit_result.simulation_config.terminal_bias}</p>
    <p><strong>Age Weight Scale:</strong> ${data.fit_result.simulation_config.age_weight_scale}</p>
    <p><strong>Grade Weight Scale:</strong> ${data.fit_result.simulation_config.grade_weight_scale}</p>
    <p><strong>Progression Weight Scale:</strong> ${data.fit_result.simulation_config.progression_weight_scale}</p>
    <p><strong>Assumption:</strong> ${data.fit_result.assumption}</p>
  `;
  configPanel.appendChild(callout);

  panelsB.append(calibrationPanel, policyPanel, configPanel);
  app.appendChild(panelsB);

  const projectComparisonPanel = createPanel("Project-Level Comparison", "GBM vs LGG");
  const projectData = Object.entries(data.fit_result.project_comparison).map(([label, values]) => ({
    label,
    observed: values.observed_mortality,
    simulated: values.simulated_terminal_rate,
  }));
  projectComparisonPanel.appendChild(renderComparisonChart(projectData));
  projectComparisonPanel.appendChild(buildLegend([
    { label: "Observed Mortality", color: COLORS.teal },
    { label: "Simulated Terminal Rate", color: COLORS.orange },
  ]));
  app.appendChild(projectComparisonPanel);

  if (data.longitudinal_fit) {
    const longitudinalPanel = createPanel("Longitudinal State Prevalence", "Trajectory-Shaped Fit");
    const prevalenceData = data.longitudinal_fit.state_prevalence_order.map(([label, count]) => ({ label, count, tooltip: `${label}: ${count} time steps` }));
    longitudinalPanel.appendChild(renderHorizontalBars(prevalenceData, "count", COLORS.sky));
    app.appendChild(longitudinalPanel);
  }

  const interactivePanel = createPanel("Interactive Simulation", "Counterfactual Explorer");
  const controls = document.createElement("div");
  controls.className = "controls-grid";
  const config = data.fit_result.simulation_config;
  const presets = {
    calibrated: { ...config },
    aggressive: { ...config, terminal_bias: config.terminal_bias + 0.8, progression_weight_scale: config.progression_weight_scale + 0.4 },
    conservative: { ...config, terminal_bias: config.terminal_bias - 0.8, intervention_weight_scale: (config.intervention_weight_scale || 1) + 0.4 },
  };

  const makeRange = (label, key, min, max, step) => {
    const wrap = document.createElement("div");
    wrap.className = "control";
    const top = document.createElement("div");
    top.className = "control-inline";
    const name = document.createElement("p");
    name.className = "control-label";
    name.textContent = label;
    const value = document.createElement("span");
    value.className = "control-value";
    value.textContent = state.profile[key];
    top.append(name, value);
    const input = document.createElement("input");
    input.type = "range";
    input.min = min;
    input.max = max;
    input.step = step;
    input.value = state.profile[key];
    input.addEventListener("input", () => {
      state.profile[key] = Number(input.value);
      value.textContent = state.profile[key];
      state.render();
    });
    wrap.append(top, input);
    return wrap;
  };

  controls.append(
    makeRange("Age", "age", 20, 85, 1),
    makeRange("Grade", "grade", 3, 4, 1),
    makeRange("Tumor Volume", "tumorVolume", 5, 140, 1),
    makeRange("Resection Extent", "resectionExtent", 0.05, 0.99, 0.01),
    makeRange("Horizon", "horizon", 8, 30, 1),
  );

  const methylationSelect = document.createElement("select");
  [["true", "Methylated"], ["false", "Unmethylated"]].forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (String(state.profile.methylated) === value) option.selected = true;
    methylationSelect.appendChild(option);
  });
  methylationSelect.addEventListener("change", () => { state.profile.methylated = methylationSelect.value === "true"; state.render(); });

  const presetSelect = document.createElement("select");
  [["calibrated", "GDC-Calibrated"], ["aggressive", "Aggressive Disease"], ["conservative", "Intervention-Friendly"]].forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (state.configKey === value) option.selected = true;
    presetSelect.appendChild(option);
  });
  presetSelect.addEventListener("change", () => { state.configKey = presetSelect.value; state.render(); });

  const policySelect = document.createElement("select");
  [["conservative", "Conservative"], ["reactive", "Reactive"], ["none", "No Treatment"]].forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (state.policyMode === value) option.selected = true;
    policySelect.appendChild(option);
  });
  policySelect.addEventListener("change", () => { state.policyMode = policySelect.value; state.render(); });

  [
    ["MGMT Methylation", methylationSelect],
    ["Config Preset", presetSelect],
    ["Policy", policySelect],
  ].forEach(([label, node]) => {
    const wrap = document.createElement("div");
    wrap.className = "control";
    const name = document.createElement("p");
    name.className = "control-label";
    name.textContent = label;
    wrap.append(name, node);
    controls.appendChild(wrap);
  });

  const chosen = simulatePatient(state.profile, presets[state.configKey], state.policyMode, state.seed, state.profile.horizon);
  const baseline = simulatePatient(state.profile, presets[state.configKey], "none", state.seed, state.profile.horizon);

  const badges = document.createElement("div");
  badges.className = "badge-row";
  [
    `Chosen final state: ${chosen.finalState}`,
    `No-treatment final state: ${baseline.finalState}`,
    `Chosen progression events: ${chosen.eventCounts.radiographic_progression}`,
    `No-treatment progression events: ${baseline.eventCounts.radiographic_progression}`,
  ].forEach((text) => {
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = text;
    badges.appendChild(badge);
  });
  controls.appendChild(badges);

  const buttonRow = document.createElement("div");
  buttonRow.className = "button-row";
  const simulateButton = document.createElement("button");
  simulateButton.textContent = "Simulate Patient";
  simulateButton.addEventListener("click", () => {
    state.seed += 1;
    state.render();
  });
  const resetButton = document.createElement("button");
  resetButton.className = "subtle-button";
  resetButton.textContent = "Reset Inputs";
  resetButton.addEventListener("click", () => {
    state.profile = { age: 58, grade: 4, methylated: true, tumorVolume: 48, resectionExtent: 0.68, horizon: 18 };
    state.configKey = "calibrated";
    state.policyMode = "conservative";
    state.seed = 11;
    state.render();
  });
  buttonRow.append(simulateButton, resetButton);
  controls.appendChild(buttonRow);
  controls.appendChild(renderLineTrajectory(chosen.states));
  controls.appendChild(renderComparisonChart([
    { label: "Seizure", observed: baseline.eventCounts.seizure, simulated: chosen.eventCounts.seizure },
    { label: "Edema", observed: baseline.eventCounts.edema_flare, simulated: chosen.eventCounts.edema_flare },
    { label: "Cognitive", observed: baseline.eventCounts.cognitive_drop, simulated: chosen.eventCounts.cognitive_drop },
    { label: "Progression", observed: baseline.eventCounts.radiographic_progression, simulated: chosen.eventCounts.radiographic_progression },
  ]));

  const uploadWrap = document.createElement("div");
  uploadWrap.className = "control";
  const uploadLabel = document.createElement("p");
  uploadLabel.className = "control-label";
  uploadLabel.textContent = "Upload Longitudinal CSV";
  const upload = document.createElement("input");
  upload.type = "file";
  upload.accept = ".csv,text/csv";
  upload.addEventListener("change", async () => {
    const file = upload.files?.[0];
    if (!file) return;
    state.uploadFit = fitLongitudinalRows(parseCsv(await file.text()));
    state.render();
  });
  uploadWrap.append(uploadLabel, upload);
  controls.appendChild(uploadWrap);

  if (state.uploadFit) {
    const uploadCallout = document.createElement("div");
    uploadCallout.className = "callout";
    uploadCallout.innerHTML = `<p><strong>Uploaded rows:</strong> ${state.uploadFit.rows}</p><p><strong>Patients:</strong> ${state.uploadFit.patients}</p>`;
    controls.appendChild(uploadCallout);
    const uploadBars = state.uploadFit.state_prevalence_order.map(([label, count]) => ({ label, count, tooltip: `${label}: ${count}` }));
    controls.appendChild(renderHorizontalBars(uploadBars, "count", COLORS.rose));
  }

  interactivePanel.appendChild(controls);
  app.appendChild(interactivePanel);

  const filteredRows = !state.activeAgeLabel
    ? data.sample_rows
    : data.sample_rows.filter((row) => {
        const value = Number(row.age_years);
        if (Number.isNaN(value)) return false;
        if (state.activeAgeLabel === "<40") return value < 40;
        if (state.activeAgeLabel === "40-49") return value >= 40 && value <= 49;
        if (state.activeAgeLabel === "50-59") return value >= 50 && value <= 59;
        if (state.activeAgeLabel === "60-69") return value >= 60 && value <= 69;
        return value >= 70;
      });

  app.appendChild(buildTable(filteredRows.length ? filteredRows : data.sample_rows, state.activeAgeLabel ? `Filtered by ${state.activeAgeLabel}` : undefined));
}

async function start() {
  const app = document.getElementById("app");
  try {
    const response = await fetch("./data/dashboard_data.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to load dashboard data (${response.status})`);
    }
    const data = await response.json();
    const state = {
      activeAgeLabel: null,
      uploadFit: null,
      profile: { age: 58, grade: 4, methylated: true, tumorVolume: 48, resectionExtent: 0.68, horizon: 18 },
      configKey: "calibrated",
      policyMode: "conservative",
      seed: 11,
      render: () => renderDashboard(data, state),
    };
    renderDashboard(data, state);
  } catch (error) {
    app.innerHTML = "";
    const card = document.createElement("section");
    card.className = "status-card";
    card.innerHTML = `
      <p class="section-kicker">Load Error</p>
      <h2>Dashboard data is missing</h2>
      <p>${error.message}</p>
      <p class="mono">Run: python -m glioma_event_lab.cli build-dashboard --max-cases 120 --out webapp/data/dashboard_data.json</p>
    `;
    app.appendChild(card);
  }
}

start();
