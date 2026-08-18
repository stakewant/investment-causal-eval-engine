from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from causal_engine import GraphCompileError, compile_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile a temporal causal factor graph")
    parser.add_argument("--catalog", required=True, help="factor catalog JSON path")
    parser.add_argument("--claims", required=True, help="source claims JSON path")
    parser.add_argument("--graph", required=True, help="turn graph JSON path")
    parser.add_argument("--output", help="optional compiled artifact JSON path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        artifact = compile_files(
            factor_catalog_path=args.catalog,
            source_claims_path=args.claims,
            graph_path=args.graph,
        )
    except (GraphCompileError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[OK] compiled graph: {output_path}")
    else:
        print(json.dumps(artifact, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


