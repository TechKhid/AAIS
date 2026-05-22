// AAIS Command & Intelligence Simulator Frontend logic
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

// DOM References
const els = {
  scenarioList: document.querySelector("#scenario-list"),
  scenarioCount: document.querySelector("#scenario-count"),
  llmProviderCard: document.querySelector("#llm-provider-card"),
  llmProviderLabel: document.querySelector("#llm-provider-label"),
  llmProviderDetail: document.querySelector("#llm-provider-detail"),
  llmBriefingProvider: document.querySelector("#llm-briefing-provider"),
  llmFlowProvider: document.querySelector("#llm-flow-provider"),
  llmStatus: document.querySelector("#llm-status"),
  start: document.querySelector("#start-session"),
  step: document.querySelector("#step-session"),
  run: document.querySelector("#run-session"),
  reset: document.querySelector("#reset-sim"),
  themeToggle: document.querySelector("#theme-toggle"),
  
  // Navigation Tabs
  tabOps: document.querySelector("#tab-operations"),
  tabRoadmap: document.querySelector("#tab-roadmap"),
  workspaceOps: document.querySelector("#workspace-operations"),
  workspaceRoadmap: document.querySelector("#workspace-roadmap"),
  briefingOverlay: document.querySelector("#briefing-overlay"),
  startBriefingDemoBtn: document.querySelector("#start-briefing-demo"),

  // Narration Deck Elements
  narratorText: document.querySelector("#narrator-text"),
  narratorImpact: document.querySelector("#narrator-impact"),
  narrationStepBadge: document.querySelector("#narration-step-badge"),
  narrationStepTitle: document.querySelector("#narration-step-title"),
  autoplayToggle: document.querySelector("#autoplay-toggle"),
  speedSlider: document.querySelector("#autoplay-speed-slider"),
  speedLabel: document.querySelector("#speed-label"),

  // Data Flow Strip Nodes
  nodes: {
    dispatch: document.querySelector("#node-dispatch"),
    ambulance: document.querySelector("#node-ambulance"),
    triage: document.querySelector("#node-triage"),
    routing: document.querySelector("#node-routing"),
    prealert: document.querySelector("#node-prealert"),
    transport: document.querySelector("#node-transport"),
    handover: document.querySelector("#node-handover")
  },

  // Telemetry & Panels
  metricIncidents: document.querySelector("#metric-incidents"),
  metricAmbulances: document.querySelector("#metric-ambulances"),
  metricBeds: document.querySelector("#metric-beds"),
  metricLoad: document.querySelector("#metric-load"),
  metricIncidentsLabel: document.querySelector("#metric-incidents-label"),
  metricAmbulancesLabel: document.querySelector("#metric-ambulances-label"),
  metricBedsLabel: document.querySelector("#metric-beds-label"),
  metricLoadLabel: document.querySelector("#metric-load-label"),

  // Workspace lists & cards
  mapElement: document.querySelector("#map"),
  mapCaption: document.querySelector("#map-caption"),
  btnRecenterMap: document.querySelector("#btn-recenter-map"),
  hospitalLoad: document.querySelector("#hospital-load"),
  fleetList: document.querySelector("#fleet-list"),
  patientCard: document.querySelector("#patient-card"),
  patientStatus: document.querySelector("#patient-status"),
  recommendations: document.querySelector("#recommendations"),
  routingExplainerPanel: document.querySelector("#routing-explainer-panel"),
  toggleRoutingExplainer: document.querySelector("#toggle-routing-explainer"),

  // Alerts & EHR Documents
  preAlertDisplayCard: document.querySelector("#pre-alert-display-card"),
  preAlertTextContent: document.querySelector("#pre-alert-text-content"),
  preAlertStatusBadge: document.querySelector("#pre-alert-status-badge"),
  handoverDisplayCard: document.querySelector("#handover-display-card"),
  handoverTextContent: document.querySelector("#handover-text-content"),
  handoverStatusBadge: document.querySelector("#handover-status-badge"),
  events: document.querySelector("#events"),
  toastStack: document.querySelector("#toast-stack")
};

// Global Autoplay Timer Reference
let autoplayTimer = null;

// Initialize Leaflet GIS layers
const leafletAvailable = typeof L !== 'undefined';
let leafletMap = null;
let markersLayerGroup = null;
let routesLayerGroup = null;

// Attach Core Event Handlers
els.start.addEventListener("click", startSession);
els.step.addEventListener("click", stepSession);
els.run.addEventListener("click", runSession);
els.reset.addEventListener("click", resetSimulation);

if (els.themeToggle) {
  els.themeToggle.addEventListener("click", toggleTheme);
}

if (els.startBriefingDemoBtn) {
  els.startBriefingDemoBtn.addEventListener("click", () => {
    els.briefingOverlay.classList.add("dismissed");
  });
}

if (els.tabOps && els.tabRoadmap) {
  els.tabOps.addEventListener("click", () => switchTab("ops"));
  els.tabRoadmap.addEventListener("click", () => switchTab("roadmap"));
}

if (els.toggleRoutingExplainer) {
  els.toggleRoutingExplainer.addEventListener("click", () => {
    els.routingExplainerPanel.classList.toggle("hidden");
    els.toggleRoutingExplainer.textContent = els.routingExplainerPanel.classList.contains("hidden")
      ? "Explain Weights"
      : "Hide Explainer";
  });
}

if (els.speedSlider) {
  els.speedSlider.addEventListener("input", (e) => {
    const ms = parseInt(e.target.value);
    els.speedLabel.textContent = `${(ms / 1000).toFixed(1)}s`;
    syncPresetHighlight(ms);
  });
}

// Speed preset buttons — one-click demo mode switching
document.querySelectorAll(".speed-preset-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const ms = parseInt(btn.dataset.speed);
    if (els.speedSlider) els.speedSlider.value = ms;
    if (els.speedLabel) els.speedLabel.textContent = `${(ms / 1000).toFixed(1)}s`;
    syncPresetHighlight(ms);
  });
});

function syncPresetHighlight(ms) {
  document.querySelectorAll(".speed-preset-btn").forEach(b => b.classList.remove("active"));
  if (ms <= 750)       document.getElementById("speed-instant")?.classList.add("active");
  else if (ms <= 3000) document.getElementById("speed-fast")?.classList.add("active");
  else                 document.getElementById("speed-detailed")?.classList.add("active");
}

if (els.btnRecenterMap) {
  els.btnRecenterMap.addEventListener("click", () => {
    recenterMap();
  });
}

// Click to skip typewriter animations on bubbles
const narratorBubble = document.querySelector(".narrator-bubble");
const impactBubble = document.querySelector(".narrator-impact-bubble");
if (narratorBubble) {
  narratorBubble.style.cursor = "pointer";
  narratorBubble.title = "Click to skip typing effect";
  narratorBubble.addEventListener("click", () => skipTypewriter("narrator-text"));
}
if (impactBubble) {
  impactBubble.style.cursor = "pointer";
  impactBubble.title = "Click to skip typing effect";
  impactBubble.addEventListener("click", () => skipTypewriter("narrator-impact"));
}

