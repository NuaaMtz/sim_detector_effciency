import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


FIT_EMIN_MEV = 1.0
FIT_EMAX_MEV = 7.0
FIT_BINS = 100
DATA_TREE = "tree_save_evnets_energy"
DATA_BRANCH = "energy"


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Fit all.root spectrum by non-negative linear combination of template ROOT spectra "
            "under build/. Uses projected-gradient NNLS (robust alternative to previous fitter)."
        )
    )
    parser.add_argument("--data-file", default="input/all.root", help="Target data ROOT path.")
    parser.add_argument("--template-dir", default="build", help="Template ROOT directory.")
    parser.add_argument("--emin", type=float, default=FIT_EMIN_MEV, help="Fit range min in MeV.")
    parser.add_argument("--emax", type=float, default=FIT_EMAX_MEV, help="Fit range max in MeV.")
    parser.add_argument("--bins", type=int, default=FIT_BINS, help="Histogram bins.")
    parser.add_argument("--tree", default=DATA_TREE, help="ROOT tree name.")
    parser.add_argument("--branch", default=DATA_BRANCH, help="ROOT branch name.")
    parser.add_argument(
        "--smooth-lambda",
        type=float,
        default=1e-2,
        help="Smoothness regularization strength on adjacent weights (>=0).",
    )
    parser.add_argument(
        "--l2-lambda",
        type=float,
        default=1e-6,
        help="L2 regularization strength on weights (>=0).",
    )
    parser.add_argument("--max-iter", type=int, default=5000, help="Maximum optimization iterations.")
    parser.add_argument("--tol", type=float, default=1e-8, help="Relative tolerance for convergence.")
    parser.add_argument("--csv-out", default="fit_v2_yield_table.csv", help="CSV output filename.")
    parser.add_argument("--plot-prefix", default="fit_v2", help="Output plot prefix.")
    return parser.parse_args()


def cache_paths(root_file: Path, cache_dir: Path):
    key = hashlib.sha1(str(root_file.resolve()).encode("utf-8")).hexdigest()[:16]
    base = f"{root_file.stem}_{key}"
    return cache_dir / f"{base}.npy", cache_dir / f"{base}.json"


def load_mev_from_root(root_file: Path, tree: str, branch: str, cache_dir: Path):
    import numpy as np
    import uproot

    cache_npy, cache_meta = cache_paths(root_file, cache_dir)
    if cache_npy.exists() and cache_meta.exists():
        try:
            meta = json.loads(cache_meta.read_text(encoding="utf-8"))
            stat = root_file.stat()
            if (
                meta.get("source_path") == str(root_file.resolve())
                and meta.get("source_mtime_ns") == stat.st_mtime_ns
                and meta.get("source_size") == stat.st_size
                and meta.get("tree") == tree
                and meta.get("branch") == branch
                and meta.get("unit") == "MeV"
            ):
                return np.load(cache_npy, allow_pickle=False)
        except Exception:
            pass

    arr = np.asarray(uproot.open(f"{root_file}:{tree}")[branch].array(library="np"), dtype=float)
    cache_npy.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_npy, arr, allow_pickle=False)
    stat = root_file.stat()
    meta = {
        "source_path": str(root_file.resolve()),
        "source_mtime_ns": stat.st_mtime_ns,
        "source_size": stat.st_size,
        "tree": tree,
        "branch": branch,
        "unit": "MeV",
    }
    cache_meta.write_text(json.dumps(meta, ensure_ascii=True, indent=2), encoding="utf-8")
    return arr


def parse_template_energy_key(stem: str):
    # 1_0__1_1
    m = re.fullmatch(r"(\d+(?:_\d+)?)__(\d+(?:_\d+)?)", stem)
    if m:
        lo = float(m.group(1).replace("_", "."))
        hi = float(m.group(2).replace("_", "."))
        return (0, 0.5 * (lo + hi))
    # 1_0_1_1
    p = stem.split("_")
    if len(p) == 4 and all(x.isdigit() for x in p):
        lo = float(f"{p[0]}.{p[1]}")
        hi = float(f"{p[2]}.{p[3]}")
        return (0, 0.5 * (lo + hi))
    # 1 or 1_5
    if re.fullmatch(r"\d+", stem):
        return (1, float(stem))
    if re.fullmatch(r"\d+_\d+", stem):
        return (1, float(stem.replace("_", ".")))
    return None


