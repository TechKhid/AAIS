const state = {
  scenarios: [],
  selectedScenarioId: null,
  session: null,
  incident: null,
  overview: null,
  health: null,
  isBusy: false,
  isAutoplaying: false,
  pendingStepIndex: null,
  lastStepMessage: null
};

const els = {
  scenarioList: document.querySelector("#scenario-list"),
  scenarioCount: document.querySelector("#scenario-count"),
  llmStatus: document.querySelector("#llm-status"),
  start: document.querySelector("#start-session"),
  step: document.querySelector("#step-session"),
  run: document.querySelector("#run-session"),
  reset: document.querySelector("#reset-sim"),
  sessionTitle: document.querySelector("#session-title"),
  sessionSubtitle: document.querySelector("#session-subtitle"),
  sessionState: document.querySelector("#session-state"),
  stepper: document.querySelector("#stepper"),
  patientCard: document.querySelector("#patient-card"),
  patientStatus: document.querySelector("#patient-status"),
  recommendations: document.querySelector("#recommendations"),
  hospitalLoad: document.querySelector("#hospital-load"),
  fleetList: document.querySelector("#fleet-list"),
  events: document.querySelector("#events"),
  map: document.querySelector("#map"),
  mapCaption: document.querySelector("#map-caption"),
  metricIncidents: document.querySelector("#metric-incidents"),
  metricAmbulances: document.querySelector("#metric-ambulances"),
  metricBeds: document.querySelector("#metric-beds"),
  metricLoad: document.querySelector("#metric-load"),
  metricIncidentsLabel: document.querySelector("#metric-incidents-label"),
  metricAmbulancesLabel: document.querySelector("#metric-ambulances-label"),
  metricBedsLabel: document.querySelector("#metric-beds-label"),
  metricLoadLabel: document.querySelector("#metric-load-label"),
  toastStack: document.querySelector("#toast-stack")
};

els.start.addEventListener("click", startSession);
els.step.addEventListener("click", stepSession);
els.run.addEventListener("click", runSession);
els.reset.addEventListener("click", resetSimulation);

boot();
setInterval(refreshPassiveState, 7000);

async function boot() {
  await Promise.all([refreshHealth(), loadScenarios(), refreshOverview()]);
  selectScenario(state.scenarios[0]?.id);
  render();
}

async function refreshPassiveState() {
  try {
    await Promise.all([refreshHealth(), refreshOverview()]);
    if (state.session) {
      state.session = await api(`/simulation/sessions/${state.session.id}`);
      if (state.session.incident_id) {
        state.incident = await api(`/incidents/${state.session.incident_id}`);
      }
    }
    render();
  } catch (error) {
    toast(error.message, "warn");
  }
}

async function refreshHealth() {
  state.health = await api("/health");
}

async function loadScenarios() {
  state.scenarios = await api("/simulation/scenarios");
  if (!state.selectedScenarioId && state.scenarios.length) {
    state.selectedScenarioId = state.scenarios[0].id;
  }
}

async function refreshOverview() {
  state.overview = await api("/command/overview");
}

async function startSession() {
  if (!state.selectedScenarioId) return;
  setBusy(true);
  try {
    state.session = await api("/simulation/sessions", {
      method: "POST",
      body: { scenario_id: state.selectedScenarioId }
    });
    state.incident = null;
    await refreshOverview();
    toast(`Session ${state.session.id} started.`);
  } catch (error) {
    toast(error.message, "warn");
  } finally {
    setBusy(false);
    render();
  }
}

async function stepSession() {
  if (!state.session) return;
  setBusy(true, "step");
  try {
    state.pendingStepIndex = state.session.current_step_index;
    state.lastStepMessage = "Advancing simulation...";
    render();
    const result = await api(`/simulation/sessions/${state.session.id}/step`, { method: "POST" });
    state.session = result.session;
    state.incident = result.incident;
    state.lastStepMessage = result.message;
    await refreshOverview();
    toast(result.message, state.session.status === "paused" ? "warn" : "info");
  } catch (error) {
    toast(error.message, "warn");
  } finally {
    state.pendingStepIndex = null;
    setBusy(false);
    render();
  }
}

async function runSession() {
  if (!state.session) return;
  state.isAutoplaying = true;
  setBusy(true, "run");
  try {
    let result = null;
    for (let i = 0; i < 10; i += 1) {
      if (!state.session || ["completed", "failed", "paused"].includes(state.session.status)) break;
      state.pendingStepIndex = state.session.current_step_index;
      state.lastStepMessage = `Running ${state.session.steps[state.pendingStepIndex]?.label || "next step"}...`;
      render();
      result = await api(`/simulation/sessions/${state.session.id}/step`, { method: "POST" });
      state.session = result.session;
      state.incident = result.incident;
      state.lastStepMessage = result.message;
      await refreshOverview();
      render();
      if (state.session.status === "paused" || state.session.status === "completed" || state.session.status === "failed") break;
      await delay(900);
    }
    if (result) {
      toast(result.message, state.session.status === "paused" ? "warn" : "info");
    }
  } catch (error) {
    toast(error.message, "warn");
  } finally {
    state.pendingStepIndex = null;
    state.isAutoplaying = false;
    setBusy(false);
    render();
  }
}

