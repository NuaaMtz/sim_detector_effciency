#!/usr/bin/env python3
"""
Generate many Geant4 macro files from a fixed template (same as run.mac layout),
without reading run.mac from disk. Scan spectrum min/max in MeV with a step
(window width = step): (emin, emin+step), (emin+step, emin+2*step), ... until
the window upper edge does not exceed emax.

After each job, rename the default ROOT output to a tokenized name, e.g.
1.1–1.2 MeV -> 1_1_1_2.root (dots -> underscores; integers get a _0 suffix).
"""

import argparse
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path
from typing import List


# Copied from run.mac (geometry + init + beamOn). Spectrum block is injected.
RUN_MAC_TEMPLATE = """########################################
# 先设置几何参数（必须带单位）
/mydet/detectorRadius 20 cm
/mydet/sourceDetectorDistance 1 m


/run/initialize
########################################
# 修改粒子源（RootSpectrum，由脚本写入能量窗口）
{spectrum_block}
########################################
# 设置事件数，开始运行
/run/beamOn {n_events}
########################################
"""


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=(
            "Generate macros from embedded run.mac template; scan "
            "/mydet/setSpectrumMinEnergy / setSpectrumMaxEnergy in MeV."
        )
    )
    parser.add_argument(
        "--emin",
        default="1",
        help="Lower edge of first window [MeV], e.g. 1 or 1.0.",
    )
    parser.add_argument(
        "--emax",
        default="7",
        help="Upper edge of last allowed window [MeV], e.g. 7 or 7.5.",
    )
    parser.add_argument(
        "--step",
        default="1",
        help="Window width and stride [MeV]. Pairs: (E, E+step).",
    )
    parser.add_argument(
        "--spectrum-root",
        default="input/all.root",
        help=(
            "Input spectrum ROOT file (absolute or relative to project root). "
            f"Default: {script_dir / 'all.root'}"
        ),
    )
    parser.add_argument(
        "--spectrum-tree",
        default="tree_save_evnets_energy",
        help="TTree name for spectrum sampling.",
    )
    parser.add_argument(
        "--spectrum-branch",
        default="energy",
        help="Branch/leaf name for spectrum sampling.",
    )
    parser.add_argument(
        "--work-dir",
        default=str(script_dir / "input/spectrum_scan_macros"),
        help="Directory to write generated .mac files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(script_dir),
        help="Directory to place renamed ROOT files after each job.",
    )
    parser.add_argument(
        "--n-events",
        default="1000000",
        help="Value for /run/beamOn in each macro.",
    )
    parser.add_argument(
        "--default-output",
        default="myfilename_R200p000000_Z1000p000000.root",
        help="Exact output filename produced under build/ (relative to project root).",
    )
    parser.add_argument(
        "--sim-cmd",
        default="cd build && ./main {mac}",
        help='Run one job; must contain "{mac}" (path to generated macro).',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only write macros and print commands; do not run simulation.",
    )
    return parser.parse_args()


def normalize_decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def window_starts(emin: str, emax: str, step: str) -> List[Decimal]:
    getcontext().prec = 28
    e_lo = Decimal(emin)
    e_hi = Decimal(emax)
    w = Decimal(step)
    if w <= 0:
        raise ValueError("step must be > 0")
    if e_hi < e_lo:
        raise ValueError("emax must be >= emin")

    eps = Decimal("1e-18")
    starts = []
    current = e_lo
    while current + w <= e_hi + eps:
        starts.append(current)
        current += w
    return starts


def energy_to_token(energy_text: str) -> str:
    token = energy_text.replace(".", "_")
    return token if "_" in token else f"{token}_0"


def output_root_basename(e_min_text: str, e_max_text: str) -> str:
    return f"{energy_to_token(e_min_text)}_{energy_to_token(e_max_text)}.root"