def discover_templates(template_dir: Path):
    templ = []
    skipped = []
    for f in sorted(template_dir.glob("*.root")):
        k = parse_template_energy_key(f.stem)
        if k is None:
            skipped.append(f.name)
            continue
        templ.append((k[0], k[1], f))
    templ.sort(key=lambda x: (x[0], x[1], x[2].name))
    return [x[2] for x in templ], skipped


def build_histograms(data_mev, template_arrays, bins, fit_range):
    import numpy as np

    bin_edges = np.linspace(fit_range[0], fit_range[1], bins + 1)
    y, _ = np.histogram(data_mev, bins=bin_edges)
    cols = []
    raw_counts = []
    for arr in template_arrays:
        c, _ = np.histogram(arr, bins=bin_edges)
        raw_counts.append(c.astype(float))
        s = float(c.sum())
        if s <= 0:
            cols.append(np.zeros_like(c, dtype=float))
        else:
            cols.append(c.astype(float) / s)  # shape column
    A = np.column_stack(cols) if cols else np.zeros((bins, 0), dtype=float)
    return y.astype(float), A, np.asarray(raw_counts, dtype=float), bin_edges


def solve_nonnegative_weights(y, A, smooth_lambda=1e-2, l2_lambda=1e-6, max_iter=5000, tol=1e-8):
    import numpy as np

    m, n = A.shape
    if n == 0:
        raise RuntimeError("No templates to fit.")
    if np.all(y <= 0):
        return np.zeros(n, dtype=float), {"iterations": 0, "converged": True, "obj": 0.0}

    # D: (n-1) x n for adjacent smoothness penalty
    if n >= 2:
        D = np.zeros((n - 1, n), dtype=float)
        for i in range(n - 1):
            D[i, i] = -1.0
            D[i, i + 1] = 1.0
        DtD = D.T @ D
    else:
        DtD = np.zeros((n, n), dtype=float)

    AtA = A.T @ A
    Aty = A.T @ y

    # Lipschitz upper bound for gradient
    H = AtA + smooth_lambda * DtD + l2_lambda * np.eye(n, dtype=float)
    eig_max = float(np.linalg.eigvalsh(H).max()) if n > 1 else float(H[0, 0])
    step = 1.0 / max(eig_max, 1e-12)

    # Initial guess: non-negative least "matched filter"
    w = np.maximum(Aty, 0.0)
    if w.sum() <= 0:
        w = np.ones(n, dtype=float)
    w *= y.sum() / max((A @ w).sum(), 1e-12)

    def objective(v):
        r = A @ v - y
        reg_s = 0.0 if n < 2 else smooth_lambda * float(v.T @ (DtD @ v))
        reg_l2 = l2_lambda * float(v.T @ v)
        return 0.5 * float(r.T @ r) + 0.5 * reg_s + 0.5 * reg_l2

    obj_prev = objective(w)
    converged = False
    for it in range(1, max_iter + 1):
        grad = AtA @ w - Aty + smooth_lambda * (DtD @ w) + l2_lambda * w
        w_new = np.maximum(w - step * grad, 0.0)
        # keep total scale near data integral
        s = float((A @ w_new).sum())
        if s > 0:
            w_new *= y.sum() / s

        rel = np.linalg.norm(w_new - w) / max(np.linalg.norm(w), 1e-12)
        w = w_new
        obj = objective(w)
        if abs(obj_prev - obj) / max(abs(obj_prev), 1.0) < tol and rel < 10 * tol:
            converged = True
            obj_prev = obj
            break
        obj_prev = obj

    return w, {"iterations": it, "converged": converged, "obj": obj_prev}


