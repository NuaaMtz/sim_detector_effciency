#!/usr/bin/env python3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import uproot

# ===== Global config =====
ROOT_FILE = "build/6_0_7_0.root"
TREE_NAME = "tree_save_evnets_energy"
BRANCH_NAME = "energy"
OUTPUT_PNG = "branch_hist.png"

BINS = 100
XRANGE = None  # e.g. (1.0, 7.0), None means auto range
TITLE = "Branch Histogram"
XLABEL = f"{BRANCH_NAME}"
YLABEL = "Counts"
# =========================


def load_branch_array(root_file: Path, tree_name: str, branch_name: str) -> np.ndarray:
    tree = uproot.open(f"{root_file}:{tree_name}")
    arr = tree[branch_name].array(library="np")
    return np.asarray(arr, dtype=float).ravel()


def main() -> None:
    root_path = Path(ROOT_FILE).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"ROOT file not found: {root_path}")

    data = load_branch_array(root_path, TREE_NAME, BRANCH_NAME)
    if data.size == 0:
        raise RuntimeError("Selected branch has no data.")

    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    ax.hist(data, bins=BINS, range=XRANGE, histtype="stepfilled", alpha=0.75, edgecolor="black")
    ax.set_title(TITLE)
    ax.set_xlabel(XLABEL)
    ax.set_ylabel(YLABEL)
    ax.grid(alpha=0.2)

    out = Path(OUTPUT_PNG).resolve()
    fig.savefig(out, bbox_inches="tight")
    print(f"saved plot: {out}")


if __name__ == "__main__":
    main()
