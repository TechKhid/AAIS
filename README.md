# AI-Powered Ambulance Intelligence System MVP

AAIS is an API-first FastAPI simulator for emergency medical coordination in a Ghana pilot context. It models the handoff between ambulance dispatch, LLM-assisted triage, deterministic hospital routing, hospital pre-alerts, ambulance transport updates, command-center monitoring, and digital handover.

The application is intentionally shaped like a production service boundary while keeping the MVP simple: state is in memory, external stakeholder systems are mocked, and the LLM layer can use either local LM Studio or NVIDIA NIM APIs for clinical text and triage extraction.

## What This Project Does

- Creates emergency incidents from ambulance scene reports.
- Links patients to mock Ghana Card, NHIS, and FHIR-style patient records when identifiers match seeded data.
- Uses LM Studio or NVIDIA NIM to extract structured triage signals from ambulance notes.
- Ranks hospitals with deterministic, explainable routing logic.
- Blocks unsafe destinations when critical required capabilities are missing.
- Generates hospital pre-alert and ambulance-to-hospital handover text with the LLM.
- Provides a browser-based command-center simulator at `/`.
- Exposes API docs at `/docs`.
- Includes automated tests with fake LLM clients so the test suite does not require LM Studio or NVIDIA NIM.

## Current MVP Boundaries

This is a simulator, not a clinical production system.

Mocked integrations include:

- National Ambulance Service dispatch and fleet telemetry
- Hospital capacity, bed, and barcode systems
- Ghana Card and NHIS identity lookup
- National EHR/FHIR patient lookup
- Traffic and ETA provider
- Hospital alerting and notification delivery
- Remote command-center clinician review

Real runtime LLM calls do not fall back to fake responses. If the selected LLM provider or configured model is unavailable, LLM-backed API endpoints return `503`, and simulation sessions pause with an explicit error.

## Tech Stack

- Python 3.11+
- FastAPI
- Pydantic v2
- Uvicorn
- OpenAI Python SDK pointed at LM Studio or NVIDIA NIM OpenAI-compatible APIs
- httpx
- pytest
- Vanilla HTML, CSS, and JavaScript frontend served by FastAPI

## Repository Layout

```text
app/
  main.py                  FastAPI app factory, dependency wiring, static UI mount
  config.py                Environment-backed runtime settings
  dependencies.py          FastAPI dependency accessors
  schemas.py               Pydantic domain and API models
  seed_data.py             Mock Ghana pilot fixtures
  store.py                 Thread-safe in-memory state store
  routers/
    health.py              LLM provider and app health endpoint
    incidents.py           Incident lifecycle endpoints
    hospitals.py           Hospital list and capacity update endpoints
    ambulances.py          Ambulance list and telemetry update endpoints
    command.py             Command-center overview and event stream
    simulation.py          Simulation scenario and session endpoints
  services/
    llm_client.py          LM Studio/NVIDIA NIM client, output parsing, normalization
    routing.py             Deterministic hospital ranking engine
    mocks.py               Mock stakeholder integration service
    simulation.py          Scenario orchestration engine
  static/
    index.html             Browser command-center shell
    app.js                 UI state, scenario controls, map, ranking, event rendering
    styles.css             Simulator styling and responsive layout
docs/
  architecture.md          MVP and production architecture notes
scripts/
  smoke_flow.py            End-to-end HTTP smoke flow against a running API
tests/
  conftest.py              Fake and unavailable LLM test clients
  test_*.py                Flow, health, routing, LLM parsing, and simulation tests
```

## Environment

Copy `.env.example` to `.env` if you want to override defaults.

```env
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=qwen/qwen3.5-9b
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b
NVIDIA_NIM_API_KEY=
LLM_TIMEOUT_SECONDS=30
```

`LLM_PROVIDER` accepts:

- `lmstudio` for local LM Studio. This remains the default.
- `nvidia_nim` for NVIDIA NIM APIs.