async function resetSimulation() {
  setBusy(true);
  try {
    await api("/simulation/reset", { method: "POST" });
    state.session = null;
    state.incident = null;
    await Promise.all([refreshOverview(), loadScenarios(), refreshHealth()]);
    toast("Simulation state reset.");
  } catch (error) {
    toast(error.message, "warn");
  } finally {
    setBusy(false);
    render();
  }
}

function selectScenario(scenarioId) {
  state.selectedScenarioId = scenarioId;
  render();
}

function render() {
  document.body.classList.toggle("autoplaying", state.isAutoplaying);
  renderHealth();
  renderScenarios();
  renderSession();
  renderMetrics();
  renderMap();
  renderPatient();
  renderRecommendations();
  renderHospitals();
  renderFleet();
  renderEvents();
  updateControls();
}

function renderHealth() {
  const health = state.health;
  if (!health) return;
  els.llmStatus.textContent = health.lmstudio_available
    ? `LM Studio loaded: ${health.lmstudio_model}`
    : `LM Studio blocked: ${health.lmstudio_model}`;
  els.llmStatus.title = health.detail || "LM Studio ready";
  els.llmStatus.classList.toggle("ok", health.lmstudio_available);
  els.llmStatus.classList.toggle("warn", !health.lmstudio_available);
}

function renderScenarios() {
  els.scenarioCount.textContent = state.scenarios.length;
  els.scenarioList.innerHTML = "";
  for (const scenario of state.scenarios) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `scenario-card ${scenario.id === state.selectedScenarioId ? "active" : ""}`;
    button.innerHTML = `
      <strong>${escapeHtml(scenario.name)}</strong>
      <span>${escapeHtml(scenario.city)} | ${escapeHtml(scenario.pathway)} | ${escapeHtml(scenario.acuity_hint)}</span>
      <small>${escapeHtml(scenario.description)}</small>
    `;
    button.addEventListener("click", () => selectScenario(scenario.id));
    els.scenarioList.appendChild(button);
  }
}

function renderSession() {
  if (!state.session) {
    const scenario = selectedScenario();
    els.sessionTitle.textContent = scenario ? scenario.name : "No active session";
    els.sessionSubtitle.textContent = scenario ? scenario.description : "Choose a scenario to initialize the command flow.";
    els.sessionState.textContent = "Ready";
    els.stepper.innerHTML = "<div class='empty-state'>Start a session to see the flow progression.</div>";
    return;
  }
  els.sessionTitle.textContent = state.session.scenario_name;
  els.sessionSubtitle.textContent = `${state.session.id} | ${state.session.status}${state.session.last_error ? ` | ${state.session.last_error}` : ""}`;
  els.sessionState.textContent = state.session.status;
  els.sessionState.className = `session-state ${state.session.status}`;
  els.stepper.innerHTML = "";
  state.session.steps.forEach((step, index) => {
    const row = document.createElement("div");
    const syntheticRunning = state.pendingStepIndex === index;
    row.className = `step-row ${syntheticRunning ? "running" : step.status}`;
    row.innerHTML = `
      <div class="step-dot">${index + 1}</div>
      <div>
        <strong>${escapeHtml(step.label)}</strong>
        <span>${escapeHtml(syntheticRunning ? state.lastStepMessage || "Running..." : step.summary || step.status)}</span>
      </div>
    `;
    els.stepper.appendChild(row);
  });
}

function renderMetrics() {
  const overview = state.overview;
  if (!overview) return;
  const focus = mapFocus();
  const hospitals = localHospitalsForFocus(focus);
  const ambulances = localAmbulancesForFocus(focus);
  const incidents = (overview.active_incidents || []).filter((incident) => incident.scene_location?.city === focus.city);
  const scopedHospitals = hospitals.length ? hospitals : overview.hospitals;
  const scopedAmbulances = ambulances.length ? ambulances : overview.ambulances;
  const scopedIncidents = focus.city === "Ghana" ? overview.active_incidents : incidents;
  const active = scopedIncidents.length;
  const online = scopedAmbulances.filter((item) => item.status !== "offline").length;
  const beds = scopedHospitals.reduce((sum, hospital) => sum + hospital.capacity.er_beds_available, 0);
  const avgLoad = scopedHospitals.length
    ? scopedHospitals.reduce((sum, hospital) => sum + hospital.capacity.er_load, 0) / scopedHospitals.length
    : 0;
  const scopeLabel = focus.city === "Ghana" ? "National" : focus.city;
  els.metricIncidentsLabel.textContent = `${scopeLabel} Active Incidents`;
  els.metricAmbulancesLabel.textContent = `${scopeLabel} Ambulances Online`;
  els.metricBedsLabel.textContent = `${scopeLabel} Open ER Beds`;
  els.metricLoadLabel.textContent = `${scopeLabel} Average ER Load`;
  els.metricIncidents.textContent = active;
  els.metricAmbulances.textContent = online;
  els.metricBeds.textContent = beds;
  els.metricLoad.textContent = `${Math.round(avgLoad * 100)}%`;
  for (const metric of document.querySelectorAll(".metric")) {
    metric.classList.toggle("live", state.session?.status === "running" || state.isAutoplaying);
  }
}