def draw_v2_plots_with_root(bin_edges, y, model_total, comp_scaled, template_files, percentages, out1, out2):
    import ROOT
    import numpy as np

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)

    nbins = len(bin_edges) - 1
    xlow = float(bin_edges[0])
    xhigh = float(bin_edges[-1])

    def make_hist(name, title=""):
        h = ROOT.TH1D(name, title, nbins, xlow, xhigh)
        h.SetDirectory(0)
        return h

    h_data = make_hist("h_v2_data")
    h_model = make_hist("h_v2_model")
    for i, v in enumerate(y, start=1):
        h_data.SetBinContent(i, float(v))
    for i, v in enumerate(model_total, start=1):
        h_model.SetBinContent(i, float(v))
    h_data.SetLineColor(ROOT.kBlack)
    h_data.SetMarkerColor(ROOT.kBlack)
    h_data.SetMarkerStyle(20)
    h_data.SetLineWidth(2)
    h_model.SetLineColor(ROOT.kRed + 1)
    h_model.SetLineWidth(2)

    root_colors = [
        ROOT.kAzure + 1,
        ROOT.kOrange + 7,
        ROOT.kGreen + 2,
        ROOT.kMagenta + 1,
        ROOT.kCyan + 1,
        ROOT.kViolet + 6,
        ROOT.kTeal + 3,
        ROOT.kPink + 6,
        ROOT.kSpring + 5,
        ROOT.kRed + 1,
    ]

    comp_hists = []
    for i, f in enumerate(template_files):
        h = make_hist(f"h_v2_comp_{i}")
        vals = comp_scaled[i]
        for b, v in enumerate(vals, start=1):
            h.SetBinContent(b, float(v))
        c = root_colors[i % len(root_colors)]
        h.SetFillColorAlpha(c, 0.45)
        h.SetLineColor(c)
        h.SetLineWidth(1)
        h.SetTitle(f"{f.stem} ({percentages[i]:.1f}%)")
        comp_hists.append((h, c))

    ymax = max(float(np.max(y)), float(np.max(model_total)), 1.0) * 1.25

    # stacked
    c1 = ROOT.TCanvas("c_v2_stack", "v2 stack", 1000, 700)
    stack = ROOT.THStack("stack_v2", "Fit V2: data #approx #sum(weight_{i} * template_{i})")
    for h, _ in comp_hists:
        stack.Add(h)
    stack.Draw("HIST")
    stack.GetXaxis().SetTitle("Deposited energy [MeV]")
    stack.GetYaxis().SetTitle("Counts")
    stack.SetMaximum(ymax)
    h_data.Draw("E1 SAME")
    h_model.Draw("HIST SAME")
    leg1 = ROOT.TLegend(0.58, 0.50, 0.90, 0.90)
    leg1.SetBorderSize(0)
    leg1.SetFillStyle(0)
    for h, _ in comp_hists:
        leg1.AddEntry(h, h.GetTitle(), "f")
    leg1.AddEntry(h_data, "data", "lep")
    leg1.AddEntry(h_model, "model", "l")
    leg1.Draw()
    c1.SaveAs(str(out1))

    # ratio with two pads
    c2 = ROOT.TCanvas("c_v2_ratio", "v2 ratio", 1000, 800)
    pad_up = ROOT.TPad("pad_up", "pad_up", 0.0, 0.30, 1.0, 1.0)
    pad_dn = ROOT.TPad("pad_dn", "pad_dn", 0.0, 0.0, 1.0, 0.30)
    pad_up.SetBottomMargin(0.02)
    pad_dn.SetTopMargin(0.02)
    pad_dn.SetBottomMargin(0.30)
    pad_up.Draw()
    pad_dn.Draw()

    pad_up.cd()
    frame_up = make_hist("h_v2_frame_up")
    frame_up.SetMinimum(0.0)
    frame_up.SetMaximum(ymax)
    frame_up.GetYaxis().SetTitle("Counts")
    frame_up.GetXaxis().SetLabelSize(0)
    frame_up.Draw("HIST")
    h_data.Draw("E1 SAME")
    h_model.Draw("HIST SAME")
    leg2 = ROOT.TLegend(0.70, 0.72, 0.90, 0.90)
    leg2.SetBorderSize(0)
    leg2.SetFillStyle(0)
    leg2.AddEntry(h_data, "data", "lep")
    leg2.AddEntry(h_model, "model", "l")
    leg2.Draw()

    pad_dn.cd()
    h_ratio = make_hist("h_v2_ratio")
    for i in range(1, nbins + 1):
        m = h_model.GetBinContent(i)
        d = h_data.GetBinContent(i)
        h_ratio.SetBinContent(i, float(d / m) if m > 1e-12 else 0.0)
    h_ratio.SetMinimum(0.0)
    h_ratio.SetMaximum(2.0)
    h_ratio.SetLineColor(ROOT.kBlue + 1)
    h_ratio.SetLineWidth(2)
    h_ratio.GetYaxis().SetTitle("data/model")
    h_ratio.GetXaxis().SetTitle("Deposited energy [MeV]")
    h_ratio.GetYaxis().SetNdivisions(505)
    h_ratio.Draw("HIST")
    line = ROOT.TLine(xlow, 1.0, xhigh, 1.0)
    line.SetLineStyle(2)
    line.SetLineColor(ROOT.kGray + 2)
    line.Draw()

    c2.SaveAs(str(out2))


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    data_file = (project_root / args.data_file).resolve()
    template_dir = (project_root / args.template_dir).resolve()
    if not data_file.exists():
        raise FileNotFoundError(f"data file not found: {data_file}")
    if not template_dir.exists():
        raise FileNotFoundError(f"template dir not found: {template_dir}")

    cache_dir = project_root / "input" / "_cache_fit_v2_mev"
    template_files, skipped = discover_templates(template_dir)
    if not template_files:
        raise RuntimeError(f"No valid template ROOT files found under {template_dir}")

    data_mev = load_mev_from_root(data_file, args.tree, args.branch, cache_dir)
    template_arrays = [load_mev_from_root(f, args.tree, args.branch, cache_dir) for f in template_files]

    y, A, raw_template_counts, bin_edges = build_histograms(
        data_mev, template_arrays, args.bins, (args.emin, args.emax)
    )

    # Filter zero-information templates in fit range
    keep = [i for i in range(A.shape[1]) if A[:, i].sum() > 0]
    if not keep:
        raise RuntimeError("All templates are empty in fit range. Check energy window and templates.")
    if len(keep) < A.shape[1]:
        template_files = [template_files[i] for i in keep]
        A = A[:, keep]
        raw_template_counts = raw_template_counts[keep, :]

    w, info = solve_nonnegative_weights(
        y,
        A,
        smooth_lambda=args.smooth_lambda,
        l2_lambda=args.l2_lambda,
        max_iter=args.max_iter,
        tol=args.tol,
    )

    import numpy as np

    model_total = A @ w
    comp_scaled = np.array([w[i] * A[:, i] for i in range(A.shape[1])], dtype=float)
    percentages = 100.0 * w / max(w.sum(), 1e-12)

    # Diagnostics
    resid = y - model_total
    chi2 = float(np.sum((resid**2) / np.maximum(y, 1.0)))
    ndof = max(len(y) - len(w), 1)

    print("\n=== Fit V2 Result (NNLS) ===")
    print(f"data file: {data_file}")
    print(f"templates used: {len(template_files)}")
    print(f"skipped templates: {len(skipped)}")
    print(f"converged: {info['converged']}, iterations: {info['iterations']}, objective: {info['obj']:.6e}")
    print(f"chi2/ndof: {chi2:.4f}/{ndof} = {chi2/ndof:.4f}")

    rows = []
    for i, f in enumerate(template_files):
        rows.append((f.stem, float(w[i]), float(percentages[i])))
    rows.sort(key=lambda x: x[0])

    print("\n=== Weight Table ===")
    print(f"{'template':>20} | {'weight':>14} | {'percent':>10}")
    print("-" * 50)
    for name, wi, pi in rows:
        print(f"{name:>20} | {wi:14.6f} | {pi:9.2f}%")

    csv_path = template_dir / args.csv_out
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["template", "weight", "percent"])
        for name, wi, pi in rows:
            wr.writerow([name, f"{wi:.6f}", f"{pi:.2f}"])
    print(f"saved csv: {csv_path}")

    out1 = template_dir / f"{args.plot_prefix}_stacked.png"
    out2 = template_dir / f"{args.plot_prefix}_ratio.png"
    draw_v2_plots_with_root(
        bin_edges=bin_edges,
        y=y,
        model_total=model_total,
        comp_scaled=comp_scaled,
        template_files=template_files,
        percentages=percentages,
        out1=out1,
        out2=out2,
    )
    print(f"saved plot: {out1}")
    print(f"saved plot: {out2}")


if __name__ == "__main__":
    main()