`LMSTUDIO_MODEL` may be either the configured full model id or a short LM Studio-loaded alias. For NVIDIA NIM, `NVIDIA_NIM_BASE_URL` defaults to NVIDIA's hosted API endpoint, and `NVIDIA_NIM_MODEL` should be a model id available to that endpoint. The app also reads `NVIDIA_API_KEY` or `NIM_API_KEY` if `NVIDIA_NIM_API_KEY` is not set.

## Setup And Run

1. Create and activate a Python environment.

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

2. Install dependencies.

```cmd
python -m pip install -r requirements.txt
```

3. Choose an LLM provider.

For local LM Studio, keep `LLM_PROVIDER=lmstudio`, start LM Studio, enable the local OpenAI-compatible server, and load the configured model. The default is:

```text
qwen/qwen3.5-9b
```

For hosted NVIDIA NIM, set these values in `.env` or in the current `cmd` session:

```cmd
set "LLM_PROVIDER=nvidia_nim"
set "NVIDIA_NIM_API_KEY=<your NVIDIA API key>"
set "NVIDIA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b"
```

For a self-hosted NIM container, point the base URL at that container's OpenAI-compatible `/v1` endpoint:

```cmd
set "LLM_PROVIDER=nvidia_nim"
set "NVIDIA_NIM_BASE_URL=http://127.0.0.1:8000/v1"
set "NVIDIA_NIM_MODEL=<model id from /v1/models>"
```

4. Start the API.

```cmd
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

5. Open the simulator or API docs.

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

On this workstation, `C:\Users\stemaider\anaconda3\envs\stemaide-env\python.exe` has previously been used as a working runtime environment for this project.

## LLM Provider Options

### LM Studio

LM Studio is the default provider and is best when you want everything local. The app checks both LM Studio's local management API and OpenAI-compatible `/models` endpoint, resolves short model aliases, and pauses LLM-backed flows when the configured model is not loaded.

Minimum `.env` values:

```env
LLM_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=qwen/qwen3.5-9b
```

### NVIDIA NIM

NVIDIA NIM is useful when you want to run AAIS on a laptop without loading a local model. Hosted NIM uses NVIDIA's OpenAI-compatible API endpoint. Self-hosted NIM containers can also be used by changing `NVIDIA_NIM_BASE_URL`.

Minimum hosted `.env` values:

```env
LLM_PROVIDER=nvidia_nim
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_MODEL=nvidia/nemotron-3-super-120b-a12b
NVIDIA_NIM_API_KEY=<your NVIDIA API key>
```

Known hosted chat model examples:

- `nvidia/nemotron-3-super-120b-a12b`
- `deepseek-ai/deepseek-v4-flash`

Minimum self-hosted `.env` values:

```env
LLM_PROVIDER=nvidia_nim
NVIDIA_NIM_BASE_URL=http://127.0.0.1:8000/v1
NVIDIA_NIM_MODEL=<model id from /v1/models>
```

## Health Check

```http
GET /health
```

The response includes:

- App status
- Active LLM provider
- Active provider availability
- Configured base URL
- Configured model
- Resolved model
- Models reported by the active provider
- Detail message when the model is missing, unloaded, or unreachable

If `/health` reports that the configured model is not loaded or listed, load the model in LM Studio, choose a loaded NIM model, or update the relevant model environment variable before running LLM-backed flows.

## Core System Flow

```mermaid
flowchart LR
    A[Ambulance scene report] --> B[POST /incidents]
    B --> C[Patient record lookup]
    C --> D[POST /incidents/{id}/ai-triage]
    D --> E[LLM triage signal]
    E --> F[POST /incidents/{id}/recommendations]
    F --> G[Deterministic hospital ranking]
    G --> H[POST /incidents/{id}/destination]
    H --> I[POST /incidents/{id}/notify]
    I --> J[PATCH /ambulances/{id}/location]
    J --> K[POST /incidents/{id}/handover]
    K --> L[GET /command/overview]