function renderMap() {
  const overview = state.overview;
  if (!overview) return;
  const focus = mapFocus();
  const selectedHospital = selectedRouteHospital();
  const activeAmbulance = activeIncidentAmbulance();
  const phase = mapPhase(activeAmbulance);
  const isComplete = phase === "complete";
  const localHospitals = localHospitalsForFocus(focus);
  const localAmbulances = localAmbulancesForFocus(focus);
  const points = [
    ...localHospitals.map((hospital) => ({
      type: "hospital",
      label: hospital.name,
      sub: `${hospital.level} | ER ${hospital.capacity.er_beds_available} | ICU ${hospital.capacity.icu_beds_available}`,
      location: hospital.location,
      id: hospital.id,
      selected: hospital.id === selectedHospital?.id,
      labelMode: hospital.id === selectedHospital?.id ? "primary" : "minor"
    })),
    ...localAmbulances.map((ambulance) => ({
      type: "ambulance",
      label: ambulance.call_sign,
      sub: ambulance.status,
      location: ambulance.location,
      id: ambulance.id,
      status: ambulance.status,
      active: !isComplete && ambulance.current_incident_id && ambulance.current_incident_id === state.incident?.id,
      labelMode: ambulance.current_incident_id === state.incident?.id ? "primary" : "minor"
    }))
  ];
  if (state.incident) {
    points.push({
      type: "incident",
      label: "Incident scene",
      sub: `${state.incident.id} | ${state.incident.patient.chief_complaint}`,
      location: state.incident.scene_location,
      status: state.incident.status,
      active: !isComplete,
      labelMode: "primary"
    });
  }
  if (selectedHospital && selectedHospital.city !== focus.city) {
    points.push({
      type: "hospital",
      label: selectedHospital.name,
      sub: `${selectedHospital.city} transfer target`,
      location: selectedHospital.location,
      id: selectedHospital.id,
      selected: true,
      labelMode: "primary"
    });
  }
  const bounds = boundsFor(points.map((point) => point.location), focus);
  const plottedPoints = points.map((point) => ({
    ...point,
    pos: project(point.location, bounds)
  }));
  const routePlan = mapRoutePlan(bounds, activeAmbulance, selectedHospital, phase, isComplete);
  const routeSamples = routePlan ? sampleRoutePoints(bounds, routePlan.start, routePlan.end, routePlan.phase) : [];
  const overlayLayout = chooseOverlayLayout(plottedPoints, routeSamples, phase);
  els.map.innerHTML = "";
  els.map.className = `ghana-map phase-${phase}`;
  els.map.classList.toggle("active-sim", Boolean(state.session && state.session.status !== "ready" && !isComplete));
  els.map.classList.toggle("completed", isComplete);
  if (routePlan) {
    drawRoute(bounds, routePlan.start, routePlan.end, { phase: routePlan.phase, animated: routePlan.animated });
  }
  const overlay = drawFocusOverlay(focus, localHospitals, localAmbulances, selectedHospital, phase, activeAmbulance, overlayLayout.position);
  for (const point of plottedPoints) {
    const pos = point.pos;
    const marker = document.createElement("div");
    marker.className = `map-marker ${point.type} ${point.status || ""} ${point.selected ? "selected" : ""} ${point.active ? "active" : ""}`;
    marker.style.left = `${pos.x}%`;
    marker.style.top = `${pos.y}%`;
    marker.title = `${point.label} - ${point.sub}`;
    els.map.appendChild(marker);
  }

  const placedLabelRects = [];
  const labelOrder = [...plottedPoints].sort((a, b) => labelPriority(b) - labelPriority(a));
  for (const point of labelOrder) {
    const pos = point.pos;
    const labelLayout = chooseLabelLayout(point, placedLabelRects, overlayLayout.rect, plottedPoints);
    const label = document.createElement("div");
    label.className = `map-label anchor-${labelLayout.anchor} ${point.selected ? "selected" : ""} ${point.active ? "active" : ""} ${point.labelMode === "minor" ? "minor" : ""}`;
    label.style.left = `${pos.x}%`;
    label.style.top = `${pos.y}%`;
    label.innerHTML = `<strong>${escapeHtml(point.label)}</strong><span>${escapeHtml(point.sub)}</span>`;
    els.map.appendChild(label);
    placedLabelRects.push(labelLayout.rect);
  }
  if (isComplete && selectedHospital) {
    drawCompletionBadge(bounds, selectedHospital.location);
  }
  resolveOverlayPlacement(overlay);
  els.mapCaption.textContent = `${focus.city} focus | ${mapPhaseText(phase)} | ${localHospitals.length} hospitals | ${localAmbulances.length} ambulances`;
}

