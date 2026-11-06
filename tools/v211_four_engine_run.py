"""Run the four configured AI engines on one image in the V2.1.1 research branch.

Default configuration requires installed real engine executables and checkpoints.
No downloaded or simulated model is silently substituted.
"""
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path
from typing import Callable

from tools.v211_four_engine_coordinator import run_candidates
from tools.v211_four_engine_subprocess import ENGINES, EngineCommand, make_processors
from tools.v211_real_engine_manifest import load_real_engine_manifest
from tools.v211_three_engine_priority_preview import PRIMARY_ENGINES, select_three_engine_preview
from tools.v211_four_engine_fusion import fuse_four_engine_details


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


_NCNN_ENGINES = ("real_esrgan", "waifu2x", "real_cugan")


def _safe_execution_record(record: dict | None) -> dict | None:
    """Keep only non-sensitive process facts in the local QA report."""
    if not isinstance(record, dict):
        return None
    allowed = (
        "status", "process_started", "pid", "exit_code",
        "process_elapsed_ms", "elapsed_ms_total", "failure_type",
    )
    return {key: record[key] for key in allowed if key in record}


def _option_value(argv: tuple[str, ...], flags: tuple[str, ...]) -> str | None:
    for index, token in enumerate(argv[:-1]):
        if token in flags:
            return argv[index + 1]
    return None


def _configured_device_selection(engine: str, command: EngineCommand) -> dict:
    """Record only backend/index flags passed to the CLI, never adapter usage."""
    argv = tuple(str(item) for item in command.argv[1:])
    if engine in _NCNN_ENGINES:
        raw_index = _option_value(argv, ("-g", "--gpu"))
        try:
            index = int(raw_index) if raw_index is not None else None
        except (TypeError, ValueError):
            index = None
        return {
            "backend": "ncnn_vulkan",
            "device_index": index,
            "explicitly_configured": raw_index is not None and index is not None,
            "actual_adapter_verified": False,
        }
    raw_backend = _option_value(argv, ("-p", "--processor"))
    raw_index = _option_value(argv, ("-d", "--device"))
    try:
        index = int(raw_index) if raw_index is not None else None
    except (TypeError, ValueError):
        index = None
    return {
        "backend": raw_backend or "auto",
        "device_index": index,
        "explicitly_configured": raw_backend in ("cuda", "opencl") and index is not None,
        "actual_adapter_verified": False,
    }


def run(source: Path, output_dir: Path, config: Path, size: tuple[int, int], *, real_engines: bool = True, v2_reference: Path | None = None, protected_regions: tuple = (), preserve_all_v2_faces: bool = False, cancel: Callable[[], bool] | None = None, progress_callback: Callable[[int, str], None] | None = None) -> dict:
    output_dir = Path(output_dir)
    if real_engines:
        commands = load_real_engine_manifest(config)
    else:
        raw = json.loads(config.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != set(ENGINES):
            raise ValueError("config must contain exactly the four engines")
        commands = {}
        for name in ENGINES:
            argv = raw[name]
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
                raise ValueError("invalid argv for " + name)
            commands[name] = EngineCommand(tuple(argv))
    execution_records: dict[str, dict] = {}
    processors = make_processors(
        commands, cancel_check=cancel, execution_records=execution_records
    )
    result = run_candidates(
        source, output_dir, size, processors,
        cancel_check=cancel, progress_callback=progress_callback,
    )
    report = {
        "research_only": True,
        "real_engine_manifest_preflight_passed": real_engines,
        "real_engine_inference_proven": False,  # Process success is not proof of physical adapter use.
        "runtime_device_use_verified": False,
        "execution_evidence_scope": (
            "native process lifecycle, exit code, and configured CLI backend/index only; "
            "physical adapter use and visual quality remain unverified"
        ),
        "engine_execution": {
            name: {
                "process": _safe_execution_record(execution_records.get(name)),
                "device_configuration": _configured_device_selection(name, commands[name]),
                "runtime_device_use_verified": False,
            }
            for name in ENGINES
        },
        "completed_engine_count": len(result["candidates"]),
        "completed_engine_names": [item.engine for item in result["candidates"]],
        "fusion_implemented": False,
        "ready_for_fusion_research": result["ready_for_fusion_research"],
        "quality_certified": False,
        "source_sha256": _sha256(source),
        "candidate_sha256": {item.engine: _sha256(item.path) for item in result["candidates"]},
        "candidates": {item.engine: str(item.path) for item in result["candidates"]},
        "failures": result["failures"],
    }
    if cancel and cancel():
        raise InterruptedError("Processing stopped by user")
    if v2_reference is not None:
        available = {item.engine: item.path for item in result["candidates"]}
        if set(PRIMARY_ENGINES).issubset(available):
            try:
                if cancel and cancel():
                    raise InterruptedError("Processing stopped by user")
                # The shop preferred Real-ESRGAN, Waifu2x and Real-CUGAN in
                # actual Windows comparisons; Anime4K remains diagnostic only.
                selection = select_three_engine_preview(
                    source, v2_reference, available,
                    output_dir / "three_engine_priority_preview.png",
                )
                report["three_engine_priority_preview"] = selection
            except (OSError, ValueError, RuntimeError) as exc:
                report["priority_preview_error"] = type(exc).__name__ + ": " + str(exc)
                (output_dir / "three_engine_priority_preview.png").unlink(missing_ok=True)
        else:
            report["priority_preview_error"] = "Three priority candidates required; Anime4K optional"
        if result["ready_for_fusion_research"]:
            try:
                fusion = fuse_four_engine_details(
                    source, v2_reference, available,
                    output_dir / "four_engine_fused_preview.png",
                    protected_regions=protected_regions,
                    preserve_all_v2_faces=preserve_all_v2_faces,
                    cancel_check=cancel,
                )
                report["four_engine_fusion"] = fusion
                report["fusion_implemented"] = bool(fusion["fusion_implemented"])
            except InterruptedError:
                raise
            except (OSError, ValueError, RuntimeError, MemoryError) as exc:
                report["fusion_error"] = type(exc).__name__ + ": " + str(exc)
                (output_dir / "four_engine_fused_preview.png").unlink(missing_ok=True)
                # Keep four candidate images for private analysis, but do
                # not describe an incomplete fusion as a release-capable job.
                report["fusion_implemented"] = False
        # Only four actual candidates allow the full four-engine research gate.
        # A valid three-engine preview is distinct from production approval.
    if cancel and cancel():
        raise InterruptedError("Processing stopped by user")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "four_engine_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("--research-commands", action="store_true",
                        help="Explicit research-only commands; default requires real engines")
    parser.add_argument("--v2-reference", type=Path,
                        help="Trusted V2 output at target dimensions")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    args = parser.parse_args()
    report = run(args.source, args.output_dir, args.config, (args.width, args.height),
                 real_engines=not args.research_commands, v2_reference=args.v2_reference)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ready_for_fusion_research"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