```

The main API flow is:

1. `POST /incidents`
2. `POST /incidents/{id}/ai-triage`
3. `POST /incidents/{id}/recommendations`
4. `POST /incidents/{id}/destination`
5. `POST /incidents/{id}/notify`
6. `PATCH /ambulances/{id}/location`
7. `POST /incidents/{id}/handover`
8. `GET /command/overview`

## LLM Responsibilities

The LLM is used for decision support text and structured extraction only. It does not choose the hospital.

LLM-backed operations:

- Structured triage extraction
- Care pathway inference
- Required capability and specialist inference
- Hospital pre-alert summary generation
- Digital handover note generation

The app asks the selected provider for JSON-only triage output and then normalizes common variants. For example, "CT scan" normalizes to `ct`, "stroke specialist" normalizes to `neurologist`, and high or urgent acuity language normalizes to `red`.

LLM safety behavior:

- Empty or malformed triage JSON triggers a repair request.
- Invalid repaired JSON returns a `502` response.
- Provider connection, timeout, auth, or unloaded-model failures return `503`.
- Simulation pauses instead of inventing LLM output when the LLM is unavailable.

## Routing Engine

Hospital ranking is deterministic and explainable. It first limits candidates to hospitals in the incident region, using the incident scene city in this MVP, then scores those regional hospitals with structured triage requirements plus seeded hospital capability, capacity, specialist, ETA, ER load, and patient continuity data.

Weights:

| Factor | Weight |
|:---|---:|
| Clinical fit | 40 |
| Capacity and resources | 25 |
| ETA | 20 |
| ER load | 10 |
| Patient record continuity | 5 |

Critical capabilities block a hospital if they are required but unavailable:

- `icu`
- `oxygen`
- `ct`
- `surgical_team`
- `neonatal_support`
- `ventilator`

Non-critical gaps reduce the score and appear in recommendation reasons. Recommendations are sorted by blocked status, descending score, then ETA.

## Seeded Pilot Data

Seeded cities:

- Accra
- Kumasi
- Tamale

Seeded hospitals:

| ID | Hospital | City | Level |
|:---|:---|:---|:---|
| `korle-bu-teaching` | Korle Bu Teaching Hospital | Accra | teaching |
| `ridge-hospital` | Greater Accra Regional Hospital | Accra | regional |
| `37-military` | 37 Military Hospital | Accra | specialist |
| `komfo-anokye` | Komfo Anokye Teaching Hospital | Kumasi | teaching |
| `kumasi-south` | Kumasi South Hospital | Kumasi | regional |
| `suntreso-hospital` | Suntreso Government Hospital | Kumasi | district |
| `tamale-teaching` | Tamale Teaching Hospital | Tamale | teaching |
| `tamale-west` | Tamale West Hospital | Tamale | regional |
| `tamale-central` | Tamale Central Hospital | Tamale | district |

Seeded ambulances:

| ID | Call Sign | City | Equipment Highlights |
|:---|:---|:---|:---|
| `amb-accra-01` | NAS Accra 01 | Accra | oxygen, monitor, defibrillator, trauma kit |
| `amb-accra-02` | NAS Accra 02 | Accra | oxygen, monitor, obstetric kit |
| `amb-kumasi-01` | NAS Kumasi 01 | Kumasi | oxygen, monitor, trauma kit |
| `amb-tamale-01` | NAS Tamale 01 | Tamale | oxygen, monitor, pediatric kit |

Seeded patient records:

| Patient ID | Name | Linked Identifiers | Preferred Hospitals |
|:---|:---|:---|:---|
| `FHIR-PAT-1001` | Ama Serwaa | Ghana Card, NHIS | Ridge Hospital, Korle Bu |
| `FHIR-PAT-1002` | Kwame Owusu | Ghana Card, NHIS | Korle Bu, 37 Military |
| `FHIR-PAT-2001` | Amina Yakubu | Ghana Card, NHIS | Tamale Teaching, Tamale West |

## API Endpoints

### Health

| Method | Path | Purpose |
|:---|:---|:---|
| `GET` | `/health` | App and active LLM provider readiness |

### Incidents

| Method | Path | Purpose |
|:---|:---|:---|
| `POST` | `/incidents` | Create incident and assign ambulance |
| `GET` | `/incidents/{incident_id}` | Fetch incident state |
| `POST` | `/incidents/{incident_id}/ai-triage` | Run LLM triage extraction |
| `POST` | `/incidents/{incident_id}/recommendations` | Rank hospitals |
| `POST` | `/incidents/{incident_id}/destination` | Confirm receiving hospital |
| `POST` | `/incidents/{incident_id}/notify` | Generate and send hospital pre-alert |
| `POST` | `/incidents/{incident_id}/handover` | Generate digital handover |

### Hospitals

| Method | Path | Purpose |
|:---|:---|:---|
| `GET` | `/hospitals` | List seeded hospitals |
| `PATCH` | `/hospitals/{hospital_id}/capacity` | Update hospital capacity |

### Ambulances

| Method | Path | Purpose |
|:---|:---|:---|
| `GET` | `/ambulances` | List seeded ambulances |
| `PATCH` | `/ambulances/{ambulance_id}/location` | Update ambulance status or location |

### Command Center

| Method | Path | Purpose |
|:---|:---|:---|
| `GET` | `/command/overview` | Active incidents, fleet, hospitals, recent events |
| `GET` | `/command/events` | Event stream with configurable limit |

### Simulation

| Method | Path | Purpose |
|:---|:---|:---|
| `GET` | `/simulation/scenarios` | List available simulation scenarios |
| `GET` | `/simulation/sessions` | List simulation sessions |
| `POST` | `/simulation/sessions` | Start a session for a scenario |
| `GET` | `/simulation/sessions/{session_id}` | Fetch session state |
| `POST` | `/simulation/sessions/{session_id}/step` | Advance one simulation step |
| `POST` | `/simulation/sessions/{session_id}/run` | Advance until paused, failed, completed, or max step limit |
| `POST` | `/simulation/reset` | Reset in-memory incidents, sessions, events, hospitals, and ambulances |

## Simulation Breakdown

The simulation engine orchestrates the same services used by the production-shaped API flow. It does not maintain a separate fake path for success cases.

### Scenario Catalog

| Scenario ID | Name | City | Pathway | Acuity Hint | Expected Needs |
|:---|:---|:---|:---|:---|:---|
| `accra-stroke` | Accra suspected stroke | Accra | stroke | red | CT, ICU, oxygen, neurologist |
| `accra-trauma` | Accra road trauma | Accra | trauma | red | CT, ICU, surgical team, blood bank, neurosurgeon |
| `accra-obstetric` | Accra obstetric emergency | Accra | obstetric | red | maternity, neonatal support, blood bank, obstetrician |
| `kumasi-cardiac` | Kumasi chest pain | Kumasi | cardiac | orange | oxygen, ICU, cardiologist |
| `tamale-pediatric-respiratory` | Tamale pediatric respiratory distress | Tamale | pediatric respiratory | orange | oxygen, pediatric care, pediatrician |

### Step Lifecycle

Each session starts with seven pending steps:

| Step | Label | What Happens | Primary Outputs |
|:---|:---|:---|:---|
| `dispatch` | Dispatch and patient pickup | Creates an incident from the selected scenario, links a patient record when possible, assigns the scenario ambulance, records `incident.created`. | Incident ID, assigned ambulance, active incident state |
| `ai_triage` | LLM-assisted triage | Calls the selected LLM provider for structured triage, stores acuity/pathway/capability/specialist requirements, records remote clinician review. | `triage_signal`, incident status `triaged` |
| `routing` | Hospital recommendation | Calls deterministic routing against hospitals in the incident region, then scores current capacity, specialists, ETA, ER load, and patient continuity. | Regional ranked recommendations, score breakdowns, blocked flags |
| `destination` | Destination confirmation | Selects the top unblocked recommendation and stores it as the receiving hospital. | `selected_hospital_id`, ambulance status `en_route` |
| `prealert` | Hospital pre-alert | Calls the selected LLM provider to draft a concise hospital alert, sends it through the mock notification gateway. | Notification event, incident status `notified` |
| `transport` | Ambulance transport update | Moves ambulance coordinates partway toward the destination and records transport progress. | Updated ambulance location and status, incident status `en_route` |
| `handover` | Digital handover | Calls the selected LLM provider to draft structured ED handover using scenario treatments, observations, and final vitals. | Handover summary, incident status `handover_complete`, ambulance status `at_hospital` |

### Session Status Rules

| Status | Meaning |
|:---|:---|
| `ready` | Session exists but no step has completed. |
| `running` | At least one step is active or complete, and more work remains. |
| `paused` | LLM dependency was unavailable or returned invalid output. User can fix the selected provider and step again. |
| `failed` | Non-LLM unexpected error occurred and was recorded. |
| `completed` | All seven steps completed successfully. |

### Pause Behavior

The simulation pauses on:

- Active LLM provider not reachable
- Configured model missing or unloaded
- Active LLM provider timeout
- Invalid LLM response after parsing or repair

Paused sessions preserve:

- Completed prior steps
- Current paused step
- Incident state
- `last_error`
- Command-center event trail

### Browser UI Behavior

The simulator UI at `/` lets an operator:

- Select a scenario.
- Start, step, run, or reset a session.
- Monitor active LLM provider readiness.
- See active incidents, ambulances, ER beds, and average ER load.
- Watch a local operating-picture map for the focused city.
- Review patient vitals and LLM triage output.
- Compare hospital ranking cards with score bars.
- Inspect hospital load, fleet status, and command timeline events.

## Example Manual API Flow

Create an incident:

```cmd
(
  echo {
  echo   "ambulance_id": "amb-accra-01",
  echo   "scene_location": {
  echo     "city": "Accra",
  echo     "latitude": 5.5792,
  echo     "longitude": -0.2057,
  echo     "address": "Osu Oxford Street"
  echo   },
  echo   "patient": {
  echo     "name": "Kwame Owusu",
  echo     "ghana_card_id": "GHA-222333444-1",
  echo     "nhis_id": "NHIS-AC-0002",
  echo     "age": 61,
  echo     "sex": "male",
  echo     "chief_complaint": "Sudden right-sided weakness, facial droop, and slurred speech started 35 minutes ago.",
  echo     "notes": "Known atrial fibrillation.",
  echo     "vitals": {
  echo       "heart_rate": 112,
  echo       "systolic_bp": 178,
  echo       "diastolic_bp": 96,
  echo       "respiratory_rate": 20,
  echo       "oxygen_saturation": 94,
  echo       "temperature_c": 36.9,
  echo       "gcs": 14,
  echo       "pain_score": 0
  echo     }
  echo   }
  echo }
) > incident.json

