import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Add src to sys.path to allow importing qol.gamepad_input
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR / "src"))

try:
    from qol import gamepad_input
except ImportError as e:
    print(f"Error: Could not import qol.gamepad_input: {e}")
    sys.exit(1)


def run_mock(steps: int) -> Dict[str, Any]:
    """
    Deterministic mock provider that simulates a sequence of gamepad states.
    """
    results: Dict[str, Any] = {
        "provider": "mock",
        "status": "ok",
        "events": [],
        "snapshots": [],
        "meta": {"steps": steps},
    }

    prev_snapshot: Optional[Dict[str, Any]] = None

    # Deterministic sequence of raw states
    # 0: neutral
    # 1: A down
    # 2: A up
    # 3: ThumbLX max
    # 4: ThumbLX neutral
    # 5: B down
    # 6: B up

    for i in range(steps):
        raw_state = {
            "index": 0,
            "status": "ok",
            "connected": True,
            "packet_number": i + 1,
            "buttons": 0,
            "thumb_lx": 0,
            "thumb_ly": 0,
            "thumb_rx": 0,
            "thumb_ry": 0,
            "left_trigger": 0,
            "right_trigger": 0,
        }

        if i == 1:
            raw_state["buttons"] = 0x1000  # A
        elif i == 3:
            raw_state["thumb_lx"] = 32767
        elif i == 5:
            raw_state["buttons"] = 0x2000  # B

        snapshot, events = gamepad_input.build_snapshot_with_events(
            raw_state, prev_snapshot
        )
        results["snapshots"].append(snapshot)
        results["events"].extend(events)
        prev_snapshot = snapshot

    results["meta"]["duration_ms"] = 0
    return results


def run_xinput(duration_ms: int) -> Dict[str, Any]:
    """
    XInput provider that probes and polls the hardware.
    """
    start_time = time.perf_counter()
    probe = gamepad_input.probe_xinput()

    results: Dict[str, Any] = {
        "provider": "xinput",
        "status": probe["status"],
        "events": [],
        "snapshots": [],
        "meta": {"probe": probe},
    }

    if probe["status"] == "ok":
        index = probe["index"]
        prev_snapshot: Optional[Dict[str, Any]] = None

        # Poll for the specified duration
        while (time.perf_counter() - start_time) * 1000 < duration_ms:
            all_states = gamepad_input.poll_controllers()
            # Find the state for our index
            raw_state = next((s for s in all_states if s["index"] == index), None)

            if raw_state:
                snapshot, events = gamepad_input.build_snapshot_with_events(
                    raw_state, prev_snapshot
                )
                results["snapshots"].append(snapshot)
                results["events"].extend(events)
                prev_snapshot = snapshot

            time.sleep(0.01)  # 10ms poll rate

    results["meta"]["duration_ms"] = int((time.perf_counter() - start_time) * 1000)
    # To keep output small, only keep last snapshot if many were taken
    if len(results["snapshots"]) > 5:
        results["last_snapshot"] = results["snapshots"][-1]
        results["snapshots"] = results["snapshots"][:5]  # Keep first 5 for context

    return results


def main():
    parser = argparse.ArgumentParser(description="Gamepad Diagnostics Smoke Test")
    parser.add_argument(
        "--provider", required=True, choices=["mock", "xinput"], help="Provider to use"
    )
    parser.add_argument("--steps", type=int, default=10, help="Steps for mock provider")
    parser.add_argument(
        "--duration-ms", type=int, default=500, help="Duration for xinput provider"
    )
    parser.add_argument("--output", required=True, help="Output JSON file path")

    # Handle invalid provider manually to match expected behavior if choices doesn't catch it or if we want custom error
    args, unknown = parser.parse_known_args()

    if args.provider not in ["mock", "xinput"]:
        print(f"Error: Invalid provider '{args.provider}'. Allowed: mock, xinput")
        sys.exit(1)

    if args.provider == "mock":
        data = run_mock(args.steps)
    else:
        data = run_xinput(args.duration_ms)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Diagnostics completed. Output written to {args.output}")


if __name__ == "__main__":
    main()