// Bootstrap Simulator app
boot();
setInterval(refreshPassiveState, 7000);

async function boot() {
  await Promise.all([refreshHealth(), loadScenarios(), refreshOverview()]);
  
  // Set default active scenario
  if (state.scenarios.length > 0) {
    selectScenario(state.scenarios[0].id);
  }
  
  if (leafletAvailable) {
    initLeafletMap();
  }
  
  render();
}

// Dynamic Theme Toggling
function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
  const newTheme = currentTheme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", newTheme);
  toast(`Theme toggled to ${newTheme} mode.`);
  
  // Re-render Leaflet Map elements as tile layer class changes
  if (leafletMap) {
    setTimeout(recenterMap, 200);
  }
}

// Navigation Swapper
function switchTab(tabId) {
  if (tabId === "ops") {
    els.tabOps.classList.add("active");
    els.tabRoadmap.classList.remove("active");
    els.workspaceOps.classList.remove("hidden");
    els.workspaceRoadmap.classList.add("hidden");
  } else {
    els.tabRoadmap.classList.add("active");
    els.tabOps.classList.remove("active");
    els.workspaceRoadmap.classList.remove("hidden");
    els.workspaceOps.classList.add("hidden");
  }
}

// Recenter GIS telemetry map
function recenterMap() {
  if (!leafletMap) return;
  
  const focus = mapFocus();
  const hospitals = localHospitalsForFocus(focus);
  const ambulances = localAmbulancesForFocus(focus);
  
  const activeCoords = [];
  if (state.incident) {
    activeCoords.push([state.incident.scene_location.latitude, state.incident.scene_location.longitude]);
  }
  const activeAmb = activeIncidentAmbulance();
  if (activeAmb) {
    activeCoords.push([activeAmb.location.latitude, activeAmb.location.longitude]);
  }
  const selectedHosp = selectedRouteHospital();
  if (selectedHosp) {
    activeCoords.push([selectedHosp.location.latitude, selectedHosp.location.longitude]);
  }

  if (activeCoords.length > 0) {
    leafletMap.fitBounds(activeCoords, { padding: [50, 50], maxZoom: 13, animate: true });
  } else if (hospitals.length > 0 || ambulances.length > 0) {
    const regionalCoords = [];
    hospitals.forEach(h => regionalCoords.push([h.location.latitude, h.location.longitude]));
    ambulances.forEach(a => regionalCoords.push([a.location.latitude, a.location.longitude]));
    leafletMap.fitBounds(regionalCoords, { padding: [40, 40], maxZoom: 12, animate: true });
  } else {
    leafletMap.setView([7.9465, -1.0232], 7);
  }
}

// Leaflet Map Initialization
function initLeafletMap() {
  if (leafletMap) return;
  
  try {
    leafletMap = L.map('map', {
      zoomControl: true,
      scrollWheelZoom: false
    }).setView([7.9465, -1.0232], 7); // Centered on central Ghana region
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(leafletMap);
    
    markersLayerGroup = L.layerGroup().addTo(leafletMap);
    routesLayerGroup = L.layerGroup().addTo(leafletMap);
  } catch (error) {
    console.error("Leaflet initialization failed", error);
  }
}

// Passive periodic fetch
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
  try {
    state.health = await api("/health");
  } catch (error) {
    state.health = null;
  }
}

async function loadScenarios() {
  try {
    state.scenarios = await api("/simulation/scenarios");
    if (!state.selectedScenarioId && state.scenarios.length) {
      state.selectedScenarioId = state.scenarios[0].id;
    }
  } catch (error) {
    toast(`Failed to load scenarios: ${error.message}`, "warn");
  }
}

async function refreshOverview() {
  try {
    state.overview = await api("/command/overview");
  } catch (error) {
    state.overview = null;
  }
}

async function startSession() {
  if (!state.selectedScenarioId) return;
  setBusy(true);
  
  // Clear any existing autoplay timers
  if (autoplayTimer) {
    clearTimeout(autoplayTimer);
    autoplayTimer = null;
  }
  state.isAutoplaying = false;
  
  try {
    state.session = await api("/simulation/sessions", {
      method: "POST",
      body: { scenario_id: state.selectedScenarioId }
    });
    state.incident = null;
    await refreshOverview();
    toast(`Session initialized for incident: ${state.session.scenario_name}`);
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
    state.lastStepMessage = "Advancing clinical flow...";
    render();
    
    const result = await api(`/simulation/sessions/${state.session.id}/step`, { method: "POST" });
    state.session = result.session;
    state.incident = result.incident;
    state.lastStepMessage = result.message;
    
    await refreshOverview();
    toast(result.message, state.session.status === "paused" ? "warn" : "info");
  } catch (error) {
    toast(error.message, "warn");
    if (autoplayTimer) {
      clearTimeout(autoplayTimer);
      autoplayTimer = null;
    }
    state.isAutoplaying = false;
  } finally {
    state.pendingStepIndex = null;
    setBusy(false);
    render();
  }
}

async function runSession() {
  if (!state.session) return;
  
  if (state.isAutoplaying) {
    // User requested to pause auto-run
    if (autoplayTimer) {
      clearTimeout(autoplayTimer);
      autoplayTimer = null;
    }
    state.isAutoplaying = false;
    toast("Simulation auto-play paused.");
    render();
    return;
  }
  
  state.isAutoplaying = true;
  toast("Auto-Play engaged. Stepping through 7 operational pipelines...");
  
  await stepAndLoop();
}

async function stepAndLoop() {
  if (!state.isAutoplaying || !state.session) return;
  if (["completed", "failed", "paused"].includes(state.session.status)) {
    state.isAutoplaying = false;
    render();
    return;
  }
  
  await stepSession();
  
  if (state.session && !["completed", "failed", "paused"].includes(state.session.status) && state.isAutoplaying) {
    const pauseMs = parseInt(els.speedSlider.value) || 4000;
    autoplayTimer = setTimeout(stepAndLoop, pauseMs);
  } else {
    state.isAutoplaying = false;
    render();
  }
}

async function resetSimulation() {
  setBusy(true);
  
  if (autoplayTimer) {
    clearTimeout(autoplayTimer);
    autoplayTimer = null;
  }
  state.isAutoplaying = false;
  
  try {
    await api("/simulation/reset", { method: "POST" });
    state.session = null;
    state.incident = null;
    await Promise.all([refreshOverview(), loadScenarios(), refreshHealth()]);
    
    // Smooth scroll back up and show briefing overlay
    if (els.briefingOverlay) {
      els.briefingOverlay.classList.remove("dismissed");
    }
    switchTab("ops");
    
    toast("Command system reset successfully.");
  } catch (error) {
    toast(error.message, "warn");
  } finally {
    setBusy(false);
    render();
  }
}

