# Glioma Event Dynamics Lab

`Glioma Event Dynamics Lab` is a neuroscience-inspired ML project that models brain-tumor progression as an evolving event system instead of a one-shot prediction problem.

It now includes three connected layers:

- a latent-state + self-exciting event simulator,
- a real-data adapter for BraTS/TCGA-style feature tables,
- and a treatment-planning environment for sequential decision-making.

It also now includes an official-data workflow using the National Cancer Institute GDC API for TCGA glioma cases, plus a calibration pass that fits a mortality model and simulator bias from real cases.

This is the kind of project that reads less like coursework and more like an independent research sandbox.

## Core idea

Rather than asking only:

- "Will this patient survive?"
- "Can I classify this MRI?"

the project asks:

**How do latent disease states, adverse-event cascades, and interventions interact over time in neuro-oncology?**

That lets you talk about:

- Markov or semi-Markov assumptions,
- Hawkes-style self-exciting event processes,
- counterfactual simulation,
- latent-state reasoning from partial observations,
- and sequential treatment decisions under uncertainty.

## Components

### 1. Event simulator

The simulator represents glioma progression with five latent states:

1. `stable`
2. `infiltrative`
3. `angiogenic`
4. `aggressive`
5. `terminal`

At each time step:

- a covariate-aware Markov transition updates latent disease state,
- symptom and progression events are emitted through a self-exciting process,
- interventions dampen future hazard,
- and patient-level instability metrics are computed.

Primary files:

- [simulator.py](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\simulator.py)
- [analysis.py](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\analysis.py)

### 2. Real-data adapter

The adapter ingests CSVs shaped like simplified BraTS or TCGA-style feature tables and maps them into patient profiles used by the simulator.

Supported feature patterns include:

- direct `tumor_volume` and `resection_extent`,
- or derived volumes like `necrotic_core_volume`, `enhancing_volume`, `edema_volume`,
- plus common clinical covariates like `age`, `grade`, and `methylated`.

Primary file:

- [data_adapter.py](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\data_adapter.py)

Example input:

- [sample_data.csv](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\sample_data.csv)

### 2b. Official TCGA glioma pull and fitting

The project can now pull public TCGA glioma case data from the GDC API, flatten it into a local CSV, and fit a simple one-year mortality model plus a simulator calibration config.

Primary files:

- [gdc.py](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\gdc.py)
- [fitting.py](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\fitting.py)

### 3. Report and figures

The reporting layer generates:

- SVG figures for average event counts,
- final-state distributions,
- top-risk patient trajectories,
- and a markdown report summarizing the run.

This keeps the project presentation-ready even without extra plotting dependencies.

Primary file:

- [reporting.py](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\reporting.py)

### 3b. Local web dashboard

The project now ships with a static browser dashboard that reads a generated JSON artifact and renders:

- observed TCGA case distributions,
- calibrated observed-versus-simulated comparisons,
- treatment-policy reward summaries,
- fitted simulator parameters,
- and a preview of flattened GDC case rows.

Primary files:

- [dashboard_data.py](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\dashboard_data.py)
- [index.html](C:\Users\chapa\OneDrive\Documents\ML3\webapp\index.html)
- [app.js](C:\Users\chapa\OneDrive\Documents\ML3\webapp\app.js)
- [styles.css](C:\Users\chapa\OneDrive\Documents\ML3\webapp\styles.css)

### 4. Treatment-planning environment

The RL-style environment exposes the simulator as a sequential decision process where actions correspond to intervention intensity.

Included baseline policies:

- `none`
- `reactive`
- `conservative`

This gives you a clean narrative for moving from predictive modeling into decision-making and control.

Primary file:

- [rl_env.py](C:\Users\chapa\OneDrive\Documents\ML3\glioma_event_lab\rl_env.py)

## Project structure

```text
glioma_event_lab/
  __init__.py
  analysis.py
  cli.py
  data_adapter.py
  dashboard_data.py
  fitting.py
  gdc.py
  reporting.py
  rl_env.py
  sample_data.csv
  simulator.py
webapp/
  index.html
  app.js
  styles.css
  data/
```

## Running

Use the package entry point:

```powershell
& "C:\Users\chapa\AppData\Local\Programs\Python\Python312\python.exe" -m glioma_event_lab.cli
```

### Simulate a synthetic cohort

```powershell
& "C:\Users\chapa\AppData\Local\Programs\Python\Python312\python.exe" -m glioma_event_lab.cli simulate --patients 40 --steps 120 --seed 7
```

### Ingest a BraTS/TCGA-style CSV and simulate from it

```powershell
& "C:\Users\chapa\AppData\Local\Programs\Python\Python312\python.exe" -m glioma_event_lab.cli ingest --data .\glioma_event_lab\sample_data.csv --steps 90 --seed 3
```

### Generate a report with figures

```powershell
& "C:\Users\chapa\AppData\Local\Programs\Python\Python312\python.exe" -m glioma_event_lab.cli report --data .\glioma_event_lab\sample_data.csv --steps 90 --seed 3 --out-dir .\outputs
```

### Compare baseline treatment policies

```powershell
& "C:\Users\chapa\AppData\Local\Programs\Python\Python312\python.exe" -m glioma_event_lab.cli rl --patients 30 --horizon 75 --seed 5
```

### Download official TCGA glioma case data

```powershell
& "C:\Users\chapa\AppData\Local\Programs\Python\Python312\python.exe" -m glioma_event_lab.cli gdc-fetch --max-cases 400 --out-csv .\data\gdc_tcga_glioma_cases.csv
```

### Fit data-driven calibration parameters from GDC cases

```powershell
& "C:\Users\chapa\AppData\Local\Programs\Python\Python312\python.exe" -m glioma_event_lab.cli fit-gdc --max-cases 400 --out-json .\outputs\gdc_fit.json
```

### Build the dashboard data artifact

```powershell
python -m glioma_event_lab.cli build-dashboard --max-cases 120 --out .\webapp\data\dashboard_data.json --seed 7
```

### Serve the local web app

```powershell
python -m glioma_event_lab.cli serve-web --port 8000 --dir .\webapp
```

## Portfolio pitch

You can describe this as:

> I built a neuro-oncology event-modeling lab that combines latent-state Markov dynamics, Hawkes-style clinical event cascades, real-data feature adaptation, and treatment-policy evaluation. The goal was to move beyond static prediction and study temporal disease evolution and intervention timing.

That sounds much stronger than:

> I trained a classifier on a medical dataset.

## Strong resume bullets

- Built a neuro-oncology simulation framework combining covariate-aware Markov state transitions with Hawkes-style self-exciting clinical events.
- Designed a real-data adapter for BraTS/TCGA-style radiogenomic feature tables and mapped them into longitudinal patient-level simulations.
- Integrated public TCGA glioma case retrieval from the NCI GDC API and fit a one-year mortality calibration model from real cases.
- Implemented a reporting pipeline that generates research-style SVG figures and markdown summaries from cohort simulations.
- Built a local browser dashboard for inspecting observed case distributions, calibrated simulator output, and treatment-policy baselines.
- Framed treatment timing as a sequential decision problem and evaluated baseline intervention policies in a custom RL-style environment.

## Best next upgrades

If you want to push this even further later:

1. fit transition and excitation parameters to real longitudinal clinical trajectories,
2. merge in richer longitudinal sources because current GDC progression labels are sparse and not strong enough for honest progression calibration,
3. infer latent states from imaging or genomic observations with a hidden Markov model,
4. learn a policy with Monte Carlo control or Q-learning,
5. and add uncertainty quantification and calibration.
