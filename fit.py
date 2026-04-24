import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

FIT_BINS = 100
FIT_EMIN_MEV = 1.0
FIT_EMAX_MEV = 7.5
DATA_UNIT = "MeV"
STEP_TREE_NAME = "tree_save_evnets_energy"
STEP_BRANCH_NAME = "energy"
MIN_TEMPLATE_SUPPORT_PER_BIN = 20.0
MIN_BINS_ALLOWED = 12


def add_local_dependency_paths(project_root: Path) -> None:
    templatefitter_path = project_root / "input/dependece" / "TemplateFitter"
    if templatefitter_path.exists() and str(templatefitter_path) not in sys.path:
        sys.path.insert(0, str(templatefitter_path))


def _cache_paths(root_file: Path, cache_dir: Path):
    key = hashlib.sha1(str(root_file.resolve()).encode("utf-8")).hexdigest()[:16]
    base = f"{root_file.stem}_{key}"
    return cache_dir / f"{base}.npy", cache_dir / f"{base}.json"


def _read_cache_if_valid(root_file: Path, cache_npy: Path, cache_meta: Path):
    import numpy as np

    if not cache_npy.exists() or not cache_meta.exists():
        return None
    try:
        meta = json.loads(cache_meta.read_text(encoding="utf-8"))
    except Exception:
        return None
    stat = root_file.stat()
    if meta.get("source_path") != str(root_file.resolve()):
        return None
    if meta.get("source_mtime_ns") != stat.st_mtime_ns:
        return None
    if meta.get("source_size") != stat.st_size:
        return None
    if meta.get("unit") != DATA_UNIT:
        return None
    return np.load(cache_npy, allow_pickle=False)


def _write_cache(root_file: Path, cache_npy: Path, cache_meta: Path, data_mev):
    import numpy as np

    cache_npy.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_npy, np.asarray(data_mev, dtype=float), allow_pickle=False)
    stat = root_file.stat()
    meta = {
        "source_path": str(root_file.resolve()),
        "source_mtime_ns": stat.st_mtime_ns,
        "source_size": stat.st_size,
        "tree": STEP_TREE_NAME,
        "branch": STEP_BRANCH_NAME,
        "unit": DATA_UNIT,
    }
    cache_meta.write_text(json.dumps(meta, ensure_ascii=True, indent=2), encoding="utf-8")


def load_step_energy_mev(root_file: Path, cache_dir: Path):
    import numpy as np
    import uproot

    cache_npy, cache_meta = _cache_paths(root_file, cache_dir)
    cached = _read_cache_if_valid(root_file, cache_npy, cache_meta)
    if cached is not None:
        return cached

    tree = uproot.open(f"{root_file}:{STEP_TREE_NAME}")
    data_mev = np.asarray(tree[STEP_BRANCH_NAME].array(library="np"), dtype=float)
    _write_cache(root_file, cache_npy, cache_meta, data_mev)
    return data_mev


def parse_root_stem_to_float(stem: str):
    # 支持两种格式：数字、数字_数字（下划线代表小数点）
    if re.fullmatch(r"\d+", stem):
        return float(stem)
    if re.fullmatch(r"\d+_\d+", stem):
        return float(stem.replace("_", "."))
    return None


def stem_to_decimal_label(stem: str) -> str:
    # 3      -> "3"
    # 3_5    -> "3.5"
    return stem.replace("_", ".")


def parse_window_stem(stem: str):
    """匹配能窗扫描命名（两种常见形式）：
    - 双下划线：1_0__1_1  -> [1.0, 1.1]
    - 四段数字：1_0_1_1   -> [1.0, 1.1]（两段各为 整数_小数 或 整数）
    """
    m = re.fullmatch(r"(\d+(?:_\d+)?)__(\d+(?:_\d+)?)", stem)
    if m:
        lo = parse_root_stem_to_float(m.group(1))
        hi = parse_root_stem_to_float(m.group(2))
        if lo is None or hi is None:
            return None
        return (lo, hi)
    parts = stem.split("_")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        lo = parse_root_stem_to_float(f"{parts[0]}_{parts[1]}")
        hi = parse_root_stem_to_float(f"{parts[2]}_{parts[3]}")
        if lo is None or hi is None:
            return None
        return (lo, hi)
    return None