function selectScenario(scenarioId) {
  state.selectedScenarioId = scenarioId;
  
  if (autoplayTimer) {
    clearTimeout(autoplayTimer);
    autoplayTimer = null;
  }
  state.isAutoplaying = false;
  state.session = null;
  state.incident = null;
  
  render();
  recenterMap();
}

// Master Render Method
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
  if (!health) {
    setProviderDisplay({
      available: false,
      providerKey: "unknown",
      provider: "LLM Provider",
      model: "Backend health unavailable",
      statusText: "OFFLINE",
      detail: "The API health check did not return provider state."
    });
    return;
  }
  const available = health.llm_available ?? health.lmstudio_available;
  const model = health.llm_model || health.lmstudio_model;
  const providerKey = health.llm_provider || "lmstudio";
  const provider = providerLabel(providerKey);
  const detail = providerDetail(providerKey, model, available, health.detail);
  setProviderDisplay({
    available,
    providerKey,
    provider,
    model,
    statusText: available ? "ACTIVE" : "BLOCKED",
    detail,
    title: [
      `Provider: ${provider}`,
      `Model: ${model}`,
      `Endpoint: ${health.llm_base_url || health.lmstudio_base_url || "unknown"}`,
      health.detail ? `Detail: ${health.detail}` : null
    ].filter(Boolean).join("\n")
  });
}

function setProviderDisplay({ available, providerKey, provider, model, statusText, detail, title }) {
  const shortModel = shortModelName(model);
  if (els.llmProviderLabel) els.llmProviderLabel.textContent = provider;
  if (els.llmStatus) {
    els.llmStatus.textContent = statusText;
    els.llmStatus.className = `model-status ${available ? "ok" : "warn"}`;
  }
  if (els.llmProviderDetail) {
    els.llmProviderDetail.textContent = detail || shortModel;
  }
  if (els.llmProviderCard) {
    els.llmProviderCard.classList.toggle("ok", available);
    els.llmProviderCard.classList.toggle("warn", !available);
    els.llmProviderCard.classList.toggle("provider-nim", providerKey === "nvidia_nim");
    els.llmProviderCard.classList.toggle("provider-lmstudio", providerKey === "lmstudio");
    els.llmProviderCard.title = title || `${provider}: ${model}`;
  }
  if (els.llmBriefingProvider) {
    els.llmBriefingProvider.textContent = `${provider} (${shortModel})`;
  }
  if (els.llmFlowProvider) {
    els.llmFlowProvider.textContent = providerKey === "nvidia_nim" ? "NVIDIA NIM" : provider;
  }
}

function providerLabel(provider) {
  return {
    lmstudio: "LM Studio",
    nvidia_nim: "NVIDIA NIM"
  }[provider] || provider;
}

function providerDetail(provider, model, available, detail) {
  const shortModel = shortModelName(model);
  if (provider === "nvidia_nim") {
    return available
      ? `${shortModel} | NVIDIA NIM API | LM Studio not required`
      : `${shortModel} | NVIDIA NIM blocked${detail ? ` | ${detail}` : ""}`;
  }
  return available
    ? `${shortModel} | Local LM Studio runtime`
    : `${shortModel} | LM Studio not ready${detail ? ` | ${detail}` : ""}`;
}

function shortModelName(model) {
  if (!model) return "No model configured";
  return String(model).split("/").pop();
}