function renderPatient() {
  if (!state.incident) {
    els.patientStatus.textContent = "Awaiting pickup";
    els.patientCard.className = "detail-card empty-state";
    els.patientCard.textContent = "No incident selected.";
    return;
  }
  const patient = state.incident.patient;
  const vitals = patient.vitals;
  const triage = state.incident.triage_signal;
  els.patientStatus.textContent = state.incident.status;
  els.patientCard.className = "detail-card";
  els.patientCard.innerHTML = `
    <strong>${escapeHtml(patient.name || "Unidentified patient")}</strong>
    <p class="muted">${escapeHtml(patient.age)} years | ${escapeHtml(patient.sex)} | ${escapeHtml(state.incident.scene_location.address || state.incident.scene_location.city)}</p>
    <p>${escapeHtml(patient.chief_complaint)}</p>
    <div class="field-grid">
      ${field("HR", vitals.heart_rate)}
      ${field("BP", `${vitals.systolic_bp || "-"} / ${vitals.diastolic_bp || "-"}`)}
      ${field("SpO2", vitals.oxygen_saturation ? `${vitals.oxygen_saturation}%` : "-")}
      ${field("GCS", vitals.gcs || "-")}
    </div>
    ${triage ? triageBlock(triage) : "<p class='muted'>LLM triage pending.</p>"}
  `;
}

function renderRecommendations() {
  els.recommendations.innerHTML = "";
  const recommendations = state.incident?.recommendations || [];
  if (!recommendations.length) {
    els.recommendations.innerHTML = "<div class='empty-state'>Recommendations appear after AI triage and routing.</div>";
    return;
  }
  recommendations.slice(0, 5).forEach((rec, index) => {
    const card = document.createElement("div");
    card.className = `ranking-card ${rec.blocked ? "blocked" : ""}`;
    card.style.animationDelay = `${index * 80}ms`;
    card.innerHTML = `
      <div class="ranking-top">
        <div>
          <strong>${escapeHtml(rec.hospital_name)}</strong>
          <span>${escapeHtml(rec.city)} | ETA ${rec.route.eta_minutes} min | ${escapeHtml(rec.route.traffic_level)} traffic</span>
        </div>
        <div class="score">${rec.blocked ? "BLOCK" : Math.round(rec.score)}</div>
      </div>
      <div class="score-bars">
        ${scoreBar("Clinical", rec.breakdown.clinical_fit, 40)}
        ${scoreBar("Capacity", rec.breakdown.capacity_resources, 25)}
        ${scoreBar("ETA", rec.breakdown.eta, 20)}
        ${scoreBar("Load", rec.breakdown.er_load, 10)}
        ${scoreBar("Record", rec.breakdown.continuity, 5)}
      </div>
      <p class="muted">${escapeHtml(rec.reasons[0] || "")}</p>
    `;
    els.recommendations.appendChild(card);
  });
}

function renderHospitals() {
  const focus = mapFocus();
  const hospitals = localHospitalsForFocus(focus);
  const title = document.querySelector("#hospital-load")?.closest(".panel")?.querySelector(".panel-title span");
  if (title) {
    title.textContent = `${focus.city} capacity dashboard | ${hospitals.length} hospitals`;
  }
  els.hospitalLoad.innerHTML = "";
  if (!hospitals.length) {
    els.hospitalLoad.innerHTML = `<div class="empty-state">No hospitals configured for ${escapeHtml(focus.city)}.</div>`;
    return;
  }
  for (const hospital of hospitals) {
    const load = Math.round(hospital.capacity.er_load * 100);
    const card = document.createElement("div");
    card.className = "hospital-card";
    card.innerHTML = `
      <strong>${escapeHtml(hospital.name)}</strong>
      <span>${escapeHtml(hospital.city)} | ER ${hospital.capacity.er_beds_available} | ICU ${hospital.capacity.icu_beds_available}</span>
      <div class="load-track"><div class="load-fill ${loadClass(load)}" style="--load:${load}%"></div></div>
      <span>${load}% ER load</span>
    `;
    els.hospitalLoad.appendChild(card);
  }
}

function renderFleet() {
  const focus = mapFocus();
  const ambulances = localAmbulancesForFocus(focus);
  const activeAmbulance = activeIncidentAmbulance();
  const phase = mapPhase(activeAmbulance);
  const isComplete = phase === "complete";
  const title = document.querySelector("#fleet-list")?.closest(".panel")?.querySelector(".panel-title span");
  if (title) {
    title.textContent = `${focus.city} NAS telemetry | ${ambulances.length} ambulances`;
  }
  els.fleetList.innerHTML = "";
  if (!ambulances.length) {
    els.fleetList.innerHTML = `<div class="empty-state">No ambulances configured for ${escapeHtml(focus.city)}.</div>`;
    return;
  }
  for (const ambulance of ambulances) {
    const active = !isComplete && ambulance.current_incident_id === state.incident?.id;
    const cardPhase = active ? phase : ambulance.status;
    const card = document.createElement("div");
    card.className = `fleet-card ${cardPhase} ${active ? "active" : ""}`;
    card.innerHTML = `
      <div>
        <strong>${escapeHtml(ambulance.call_sign)}</strong>
        <span>${escapeHtml(ambulance.city)} | ${escapeHtml(ambulance.location.address || "GPS active")}</span>
        ${active ? `<em>${escapeHtml(fleetPhaseText(phase))}</em>` : ""}
      </div>
      <span class="status-chip ${escapeHtml(ambulance.status)}">${escapeHtml(ambulance.status)}</span>
    `;
    els.fleetList.appendChild(card);
  }
}