curl.exe -X POST "http://127.0.0.1:8000/incidents" -H "Content-Type: application/json" --data-binary @incident.json
```

Then call the incident lifecycle endpoints in order:

```cmd
set "INCIDENT_ID=<incident id>"

curl.exe -X POST "http://127.0.0.1:8000/incidents/%INCIDENT_ID%/ai-triage"
curl.exe -X POST "http://127.0.0.1:8000/incidents/%INCIDENT_ID%/recommendations"
```

Select one unblocked recommendation:

```cmd
set "HOSPITAL_ID=<hospital id>"

curl.exe -X POST "http://127.0.0.1:8000/incidents/%INCIDENT_ID%/destination" -H "Content-Type: application/json" -d "{\"hospital_id\":\"%HOSPITAL_ID%\"}"
```

Notify and hand over:

```cmd
curl.exe -X POST "http://127.0.0.1:8000/incidents/%INCIDENT_ID%/notify"

(
  echo {
  echo   "treatments_administered": ["oxygen applied", "IV access established"],
  echo   "observations": "Patient remained under ambulance monitoring during transport."
  echo }
) > handover.json

curl.exe -X POST "http://127.0.0.1:8000/incidents/%INCIDENT_ID%/handover" -H "Content-Type: application/json" --data-binary @handover.json
```

## Smoke Test Against A Running Server

Start the API first, then run:

```cmd
python scripts\smoke_flow.py
```

Use a different base URL when needed:

```cmd
set "AAIS_BASE_URL=http://127.0.0.1:8001"
python scripts\smoke_flow.py
```

The smoke script checks health, creates a stroke incident, runs triage, ranks hospitals, selects a destination, sends a pre-alert, completes handover, and prints event count.

To test NVIDIA NIM chat connectivity directly against the two hosted chat models above:

```cmd
set "NVIDIA_NIM_API_KEY=<your NVIDIA API key>"
C:\Users\stemaider\anaconda3\envs\aiis-env\python.exe scripts\nim_model_smoke.py
```

To test one model at a time:

```cmd
C:\Users\stemaider\anaconda3\envs\aiis-env\python.exe scripts\nim_model_smoke.py nvidia/nemotron-3-super-120b-a12b
C:\Users\stemaider\anaconda3\envs\aiis-env\python.exe scripts\nim_model_smoke.py deepseek-ai/deepseek-v4-flash
```

To test the AAIS client path or structured triage path:

```cmd
C:\Users\stemaider\anaconda3\envs\aiis-env\python.exe scripts\nim_model_smoke.py --client-chat nvidia/nemotron-3-super-120b-a12b
C:\Users\stemaider\anaconda3\envs\aiis-env\python.exe scripts\nim_model_smoke.py --triage nvidia/nemotron-3-super-120b-a12b
```

## Automated Tests

Run the test suite:

```cmd
python -m pytest
```

Tests use `FakeLLM` and `UnavailableLLM` from `tests/conftest.py`, so they verify normal and unavailable LLM behavior without requiring LM Studio or NVIDIA NIM.

Coverage includes:

- App health and seeded command overview
- Full happy-path incident lifecycle
- Recommendation precondition checks
- LLM unavailable `503` handling
- LLM response parsing and normalization
- Deterministic routing behavior
- Capacity updates changing routing outcomes
- Simulation scenario listing, full run, pause behavior, and reset

## State Model

The MVP state is stored in `InMemoryStore`:

- Hospitals
- Ambulances
- Patient records
- Patient identifier index
- Incidents
- Simulation sessions
- Event records

State resets when:

- The server process restarts.
- `POST /simulation/reset` is called.

The store uses a reentrant lock around mutations to keep the in-memory model consistent under concurrent request handling.

## Event Trail

The app records operational events such as:

- `system.boot`
- `incident.created`
- `incident.ai_triaged`
- `remote_triage.reviewed`
- `incident.recommendations_ready`
- `incident.destination_confirmed`
- `hospital.prealert_sent`
- `simulation.transport_progress`
- `incident.handover_complete`
- `simulation.paused`
- `simulation.completed`
- `simulation.failed`

Recent events are visible in the browser UI and via:

```http
GET /command/events
GET /command/overview
```

## Production Evolution Notes

The current architecture is designed so mock services can be replaced with real adapters:

- National EHR/FHIR exchange
- Ghana Card and NHIS lookup
- NAS dispatch and fleet telemetry
- Hospital bed and barcode capacity systems
- Traffic and maps provider
- SMS, push, radio, and hospital alerting gateways

Likely production infrastructure:

- PostgreSQL plus PostGIS for durable geospatial state
- Redis for realtime operational state
- Durable object storage for attachments
- Event streaming for national-scale dispatch and audit events
- OIDC authentication
- Role-based authorization
- Encryption in transit and at rest
- Immutable audit logs
- PHI-safe logging and least-privilege service accounts
- Ghana Data Protection Act aligned emergency health data handling

The LLM should remain behind a provider interface. Prompts, model ids, outputs, and downstream actions should be auditable, and LLM output should remain decision support rather than the legal or clinical decision-maker.

## Related Documentation

See `docs/architecture.md` for the shorter MVP and production architecture note.

See `docs/deployment.md` for the Fly.io backend and Vercel frontend deployment runbook.
