# AAIS MVP And Production Architecture

## MVP

The MVP is a FastAPI modular monolith with in-memory state. It mocks NAS dispatch, ambulance GPS, hospital capacity, bed/barcode tracking, EHR/FHIR lookup, Ghana Card/NHIS lookup, traffic/ETA, notification delivery, and command-center monitoring.

The LLM layer supports LM Studio and NVIDIA NIM as selectable OpenAI-compatible providers for:

- structured triage extraction
- care pathway and capability inference
- hospital pre-alert summaries
- digital handover notes

The routing engine remains deterministic. It first limits candidates to hospitals in the incident region, using scene city as the MVP region boundary, then scores each remaining hospital with these weights:

- clinical fit: 40
- capacity/resources: 25
- ETA: 20
- ER load: 10
- patient record continuity: 5

Critical missing capabilities such as ICU, oxygen, CT, surgical team, neonatal support, or ventilator block a hospital. Non-critical gaps reduce the score and are shown in the reasons.

The simulation engine is a thin orchestration layer over the same production-shaped services. It owns scenario sessions and advances them through dispatch, AI triage, routing, destination selection, hospital pre-alert, transport progress, and handover. It pauses when the LLM is unavailable so the demo keeps the same safety rule as the API.

LM Studio remains the default local provider. NVIDIA NIM can be selected with `LLM_PROVIDER=nvidia_nim` for hosted API usage or self-hosted NIM containers, which makes the demo easier to run on laptops that should not load a local model.

## Production Evolution

Production should keep the same service boundaries while replacing mocks with real adapters:

- national EHR/FHIR exchange
- Ghana Card/NHIS identity lookup
- NAS dispatch and fleet telemetry
- hospital bed/barcode capacity systems
- traffic/maps provider
- SMS, push, radio, and hospital alerting gateways

State should move to PostgreSQL with PostGIS, Redis for realtime state, durable object storage for attachments, and event streaming once national-scale event volume requires it.

The LLM should stay behind a provider interface. Every prompt, model, output, and downstream action should be auditable. LLM output remains decision support, not the legal or clinical decision-maker.

## Security And Governance

Production needs OIDC login, role-based access, encryption in transit and at rest, immutable audit logs, least-privilege service accounts, PHI-safe logging, and Ghana Data Protection Act aligned handling of emergency health data.