function renderEvents() {
  const events = state.overview?.recent_events || [];
  els.events.innerHTML = "";
  events.forEach((event, index) => {
    const row = document.createElement("div");
    row.className = "event-row";
    row.style.animationDelay = `${Math.min(index, 8) * 35}ms`;
    row.innerHTML = `
      <time>${new Date(event.timestamp).toLocaleTimeString()}</time>
      <code>${escapeHtml(event.event_type)}</code>
      <span>${escapeHtml(event.message)}</span>
    `;
    els.events.appendChild(row);
  });
}

function updateControls() {
  const hasScenario = Boolean(state.selectedScenarioId);
  const hasSession = Boolean(state.session);
  const terminal = ["completed", "failed"].includes(state.session?.status);
  els.start.disabled = state.isBusy || !hasScenario;
  els.step.disabled = state.isBusy || !hasSession || terminal;
  els.run.disabled = state.isBusy || !hasSession || terminal;
  els.run.textContent = state.isAutoplaying ? "Running" : "Run";
}

function selectedScenario() {
  return state.scenarios.find((scenario) => scenario.id === state.selectedScenarioId);
}

function mapFocus() {
  const scenario = selectedScenario();
  const city = state.incident?.scene_location?.city || scenario?.city || "Ghana";
  const scene = state.incident?.scene_location || scenario?.scene_location || null;
  return {
    city,
    scene,
    scenario
  };
}

function localHospitalsForFocus(focus) {
  return (state.overview?.hospitals || []).filter((hospital) => hospital.city === focus.city);
}

function localAmbulancesForFocus(focus) {
  return (state.overview?.ambulances || []).filter(
    (ambulance) => ambulance.city === focus.city || ambulance.current_incident_id === state.incident?.id
  );
}

function field(label, value) {
  return `<div class="field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "-")}</strong></div>`;
}

function triageBlock(triage) {
  const tags = [
    `<span class="tag ${escapeHtml(triage.acuity)}">${escapeHtml(triage.acuity)}</span>`,
    ...triage.care_pathways.map((item) => `<span class="tag">${escapeHtml(item)}</span>`),
    ...triage.required_capabilities.map((item) => `<span class="tag green">${escapeHtml(item)}</span>`)
  ].join("");
  return `
    <div class="tag-row">${tags}</div>
    <p class="muted">${escapeHtml(triage.summary)}</p>
    <p class="muted">${escapeHtml(triage.rationale)}</p>
  `;
}

function scoreBar(label, value, max) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return `
    <div class="bar-row">
      <span>${escapeHtml(label)}</span>
      <div class="bar-track"><div class="bar-fill" style="--pct:${pct}%"></div></div>
      <span>${Math.round(value)}</span>
    </div>
  `;
}

function selectedRouteHospital() {
  const hospitals = state.overview?.hospitals || [];
  const selectedId = state.incident?.selected_hospital_id;
  if (selectedId) {
    return hospitals.find((hospital) => hospital.id === selectedId);
  }
  const top = state.incident?.recommendations?.find((item) => !item.blocked);
  return top ? hospitals.find((hospital) => hospital.id === top.hospital_id) : null;
}

function activeIncidentAmbulance() {
  if (!state.incident) return null;
  return (state.overview?.ambulances || []).find((ambulance) => ambulance.id === state.incident.ambulance_id) || null;
}

function mapPhase(activeAmbulance) {
  if (state.incident?.status === "handover_complete" || state.session?.status === "completed") return "complete";
  if (!state.incident) return "idle";
  if (activeAmbulance?.status === "en_route" || ["destination_confirmed", "notified", "en_route"].includes(state.incident.status)) {
    return "en_route";
  }
  if (activeAmbulance?.status === "assigned" || ["created", "triaged", "recommended"].includes(state.incident.status)) {
    return "assigned";
  }
  return "idle";
}

function mapPhaseText(phase) {
  return {
    idle: "Awaiting dispatch",
    assigned: "NAS assigned to scene",
    en_route: "Ambulance en route",
    complete: "Digital handover done"
  }[phase] || "Awaiting dispatch";
}

function mapPhaseDescription(phase, activeAmbulance, selectedHospital) {
  if (phase === "assigned") {
    return `${activeAmbulance?.call_sign || "NAS unit"} is moving toward the patient scene.`;
  }
  if (phase === "en_route") {
    return `${activeAmbulance?.call_sign || "NAS unit"} is transporting the patient to ${selectedHospital?.name || "the receiving hospital"}.`;
  }
  if (phase === "complete") {
    return `The patient handover is complete at ${selectedHospital?.name || "the receiving hospital"}.`;
  }
  return "No active ambulance movement is underway.";
}

