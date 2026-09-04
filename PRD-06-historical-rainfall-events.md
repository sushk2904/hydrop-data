# PRD-06 — Historical Extreme Rainfall Event Dataset

## Objective
Create a small, well-documented collection of historical heavy-rainfall events for replaying and validating the prototype.

## Initial Scope
Start with:
- 2–3 significant rainfall events for Mumbai
- 2–3 for Delhi
- 2–3 for Chennai

Do not download years of data during the first development sprint.

## Event Structure
Each event should contain:
```text
event_id
city
start_time_utc
end_time_utc
rainfall_source
rainfall_files
event_description
source_reference
```

## Directory
```text
data/events/
├── mumbai/
├── delhi/
└── chennai/
```

## Requirements
1. Select events with substantial rainfall.
2. Prefer events with accessible rainfall observations.
3. Record exact start/end times.
4. Link each event to rainfall files.
5. Store source references.
6. Keep the event definition reproducible.
7. Do not label predicted flood output as ground truth.

## Validation Concept
```text
Historical rainfall event
        ↓
Our model
        ↓
Predicted inundation
        ↓
Compare against available observations/reports
```

## Agent Prompt
Build a historical rainfall event catalogue for SIH26085.

Initially select 2–3 major rainfall events for Mumbai, Delhi and Chennai. Prefer events for which reliable rainfall observations are accessible.

For each event, record event ID, city, start/end UTC timestamps, rainfall source, associated rainfall files, event description and source reference.

Do not attempt to collect a massive multi-year dataset in the first sprint.

Directory: `data/events/<city>/`.

Create a machine-readable event catalogue and a human-readable README.