function activeProviderName() {
  return providerLabel(state.health?.llm_provider || "lmstudio");
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
      <span>${escapeHtml(scenario.city)} | ${escapeHtml(scenario.pathway)} | ${escapeHtml(scenario.acuity_hint.toUpperCase())}</span>
      <small>${escapeHtml(scenario.description)}</small>
    `;
    button.addEventListener("click", () => selectScenario(scenario.id));
    els.scenarioList.appendChild(button);
  }
}

function renderSession() {
  if (!state.session) {
    const scenario = selectedScenario();
    els.narrationStepBadge.textContent = "STEP 0/7";
    els.narrationStepTitle.textContent = "Initialize Incident Pipeline";
    
    // Typewriter narrative intro
    els.narratorText.textContent = scenario 
      ? `You have loaded "${scenario.name}". Click "Initialize Incident" to dispatch NAS dispatcher telemetry. This incident takes place in ${scenario.city}.`
      : "Select an incident scenario from the left panel to begin the walkthrough.";
    
    els.narratorImpact.textContent = "Emergency clinical dispatching platforms require seamless integration of ambulance state and ER resources. Start the walk to see this live.";
    
    updateDataFlowNodes(-1);
    
    // Clear Alerts & Handover panels
    clearDocumentDisplayCards();
    return;
  }

  const currentStepIdx = state.session.current_step_index;
  const totalSteps = state.session.steps.length;
  
  // Update step indicators
  els.narrationStepBadge.textContent = `STAGE ${currentStepIdx + 1}/${totalSteps}`;
  
  const currentStep = state.session.steps[currentStepIdx] || state.session.steps[totalSteps - 1];
  els.narrationStepTitle.textContent = currentStep ? currentStep.label : "Active simulation";

  // Trigger Typewriter Animation for narration
  const stepNarrationObj = getNarrationContent(currentStep?.id || "dispatch");
  
  if (state.pendingStepIndex !== null) {
    els.narratorText.textContent = state.lastStepMessage || "Processing stage metrics...";
  } else {
    // Only typewrite if this step just loaded to prevent redraw typewriter flashes during passive polling
    const uniqueTextMark = `step-${currentStepIdx}-${state.session.id}`;
    if (els.narratorText.dataset.stepMark !== uniqueTextMark) {
      els.narratorText.dataset.stepMark = uniqueTextMark;
      
      // Calculate a dynamic typewriter speed matching the autoplay speed slider.
      // Under 750ms we render text instantly (0ms speed), otherwise scale speed down for fast pacing.
      const sliderVal = parseInt(els.speedSlider?.value) || 2000;
      const computedSpeed = sliderVal <= 750 ? 0 : Math.max(1, Math.min(12, Math.floor(sliderVal / 250)));
      
      typewriteText("narrator-text", stepNarrationObj.text, computedSpeed);
      typewriteText("narrator-impact", stepNarrationObj.impact, computedSpeed);
    }
  }

  // Update Data Flow Strip nodes
  updateDataFlowNodes(currentStepIdx);

  // Sync Alerting and Digital Handover Documents
  syncDocuments(currentStepIdx);
}

// Clear alert/handover templates
function clearDocumentDisplayCards() {
  els.preAlertDisplayCard.className = "document-display-card alert-inactive";
  els.preAlertStatusBadge.textContent = "NOT SENT";
  els.preAlertTextContent.classList.add("hidden");
  els.preAlertTextContent.innerHTML = "";
  els.preAlertDisplayCard.querySelector(".placeholder-text").classList.remove("hidden");

  els.handoverDisplayCard.className = "document-display-card handover-inactive";
  els.handoverStatusBadge.textContent = "AWAITING HANDOVER";
  els.handoverTextContent.classList.add("hidden");
  els.handoverTextContent.innerHTML = "";
  els.handoverDisplayCard.querySelector(".placeholder-text").classList.remove("hidden");
}

// Document Synchronization (Pre-alert on Step 5, Handover SBAR on Step 7)
function syncDocuments(currentStepIdx) {
  // Step 5 index in Python catalog is `prealert` (typically index 4 in zero-indexed list)
  const isPreAlertSent = state.incident?.status === "notified" || state.incident?.status === "en_route" || state.incident?.status === "handover_complete" || currentStepIdx >= 4;
  const isHandoverSent = state.incident?.status === "handover_complete" || state.session?.status === "completed" || currentStepIdx >= 6;

  if (isPreAlertSent && state.incident?.notification) {
    els.preAlertDisplayCard.className = "document-display-card alert-active";
    els.preAlertStatusBadge.textContent = "DELIVERED SENT";
    els.preAlertDisplayCard.querySelector(".placeholder-text").classList.add("hidden");
    els.preAlertTextContent.classList.remove("hidden");
    els.preAlertTextContent.innerHTML = `
      <div style="font-weight: 700; margin-bottom: 6px; border-bottom:1px dashed var(--blue); padding-bottom:4px;">
        API DISPATCH ROUTE CHANNEL: ${escapeHtml(state.incident.notification.channel.toUpperCase())}
      </div>
      <div>${escapeHtml(state.incident.notification.summary)}</div>
      <div style="font-size: 10px; margin-top: 8px; text-align: right; opacity: 0.7;">
        TIMELOG: ${new Date(state.incident.notification.sent_at).toLocaleTimeString()}
      </div>
    `;
  } else if (!isPreAlertSent) {
    els.preAlertDisplayCard.className = "document-display-card alert-inactive";
    els.preAlertStatusBadge.textContent = "NOT SENT";
    els.preAlertTextContent.classList.add("hidden");
    els.preAlertDisplayCard.querySelector(".placeholder-text").classList.remove("hidden");
  }

  if (isHandoverSent && state.incident?.handover) {
    els.handoverDisplayCard.className = "document-display-card handover-active";
    els.handoverStatusBadge.textContent = "EHR WRITE DONE";
    els.handoverDisplayCard.querySelector(".placeholder-text").classList.add("hidden");
    els.handoverTextContent.classList.remove("hidden");
    
    // Parse structured SBAR sections if formatted with headers
    const rawSbar = state.incident.handover.summary;
    let formattedSbar = "";
    
    if (rawSbar.includes("S:") || rawSbar.includes("Situation:")) {
      // Style SBAR into printout document card
      formattedSbar = parseSbarIntoOfficialTemplate(rawSbar);
    } else {
      // Raw monospaced rendering
      formattedSbar = `
        <div class="clinical-handover-box">
          <div class="sbar-header">
            <h4>EHR EMERGENCY TRANSFER SBAR</h4>
            <span>ID: ${state.incident.id.toUpperCase()}</span>
          </div>
          <pre style="white-space: pre-wrap; font-family:var(--font-mono); font-size:11.5px; color:#1e293b;">${escapeHtml(rawSbar)}</pre>
          <div class="sbar-footer">
            <span>RECEIVING: ${escapeHtml(selectedRouteHospital()?.name || "Target Hospital")}</span>
            <span>SIGNED AT: ${new Date(state.incident.handover.generated_at).toLocaleTimeString()}</span>
          </div>
        </div>
      `;
    }
    els.handoverTextContent.innerHTML = formattedSbar;
  } else if (!isHandoverSent) {
    els.handoverDisplayCard.className = "document-display-card handover-inactive";
    els.handoverStatusBadge.textContent = "AWAITING HANDOVER";
    els.handoverTextContent.classList.add("hidden");
    els.handoverDisplayCard.querySelector(".placeholder-text").classList.remove("hidden");
  }
}

// Convert unstructured SBAR response into an authentic printout page
function parseSbarIntoOfficialTemplate(sbarText) {
  // Simple extraction of S, B, A, R sections
  const sections = { situation: "", background: "", assessment: "", recommendation: "" };
  
  const sitRegex = /(?:S:|Situation:)\s*([\s\S]*?)(?=(?:B:|Background:|$))/i;
  const bgRegex = /(?:B:|Background:)\s*([\s\S]*?)(?=(?:A:|Assessment:|$))/i;
  const assessRegex = /(?:A:|Assessment:)\s*([\s\S]*?)(?=(?:R:|Recommendation:|Requested readiness:|$))/i;
  const recRegex = /(?:R:|Recommendation:|Requested readiness:)\s*([\s\S]*?)$/i;

  const sitMatch = sbarText.match(sitRegex);
  const bgMatch = sbarText.match(bgRegex);
  const assessMatch = sbarText.match(assessRegex);
  const recMatch = sbarText.match(recRegex);

  sections.situation = sitMatch ? sitMatch[1].trim() : sbarText.substring(0, 150) + "...";
  sections.background = bgMatch ? bgMatch[1].trim() : "Patient medical history verified via NHIS record lookup.";
  sections.assessment = assessMatch ? assessMatch[1].trim() : "Acutely distressed vital telemetry synced from NAS transport module.";
  sections.recommendation = recMatch ? recMatch[1].trim() : "Emergency Room pre-alert dispatched. Prepare trauma bays.";

  return `
    <div class="clinical-handover-box">
      <div class="sbar-header">
        <div>
          <h4 style="font-weight: 800; font-family:var(--font-display);">NATIONAL CLINICAL HANDOVER (SBAR)</h4>
          <span style="font-size:10px; color:#475569;">EHR SYSTEM SYNC: HL7 FHIR FORMAT DONE</span>
        </div>
        <div style="text-align: right;">
          <strong style="display:block; font-size:11px; color:#dc2626;">ACUITY Triage: ${escapeHtml(state.incident?.triage_signal?.acuity.toUpperCase() || "RED")}</strong>
          <span style="font-size:9px; color:#64748b;">REF: ${escapeHtml(state.incident?.id.substring(0,8).toUpperCase())}</span>
        </div>
      </div>
      
      <h5>Situation</h5>
      <p style="font-size:11.5px; margin-bottom:8px; line-height:1.4; color:#334155;">${escapeHtml(sections.situation)}</p>
      
      <h5>Background</h5>
      <p style="font-size:11.5px; margin-bottom:8px; line-height:1.4; color:#334155;">${escapeHtml(sections.background)}</p>
      
      <h5>Assessment</h5>
      <p style="font-size:11.5px; margin-bottom:8px; line-height:1.4; color:#334155;">${escapeHtml(sections.assessment)}</p>
      
      <h5>Recommendation / Readiness</h5>
      <p style="font-size:11.5px; margin-bottom:8px; line-height:1.4; color:#334155;">${escapeHtml(sections.recommendation)}</p>
      
      <div class="sbar-footer">
        <span>UNIT LOG: ${escapeHtml(state.incident?.ambulance_id.toUpperCase())} &rarr; ${escapeHtml(selectedRouteHospital()?.name || "ER STAFF")}</span>
        <span style="font-weight:700;">SIGNED DIGITAL: SECURE-BIO-MD</span>
      </div>
    </div>
  `;
}

// Map dynamic narrative content
function getNarrationContent(stepId) {
  const scenario = selectedScenario();
  const pName = state.incident?.patient?.name || scenario?.patient?.name || "unidentified casualty";
  const ambId = state.incident?.ambulance_id || scenario?.ambulance_id || "a dispatch vehicle";
  const city = state.incident?.scene_location?.city || scenario?.city || "Accra";
  const pathway = state.incident?.triage_signal?.care_pathways?.[0] || scenario?.pathway || "general triage";
  const acuity = state.incident?.triage_signal?.acuity || scenario?.acuity_hint || "high";
  const hospName = selectedRouteHospital()?.name || "closest certified emergency room";
  const eta = state.incident?.recommendations?.find(r => r.hospital_id === state.incident.selected_hospital_id)?.route?.eta_minutes || "12";
  
  const narrations = {
    "dispatch": {
      text: `An emergency call has been logged at NAS Central Dispatch. Dispatch unit ${ambId.toUpperCase()} has been commissioned to respond to ${pName} in ${city}. Initial identity registries search verifies valid Ghana Card and NHIS coverage for the patient.`,
      impact: `Instantly linking biometric profiles at dispatch validates health eligibility. This resolves critical patient administration bottlenecks and allows clinicians to focus purely on active care upon arrival.`
    },
    "ai_triage": {
      text: `NAS paramedics have logged initial patient telemetry. The ${activeProviderName()} clinical assistant parses the raw telemetry, generating a structured clinical signal: ${acuity.toUpperCase()} priority classification, assigned to the ${pathway.toUpperCase()} pathway, requiring capabilities like: ${(state.incident?.triage_signal?.required_capabilities || []).join(', ').toUpperCase() || 'ICU & Oxygen points'}.`,
      impact: `AI triage extracts core clinical signals from verbal paramedic telemetry instantly. This acts as a redundant clinical guardrail, ensuring dispatch errors are caught before route lock.`
    },
    "routing": {
      text: `The deterministic multi-factor scoring algorithm evaluates clinical centers in the ${city} incident region only. It hard-filters out any regional centers missing critical device pathways (e.g., CT scanners for stroke), then ranks remaining candidates by capacity (25%), clinical fit (40%), ETA (20%), and local ER overcrowding (10%).`,
      impact: `Deterministic mathematical scoring guarantees the patient goes to the highest-scoring matching clinic, bypassing overcrowded facilities and eliminating immediate destination diversion delays.`
    },
    "destination": {
      text: `The regional NAS clinical lead approves the routing choice. ${hospName} is confirmed as the destination nodes lock. Ambulance units lock drive paths.`,
      impact: `Locking dynamic destination protocols eliminates cognitive overload for drivers. This guarantees optimal hospital load balance across pilot municipal regions.`
    },
    "prealert": {
      text: `A structured digital pre-alert compiled by the triage engine has been sent to the receiving desk at ${hospName}. The message transmits over designated high-priority SMS/WhatsApp secure channels, notifying doctors of ETA and clinical indicators.`,
      impact: `ER Pre-alerts allow surgical teams, ICU nurses, and blood banks to prepare the trauma bay *before* the ambulance arrives, cutting average door-to-treatment times by over 20 minutes.`
    },
    "transport": {
      text: `The paramedic team updates dynamic telemetry in transit. Ambulance ${ambId.toUpperCase()} traverses the optimal path towards ${hospName}. Driving ETA is checked against live traffic feeds, currently tracking at ${eta} minutes.`,
      impact: `Live dynamic ETA telemetry syncs transit grids with ER schedules, allowing emergency staffs to maintain accurate timetables for trauma center readiness.`
    },
    "handover": {
      text: `Vehicle ${ambId.toUpperCase()} has arrived at ${hospName}. The AI engine compiles the complete situation, background, assessment and recommendation profiles, automatically printing and synchronizing a digital EHR SBAR handover record. incident resolved.`,
      impact: `Structured digital SBAR handovers replace verbal handoffs, mitigating clinical error risks during transfer transitions and maintaining legal audit records permanently.`
    }
  };

  return narrations[stepId] || {
    text: `Demonstration state active. Click advance step to walkthrough the AAIS clinical pipeline.`,
    impact: `AAIS pilot shows substantial clinical time savings and resource optimization.`
  };
}

// Data Flow Node Strip Highlight
function updateDataFlowNodes(currentStepIdx) {
  const nodeKeys = ["dispatch", "ambulance", "triage", "routing", "prealert", "transport", "handover"];
  
  nodeKeys.forEach((key, index) => {
    const nodeEl = els.nodes[key];
    if (!nodeEl) return;
    
    nodeEl.className = "flow-node";
    const statusTextEl = nodeEl.querySelector(".node-status");
    
    if (index === currentStepIdx) {
      nodeEl.classList.add("active");
      statusTextEl.textContent = "Processing";
      
      // If simulation failed/paused at this step
      if (state.session?.status === "paused") {
        nodeEl.classList.remove("active");
        nodeEl.classList.add("paused");
        statusTextEl.textContent = "Awaiting AI";
      }
    } else if (index < currentStepIdx) {
      nodeEl.classList.add("complete");
      statusTextEl.textContent = "Complete";
    } else {
      statusTextEl.textContent = "Pending";
    }
  });
}

function renderMetrics() {
  const overview = state.overview;
  if (!overview) return;
  
  const focus = mapFocus();
  const hospitals = localHospitalsForFocus(focus);
  const ambulances = localAmbulancesForFocus(focus);
  
  const scopedHospitals = hospitals.length ? hospitals : overview.hospitals;
  const scopedAmbulances = ambulances.length ? ambulances : overview.ambulances;
  
  const scopedIncidents = focus.city === "Ghana" 
    ? overview.active_incidents 
    : (overview.active_incidents || []).filter(i => i.scene_location?.city === focus.city);
    
  const active = scopedIncidents.length;
  const online = scopedAmbulances.filter((item) => item.status !== "offline").length;
  const beds = scopedHospitals.reduce((sum, hospital) => sum + hospital.capacity.er_beds_available, 0);
  const avgLoad = scopedHospitals.length
    ? scopedHospitals.reduce((sum, hospital) => sum + hospital.capacity.er_load, 0) / scopedHospitals.length
    : 0;
    
  const scopeLabel = focus.city === "Ghana" ? "National" : focus.city;
  
  els.metricIncidentsLabel.textContent = `${scopeLabel} Active Incidents`;
  els.metricAmbulancesLabel.textContent = `${scopeLabel} Fleet Online`;
  els.metricBedsLabel.textContent = `${scopeLabel} Open ER Beds`;
  els.metricLoadLabel.textContent = `${scopeLabel} Avg ER Load`;
  
  els.metricIncidents.textContent = active;
  els.metricAmbulances.textContent = online;
  els.metricBeds.textContent = beds;
  els.metricLoad.textContent = `${Math.round(avgLoad * 100)}%`;
  
  for (const metric of document.querySelectorAll(".metric")) {
    metric.classList.toggle("live", state.session?.status === "running" || state.isAutoplaying);
  }
}

// Render dynamic Leaflet map markers
function renderMap() {
  if (!leafletMap) {
    // If Leaflet is offline, clear element
    els.mapElement.innerHTML = `
      <div style="padding: 40px; text-align: center; color:var(--muted); height:100%; display:flex; flex-direction:column; justify-content:center;">
        <strong>Tactical Map Offline</strong>
        <span style="font-size:11px;">External mapping CDNs are currently unreachable. Simulation endpoints remain fully active.</span>
      </div>
    `;
    return;
  }
  
  // Clear existing layers
  markersLayerGroup.clearLayers();
  routesLayerGroup.clearLayers();
  
  const focus = mapFocus();
  const localHospitals = localHospitalsForFocus(focus);
  const localAmbulances = localAmbulancesForFocus(focus);
  
  const activeAmb = activeIncidentAmbulance();
  const selectedHosp = selectedRouteHospital();
  const phase = mapPhase(activeAmb);
  
  // 1. Draw Hospitals
  localHospitals.forEach(hospital => {
    const isSelected = selectedHosp && hospital.id === selectedHosp.id;
    
    // Custom icon matching style
    const iconHtml = isSelected
      ? `<div class="tactical-circle-selected" style="width:20px; height:20px; border:3px solid #ffffff; background:var(--green); border-radius:50%; box-shadow:var(--glow-green); animation: primaryPulse 2.5s infinite;"></div>`
      : `<div class="tactical-circle" style="width:14px; height:14px; border:2px solid #ffffff; background:var(--blue); border-radius:50%; box-shadow:0 0 8px rgba(0, 176, 255, 0.4)"></div>`;
      
    const marker = L.marker([hospital.location.latitude, hospital.location.longitude], {
      icon: L.divIcon({
        className: `leaflet-hospital-marker ${isSelected ? 'selected' : ''}`,
        html: iconHtml,
        iconSize: isSelected ? [20, 20] : [14, 14],
        iconAnchor: isSelected ? [10, 10] : [7, 7]
      })
    });
    
    marker.bindPopup(`
      <h4>${escapeHtml(hospital.name)}</h4>
      <p>City: ${escapeHtml(hospital.city)} | Level: ${escapeHtml(hospital.level)}</p>
      <p>ER Load: ${Math.round(hospital.capacity.er_load * 100)}% | Available Beds: ${hospital.capacity.er_beds_available}</p>
    `);
    
    markersLayerGroup.addLayer(marker);
  });
  
  // 2. Draw Ambulances
  localAmbulances.forEach(ambulance => {
    const isActive = activeAmb && ambulance.id === activeAmb.id;
    
    // Custom active ambulance vs static
    const iconHtml = isActive
      ? `<div class="tactical-diamond active" style="width:16px; height:16px; border:2px solid #ffffff; background:var(--amber); border-radius:3px; transform:rotate(45deg); box-shadow:var(--glow-amber); animation: ambulanceBlink 1.1s ease-in-out infinite;"></div><div class="siren-flash-sbar" style="position:absolute; top:-4px; left:6px; width:4px; height:4px; border-radius:50%; background:#60a5fa; box-shadow: 8px 0 0 #ef4444; animation: sirenFlash 620ms steps(2,end) infinite;"></div>`
      : `<div class="tactical-diamond" style="width:12px; height:12px; border:1px solid #ffffff; background:var(--muted); border-radius:2px; transform:rotate(45deg);"></div>`;
      
    const marker = L.marker([ambulance.location.latitude, ambulance.location.longitude], {
      icon: L.divIcon({
        className: `leaflet-ambulance-marker ${isActive ? 'active' : ''}`,
        html: iconHtml,
        iconSize: isActive ? [16, 16] : [12, 12],
        iconAnchor: isActive ? [8, 8] : [6, 6]
      })
    });
    
    marker.bindPopup(`
      <h4>NAS Unit: ${escapeHtml(ambulance.call_sign)}</h4>
      <p>Status: ${escapeHtml(ambulance.status.toUpperCase())}</p>
      <p>Crew: ${escapeHtml(ambulance.crew.join(', '))}</p>
    `);
    
    markersLayerGroup.addLayer(marker);
  });
  
  // 3. Draw Incident Scene
  if (state.incident) {
    const isComplete = phase === "complete";
    
    const iconHtml = isComplete
      ? `<div class="tactical-pulse-incident complete" style="width:16px; height:16px; border:2px solid #ffffff; background:var(--muted); border-radius:50%;"></div>`
      : `<div class="tactical-pulse-incident" style="width:22px; height:22px; border:2px solid #ffffff; background:var(--red); border-radius:50%; box-shadow:var(--glow-red); animation: incidentPulse 1.45s ease-out infinite;"></div>`;
      
    const marker = L.marker([state.incident.scene_location.latitude, state.incident.scene_location.longitude], {
      icon: L.divIcon({
        className: `leaflet-incident-marker ${isComplete ? 'complete' : 'active'}`,
        html: iconHtml,
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      })
    });
    
    marker.bindPopup(`
      <h4>Emergency Scene</h4>
      <p>Patient: ${escapeHtml(state.incident.patient.name)}</p>
      <p>Complaint: ${escapeHtml(state.incident.patient.chief_complaint)}</p>
      <p>Triage Acuity: ${escapeHtml((state.incident.triage_signal?.acuity || "PENDING").toUpperCase())}</p>
    `);
    
    markersLayerGroup.addLayer(marker);
  }
  
  // 4. Draw Connective GIS routes
  if (state.incident) {
    if (activeAmb && phase === "assigned") {
      L.polyline([
        [activeAmb.location.latitude, activeAmb.location.longitude],
        [state.incident.scene_location.latitude, state.incident.scene_location.longitude]
      ], {
        color: 'var(--amber)',
        weight: 3,
        dashArray: '5, 5',
        opacity: 0.8
      }).addTo(routesLayerGroup);
    } else if (activeAmb && selectedHosp && phase === "en_route") {
      L.polyline([
        [state.incident.scene_location.latitude, state.incident.scene_location.longitude],
        [selectedHosp.location.latitude, selectedHosp.location.longitude]
      ], {
        color: 'var(--green)',
        weight: 4,
        dashArray: '8, 4',
        opacity: 0.9
      }).addTo(routesLayerGroup);
      
      // Interpolate real time ambulance marker transit if enroute
      animateTelemetryAmbulance(activeAmb, selectedHosp);
    } else if (selectedHosp && phase === "complete") {
      L.polyline([
        [state.incident.scene_location.latitude, state.incident.scene_location.longitude],
        [selectedHosp.location.latitude, selectedHosp.location.longitude]
      ], {
        color: 'var(--muted)',
        weight: 2,
        opacity: 0.5
      }).addTo(routesLayerGroup);
    }
  }
  
  els.mapCaption.textContent = `${focus.city} Zone focused | ${mapPhaseText(phase)} | ${localHospitals.length} hospitals mapping`;
}

// Telemetry Marker Animation along locked route
function animateTelemetryAmbulance(ambulance, hospital) {
  if (!leafletMap || !markersLayerGroup) return;
  
  // Find current ambulance marker instance
  const start = ambulance.location;
  const end = hospital.location;
  
  // Find active moving ambulance marker
  let activeMarker = null;
  markersLayerGroup.eachLayer(layer => {
    if (layer.options.icon.options.className.includes("active-moving") || layer._popup?._content.includes(ambulance.call_sign)) {
      activeMarker = layer;
    }
  });

  if (activeMarker) {
    const duration = 8000; // 8s loop
    const startTime = performance.now();
    
    function animate(now) {
      if (!state.session || state.session.status !== "running" && !state.isAutoplaying) {
        activeMarker.setLatLng([start.latitude, start.longitude]);
        return;
      }
      
      const elapsed = now - startTime;
      const progress = (elapsed % duration) / duration;
      
      const lat = start.latitude + (end.latitude - start.latitude) * progress;
      const lon = start.longitude + (end.longitude - start.longitude) * progress;
      
      activeMarker.setLatLng([lat, lon]);
      
      requestAnimationFrame(animate);
    }
    
    requestAnimationFrame(animate);
  }
}

// Patient profile rendering
function renderPatient() {
  if (!state.incident) {
    els.patientStatus.textContent = "Awaiting Pickup";
    els.patientCard.className = "detail-card empty-state";
    els.patientCard.innerHTML = "No incident selected. Initialize a workflow to verify identity registries.";
    return;
  }
  
  const patient = state.incident.patient;
  const vitals = patient.vitals;
  const triage = state.incident.triage_signal;
  
  els.patientStatus.textContent = state.incident.status.replace('_', ' ').toUpperCase();
  els.patientCard.className = "detail-card";
  
  // Acuity vitals critical status evaluations
  const hrState = classifyVital("hr", vitals.heart_rate);
  const spo2State = classifyVital("spo2", vitals.oxygen_saturation);
  const gcsState = classifyVital("gcs", vitals.gcs);
  
  els.patientCard.innerHTML = `
    <div class="patient-header">
      <div class="patient-header-details">
        <h3>${escapeHtml(patient.name || "John Doe (Unidentified)")}</h3>
        <p style="font-size:12px; color:var(--muted);">${escapeHtml(patient.age)} YRS | ${escapeHtml(patient.sex.toUpperCase())} | scene: ${escapeHtml(state.incident.scene_location.address || "Live coordinates")}</p>
      </div>
      <div class="patient-id-badges">
        <div class="patient-id-badge" title="Ghana ID Card">GHCard: ${escapeHtml(patient.ghana_card_id || "GHA-77829-09")}</div>
        <div class="patient-id-badge" title="NHIS Eligible Status">NHIS: ${escapeHtml(patient.nhis_id || "NHIS-992-Active")}</div>
      </div>
    </div>
    
    <div class="complaint-box">
      <h4>Paramedic Intake Complaint</h4>
      <p>${escapeHtml(patient.chief_complaint)}</p>
    </div>
    
    <!-- Medical Vitals Grid -->
    <div class="vitals-grid">
      <div class="vital-card ${hrState}">
        <span class="vital-label">HR (BPM)</span>
        <span class="vital-value">${vitals.heart_rate || "—"}</span>
        <div class="vital-bar"><div class="vital-bar-fill" style="width: ${vitals.heart_rate ? Math.min((vitals.heart_rate/180)*100, 100) : 0}%"></div></div>
      </div>
      
      <div class="vital-card">
        <span class="vital-label">BP (mmHg)</span>
        <span class="vital-value" style="font-size:13px; margin: 6.5px 0;">${vitals.systolic_bp || "—"}/${vitals.diastolic_bp || "—"}</span>
        <div class="vital-bar"><div class="vital-bar-fill" style="width: ${vitals.systolic_bp ? Math.min((vitals.systolic_bp/200)*100, 100) : 0}%"></div></div>
      </div>
      
      <div class="vital-card ${spo2State}">
        <span class="vital-label">SpO2 (%)</span>
        <span class="vital-value">${vitals.oxygen_saturation || "—"}%</span>
        <div class="vital-bar"><div class="vital-bar-fill" style="width: ${vitals.oxygen_saturation || 0}%"></div></div>
      </div>
      
      <div class="vital-card ${gcsState}">
        <span class="vital-label">GCS</span>
        <span class="vital-value">${vitals.gcs || "—"}</span>
        <div class="vital-bar"><div class="vital-bar-fill" style="width: ${vitals.gcs ? (vitals.gcs/15)*100 : 0}%"></div></div>
      </div>
    </div>
    
    <!-- Triage LLM details -->
    ${triage ? `
      <div class="triage-output-box">
        <h4>AI Cognitive Classification Output</h4>
        <div class="triage-badge-strip">
          <span class="triage-pill acuity-${triage.acuity.toLowerCase()}">ACUITY: ${triage.acuity.toUpperCase()}</span>
          <span class="triage-pill">PATHWAY: ${triage.care_pathways.join(', ').toUpperCase()}</span>
          ${triage.required_capabilities.map(c => `<span class="triage-pill capability">${c.toUpperCase()}</span>`).join('')}
        </div>
        <p class="triage-summary-text">${escapeHtml(triage.summary)}</p>
        <p class="triage-rationale-text">Clinical rationale: ${escapeHtml(triage.rationale)}</p>
        <div class="confidence-indicator">
          <span>Triage LLM Model: <strong>${escapeHtml(triage.source_model)}</strong></span>
          <span>Confidence: <strong>${Math.round(triage.confidence * 100)}%</strong></span>
        </div>
      </div>
    ` : `
      <div style="text-align: center; padding: 12px; border:1px dashed var(--line); border-radius:10px; color:var(--muted); font-size:12px;">
        AI clinical reasoning pending (${escapeHtml(activeProviderName())} triage prompt will run on the selected provider)
      </div>
    `}
  `;
}

function classifyVital(metric, value) {
  if (!value) return "";
  if (metric === "hr") {
    if (value > 120 || value < 50) return "critical";
    if (value > 100 || value < 60) return "warning";
  }
  if (metric === "spo2") {
    if (value < 90) return "critical";
    if (value < 95) return "warning";
  }
  if (metric === "gcs") {
    if (value <= 8) return "critical";
    if (value < 15) return "warning";
  }
  return "";
}

function renderRecommendations() {
  els.recommendations.innerHTML = "";
  const recommendations = state.incident?.recommendations || [];
  if (!recommendations.length) {
    els.recommendations.innerHTML = "<div class='empty-state'>Dynamic routing metrics populate after step 3 (Triage) locks indicators.</div>";
    return;
  }
  
  recommendations.slice(0, 5).forEach((rec, index) => {
    const card = document.createElement("div");
    const isSelected = state.incident.selected_hospital_id === rec.hospital_id || (!state.incident.selected_hospital_id && index === 0 && !rec.blocked);
    card.className = `ranking-card ${rec.blocked ? "blocked" : ""} ${isSelected ? "selected" : ""}`;
    card.style.animationDelay = `${index * 80}ms`;
    
    card.innerHTML = `
      <div class="ranking-top">
        <div>
          <strong>${escapeHtml(rec.hospital_name)}</strong>
          <span>${escapeHtml(rec.city)} | ETA ${rec.route.eta_minutes} MIN | Traffic: ${escapeHtml(rec.route.traffic_level.toUpperCase())}</span>
        </div>
        <div class="score">${rec.blocked ? "BLOCKED" : Math.round(rec.score)}</div>
      </div>
      
      ${rec.blocked ? `
        <div class="blocked-badge">CRITICAL REQUIREMENT MISSING: ${escapeHtml((rec.missing_requirements || []).join(', ').toUpperCase())}</div>
      ` : `
        <div class="score-bars">
          ${scoreBarCell("Clinical", rec.breakdown.clinical_fit, 40)}
          ${scoreBarCell("Capacity", rec.breakdown.capacity_resources, 25)}
          ${scoreBarCell("ETA", rec.breakdown.eta, 20)}
          ${scoreBarCell("Load", rec.breakdown.er_load, 10)}
          ${scoreBarCell("Record", rec.breakdown.continuity, 5)}
        </div>
      `}
      
      <p class="muted" style="margin-top: 6px; font-size:11.5px;">
        ${rec.reasons[0] ? `&bull; ${escapeHtml(rec.reasons[0])}` : ""}
        ${rec.reasons[1] ? `<br>&bull; ${escapeHtml(rec.reasons[1])}` : ""}
      </p>
    `;
    
    els.recommendations.appendChild(card);
  });
}

function scoreBarCell(label, value, max) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return `
    <div class="bar-row">
      <span>${escapeHtml(label)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <span>${Math.round(value)}</span>
    </div>
  `;
}

function renderHospitals() {
  const focus = mapFocus();
  const hospitals = localHospitalsForFocus(focus);
  els.hospitalLoad.innerHTML = "";
  
  if (!hospitals.length) {
    els.hospitalLoad.innerHTML = `<div class="empty-state">No medical centers localized in this zone.</div>`;
    return;
  }
  
  for (const hospital of hospitals) {
    const load = Math.round(hospital.capacity.er_load * 100);
    const card = document.createElement("div");
    card.className = "hospital-card";
    card.innerHTML = `
      <strong>${escapeHtml(hospital.name)}</strong>
      <span>${escapeHtml(hospital.city)} | ER beds available: ${hospital.capacity.er_beds_available}</span>
      <div class="load-track"><div class="load-fill ${loadClass(load)}" style="width:${load}%"></div></div>
      <span>Emergency overcrowding index: ${load}%</span>
    `;
    els.hospitalLoad.appendChild(card);
  }
}

function renderFleet() {
  const focus = mapFocus();
  const ambulances = localAmbulancesForFocus(focus);
  const activeAmb = activeIncidentAmbulance();
  const phase = mapPhase(activeAmb);
  
  els.fleetList.innerHTML = "";
  if (!ambulances.length) {
    els.fleetList.innerHTML = `<div class="empty-state">No active fleet online in this zone.</div>`;
    return;
  }
  
  for (const ambulance of ambulances) {
    const active = activeAmb && ambulance.id === activeAmb.id;
    const cardPhase = active ? phase : ambulance.status;
    const card = document.createElement("div");
    card.className = `fleet-card ${cardPhase} ${active ? "active" : ""}`;
    card.innerHTML = `
      <div>
        <strong>${escapeHtml(ambulance.call_sign)}</strong>
        <span>${escapeHtml(ambulance.city)} | GPS: ${escapeHtml(ambulance.location.address || "Active Telemetry")}</span>
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
  
  els.start.textContent = hasSession ? "Restart Walkthrough" : "Initialize Incident";
  els.run.textContent = state.isAutoplaying ? "Pause Auto-Play" : "Auto-Play Demo";
}

// Helpers & Utilities
function selectedScenario() {
  return state.scenarios.find((scenario) => scenario.id === state.selectedScenarioId);
}

function mapFocus() {
  const scenario = selectedScenario();
  const city = state.incident?.scene_location?.city || scenario?.city || "Ghana";
  const scene = state.incident?.scene_location || scenario?.scene_location || null;
  return { city, scene, scenario };
}

function localHospitalsForFocus(focus) {
  return (state.overview?.hospitals || []).filter((hospital) => hospital.city === focus.city);
}

function localAmbulancesForFocus(focus) {
  return (state.overview?.ambulances || []).filter(
    (ambulance) => ambulance.city === focus.city || ambulance.current_incident_id === state.incident?.id
  );
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
    assigned: "Dispatched to scene",
    en_route: "Transporting to ER",
    complete: "EHR Handover Done"
  }[phase] || "Awaiting dispatch";
}