function fleetPhaseText(phase) {
  return {
    assigned: "Dispatched toward scene",
    en_route: "Transporting patient",
    complete: "Handover complete",
    idle: "Monitoring"
  }[phase] || "Monitoring";
}

function mapRoutePlan(bounds, activeAmbulance, selectedHospital, phase, isComplete) {
  if (state.incident && activeAmbulance && phase === "assigned") {
    return { start: activeAmbulance.location, end: state.incident.scene_location, phase: "assigned", animated: true };
  }
  if (state.incident && activeAmbulance && selectedHospital && phase === "en_route") {
    return { start: activeAmbulance.location, end: selectedHospital.location, phase: "en_route", animated: true };
  }
  if (state.incident && selectedHospital && isComplete) {
    return { start: state.incident.scene_location, end: selectedHospital.location, phase: "complete", animated: false };
  }
  return null;
}

function chooseOverlayLayout(points, routeSamples, phase) {
  const size = mapPixelSize();
  const marginX = pxToPct(12, size.width);
  const marginY = pxToPct(12, size.height);
  const width = pxToPct(Math.min(380, Math.max(260, size.width - 24)), size.width);
  const height = pxToPct(phase === "idle" ? 118 : 140, size.height);
  const candidates = [
    overlayCandidate("bottom-left", marginX, 100 - marginY - height, width, height, 0),
    overlayCandidate("top-left", marginX, marginY, width, height, 1),
    overlayCandidate("bottom-right", 100 - marginX - width, 100 - marginY - height, width, height, 2),
    overlayCandidate("top-right", 100 - marginX - width, marginY, width, height, 3)
  ];
  let best = candidates[0];
  for (const candidate of candidates) {
    const score = overlayCollisionScore(candidate.rect, points, routeSamples) + candidate.bias;
    if (score < best.score) {
      best = { ...candidate, score };
    }
  }
  return best;
}

function overlayCandidate(position, x, y, width, height, bias) {
  return {
    position,
    bias,
    score: Number.POSITIVE_INFINITY,
    rect: {
      x1: clamp(x, 0, 100 - width),
      y1: clamp(y, 0, 100 - height),
      x2: clamp(x, 0, 100 - width) + width,
      y2: clamp(y, 0, 100 - height) + height
    }
  };
}

function overlayCollisionScore(rect, points, routeSamples) {
  let score = 0;
  const expanded = expandRect(rect, 2.5);
  for (const point of points) {
    if (!point.pos) continue;
    const weight = labelPriority(point);
    const reserved = pointReservationRect(point);
    if (rectsOverlap(expanded, reserved)) score += weight >= 10 ? 900 : 80 + weight * 20;
    if (rectsOverlap(rect, reserved)) score += weight >= 10 ? 2200 : 160 + weight * 38;
    if (containsPoint(expanded, point.pos)) score += weight >= 10 ? 800 : 20 + weight * 9;
    if (containsPoint(rect, point.pos)) score += weight >= 10 ? 1800 : 35 + weight * 16;
  }
  for (const sample of routeSamples) {
    if (containsPoint(expanded, sample)) score += 160;
    if (containsPoint(rect, sample)) score += 360;
  }
  return score;
}

function pointReservationRect(point) {
  const activePadX = point.active || point.type === "incident" ? 16 : 5;
  const activePadY = point.active || point.type === "incident" ? 12 : 5;
  const labelReach = point.labelMode === "minor" ? 18 : 30;
  return {
    x1: point.pos.x - activePadX,
    y1: point.pos.y - activePadY,
    x2: point.pos.x + activePadX + labelReach,
    y2: point.pos.y + activePadY
  };
}

function chooseLabelLayout(point, placedRects, overlayRect, allPoints) {
  const size = mapPixelSize();
  const dimensions = labelDimensions(point, size);
  const candidates = ["right", "left", "top", "bottom", "upper-right", "upper-left", "lower-right", "lower-left"];
  let best = null;
  for (const anchor of candidates) {
    const rect = labelRect(point.pos, dimensions, anchor);
    const score = labelCollisionScore(rect, point, anchor, placedRects, overlayRect, allPoints);
    if (!best || score < best.score) {
      best = { anchor, rect, score };
    }
  }
  return best;
}

function labelDimensions(point, size) {
  const labelWidth = point.labelMode === "minor" ? 134 : 210;
  const labelHeight = point.labelMode === "minor" ? 28 : 48;
  return {
    width: pxToPct(labelWidth, size.width),
    height: pxToPct(labelHeight, size.height),
    gapX: pxToPct(10, size.width),
    gapY: pxToPct(10, size.height)
  };
}

