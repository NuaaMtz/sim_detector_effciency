#!/usr/bin/env python3
"""Batch submit Geant4 runs with configurable geometry/source scan."""

from __future__ import annotations

import argparse
import itertools
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


RADIUS_CMD = "/mydet/detectorRadius"
DIST_CMD = "/mydet/sourceDetectorDistance"
SOURCE_CMD = "/mydet/setSource"
BEAM_CMD = "/run/beamOn"
WORLD_HALF_LENGTH_CM = 100.0
UNIT_TO_CM = {"mm": 0.1, "cm": 1.0, "m": 100.0}


@dataclass(frozen=True)
class Job:
    idx: int
    radius: float
    distance: float
    source: str
    events: int
    radius_unit: str
    distance_unit: str


def float_range(start: float, end: float, step: float) -> List[float]:
    if step <= 0:
        raise ValueError("step must be > 0")
    if end < start:
        raise ValueError("end must be >= start")
    values: List[float] = []
    current = start
    eps = step * 1e-9
    while current <= end + eps:
        values.append(round(current, 10))
        current += step
    return values


def to_cm(value: float, unit: str) -> float:
    if unit not in UNIT_TO_CM:
        raise ValueError(f"Unsupported unit '{unit}'. Supported: mm, cm, m")
    return value * UNIT_TO_CM[unit]


def from_cm(value_cm: float, unit: str) -> float:
    if unit not in UNIT_TO_CM:
        raise ValueError(f"Unsupported unit '{unit}'. Supported: mm, cm, m")
    return value_cm / UNIT_TO_CM[unit]


def fmt_number(value: float) -> str:
    if math.isclose(value, round(value)):
        return str(int(round(value)))
    return f"{value:.10g}"


def replace_or_append(lines: Sequence[str], command: str, new_line: str) -> List[str]:
    updated: List[str] = []
    replaced = False
    for line in lines:
        if line.strip().startswith(command):
            updated.append(new_line)
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(new_line)
    return updated


def build_macro(template_lines: Sequence[str], job: Job) -> str:
    lines = list(template_lines)
    lines = replace_or_append(
        lines,
        RADIUS_CMD,
        f"{RADIUS_CMD} {fmt_number(job.radius)} {job.radius_unit}",
    )
    lines = replace_or_append(
        lines,
        DIST_CMD,
        f"{DIST_CMD} {fmt_number(job.distance)} {job.distance_unit}",
    )
    lines = replace_or_append(lines, SOURCE_CMD, f"{SOURCE_CMD} {job.source}")
    lines = replace_or_append(lines, BEAM_CMD, f"{BEAM_CMD} {job.events}")
    return "\n".join(lines).rstrip() + "\n"


def generate_jobs(args: argparse.Namespace) -> Iterable[Job]:
    if args.scan_mode == "mutual":
        radius_cm = to_cm(args.fixed_radius, args.radius_unit)
        distance_cm = to_cm(args.fixed_distance, args.distance_unit)
        step_cm = 1.0
        min_positive_cm = 1.0

        if radius_cm <= 0:
            raise ValueError("--fixed-radius must be > 0")
        if distance_cm < 0:
            raise ValueError("--fixed-distance must be >= 0")
        if radius_cm >= WORLD_HALF_LENGTH_CM:
            raise ValueError("fixed radius must be smaller than world half-length (1m)")

        # Sweep 1: fixed radius, scan distance with no-overlap and in-world limits.
        d_min_cm = radius_cm
        d_max_cm = WORLD_HALF_LENGTH_CM - radius_cm
        distance_scan_cm = float_range(d_min_cm, d_max_cm, step_cm)

        # Sweep 2: fixed distance, scan radius with no-overlap and in-world limits.
        d_for_radius_cm = min(max(distance_cm, 0.0), WORLD_HALF_LENGTH_CM)
        r_max_cm = min(d_for_radius_cm, WORLD_HALF_LENGTH_CM - d_for_radius_cm)
        radius_scan_cm: List[float] = []
        if r_max_cm >= min_positive_cm:
            radius_scan_cm = float_range(min_positive_cm, r_max_cm, step_cm)

        pairs_cm: List[Tuple[float, float]] = []
        pairs_cm.extend((radius_cm, d) for d in distance_scan_cm)
        pairs_cm.extend((r, d_for_radius_cm) for r in radius_scan_cm)

        # De-duplicate intersection point if both sweeps include it.
        seen = set()
        dedup_pairs_cm: List[Tuple[float, float]] = []
        for r_cm, d_cm in pairs_cm:
            key = (round(r_cm, 6), round(d_cm, 6))
            if key not in seen:
                seen.add(key)
                dedup_pairs_cm.append((r_cm, d_cm))

        for idx, (radius_val_cm, distance_val_cm) in enumerate(dedup_pairs_cm):
            yield Job(
                idx=idx,
                radius=from_cm(radius_val_cm, args.radius_unit),
                distance=from_cm(distance_val_cm, args.distance_unit),
                source=args.source,
                events=args.events,
                radius_unit=args.radius_unit,
                distance_unit=args.distance_unit,
            )
        return

    radius_values = float_range(args.radius_start, args.radius_end, args.radius_step)
    distance_values = float_range(
        args.distance_start, args.distance_end, args.distance_step
    )

    if args.scan_mode == "grid":
        pairs: Iterable[Tuple[float, float]] = itertools.product(
            radius_values, distance_values
        )
    else:
        limit = min(len(radius_values), len(distance_values))
        pairs = zip(radius_values[:limit], distance_values[:limit])

    for idx, (radius, distance) in enumerate(pairs):
        yield Job(
            idx=idx,
            radius=radius,
            distance=distance,
            source=args.source,
            events=args.events,
            radius_unit=args.radius_unit,
            distance_unit=args.distance_unit,
        )