function fleetPhaseText(phase) {
  return {
    assigned: "Assigned toward incident",
    en_route: "Transporting patient",
    complete: "Handover resolved",
    idle: "Ready"
  }[phase] || "Ready";
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

// REST call client wrapper
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

// Typewriter clinical engine
function typewriteText(elementId, text, speed = 15) {
  const el = document.getElementById(elementId);
  if (!el) return;
  
  el.dataset.rawText = text;
  el.dataset.isTyping = speed > 0 ? "true" : "false";
  
  // Clear any existing timeouts running on this element
  if (el.typewriterTimeout) {
    clearTimeout(el.typewriterTimeout);
  }
  
  if (speed === 0) {
    el.innerHTML = text;
    el.classList.remove("typewriter-cursor");
    return;
  }
  
  el.innerHTML = "";
  el.classList.add("typewriter-cursor");
  
  let i = 0;
  function type() {
    if (i < text.length) {
      el.innerHTML += text.charAt(i);
      i++;
      el.typewriterTimeout = setTimeout(type, speed);
    } else {
      el.classList.remove("typewriter-cursor");
      el.dataset.isTyping = "false";
    }
  }
  type();
}

function skipTypewriter(elementId) {
  const el = document.getElementById(elementId);
  if (el && el.dataset.isTyping === "true") {
    if (el.typewriterTimeout) {
      clearTimeout(el.typewriterTimeout);
    }
    el.innerHTML = el.dataset.rawText || el.innerHTML;
    el.classList.remove("typewriter-cursor");
    el.dataset.isTyping = "false";
  }
}

function toast(message, type = "info") {
  const note = document.createElement("div");
  note.className = `toast ${type}`;
  note.textContent = message;
  els.toastStack.appendChild(note);
  window.setTimeout(() => note.remove(), 5000);
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
