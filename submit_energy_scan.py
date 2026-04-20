#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description=(
            "Scan RootSpectrum energy range in run.mac and submit jobs. "
            "Output files are renamed to 数字_数字.root."
        )
    )
    parser.add_argument("--min", dest="emin", default="1.0", help="Energy lower bound in MeV.")
    parser.add_argument("--max", dest="emax", default="7.4", help="Energy upper bound in MeV.")
    parser.add_argument("--step", dest="estep", default="0.1", help="Energy step in MeV.")
    parser.add_argument(
        "--window",
        dest="ewindow",
        default="0.1",
        help="Window width in MeV. Each job uses [E, E+window].",
    )
    parser.add_argument(
        "--run-mac",
        default=str(script_dir / "run.mac"),
        help="Path to source run.mac.",
    )
    parser.add_argument(
        "--work-dir",
        default=str(script_dir / "input/scan_jobs"),
        help="Working directory for generated files.",
    )
    parser.add_argument(
        "--sim-cmd",
        default="cd build && ./main {mac}",
        help='Simulation command template, must include "{mac}".',
    )
    parser.add_argument(
        "--submit-cmd",
        default="bash {job}",
        help='Submit command template, must include "{job}" (job script path).',
    )
    parser.add_argument(
        "--default-output",
        default="build/myfilename*.root",
        help=(
            "Simulation output ROOT to rename after each job. "
            "Use a path relative to the project root, e.g. build/myfilename*.root "
            "(wildcards allowed)."
        ),
    )
    return parser.parse_args()


def normalize_decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def energy_list(emin: str, emax: str, estep: str) -> list[str]:
    getcontext().prec = 28
    e_min = Decimal(emin)
    e_max = Decimal(emax)
    e_step = Decimal(estep)

    if e_step <= 0:
        raise ValueError("step must be > 0")
    if e_max < e_min:
        raise ValueError("max must be >= min")

    values: list[str] = []
    idx = 0
    eps = Decimal("1e-18")
    current = e_min
    while current <= e_max + eps:
        values.append(normalize_decimal_text(current))
        idx += 1
        current = e_min + e_step * idx
    return values


def energy_to_token(energy_text: str) -> str:
    token = energy_text.replace(".", "_")
    return token if "_" in token else f"{token}_0"


