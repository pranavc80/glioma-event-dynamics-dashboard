"""Command-line entry point for the Glioma Event Dynamics Lab."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from glioma_event_lab.analysis import build_patient_summaries, summarize_cohort
    from glioma_event_lab.data_adapter import simulate_dataset
    from glioma_event_lab.dashboard_data import write_dashboard_payload
    from glioma_event_lab.fitting import fit_from_gdc_cases
    from glioma_event_lab.gdc import fetch_gdc_cases, flatten_cases, write_case_csv
    from glioma_event_lab.longitudinal import export_demo_longitudinal, fit_longitudinal_csv
    from glioma_event_lab.reporting import write_markdown_report
    from glioma_event_lab.rl_env import POLICIES, rollout_policy
    from glioma_event_lab.simulator import simulate_cohort
    from glioma_event_lab.web import serve_directory
except ModuleNotFoundError:
    from analysis import build_patient_summaries, summarize_cohort
    from data_adapter import simulate_dataset
    from dashboard_data import write_dashboard_payload
    from fitting import fit_from_gdc_cases
    from gdc import fetch_gdc_cases, flatten_cases, write_case_csv
    from longitudinal import export_demo_longitudinal, fit_longitudinal_csv
    from reporting import write_markdown_report
    from rl_env import POLICIES, rollout_policy
    from simulator import simulate_cohort
    from web import serve_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Glioma event dynamics lab.")
    subparsers = parser.add_subparsers(dest="command")

    simulate_parser = subparsers.add_parser("simulate", help="Simulate a synthetic cohort.")
    simulate_parser.add_argument("--patients", type=int, default=50, help="Number of synthetic patients to simulate.")
    simulate_parser.add_argument("--steps", type=int, default=120, help="Number of time steps per patient.")
    simulate_parser.add_argument("--seed", type=int, default=0, help="Random seed for cohort generation.")
    simulate_parser.add_argument("--top-k", type=int, default=5, help="Number of highest-risk patients to display.")

    report_parser = subparsers.add_parser("report", help="Generate figures and a markdown report.")
    report_parser.add_argument("--patients", type=int, default=50, help="Number of synthetic patients to simulate.")
    report_parser.add_argument("--steps", type=int, default=120, help="Number of time steps per patient.")
    report_parser.add_argument("--seed", type=int, default=0, help="Random seed for cohort generation.")
    report_parser.add_argument("--out-dir", type=str, default="outputs", help="Directory for report artifacts.")
    report_parser.add_argument("--data", type=str, default="", help="Optional CSV of BraTS/TCGA-style features.")

    ingest_parser = subparsers.add_parser("ingest", help="Adapt a feature CSV and simulate from it.")
    ingest_parser.add_argument("--data", type=str, required=True, help="Path to a feature CSV.")
    ingest_parser.add_argument("--steps", type=int, default=120, help="Number of time steps per patient.")
    ingest_parser.add_argument("--seed", type=int, default=0, help="Random seed.")
    ingest_parser.add_argument("--top-k", type=int, default=5, help="Number of highest-risk patients to display.")

    rl_parser = subparsers.add_parser("rl", help="Evaluate baseline treatment policies.")
    rl_parser.add_argument("--patients", type=int, default=40, help="Number of synthetic patients per policy.")
    rl_parser.add_argument("--horizon", type=int, default=90, help="Episode horizon.")
    rl_parser.add_argument("--seed", type=int, default=0, help="Random seed.")
    rl_parser.add_argument(
        "--policies",
        type=str,
        nargs="*",
        default=list(POLICIES.keys()),
        help="Policies to evaluate.",
    )

    gdc_parser = subparsers.add_parser("gdc-fetch", help="Download public TCGA glioma cases from GDC.")
    gdc_parser.add_argument("--max-cases", type=int, default=400, help="Maximum number of cases to fetch.")
    gdc_parser.add_argument("--out-csv", type=str, default="data/gdc_tcga_glioma_cases.csv", help="Output CSV path.")

    fit_parser = subparsers.add_parser("fit-gdc", help="Fetch GDC glioma cases and fit calibration parameters.")
    fit_parser.add_argument("--max-cases", type=int, default=400, help="Maximum number of cases to fetch.")
    fit_parser.add_argument("--out-json", type=str, default="outputs/gdc_fit.json", help="Where to write fitted parameters.")

    dashboard_parser = subparsers.add_parser("build-dashboard", help="Build the JSON artifact consumed by the static web dashboard.")
    dashboard_parser.add_argument("--max-cases", type=int, default=120, help="Maximum number of GDC cases to fetch.")
    dashboard_parser.add_argument("--out", type=str, default="webapp/data/dashboard_data.json", help="Output dashboard JSON path.")
    dashboard_parser.add_argument("--seed", type=int, default=0, help="Random seed for simulated policy summaries.")
    dashboard_parser.add_argument("--longitudinal-csv", type=str, default="outputs/demo_longitudinal.csv", help="Where to write the demo longitudinal CSV.")
    dashboard_parser.add_argument("--longitudinal-fit", type=str, default="outputs/longitudinal_fit.json", help="Where to write the fitted longitudinal summary.")

    serve_parser = subparsers.add_parser("serve-web", help="Serve the local dashboard.")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port for the local web server.")
    serve_parser.add_argument("--dir", type=str, default="webapp", help="Directory to serve.")

    demo_long_parser = subparsers.add_parser("export-longitudinal-demo", help="Export a demo trajectory-shaped CSV for longitudinal fitting.")
    demo_long_parser.add_argument("--out-csv", type=str, default="outputs/demo_longitudinal.csv", help="Output CSV path.")
    demo_long_parser.add_argument("--patients", type=int, default=24, help="Number of demo patients.")
    demo_long_parser.add_argument("--steps", type=int, default=18, help="Number of time steps.")
    demo_long_parser.add_argument("--seed", type=int, default=11, help="Random seed.")

    fit_long_parser = subparsers.add_parser("fit-longitudinal", help="Fit state transitions and event rates from a trajectory-shaped CSV.")
    fit_long_parser.add_argument("--csv", type=str, required=True, help="Path to a longitudinal CSV.")
    fit_long_parser.add_argument("--out-json", type=str, default="outputs/longitudinal_fit.json", help="Output JSON path.")

    parser.set_defaults(command="simulate")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "simulate":
        trajectories = simulate_cohort(size=args.patients, steps=args.steps, seed=args.seed)
        cohort_summary = summarize_cohort(trajectories)
        patient_summaries = build_patient_summaries(trajectories)
        print("=== Cohort Summary ===")
        print(json.dumps(cohort_summary, indent=2))
        print()
        print(f"=== Top {args.top_k} Highest-Risk Patients ===")
        print(json.dumps(patient_summaries[: args.top_k], indent=2))
        return

    if args.command == "ingest":
        dataset, trajectories = simulate_dataset(path=args.data, steps=args.steps, seed=args.seed)
        print("=== Dataset Metadata ===")
        print(json.dumps(dataset.metadata, indent=2))
        print()
        print("=== Cohort Summary ===")
        print(json.dumps(summarize_cohort(trajectories), indent=2))
        print()
        print(f"=== Top {args.top_k} Highest-Risk Patients ===")
        print(json.dumps(build_patient_summaries(trajectories)[: args.top_k], indent=2))
        return

    if args.command == "report":
        dataset_metadata = None
        if args.data:
            dataset, trajectories = simulate_dataset(path=args.data, steps=args.steps, seed=args.seed)
            dataset_metadata = dataset.metadata
        else:
            trajectories = simulate_cohort(size=args.patients, steps=args.steps, seed=args.seed)

        report_path = write_markdown_report(trajectories, out_dir=args.out_dir, dataset_metadata=dataset_metadata)
        print(json.dumps({"report_path": str(report_path), "output_dir": str(Path(args.out_dir).resolve())}, indent=2))
        return

    if args.command == "rl":
        results = [rollout_policy(name, patients=args.patients, horizon=args.horizon, seed=args.seed) for name in args.policies]
        print(json.dumps(results, indent=2))
        return

    if args.command == "gdc-fetch":
        cases = fetch_gdc_cases(max_cases=args.max_cases)
        rows = flatten_cases(cases)
        csv_path = write_case_csv(rows, args.out_csv)
        print(json.dumps({"cases_fetched": len(cases), "csv_path": str(csv_path.resolve())}, indent=2))
        return

    if args.command == "fit-gdc":
        cases = fetch_gdc_cases(max_cases=args.max_cases)
        result = fit_from_gdc_cases(cases, out_path=args.out_json)
        print(json.dumps(result, indent=2))
        return

    if args.command == "build-dashboard":
        cases = fetch_gdc_cases(max_cases=args.max_cases)
        destination = write_dashboard_payload(
            cases,
            path=args.out,
            seed=args.seed,
            longitudinal_csv_path=args.longitudinal_csv,
            longitudinal_fit_path=args.longitudinal_fit,
        )
        print(json.dumps({"dashboard_path": str(destination.resolve()), "cases_fetched": len(cases)}, indent=2))
        return

    if args.command == "serve-web":
        serve_directory(args.dir, port=args.port)
        return

    if args.command == "export-longitudinal-demo":
        destination = export_demo_longitudinal(args.out_csv, patients=args.patients, steps=args.steps, seed=args.seed)
        print(json.dumps({"csv_path": str(destination.resolve())}, indent=2))
        return

    if args.command == "fit-longitudinal":
        result = fit_longitudinal_csv(args.csv, out_path=args.out_json)
        print(json.dumps(result, indent=2))
        return


if __name__ == "__main__":
    main()