def window_label_from_path(path: Path) -> str:
    stem = path.stem
    m = re.fullmatch(r"(\d+(?:_\d+)?)__(\d+(?:_\d+)?)", stem)
    if m:
        return f"{stem_to_decimal_label(m.group(1))}~{stem_to_decimal_label(m.group(2))}"
    parts = stem.split("_")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        a = f"{parts[0]}_{parts[1]}"
        b = f"{parts[2]}_{parts[3]}"
        return f"{stem_to_decimal_label(a)}~{stem_to_decimal_label(b)}"
    return stem


def discover_window_template_files(template_dir: Path):
    """只选取能窗模板：*_*__*_*.root（两段各为整数或 整数_小数 形式）。"""
    templates = []
    skipped = []
    for f in sorted(template_dir.glob("*.root")):
        win = parse_window_stem(f.stem)
        if win is None:
            skipped.append(f.name)
            continue
        lo, hi = win
        templates.append((lo, hi, f))
    templates.sort(key=lambda x: (x[0], x[1]))
    return [t[2] for t in templates], skipped


def build_argparser():
    parser = argparse.ArgumentParser(
        description=(
            "Template fit: data=input/all.root (step energy in MeV); "
            "templates=build/{min}__{max}.root with underscore decimals, e.g. 1_0__1_1.root."
        )
    )
    parser.add_argument(
        "--template-dir",
        default="./build",
        help="Directory containing window template ROOT files (name like 1_0__1_1.root).",
    )
    parser.add_argument(
        "--input-dir",
        default=None,
        help="Deprecated: same as --template-dir if set.",
    )
    parser.add_argument(
        "--data-file",
        default="input/all.root",
        help="Data ROOT path relative to project root (default: input/all.root).",
    )
    parser.add_argument(
        "--min-template-support",
        type=float,
        default=MIN_TEMPLATE_SUPPORT_PER_BIN,
        help="Minimum total template counts per bin; bins will be reduced if below this support.",
    )
    parser.add_argument(
        "--min-bins",
        type=int,
        default=MIN_BINS_ALLOWED,
        help="Lower bound for adaptive bin reduction.",
    )
    parser.add_argument(
        "--validate-profile",
        action="store_true",
        help="Run profile-likelihood validation (slower), similar to TemplateFitter example.",
    )
    parser.add_argument(
        "--profile-points",
        type=int,
        default=40,
        help="Number of profile points when --validate-profile is enabled.",
    )
    parser.add_argument(
        "--profile-sigma",
        type=float,
        default=2.0,
        help="Profile scan width in sigma when --validate-profile is enabled.",
    )
    parser.add_argument(
        "--profile-cpu",
        type=int,
        default=4,
        help="CPU workers for profile scan.",
    )
    parser.add_argument(
        "--toy-pull",
        action="store_true",
        help="Run toy-study pull validation for the first process.",
    )
    parser.add_argument(
        "--toy-nexp",
        type=int,
        default=100,
        help="Number of toy experiments for pull validation.",
    )
    parser.add_argument(
        "--toy-max-tries",
        type=int,
        default=10,
        help="Maximum retries per toy experiment.",
    )
    parser.add_argument(
        "--pull-png",
        default="fit_pull_hist.png",
        help="Output PNG filename for pull histogram.",
    )
    parser.add_argument("--csv-out", default="fit_yield_table.csv", help="Output CSV filename.")
    return parser