function labelRect(pos, dimensions, anchor) {
  const halfW = dimensions.width / 2;
  const halfH = dimensions.height / 2;
  const layouts = {
    right: { x1: pos.x + dimensions.gapX, y1: pos.y - halfH },
    left: { x1: pos.x - dimensions.gapX - dimensions.width, y1: pos.y - halfH },
    top: { x1: pos.x - halfW, y1: pos.y - dimensions.gapY - dimensions.height },
    bottom: { x1: pos.x - halfW, y1: pos.y + dimensions.gapY },
    "upper-right": { x1: pos.x + dimensions.gapX, y1: pos.y - dimensions.gapY - dimensions.height },
    "upper-left": { x1: pos.x - dimensions.gapX - dimensions.width, y1: pos.y - dimensions.gapY - dimensions.height },
    "lower-right": { x1: pos.x + dimensions.gapX, y1: pos.y + dimensions.gapY },
    "lower-left": { x1: pos.x - dimensions.gapX - dimensions.width, y1: pos.y + dimensions.gapY }
  };
  const layout = layouts[anchor];
  return {
    x1: layout.x1,
    y1: layout.y1,
    x2: layout.x1 + dimensions.width,
    y2: layout.y1 + dimensions.height
  };
}

function labelCollisionScore(rect, point, anchor, placedRects, overlayRect, allPoints) {
  let score = 0;
  if (rect.x1 < 1 || rect.y1 < 1 || rect.x2 > 99 || rect.y2 > 99) score += 200;
  if (rectsOverlap(rect, overlayRect)) score += point.active || point.selected ? 900 : 600;
  for (const placed of placedRects) {
    if (rectsOverlap(rect, expandRect(placed, 0.8))) score += 80;
  }
  for (const other of allPoints) {
    if (other === point || !other.pos) continue;
    const markerRect = { x1: other.pos.x - 2.3, y1: other.pos.y - 2.3, x2: other.pos.x + 2.3, y2: other.pos.y + 2.3 };
    if (rectsOverlap(rect, markerRect)) score += 35;
  }
  if (point.active && ["right", "lower-right", "upper-right"].includes(anchor)) score -= 8;
  if (point.selected && ["right", "upper-right", "lower-right"].includes(anchor)) score -= 5;
  if (point.labelMode === "minor" && ["top", "bottom"].includes(anchor)) score += 8;
  return score;
}

function sampleRoutePoints(bounds, start, end, phase) {
  const a = project(start, bounds);
  const b = project(end, bounds);
  const midX = (a.x + b.x) / 2;
  const midY = (a.y + b.y) / 2 + (phase === "assigned" ? 7 : -8);
  const samples = [];
  for (let i = 0; i <= 10; i += 1) {
    const t = i / 10;
    const inv = 1 - t;
    samples.push({
      x: inv * inv * a.x + 2 * inv * t * midX + t * t * b.x,
      y: inv * inv * a.y + 2 * inv * t * midY + t * t * b.y
    });
  }
  return samples;
}

function labelPriority(point) {
  if (point.type === "incident") return 12;
  if (point.active) return 11;
  if (point.selected) return 10;
  if (point.labelMode === "primary") return 7;
  return 2;
}

function drawRoute(bounds, start, end, options = {}) {
  const phase = options.phase || "en_route";
  const animated = options.animated !== false;
  const a = project(start, bounds);
  const b = project(end, bounds);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", `route-layer ${phase} ${animated ? "animated" : "static"}`);
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("preserveAspectRatio", "none");

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  const midX = (a.x + b.x) / 2;
  const midY = (a.y + b.y) / 2 + (phase === "assigned" ? 7 : -8);
  path.setAttribute("d", `M ${a.x} ${a.y} Q ${midX} ${midY} ${b.x} ${b.y}`);
  path.setAttribute("class", `route-path ${phase}`);
  svg.appendChild(path);

  const glow = document.createElementNS("http://www.w3.org/2000/svg", "path");
  glow.setAttribute("d", path.getAttribute("d"));
  glow.setAttribute("class", `route-glow ${phase}`);
  svg.appendChild(glow);

  els.map.appendChild(svg);

  if (!animated) return;
  const runner = document.createElement("div");
  runner.className = `route-runner ${phase}`;
  runner.style.setProperty("--start-x", `${a.x}%`);
  runner.style.setProperty("--start-y", `${a.y}%`);
  runner.style.setProperty("--end-x", `${b.x}%`);
  runner.style.setProperty("--end-y", `${b.y}%`);
  els.map.appendChild(runner);
}

function drawCompletionBadge(bounds, location) {
  const pos = project(location, bounds);
  const badge = document.createElement("div");
  badge.className = "completion-badge";
  badge.style.left = `${pos.x}%`;
  badge.style.top = `${pos.y}%`;
  badge.textContent = "Handover complete";
  els.map.appendChild(badge);
}

function boundsFor(locations, focus = null) {
  const safeLocations = locations.length ? locations : [focus?.scene].filter(Boolean);
  const lats = safeLocations.map((loc) => loc.latitude);
  const lons = safeLocations.map((loc) => loc.longitude);
  const latSpan = Math.max(Math.max(...lats) - Math.min(...lats), 0.045);
  const lonSpan = Math.max(Math.max(...lons) - Math.min(...lons), 0.045);
  const latPad = Math.max(latSpan * 0.32, 0.018);
  const lonPad = Math.max(lonSpan * 0.32, 0.018);
  return {
    minLat: Math.min(...lats) - latPad,
    maxLat: Math.max(...lats) + latPad,
    minLon: Math.min(...lons) - lonPad,
    maxLon: Math.max(...lons) + lonPad
  };
}