def spectrum_block(
    root_path: str, tree: str, branch: str, e_min: str, e_max: str
) -> str:
    return "\n".join(
        [
            "/mydet/setSource RootSpectrum",
            f"/mydet/setSpectrumRootFile {root_path}",
            f"/mydet/setSpectrumTree {tree}",
            f"/mydet/setSpectrumBranch {branch}",
            f"/mydet/setSpectrumMinEnergy {e_min} MeV",
            f"/mydet/setSpectrumMaxEnergy {e_max} MeV",
        ]
    )


def write_macro(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_sim(project_root: Path, sim_cmd: str, mac_path: Path, log_path: Path) -> int:
    cmd = sim_cmd.replace("{mac}", str(mac_path.resolve()))
    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.run(
            cmd,
            cwd=str(project_root),
            shell=True,
            text=True,
            stdout=logf,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return proc.returncode


def rename_build_output(
    project_root: Path,
    build_relative: str,
    dest_name: str,
) -> bool:
    src = project_root / "build" / build_relative
    if not src.is_file():
        return False
    # 强制原地改名：无论传入什么参数，都保持在 build/ 目录内。
    dst = src.with_name(dest_name)
    src.replace(dst)
    return True


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    work_dir = Path(args.work_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if "{mac}" not in args.sim_cmd:
        print('Error: --sim-cmd must include "{mac}".', file=sys.stderr)
        return 1

    spectrum_root = Path(args.spectrum_root)
    if not spectrum_root.is_absolute():
        spectrum_root = (project_root / spectrum_root).resolve()
    if not args.dry_run and not spectrum_root.is_file():
        print(f"Error: spectrum ROOT not found: {spectrum_root}", file=sys.stderr)
        return 1

    try:
        starts = window_starts(args.emin, args.emax, args.step)
    except Exception as exc:
        print(f"Error: invalid scan parameters: {exc}", file=sys.stderr)
        return 1
    if not starts:
        print(
            "Error: no windows; need emin + step <= emax (e.g. emin=1 emax=7 step=1).",
            file=sys.stderr,
        )
        return 1

    print("Spectrum window scan:")
    print(f"  PROJECT_ROOT: {project_root}")
    print(f"  WORK_DIR: {work_dir}")
    print(f"  OUTPUT_DIR: {output_dir}")
    print(f"  WINDOWS [MeV]: {args.emin} .. {args.emax}, step={args.step}")
    print(f"  SPECTRUM: {spectrum_root}")
    print(f"  TREE/BRANCH: {args.spectrum_tree} / {args.spectrum_branch}")
    print(f"  DEFAULT_BUILD_OUTPUT: build/{args.default_output}")
    print("")

    w = Decimal(args.step)
    for e_start in starts:
        e_end = e_start + w
        e_min_text = normalize_decimal_text(e_start)
        e_max_text = normalize_decimal_text(e_end)
        out_name = output_root_basename(e_min_text, e_max_text)
        token = out_name[:-5]  # without .root for macro filename
        mac_path = work_dir / f"run_{token}.mac"
        log_path = work_dir / f"run_{token}.log"

        block = spectrum_block(
            str(spectrum_root),
            args.spectrum_tree,
            args.spectrum_branch,
            e_min_text,
            e_max_text,
        )
        body = RUN_MAC_TEMPLATE.format(
            spectrum_block=block,
            n_events=args.n_events.strip(),
        )
        write_macro(mac_path, body)
        print(f"[Macro] [{e_min_text}, {e_max_text}] MeV -> {mac_path.name}")

        if args.dry_run:
            continue

        ret = run_sim(project_root, args.sim_cmd, mac_path, log_path)
        if ret != 0:
            print(f"  [WARN] simulation failed, see: {log_path}")
            continue

        ok = rename_build_output(project_root, args.default_output, out_name)
        if not ok:
            print(
                f"  [WARN] output not found: build/{args.default_output} "
                f"(expected after job [{e_min_text}, {e_max_text}] MeV)"
            )
        else:
            print(f"  [OK] saved: {project_root / 'build' / out_name}")

    print("")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
