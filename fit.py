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
    parser.add_argument("--csv-out", default="fit_yield_table.csv", help="Output CSV filename.")
    return parser


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
    import matplotlib.pyplot as plt
    import numpy as np

    cache_dir = project_root / "input" / "_cache_step_energy_mev"

    template_files, skipped_files = discover_window_template_files(template_dir)
    if len(template_files) == 0:
        raise RuntimeError(
            "No window template ROOT files found under template-dir. "
            "Expected names like 1_0__1_1.root (two underscore-decimal tokens separated by __)."
        )

    bins = FIT_BINS
    fit_range = (FIT_EMIN_MEV, FIT_EMAX_MEV)
    channel_name = "xray"
    observable = "energy_MeV"

    # 动态创建 process，按文件名排序后的顺序绑定
    processes = [f"p{i}" for i in range(len(template_files))]
    process_labels = [f.name for f in template_files]
    colors = plt.cm.tab10(np.linspace(0, 1, len(template_files)))

    templates = {}
    component_raw_data = {}
    for proc, src_file, color in zip(processes, template_files, colors):
        data_mev = load_step_energy_mev(src_file, cache_dir)
        component_raw_data[proc] = data_mev
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

    fitter = tf.TemplateFitter(mct, "scipy")
    yield_max = float(len(data_mev))
    for proc in processes:
        fitter.set_parameter_bounds(f"{proc}_yield", (0.0, yield_max))
    result = fitter.do_fit(update_templates=False, get_hesse=False, verbose=0)

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

    print("\n=== Fit Result ===")
    print("success:", result.succes)
    print("fcn_min_val:", result.fcn_min_val)
    print("data file:", data_file.name)
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

    # 图1：堆叠
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    bin_width = bin_edges[1] - bin_edges[0]
    fig_stack, ax_stack = plt.subplots(1, 1, figsize=(9, 6), dpi=150)
    running_bottom = np.zeros_like(model_total)
    for proc, label, color in zip(processes, process_labels, colors):
        vals = component_scaled_counts[proc]
        ax_stack.bar(
            bin_centers,
            vals,
            width=bin_width,
            bottom=running_bottom,
            color=color,
            alpha=0.55,
            edgecolor="none",
            label=f"{label} (a={fitted_yields[proc]:.2f})",
            align="center",
        )
        running_bottom += vals
    ax_stack.step(bin_edges[:-1], data_counts, where="post", color="black", lw=1.5, label=f"{data_file.name} data")
    ax_stack.step(bin_edges[:-1], model_total, where="post", color="crimson", lw=1.5, label="sum(a_i*h_i)")
    ax_stack.set_xlabel("Step deposited energy [MeV]")
    ax_stack.set_ylabel("Counts")
    ax_stack.set_title("Template fit stacked: h_all = sum(a_i * h_i)")
    ax_stack.legend()
    out_stack_png = template_dir / "fit_to_all_stacked.png"
    fig_stack.savefig(out_stack_png, bbox_inches="tight")
    print("saved plot:", out_stack_png)

    # 图2：分量叠加
    fig_comp, ax_comp = plt.subplots(1, 1, figsize=(10, 7), dpi=150)
    ax_comp.step(bin_edges[:-1], data_counts, where="post", color="black", lw=1.8, label=f"{data_file.name} data")
    for proc, label, color in zip(processes, process_labels, colors):
        ax_comp.step(
            bin_edges[:-1],
            component_scaled_counts[proc],
            where="post",
            color=color,
            lw=1.4,
            label=f"{label} (a={fitted_yields[proc]:.2f})",
        )
    ax_comp.step(bin_edges[:-1], model_total, where="post", color="crimson", lw=1.8, label="sum(a_i*h_i)")
    ax_comp.set_title("All data with overlaid fitted components")
    ax_comp.set_xlabel("Step deposited energy [MeV]")
    ax_comp.set_ylabel("Counts")
    ax_comp.legend(loc="upper right")
    out_comp_png = template_dir / "fit_to_all_components_overlay.png"
    fig_comp.savefig(out_comp_png, bbox_inches="tight")
    print("saved plot:", out_comp_png)


if __name__ == "__main__":
    main()