def _strip_comment_prefix(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("#"):
        stripped = stripped[1:].lstrip()
    return stripped


def _replace_or_uncomment_command(
    lines: list[str], command: str, value: str | None = None
) -> bool:
    for idx, line in enumerate(lines):
        normalized = _strip_comment_prefix(line).strip()
        if normalized.startswith(command):
            newline = "\n" if line.endswith("\n") else ""
            if value is None:
                # 只去掉注释，保留命令后的参数（如 ROOT 路径、tree、branch）
                lines[idx] = f"{normalized}{newline}"
            else:
                lines[idx] = f"{command} {value}{newline}"
            return True
    return False


def write_run_mac(
    src_text: str, dst_path: Path, energy_min_text: str, energy_max_text: str
) -> None:
    lines = src_text.splitlines(keepends=True)
    required_commands = [
        ("/mydet/setSource", "RootSpectrum"),
        ("/mydet/setSpectrumRootFile", None),
        ("/mydet/setSpectrumTree", None),
        ("/mydet/setSpectrumBranch", None),
        ("/mydet/setSpectrumMinEnergy", f"{energy_min_text} MeV"),
        ("/mydet/setSpectrumMaxEnergy", f"{energy_max_text} MeV"),
    ]
    for command, value in required_commands:
        ok = _replace_or_uncomment_command(lines, command, value)
        if not ok:
            raise RuntimeError(f"Cannot find '{command} ...' in run.mac")
    dst_path.write_text("".join(lines), encoding="utf-8")


def run_command(command: str, cwd: Path, log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            shell=True,
            text=True,
            stdout=logf,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return proc.returncode


def write_job_script(job_script: Path, sim_cmd: str, root_dir: Path) -> None:
    content = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'cd "{root_dir}"\n\n'
        f"{sim_cmd}\n"
    )
    job_script.write_text(content, encoding="utf-8")
    job_script.chmod(0o755)


def _pick_latest_match(matches: list[Path]) -> Path | None:
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def move_output(root_dir: Path, default_output: str, target_name: str) -> bool:
    rel = Path(default_output)
    candidates: list[Path] = []

    def add_glob(base: Path, pattern: str) -> None:
        found = sorted(base.glob(pattern))
        if found:
            candidates.extend(found)

    pattern = rel.as_posix()
    if any(ch in pattern for ch in "*?["):
        add_glob(root_dir, pattern)
        if not pattern.startswith("build/"):
            add_glob(root_dir, f"build/{pattern}")
    else:
        p1 = root_dir / rel
        p2 = root_dir / "build" / rel.name if rel.parent == Path(".") else root_dir / rel
        for p in (p1, p2):
            if p.exists():
                candidates.append(p)

    src = _pick_latest_match(candidates)
    if src is None:
        return False
    dst = root_dir / target_name
    src.replace(dst)
    return True


def main() -> int:
    args = parse_args()

    run_mac = Path(args.run_mac).resolve()
    work_dir = Path(args.work_dir).resolve()
    root_dir = Path(__file__).resolve().parent

    if "{mac}" not in args.sim_cmd:
        print('Error: --sim-cmd must include "{mac}" placeholder.', file=sys.stderr)
        return 1
    if "{job}" not in args.submit_cmd:
        print('Error: --submit-cmd must include "{job}" placeholder.', file=sys.stderr)
        return 1
    if not run_mac.is_file():
        print(f"Error: run.mac not found: {run_mac}", file=sys.stderr)
        return 1

    try:
        energies = energy_list(args.emin, args.emax, args.estep)
        e_window = Decimal(args.ewindow)
    except Exception as exc:
        print(f"Error: invalid energy range: {exc}", file=sys.stderr)
        return 1
    if e_window < 0:
        print("Error: window must be >= 0", file=sys.stderr)
        return 1
    if not energies:
        print("Error: no energy points generated.", file=sys.stderr)
        return 1

    work_dir.mkdir(parents=True, exist_ok=True)
    run_mac_text = run_mac.read_text(encoding="utf-8")

    print("Energy scan config:")
    print(f"  RUN_MAC: {run_mac}")
    print(f"  WORK_DIR: {work_dir}")
    print(f"  ENERGY_MIN/MAX/STEP: {args.emin} / {args.emax} / {args.estep} MeV")
    print(f"  WINDOW: {args.ewindow} MeV")
    print(f"  SIM_CMD: {args.sim_cmd}")
    print(f"  SUBMIT_CMD: {args.submit_cmd}")
    print(f"  DEFAULT_OUTPUT_NAME: {args.default_output}")
    print("")

    for energy in energies:
        e_min = Decimal(energy)
        e_max = e_min + e_window
        e_min_text = normalize_decimal_text(e_min)
        e_max_text = normalize_decimal_text(e_max)
        token = f"{energy_to_token(e_min_text)}__{energy_to_token(e_max_text)}"
        output_name = f"{token}.root"
        job_mac = work_dir / f"run_{token}.mac"
        job_script = work_dir / f"job_{token}.sh"
        submit_log = work_dir / f"job_{token}.log"

        write_run_mac(run_mac_text, job_mac, e_min_text, e_max_text)

        sim_cmd = args.sim_cmd.replace("{mac}", str(job_mac))
        write_job_script(job_script, sim_cmd, root_dir)
        submit_cmd = args.submit_cmd.replace("{job}", str(job_script))

        print(f"[Submit] E=[{e_min_text}, {e_max_text}] MeV -> {output_name}")
        ret = run_command(submit_cmd, root_dir, submit_log)
        if ret != 0:
            print(f"  [WARN] submit command failed, see log: {submit_log}")
            continue

        moved = move_output(root_dir, args.default_output, output_name)
        if not moved:
            print(
                f"  [WARN] default output not found for E=[{e_min_text}, {e_max_text}] MeV: "
                f"{args.default_output}"
            )

    print("")
    print(f"All tasks submitted. Generated files are in: {work_dir}")
    print(f"Per-job logs: {work_dir}/job_*.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