def pick_stable_bin_count(template_arrays, fit_range, initial_bins, min_support, min_bins):
    import numpy as np

    bins = int(initial_bins)
    min_bins = max(4, int(min_bins))
    while True:
        edges = np.linspace(fit_range[0], fit_range[1], bins + 1)
        support = np.zeros(bins, dtype=float)
        for arr in template_arrays:
            c, _ = np.histogram(arr, bins=edges)
            support += c.astype(float)
        # 允许少量低统计 bin，但不能大面积空洞
        low_support_frac = float((support < min_support).sum()) / float(len(support))
        if low_support_frac <= 0.05 or bins <= min_bins:
            return bins, support, low_support_frac
        next_bins = max(min_bins, bins // 2)
        if next_bins == bins:
            return bins, support, low_support_frac
        bins = next_bins


def draw_plots_with_root(
    bin_edges,
    data_counts,
    model_total,
    component_scaled_counts,
    processes,
    process_labels,
    fitted_yields,
    data_label,
    out_stack_png,
    out_comp_png,
):
    import ROOT
    import numpy as np

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)

    nbins = len(bin_edges) - 1
    xlow = float(bin_edges[0])
    xhigh = float(bin_edges[-1])
    centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    def make_hist(name, title):
        h = ROOT.TH1D(name, title, nbins, xlow, xhigh)
        h.SetDirectory(0)
        return h

    # Build histograms
    h_data = make_hist("h_data", "")
    h_model = make_hist("h_model", "")
    comp_hists = []

    for i, y in enumerate(data_counts, start=1):
        h_data.SetBinContent(i, float(y))
    for i, y in enumerate(model_total, start=1):
        h_model.SetBinContent(i, float(y))

    root_colors = [
        ROOT.kAzure + 1,
        ROOT.kOrange + 7,
        ROOT.kGreen + 2,
        ROOT.kMagenta + 1,
        ROOT.kCyan + 1,
        ROOT.kRed + 1,
        ROOT.kViolet + 6,
        ROOT.kTeal + 3,
        ROOT.kPink + 6,
        ROOT.kSpring + 5,
    ]

    for idx, (proc, label) in enumerate(zip(processes, process_labels)):
        h = make_hist(f"h_comp_{proc}", "")
        vals = component_scaled_counts[proc]
        for i, v in enumerate(vals, start=1):
            h.SetBinContent(i, float(v))
        c = root_colors[idx % len(root_colors)]
        h.SetFillColorAlpha(c, 0.45)
        h.SetLineColor(c)
        h.SetLineWidth(1)
        h.SetTitle(f"{label} (a={fitted_yields[proc]:.2f})")
        comp_hists.append((proc, label, h, c))

    h_data.SetLineColor(ROOT.kBlack)
    h_data.SetLineWidth(2)
    h_data.SetMarkerStyle(20)
    h_data.SetMarkerSize(0.8)
    h_data.SetMarkerColor(ROOT.kBlack)

    h_model.SetLineColor(ROOT.kRed + 1)
    h_model.SetLineWidth(2)

    # Plot 1: stacked
    c1 = ROOT.TCanvas("c_fit_stack", "fit stack", 1000, 700)
    stack = ROOT.THStack("stack_fit", "Template fit stacked: h_{all} = #sum(a_{i} h_{i})")
    for _, _, h, _ in comp_hists:
        stack.Add(h)
    stack.Draw("HIST")
    stack.GetXaxis().SetTitle("Step deposited energy [MeV]")
    stack.GetYaxis().SetTitle("Counts")
    ymax = max(float(np.max(data_counts)), float(np.max(model_total)), 1.0) * 1.25
    stack.SetMaximum(ymax)
    h_data.Draw("E1 SAME")
    h_model.Draw("HIST SAME")

    leg1 = ROOT.TLegend(0.62, 0.52, 0.90, 0.90)
    leg1.SetBorderSize(0)
    leg1.SetFillStyle(0)
    for _, label, h, _ in comp_hists:
        leg1.AddEntry(h, h.GetTitle(), "f")
    leg1.AddEntry(h_data, f"{data_label} data", "lep")
    leg1.AddEntry(h_model, "sum(a_i*h_i)", "l")
    leg1.Draw()
    c1.SaveAs(str(out_stack_png))

    # Plot 2: components overlay
    c2 = ROOT.TCanvas("c_fit_overlay", "fit overlay", 1000, 700)
    h_frame = make_hist("h_frame", "All data with overlaid fitted components")
    h_frame.GetXaxis().SetTitle("Step deposited energy [MeV]")
    h_frame.GetYaxis().SetTitle("Counts")
    h_frame.SetMinimum(0.0)
    h_frame.SetMaximum(ymax)
    h_frame.Draw("HIST")

    x_centers = np.asarray(0.5 * (bin_edges[:-1] + bin_edges[1:]), dtype=float)
    y_data = np.asarray(data_counts, dtype=float)
    g_data = ROOT.TGraph(len(x_centers), x_centers, y_data)
    g_data.SetName("g_data_overlay")
    g_data.SetLineColor(ROOT.kBlack)
    g_data.SetMarkerColor(ROOT.kBlack)
    g_data.SetMarkerStyle(20)
    g_data.SetMarkerSize(0.8)
    g_data.SetLineWidth(2)
    g_data.Draw("LP SAME")

    overlay_hists = []
    overlay_graphs = []
    for _, _, h, c in comp_hists:
        h_line = h.Clone(f"{h.GetName()}_line")
        h_line.SetDirectory(0)
        # 仅用于可视化：平滑模板分量曲线，便于区分不同成分
        h_line.Smooth(1)
        overlay_hists.append(h_line)
        y_vals = np.asarray([h_line.GetBinContent(i + 1) for i in range(len(x_centers))], dtype=float)
        g = ROOT.TGraph(len(x_centers), x_centers, y_vals)
        g.SetName(f"g_{h.GetName()}_line")
        g.SetLineColor(c)
        g.SetLineWidth(2)
        g.Draw("L SAME")
        overlay_graphs.append(g)

    g_model = ROOT.TGraph(len(x_centers), x_centers, np.asarray(model_total, dtype=float))
    g_model.SetName("g_model_overlay")
    g_model.SetLineColor(ROOT.kRed + 1)
    g_model.SetLineWidth(3)
    g_model.Draw("L SAME")

    leg2 = ROOT.TLegend(0.62, 0.52, 0.90, 0.90)
    leg2.SetBorderSize(0)
    leg2.SetFillStyle(0)
    leg2.AddEntry(g_data, f"{data_label} data", "lp")
    legend_hists = []
    for _, _, h, c in comp_hists:
        h_line = h.Clone(f"{h.GetName()}_leg")
        h_line.SetDirectory(0)
        h_line.Smooth(1)
        h_line.SetFillStyle(0)
        h_line.SetLineColor(c)
        h_line.SetLineWidth(2)
        leg2.AddEntry(h_line, h.GetTitle(), "l")
        legend_hists.append(h_line)
    leg2.AddEntry(g_model, "sum(a_i*h_i)", "l")
    leg2.Draw()
    c2.Update()
    c2.SaveAs(str(out_comp_png))


