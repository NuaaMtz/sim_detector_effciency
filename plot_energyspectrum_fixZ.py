#!/usr/bin/env python3
"""Overlay energy spectra at fixed Z for multiple R values."""

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import uproot


TREE_NAME = "tree_save_evnets_energy"
BRANCH_NAME = "energy"
FILENAME_RE = re.compile(
    r"^myfilename_R(?P<ri>\d+)p(?P<rf>\d+)_Z(?P<zi>\d+)p(?P<zf>\d+)\.root$"
)


def parse_value(int_part: str, frac_part: str) -> float:
    return float(f"{int_part}.{frac_part}")


def parse_rz_from_filename(path: Path) -> Optional[Tuple[float, float]]:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    r_val = parse_value(match.group("ri"), match.group("rf"))
    z_val = parse_value(match.group("zi"), match.group("zf"))
    return r_val, z_val


def collect_files_for_fixed_z(
    data_dir: Path, fixed_z: float, atol: float
) -> List[Tuple[Path, float]]:
    selected: List[Tuple[Path, float]] = []
    for root_file in sorted(data_dir.glob("myfilename_R*p*_Z*p*.root")):
        parsed = parse_rz_from_filename(root_file)
        if parsed is None:
            continue
        r_val, z_val = parsed
        if np.isclose(z_val, fixed_z, atol=atol, rtol=0.0):
            selected.append((root_file, r_val))
    selected.sort(key=lambda item: item[1])
    return selected


def read_energy_array(root_path: Path) -> np.ndarray:
    with uproot.open(root_path) as file:
        if TREE_NAME not in file:
            raise KeyError(f"{root_path.name}: missing tree '{TREE_NAME}'")
        tree = file[TREE_NAME]
        if BRANCH_NAME not in tree:
            raise KeyError(f"{root_path.name}: missing branch '{BRANCH_NAME}'")
        energy = tree[BRANCH_NAME].array(library="np")
    return energy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plot overlaid energy spectra for fixed Z and varying R."
    )
    parser.add_argument(
        "--data-dir",
        default="build",
        help="Directory containing myfilename_R..._Z....root files.",
    )
    parser.add_argument(
        "--fixed-z",
        type=float,
        default=500.0,
        help="Fixed Z value used to filter files (same unit as filename).",
    )
    parser.add_argument(
        "--z-atol",
        type=float,
        default=1e-6,
        help="Absolute tolerance when matching Z from filename.",
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=300,
        help="Histogram bins for spectra.",
    )
    parser.add_argument(
        "--emin",
        type=float,
        default=None,
        help="Minimum energy for histogram range (optional).",
    )
    parser.add_argument(
        "--emax",
        type=float,
        default=None,
        help="Maximum energy for histogram range (optional).",
    )
    parser.add_argument(
        "--density",
        action="store_true",
        help="Normalize each histogram to probability density.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output figure path. Default: spectrum_fixZ_<Z>.png",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    matched = collect_files_for_fixed_z(data_dir, args.fixed_z, args.z_atol)
    if not matched:
        print(f"No files found for fixed Z={args.fixed_z} in {data_dir}")
        return 1

    spectra: Dict[float, np.ndarray] = {}
    for root_path, r_val in matched:
        energy = read_energy_array(root_path)
        if energy.size == 0:
            print(f"Skip empty energy branch: {root_path.name}")
            continue
        spectra[r_val] = energy

    if not spectra:
        print("No non-empty spectra to plot.")
        return 1

    all_energy = np.concatenate(list(spectra.values()))
    e_min = args.emin if args.emin is not None else float(np.min(all_energy))
    e_max = args.emax if args.emax is not None else float(np.max(all_energy))
    if e_max <= e_min:
        raise ValueError(f"Invalid energy range: [{e_min}, {e_max}]")

    plt.figure(figsize=(12, 6))
    for r_val in sorted(spectra.keys()):
        plt.hist(
            spectra[r_val],
            bins=args.bins,
            range=(e_min, e_max),
            histtype="step",
            linewidth=1.6,
            density=args.density,
            label=f"R={r_val:g}",
        )

    plt.title(f"Energy spectra at fixed Z={args.fixed_z:g}")
    plt.xlabel("Energy")
    plt.ylabel("Density" if args.density else "Counts")
    plt.legend(
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        borderaxespad=0.0,
        frameon=True,
    )
    plt.grid(alpha=0.3)
    plt.tight_layout(rect=(0, 0, 0.82, 1))

    output = (
        Path(args.output).resolve()
        if args.output
        else Path.cwd() / f"spectrum_fixZ_{args.fixed_z:g}.png"
    )
    plt.savefig(output, dpi=200)
    print(f"Saved plot: {output}")
    print(f"Used files: {len(spectra)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
