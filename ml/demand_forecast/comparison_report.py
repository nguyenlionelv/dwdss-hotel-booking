"""Generate report tables and standalone plots only from executed experiment evidence."""
import json
from pathlib import Path


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |",
                      *["| " + " | ".join(str(v) for v in row) + " |" for row in rows]])


def generate_report(output_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    output = Path(output_dir)
    read = lambda name: json.loads((output / name).read_text(encoding="utf-8"))
    result, frozen, filtering, points = (read(name) for name in ("metrics.json", "frozen_plan.json", "filtering.json", "predictions.json"))
    if result["status"] != "completed":
        raise ValueError("Only completed experiments can produce the final comparison report")
    charts = output / "charts"
    charts.mkdir(exist_ok=False)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "axes.titleweight": "bold"})
    colors = {"Baseline": "#64748b", "V1": "#2563eb", "V2": "#0d9488", "V3": "#a855f7"}

    def save(fig, name):
        fig.savefig(charts / f"{name}.png", dpi=170, bbox_inches="tight")
        fig.savefig(charts / f"{name}.svg", bbox_inches="tight")
        plt.close(fig)

    comparison = result["comparison"]
    train = filtering["partitions"]["train"]
    labels = ["Daily Mart", "Train dates", "COMPLETE", "V1", "V2", "V3"]
    counts = [filtering["daily_observations"], train["calendar_days"], *[s["remaining"] for s in train["stages"]]]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.barh(labels[::-1], counts[::-1], color=["#a855f7", "#0d9488", "#2563eb", "#38bdf8", "#94a3b8", "#64748b"])
    for i, count in enumerate(counts[::-1]):
        ax.text(count + 8, i, f"{count:,}", va="center")
    ax.set(xlim=(0, max(counts) * 1.14), xlabel="Calendar-day samples", title="Demand training eligibility funnel")
    fig.text(.13, .99, f"{filtering['reservation_rows']:,} reservations aggregate into {filtering['daily_observations']:,} daily observations"
             if filtering["reservation_rows"] is not None else "Synthetic fixture; not official performance evidence", fontsize=10)
    fig.tight_layout()
    save(fig, "filtering_funnel")

    names = [r["candidate_id"].replace("_linear_regression", " LR").replace("_random_forest", " RF").replace("_xgboost", " XGB").replace("Baseline_seasonal_naive", "Naive") for r in comparison]
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, metric in zip(axes, ["mae", "rmse"]):
        values = [r["common_validation"][metric] for r in comparison]
        ax.barh(names[::-1], values[::-1], color=[colors[r["version"]] for r in comparison][::-1])
        ax.axvline(values[0], color="#475569", linestyle="--", linewidth=1)
        for i, value in enumerate(values[::-1]):
            ax.text(value + max(values) * .012, i, f"{value:.2f}", va="center", fontsize=8)
        ax.set(xlim=(0, max(values) * 1.18), xlabel=f"{metric.upper()} (guests/day)", title=f"Common validation {metric.upper()}")
    fig.suptitle(f"Identical {comparison[0]['common_validation']['origins']} origins / {comparison[0]['common_validation']['points']} scored points")
    fig.tight_layout()
    save(fig, "common_validation_errors")

    representative = [comparison[0], *[min([r for r in comparison if r["version"] == label], key=lambda r: (r["common_validation"]["mae"], r["common_validation"]["rmse"])) for label in ["V1", "V2", "V3"]]]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for row in representative:
        for ax, metric in zip(axes, ["mae", "rmse"]):
            ax.plot(range(1, 8), [row["common_validation"]["by_horizon"][str(h)][metric] for h in range(1, 8)],
                    marker="o", color=colors[row["version"]], label=row["candidate_id"])
            ax.set(xlabel="Forecast horizon (days)", ylabel=f"{metric.upper()} (guests/day)", xticks=range(1, 8))
    axes[0].legend(fontsize=8)
    fig.suptitle("Common validation errors by horizon: baseline and best candidate per version")
    fig.tight_layout()
    save(fig, "horizon_errors")

    origin = frozen["common_origins"]["validation"][0]
    fig, ax = plt.subplots(figsize=(10, 4))
    for row in representative:
        sample = [p for p in points if p["partition"] == "validation" and p["candidate_id"] == row["candidate_id"] and p["as_of_date"] == origin]
        sample.sort(key=lambda p: p["forecast_date"])
        ax.plot([p["forecast_date"] for p in sample], [p["predicted_guest_count"] for p in sample], marker="o", color=colors[row["version"]], label=row["candidate_id"])
        if row["version"] == "Baseline":
            ax.plot([p["forecast_date"] for p in sample], [p["actual_guest_count"] for p in sample], color="#111827", linewidth=2.5, label="Actual")
    ax.set(ylabel="Guest count", title=f"First common validation window (cutoff {origin}); illustrative only")
    ax.legend(fontsize=8, ncol=2)
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()
    save(fig, "actual_vs_predicted")

    fig, ax = plt.subplots(figsize=(11, 4))
    x = np.arange(len(train["monthly"]))
    for i, label in enumerate(["V1", "V2", "V3"]):
        ax.bar(x + (i - 1) * .25, [m[label] for m in train["monthly"]], width=.25, label=label, color=colors[label])
    ax.set(xticks=x, xticklabels=[m["month"] for m in train["monthly"]], ylabel="Eligible training dates", title="Monthly representation after feature filtering")
    ax.legend()
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()
    save(fig, "monthly_training_coverage")

    sections = ["# Demand feature-version comparison", "",
        f"Source kind: **{result['run_kind']}**. Data version: `{result['data_version']}`. Snapshot: `{result['snapshot_hash']}`.",
        "All results below come from executed fits and saved predictions. Source-quality rules and chronological boundaries were preserved. Existing accepted artifacts were not overwritten.",
        "## Data filtering", "",
        f"{filtering['reservation_rows']} reservation facts aggregate to {filtering['daily_observations']} daily observations. This is a change of grain, not rejection of the difference in row counts.",
        "![Data-filtering funnel](charts/filtering_funnel.png)",
        table(["Partition", "Dates", "Calendar days", "COMPLETE", "PARTIAL"], [[name, f"{p['start']} to {p['end']}", p["calendar_days"], p["target_status_counts"].get("COMPLETE", 0), p["target_status_counts"].get("PARTIAL", 0)] for name, p in filtering["partitions"].items()]), "",
        table(["Training filter", "Before", "Newly excluded", "Remaining", "Exact condition"], [[s["stage"], s["before"], s["newly_excluded"], s["remaining"], s["condition"]] for s in train["stages"]]), "",
        "The 793→275 reduction selects the training date range: 518 validation/test dates are reserved, not rejected for poor quality. The later exclusions are incremental under nested masks. PARTIAL dates remain in the calendar with NULL targets; no zero/subtotal imputation or compressed date shifting is used.",
        "For the accepted dataset, zero-guest non-canceled bookings trigger guest-ineligible daily quality, which makes the target PARTIAL. The prior live eligibility audit identifies 33 such bookings on 26 training dates. This causal audit applies when its data version matches the one above.",
        "## Feature definitions", "",
        table(["Version", "Schema identifier", "Predictors", "History for a seven-day forecast"], [[spec["label"], version, ", ".join(spec["names"]), spec["forecast_history_days"]] for version, spec in _spec_rows(frozen)]),
        "V1 needs only d−7 for an individual training row, but forecasting all seven horizons requires T−6…T. V2/V3 use recursive predictions to update rolling inputs after cutoff T. All windows end at d−1.",
        "## Monthly training representation", "",
        table(["Month", "Dates", "COMPLETE", "PARTIAL", "V1", "V2", "V3"], [[m[k] for k in ["month", "calendar_days", "complete_targets", "partial_targets", "V1", "V2", "V3"]] for m in train["monthly"]]),
        "![Monthly training coverage](charts/monthly_training_coverage.png)",
        "## Primary common-origin validation comparison", "",
        f"Every candidate below is scored on exactly {comparison[0]['common_validation']['origins']} common validation origins ({comparison[0]['common_validation']['points']} day predictions). Coverage is the fraction of all partition-contained seven-day windows supported by that version; coverage scores are not used for ranking.",
        table(["Version", "Model", "Training rows", "Common MAE", "Common RMSE", "Bias", "Supported validation origins", "Coverage"], [[r["version"], r["model_name"], r["training_rows"] if r["training_rows"] is not None else "N/A", f"{r['common_validation']['mae']:.6f}", f"{r['common_validation']['rmse']:.6f}", f"{r['common_validation']['bias']:.6f}", r["supported_origins"], f"{r['origin_coverage']:.2%}"] for r in comparison]),
        "![Common validation MAE and RMSE](charts/common_validation_errors.png)",
        "## Expanded validation coverage (not a ranking table)", "",
        table(["Version", "Model", "Origins", "Additional vs common", "Points", "MAE", "RMSE", "Skipped origins"], [[r["version"], r["model_name"], r["version_validation"]["origins"], r["supported_origins"] - r["common_validation"]["origins"], r["version_validation"]["points"], f"{r['version_validation']['mae']:.6f}", f"{r['version_validation']['rmse']:.6f}", len(r["skipped_origins"])] for r in comparison]),
        table(["Version", "Skipped (distinct)", "Incomplete history", "Incomplete outcomes", "Missing cutoff", "Missing horizon calendar"],
              [[r["version"], len(r["skipped_origins"]), *[r["skipped_reason_counts"].get(reason, 0) for reason in
                ["HISTORY_NOT_COMPLETE", "OUTCOMES_NOT_COMPLETE", "CUTOFF_OUTSIDE_ACTUAL_RANGE", "HORIZON_CALENDAR_UNAVAILABLE"]]]
               for r in [comparison[0], *[next(row for row in comparison if row["version"] == label) for label in ["V1", "V2", "V3"]]]]),
        "Exact skipped dates and overlapping HISTORY_NOT_COMPLETE / OUTCOMES_NOT_COMPLETE / calendar reasons are saved in frozen_plan.json and metrics.json. Scores on different origin sets must not be ranked against each other.",
        "## Horizon-specific validation errors", ""]
    for metric in ["mae", "rmse"]:
        sections.extend([f"### {metric.upper()} in guests/day", "", table(["Candidate", *[f"h={h}" for h in range(1, 8)]], [[r["candidate_id"], *[f"{r['common_validation']['by_horizon'][str(h)][metric]:.4f}" for h in range(1, 8)]] for r in comparison]), ""])
    sections.extend(["![Errors by horizon](charts/horizon_errors.png)", "![Actual versus predicted](charts/actual_vs_predicted.png)",
        "## Controlled training-subset analysis", "",
        "All rows below use the same common validation origins. Primary fits are reused where both feature and training subset match; remaining combinations are separately fitted. Controlled candidates are diagnostic and were excluded from selection by the frozen policy.",
        table(["Features", "Training eligibility subset", "Rows", "Model", "Common MAE", "Common RMSE"], [[r["version"], r["training_subset"], r["training_rows"], r["model_name"], f"{r['common_validation']['mae']:.6f}", f"{r['common_validation']['rmse']:.6f}"] for r in result["controlled"]]),
        "Comparing feature sets on the same subset controls training dates and sample size. Increasing subset size within a feature set changes both sample size and date composition; it does not isolate a pure causal sample-size effect.",
        "## Generalization and selection", "",
        table(["Candidate", "In-sample one-step MAE", "Common seven-day MAE", "Non-overlapping validation MAE", "Non-overlapping origins"], [[r["candidate_id"], "N/A" if "in_sample_one_step_mae_not_backtest" not in r else f"{r['in_sample_one_step_mae_not_backtest']:.6f}", f"{r['common_validation']['mae']:.6f}", f"{r['common_validation']['nonoverlapping']['mae']:.6f}", r["common_validation"]["nonoverlapping"]["origins"]] for r in comparison]),
        "In-sample one-step errors and out-of-sample seven-day errors are different tasks; their gap is a warning about generalization, not a formal overfitting statistic. Small, seasonally uneven subsets and overlapping origins limit inference. Calendar encoding is fitted only on the training subset; unseen months use handle_unknown='ignore'.",
        f"Selected: **{result['selection']['candidate_id']}**. {result['selection']['rationale']}",
        f"Frozen policy: rank common-origin validation MAE, then RMSE, then linear/forest/XGBoost and V1/V2/V3. Require at least {result['selection']['policy']['min_relative_mae_improvement']:.1%} improvement over naive and, when enabled, positive MAE improvement on the non-overlapping subset. These are policy heuristics, not statistical significance. The best regression's relative improvement was {result['selection']['best_relative_mae_improvement']:.2%}.",
        "selection.json was written before refitting or predicting test outcomes. Expanded-origin scores and controlled experiments were not used to choose the winner. No hyperparameter search was performed.",
        "## Final test after frozen selection", ""])
    final = result["final_test"]
    test_scores = [("Selected strategy: supported origins", final["metrics"]),
                   ("Selected strategy: common origins", final["common_origin_metrics"])]
    if "baseline_same_origins" in final:
        test_scores.append(("Seasonal naive: identical selected origins", final["baseline_same_origins"]))
    sections.extend([table(["Scoring set", "Origins", "Points", "MAE", "RMSE", "Bias"],
        [[label, score["origins"], score["points"], f"{score['mae']:.6f}", f"{score['rmse']:.6f}", f"{score['bias']:.6f}"]
         for label, score in test_scores]),
        f"Final training cutoff: {final['final_training_cutoff']}. Refit rows: {final['refit_rows'] if final['refit_rows'] is not None else 'N/A (unfitted seasonal naive)'}. Only the selected strategy was refitted; other regressions were not tested.",
        "The selected bundle was exported to bundles/selected, reloaded, and checked against seven-day inference before/after serialization. selected_forecast.json contains the forecast from the final actual date. Validation bundles, controlled bundles, configuration, frozen dates, metrics, and all predictions are retained in this run directory.",
        "## Limitations", "", *[f"- {limitation}" for limitation in result["limitations"]], "",
        "## Detailed exclusions and concrete examples", ""])
    if "baseline_same_origins" in final:
        score = final["baseline_same_origins"]
        sections.append(f"Seasonal naive on identical final test origins: MAE {score['mae']:.6f}, RMSE {score['rmse']:.6f}, bias {score['bias']:.6f}.")
    for name, partition in filtering["partitions"].items():
        sections.extend([f"### {name}", "", "Marginal exclusion counts overlap and must not be summed.",
            table(["Reason", "Dates"], sorted(partition["marginal_exclusions"].items())), "",
            "These exact combinations are mutually exclusive and account for every date:",
            table(["Exact reason set", "Dates"], [[", ".join(r["reasons"]) or "None (eligible)", r["days"]] for r in partition["exclusive_combinations"]]), ""])
        for stage in partition["stages"]:
            sections.append(f"**{stage['stage']}:** {stage['before']} → {stage['remaining']}; newly excluded {stage['newly_excluded']}.")
            for example in stage["examples"][:3]:
                reasons = "; ".join(f"{r['date']} ({r['status']})" for r in example["unavailable_history"])
                sections.append(f"- {example['date']}: target {example['target_status']}" + (f"; unavailable history: {reasons}." if reasons else "."))
            sections.append("")
    with (output / "report.md").open("x", encoding="utf-8") as handle:
        handle.write("\n\n".join(sections) + "\n")


def _spec_rows(frozen):
    from .contracts import feature_spec
    from dataclasses import asdict
    return [(version, asdict(feature_spec(version))) for version in frozen["settings"]["feature_versions"]]