def main():
    args = build_argparser().parse_args()
    project_root = Path(__file__).resolve().parent
    template_rel = args.input_dir if args.input_dir is not None else args.template_dir
    template_dir = (project_root / template_rel).resolve()
    data_file = (project_root / args.data_file).resolve()
    if not template_dir.exists():
        raise FileNotFoundError(f"template dir not found: {template_dir}")
    if not data_file.exists():
        raise FileNotFoundError(f"data file not found: {data_file}")

    add_local_dependency_paths(project_root)
    import templatefitter as tf
    import numpy as np

    cache_dir = project_root / "input" / "_cache_step_energy_mev"

    template_files, skipped_files = discover_window_template_files(template_dir)
    if len(template_files) == 0:
        raise RuntimeError(
            "No window template ROOT files found under template-dir. "
            "Expected names like 1_0__1_1.root (two underscore-decimal tokens separated by __)."
        )

    fit_range = (FIT_EMIN_MEV, FIT_EMAX_MEV)
    channel_name = "xray"
    observable = "energy_MeV"

    # 动态创建 process，按文件名排序后的顺序绑定
    processes = [f"p{i}" for i in range(len(template_files))]
    process_labels = [f.name for f in template_files]
    colors = [f"C{i % 10}" for i in range(len(template_files))]

    component_raw_data = {}
    for proc, src_file in zip(processes, template_files):
        data_mev = load_step_energy_mev(src_file, cache_dir)
        component_raw_data[proc] = data_mev

    bins, template_support, low_support_frac = pick_stable_bin_count(
        [component_raw_data[p] for p in processes],
        fit_range,
        FIT_BINS,
        args.min_template_support,
        args.min_bins,
    )
    print(
        f"adaptive bins: {FIT_BINS} -> {bins}, "
        f"low-support-bin fraction: {low_support_frac * 100:.2f}% "
        f"(threshold<{args.min_template_support})"
    )

    templates = {}
    for proc, src_file, color in zip(processes, template_files, colors):
        data_mev = component_raw_data[proc]
        h = tf.histograms.Hist1d(bins, fit_range, data=data_mev)
        templates[proc] = tf.templates.Template1d(proc, observable, h, color=color)

    # 组合模板 + data
    mct = tf.templates.MultiChannelTemplate()
    mct.define_channel(channel_name, bins, fit_range)
    for proc in processes:
        mct.define_process(proc)
        mct.add_template(channel_name, proc, templates[proc])

    data_mev = load_step_energy_mev(data_file, cache_dir)
    h_data = tf.histograms.Hist1d(bins, fit_range, data=data_mev)
    mct.add_data(**{channel_name: h_data})

    fitter = tf.TemplateFitter(mct, "iminuit")
    yield_max = float(len(data_mev))
    for proc in processes:
        fitter.set_parameter_bounds(f"{proc}_yield", (0.0, yield_max))
    result = fitter.do_fit(update_templates=True, get_hesse=True, verbose=0, fix_nui_params=True)

    # 按 h_all = sum(a_i * h_i) 计算可视化
    bin_edges = np.linspace(fit_range[0], fit_range[1], bins + 1)
    data_counts, _ = np.histogram(data_mev, bins=bin_edges)

    fitted_yields = {}
    component_scaled_counts = {}
    for proc in processes:
        fitted_yield = float(result.params.get_param_value(f"{proc}_yield"))
        fitted_yields[proc] = fitted_yield
        comp_counts, _ = np.histogram(component_raw_data[proc], bins=bin_edges)
        comp_counts = comp_counts.astype(float)
        comp_shape = comp_counts / comp_counts.sum() if comp_counts.sum() > 0 else np.zeros_like(comp_counts)
        component_scaled_counts[proc] = fitted_yield * comp_shape

    model_total = np.zeros_like(data_counts, dtype=float)
    for proc in processes:
        model_total += component_scaled_counts[proc]

    # Validation following TemplateFitter example patterns:
    # 1) GOF tests (Pearson and binned likelihood based)
    # 2) Optional profile likelihood scan for one process
    valid = np.asarray(model_total, dtype=float) > 1e-12
    dof = max(int(valid.sum()) - len(processes), 1)
    pearson_chi2 = float("nan")
    pearson_chi2_ndof = float("nan")
    pearson_p = float("nan")
    cowan_chi2 = float("nan")
    cowan_chi2_ndof = float("nan")
    cowan_p = float("nan")
    if np.any(valid):
        data_valid = np.asarray(data_counts, dtype=float)[valid]
        model_valid = np.asarray(model_total, dtype=float)[valid]
        pearson_chi2, pearson_chi2_ndof, pearson_p = tf.pearson_chi2_test(
            data_valid, model_valid, dof
        )
        cowan_chi2, cowan_chi2_ndof, cowan_p = tf.cowan_binned_likelihood_gof(
            data_valid, model_valid, dof
        )

    profile_result = None
    significance_result = None
    if args.validate_profile and len(processes) > 0:
        prof_proc = processes[0]
        try:
            profile_points, profile_nll, profile_hesse = fitter.profile(
                f"{prof_proc}_yield",
                num_cpu=max(1, int(args.profile_cpu)),
                num_points=max(5, int(args.profile_points)),
                sigma=float(args.profile_sigma),
                fix_nui_params=True,
            )
            profile_result = (prof_proc, profile_points, profile_nll, profile_hesse)
        except Exception as exc:
            profile_result = ("ERROR", str(exc))
        try:
            significance_result = fitter.get_significance(prof_proc, verbose=False, fix_nui_params=True)
        except Exception as exc:
            significance_result = f"ERROR: {exc}"

    pull_stats = None
    if args.toy_pull and len(processes) > 0:
        pull_proc = processes[0]
        try:
            toys = tf.ToyStudy(mct, "iminuit")
            toys.do_experiments(
                n_exp=max(1, int(args.toy_nexp)),
                max_tries=max(1, int(args.toy_max_tries)),
            )
            pulls = np.asarray(toys.get_toy_result_pulls(pull_proc), dtype=float)
            pulls = pulls[np.isfinite(pulls)]
            pull_mean = float(np.mean(pulls)) if pulls.size > 0 else float("nan")
            pull_sigma = float(np.std(pulls)) if pulls.size > 0 else float("nan")
            pull_stats = (pull_proc, pull_mean, pull_sigma, pulls)
        except Exception as exc:
            pull_stats = ("ERROR", str(exc), None, None)

    print("\n=== Fit Result ===")
    print("success:", result.succes)
    print("fcn_min_val:", result.fcn_min_val)
    print("data file:", data_file.name)
    print(f"pearson chi2/ndof: {pearson_chi2:.6g}/{dof} = {pearson_chi2_ndof:.6g}, p={pearson_p:.4g}")
    print(f"cowan   chi2/ndof: {cowan_chi2:.6g}/{dof} = {cowan_chi2_ndof:.6g}, p={cowan_p:.4g}")
    if significance_result is not None:
        print(f"significance({processes[0]}): {significance_result}")
    if profile_result is not None:
        if profile_result[0] == "ERROR":
            print(f"profile validation failed: {profile_result[1]}")
        else:
            proc_name, p_points, p_nll, p_hesse = profile_result
            print(
                f"profile validation done for {proc_name}: "
                f"{len(p_points)} points, finite(profile)={np.isfinite(p_nll).all()}"
            )
    if pull_stats is not None:
        if pull_stats[0] == "ERROR":
            print(f"pull validation failed: {pull_stats[1]}")
        else:
            pull_proc, pull_mean, pull_sigma, _ = pull_stats
            print(
                f"pull({pull_proc}) mean/sigma: {pull_mean:.6f}/{pull_sigma:.6f} "
                "(ideal: 0 / 1)"
            )
    if skipped_files:
        print("skipped non-template files:", ", ".join(skipped_files))

    # 结果表格：文件名(小数格式)、产额、百分比
    total_yield = sum(fitted_yields.values())
    table_rows = []
    for proc, src_file in zip(processes, template_files):
        file_label = window_label_from_path(src_file)
        yld = fitted_yields[proc]
        pct = (100.0 * yld / total_yield) if total_yield > 0 else 0.0
        table_rows.append((file_label, yld, pct))

    print("\n=== Yield Table ===")
    col_w = max(12, max(len(r[0]) for r in table_rows) if table_rows else 12)
    print(f"{'window':>{col_w}} | {'yield':>14} | {'percent':>10}")
    print("-" * (col_w + 14 + 12))
    for file_label, yld, pct in table_rows:
        print(f"{file_label:>{col_w}} | {yld:14.6f} | {pct:9.2f}%")

    csv_path = template_dir / args.csv_out
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "yield", "percent"])
        for file_label, yld, pct in table_rows:
            writer.writerow([file_label, f"{yld:.6f}", f"{pct:.2f}"])
    print("saved csv:", csv_path)

    out_stack_png = template_dir / "fit_to_all_stacked.png"
    out_comp_png = template_dir / "fit_to_all_components_overlay.png"
    draw_plots_with_root(
        bin_edges=bin_edges,
        data_counts=data_counts,
        model_total=model_total,
        component_scaled_counts=component_scaled_counts,
        processes=processes,
        process_labels=process_labels,
        fitted_yields=fitted_yields,
        data_label=data_file.name,
        out_stack_png=out_stack_png,
        out_comp_png=out_comp_png,
    )
    print("saved plot:", out_stack_png)
    print("saved plot:", out_comp_png)

    if pull_stats is not None and pull_stats[0] != "ERROR":
        import ROOT

        pull_proc, pull_mean, pull_sigma, pulls = pull_stats
        if pulls.size > 0:
            ROOT.gROOT.SetBatch(True)
            ROOT.gStyle.SetOptStat(1110)
            c_pull = ROOT.TCanvas("c_fit_pull", "fit pull", 900, 650)
            h_pull = ROOT.TH1D(
                "h_fit_pull",
                f"Pull distribution ({pull_proc});pull;Entries",
                60,
                -5.0,
                5.0,
            )
            h_pull.SetDirectory(0)
            for v in pulls:
                h_pull.Fill(float(v))
            h_pull.SetLineColor(ROOT.kBlue + 1)
            h_pull.SetLineWidth(2)
            h_pull.Draw("HIST")

            line0 = ROOT.TLine(0.0, 0.0, 0.0, h_pull.GetMaximum() * 1.05)
            line0.SetLineColor(ROOT.kRed + 1)
            line0.SetLineStyle(2)
            line0.Draw()

            text = ROOT.TLatex()
            text.SetNDC(True)
            text.SetTextSize(0.035)
            text.DrawLatex(0.58, 0.86, f"mean = {pull_mean:.4f}")
            text.DrawLatex(0.58, 0.81, f"sigma = {pull_sigma:.4f}")

            out_pull_png = template_dir / args.pull_png
            c_pull.SaveAs(str(out_pull_png))
            print("saved plot:", out_pull_png)


if __name__ == "__main__":
    main()

