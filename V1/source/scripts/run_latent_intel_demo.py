from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.intel_agents.tools.latent_intel_mining_tools import (  # noqa: E402
    LatentIntelConfig,
    export_results,
    load_samples,
    mine_latent_intel_candidates,
    print_top_candidates,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the latent intelligence mining demo."""

    parser = argparse.ArgumentParser(
        description="Mine latent LLM-security intelligence candidates from public-source text samples."
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Optional JSON input path. Supports a list or an object with an 'items' list.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/latent_intel",
        help="Directory for latent_intel_candidates.json and latent_intel_candidates.csv.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of high-confidence candidates to print.",
    )
    parser.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.86,
        help="TF-IDF cosine similarity threshold for near-duplicate removal.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the end-to-end latent intelligence mining demo."""

    args = parse_args()
    items = load_samples(args.input)
    raw_candidates, deduped_candidates = mine_latent_intel_candidates(
        items,
        LatentIntelConfig(dedup_threshold=args.dedup_threshold),
    )
    json_path, csv_path = export_results(deduped_candidates, args.output_dir)

    print("Latent Intelligence Mining Demo")
    print("=" * 35)
    print(f"Total input items: {len(items)}")
    print(f"AI-security relevant candidates: {len(raw_candidates)}")
    print(f"Deduplicated candidates: {len(deduped_candidates)}")
    print(f"Top {min(args.top_k, len(deduped_candidates))} high-confidence latent intel:")
    print_top_candidates(deduped_candidates, top_k=args.top_k)
    print(f"JSON output: {json_path}")
    print(f"CSV output: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