def run_one_job(
    exe: Path,
    job: Job,
    out_dir: Path,
    template_lines: Sequence[str],
) -> Tuple[Job, int]:
    run_name = (
        f"job_{job.idx:04d}_r{fmt_number(job.radius)}{job.radius_unit}"
        f"_d{fmt_number(job.distance)}{job.distance_unit}_s{job.source}"
    ).replace("/", "_")
    macro_path = out_dir / f"{run_name}.mac"
    log_path = out_dir / f"{run_name}.log"
    macro_path.write_text(build_macro(template_lines, job), encoding="utf-8")

    with log_path.open("w", encoding="utf-8") as log_fp:
        proc = subprocess.run(
            [str(exe), str(macro_path)],
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return job, proc.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit Geant4 scan with configurable ranges and concurrency."
    )
    parser.add_argument("--exe", default="./build/main", help="Path to Geant4 executable.")
    parser.add_argument("--template", default="run.mac", help="Template macro path.")
    parser.add_argument(
        "--output-dir",
        default="scan_runs",
        help="Directory to store generated macros and logs.",
    )
    parser.add_argument("--source", default="Cs137", help="Source type for /mydet/setSource.")
    parser.add_argument("--events", type=int, default=10_000_000, help="beamOn events.")
    parser.add_argument(
        "--radius-start",
        type=float,
        default=20.0,
        help="Detector radius range start.",
    )
    parser.add_argument(
        "--radius-end",
        type=float,
        default=20.0,
        help="Detector radius range end.",
    )
    parser.add_argument(
        "--radius-step",
        type=float,
        default=1.0,
        help="Detector radius scan step.",
    )
    parser.add_argument("--radius-unit", default="cm", help="Detector radius unit.")
    parser.add_argument(
        "--distance-start",
        type=float,
        default=1.0,
        help="Source-detector distance range start.",
    )
    parser.add_argument(
        "--distance-end",
        type=float,
        default=1.0,
        help="Source-detector distance range end.",
    )
    parser.add_argument(
        "--distance-step",
        type=float,
        default=1.0,
        help="Source-detector distance scan step.",
    )
    parser.add_argument("--distance-unit", default="cm", help="Distance unit.")
    parser.add_argument(
        "--scan-mode",
        choices=("grid", "zip", "mutual"),
        default="mutual",
        help="grid: Cartesian product; zip: lockstep; mutual: fixed-radius distance sweep + fixed-distance radius sweep.",
    )
    parser.add_argument(
        "--fixed-radius",
        type=float,
        default=10,
        help="Used by mutual mode: fixed detector radius.",
    )
    parser.add_argument(
        "--fixed-distance",
        type=float,
        default=0.1,
        help="Used by mutual mode: fixed source-detector distance.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=50,
        help="Maximum parallel jobs.",
    )
    return parser.parse_args()


def resolve_user_path(path_str: str, base_dir: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path

    # Prefer paths relative to script directory (project root).
    candidate = (base_dir / path).resolve()
    if candidate.exists():
        return candidate

    # Fallback to current working directory for ad-hoc runs.
    return (Path.cwd() / path).resolve()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    exe = resolve_user_path(args.exe, script_dir)
    template = resolve_user_path(args.template, script_dir)
    out_dir = resolve_user_path(args.output_dir, script_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not exe.exists():
        raise FileNotFoundError(f"Executable not found: {exe}")
    if not template.exists():
        raise FileNotFoundError(f"Template macro not found: {template}")
    if args.events <= 0:
        raise ValueError("--events must be > 0")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be > 0")

    template_lines = template.read_text(encoding="utf-8").splitlines()
    jobs = list(generate_jobs(args))
    if not jobs:
        print("No jobs generated. Please check range settings.")
        return 1

    print(f"Submitting {len(jobs)} jobs with concurrency={args.concurrency}")
    failed = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(run_one_job, exe, job, out_dir, template_lines) for job in jobs
        ]
        for future in as_completed(futures):
            job, code = future.result()
            mark = "OK" if code == 0 else "FAIL"
            if code != 0:
                failed += 1
            print(
                f"[{mark}] job={job.idx} "
                f"radius={fmt_number(job.radius)}{job.radius_unit} "
                f"distance={fmt_number(job.distance)}{job.distance_unit} "
                f"source={job.source} code={code}"
            )

    print(f"Done. total={len(jobs)}, failed={failed}, output={out_dir}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