function project(location, bounds) {
  const x = ((location.longitude - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * 76 + 12;
  const y = (1 - ((location.latitude - bounds.minLat) / (bounds.maxLat - bounds.minLat))) * 76 + 12;
  return { x, y };
}

function mapPixelSize() {
  const rect = els.map.getBoundingClientRect();
  return {
    width: Math.max(rect.width || 0, 360),
    height: Math.max(rect.height || 0, 320)
  };
}

function pxToPct(value, total) {
  return (value / Math.max(total, 1)) * 100;
}

function rectsOverlap(a, b) {
  return a.x1 < b.x2 && a.x2 > b.x1 && a.y1 < b.y2 && a.y2 > b.y1;
}

function containsPoint(rect, point) {
  return point.x >= rect.x1 && point.x <= rect.x2 && point.y >= rect.y1 && point.y <= rect.y2;
}

function expandRect(rect, amount) {
  return {
    x1: rect.x1 - amount,
    y1: rect.y1 - amount,
    x2: rect.x2 + amount,
    y2: rect.y2 + amount
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function drawFocusOverlay(focus, localHospitals, localAmbulances, selectedHospital, phase, activeAmbulance, position) {
  const overlay = document.createElement("div");
  overlay.className = `map-focus-overlay phase-${phase} ${position}`;
  overlay.innerHTML = `
    <div>
      <span>Focused Zone</span>
      <strong>${escapeHtml(focus.city)}</strong>
    </div>
    <div>
      <span>Flow State</span>
      <strong>${escapeHtml(mapPhaseText(phase))}</strong>
    </div>
    <div>
      <span>NAS Unit</span>
      <strong>${escapeHtml(activeAmbulance?.call_sign || "awaiting assignment")}</strong>
    </div>
    <div>
      <span>Receiving Target</span>
      <strong>${escapeHtml(selectedHospital?.name || "pending routing")}</strong>
    </div>
    <div class="map-legend">
      <span><i class="legend-dot incident"></i>Incident</span>
      <span><i class="legend-dot ambulance"></i>Ambulance</span>
      <span><i class="legend-dot hospital"></i>Hospital</span>
    </div>
    <p>${escapeHtml(mapPhaseDescription(phase, activeAmbulance, selectedHospital))} ${localHospitals.length} local hospitals and ${localAmbulances.length} local ambulances are shown.</p>
  `;
  els.map.appendChild(overlay);
  return overlay;
}

function resolveOverlayPlacement(overlay) {
  if (!overlay) return;
  const positions = ["top-left", "top-right", "bottom-left", "bottom-right"];
  let bestPosition = positions[0];
  let bestScore = Number.POSITIVE_INFINITY;
  for (const position of positions) {
    setOverlayPositionClass(overlay, position);
    const score = domOverlayCollisionScore(overlay, position);
    if (score < bestScore) {
      bestScore = score;
      bestPosition = position;
    }
  }
  setOverlayPositionClass(overlay, bestPosition);
}

function setOverlayPositionClass(overlay, position) {
  overlay.classList.remove("top-left", "top-right", "bottom-left", "bottom-right");
  overlay.classList.add(position);
}

function domOverlayCollisionScore(overlay, position) {
  const overlayRect = overlay.getBoundingClientRect();
  const importantTargets = els.map.querySelectorAll(
    ".map-label.active, .map-marker.active, .map-label.selected, .map-marker.selected, .map-marker.incident, .route-runner"
  );
  const secondaryTargets = els.map.querySelectorAll(".map-label, .map-marker");
  let score = overlayCornerBias(position);
  for (const target of importantTargets) {
    score += rectOverlapArea(overlayRect, target.getBoundingClientRect()) * 12;
  }
  for (const target of secondaryTargets) {
    score += rectOverlapArea(overlayRect, target.getBoundingClientRect()) * 1.2;
  }
  return score;
}

function overlayCornerBias(position) {
  return {
    "top-left": 0,
    "top-right": 8,
    "bottom-right": 16,
    "bottom-left": 24
  }[position] || 0;
}

function rectOverlapArea(a, b) {
  const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
  const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  return width * height;
}

function loadClass(load) {
  if (load > 70) return "high";
  if (load > 45) return "medium";
  return "low";
}

function setBusy(isBusy, mode = null) {
  state.isBusy = isBusy;
  document.body.classList.toggle("busy", isBusy);
  document.body.dataset.busyMode = mode || "";
  els.start.disabled = isBusy;
  els.step.disabled = isBusy;
  els.run.disabled = isBusy;
  els.reset.disabled = isBusy;
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || `Request failed with ${response.status}`);
  }
  return body;
}

function toast(message, type = "info") {
  const note = document.createElement("div");
  note.className = `toast ${type}`;
  note.textContent = message;
  els.toastStack.appendChild(note);
  window.setTimeout(() => note.remove(), 5200);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[char]));
}
