"""Export a page of offline execution diagnostics from an operator-owned copy."""
import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.persistence.execution_inventory import load_inventory_json, sqlite_inventory_page, sqlite_release_drain, sqlite_store_residuals
from src.runtime.execution_affinity import ExecutionAffinity


def write_inventory_report(path, page):
    """Publish a complete file exclusively, including when two observers race."""
    target = Path(path)
    temporary = None
    try:
        with NamedTemporaryFile(dir=target.parent, delete=False, mode="w", encoding="utf-8") as output:
            temporary = Path(output.name)
            json.dump({**page, "exported_utc": datetime.now(UTC).isoformat()}, output,
                      ensure_ascii=False, indent=2, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--consumer-affinity", type=Path)
    scope.add_argument("--release-drain", type=Path, metavar="AFFINITY",
                       help="Assess all pages on a stable copy of all stores and checkpoints")
    scope.add_argument("--store-residuals", action="store_true", help="Whole-store administrator counts")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--legacy-database", type=Path)
    parser.add_argument("--checkpoint-encoding", help="Source text encoding of the checkpoint files")
    parser.add_argument("--vm-start-dispatch", action="store_true",
                        help="Include open VM Start dispatch evidence using the operator's Foundry deployment")
    parser.add_argument("--after")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    deployment = None
    if args.vm_start_dispatch:
        from src.config.foundry_deployment import build_foundry_deployment_configuration

        if not args.consumer_affinity:
            parser.error("--vm-start-dispatch requires --consumer-affinity")
        deployment = build_foundry_deployment_configuration(os.environ)
        if deployment is None:
            parser.error("--vm-start-dispatch requires FOUNDRY_DEPLOYMENT_JSON and FOUNDRY_PROJECT_ENDPOINT")
    if args.output.resolve().is_relative_to(args.checkpoints.resolve()):
        parser.error("Choose an output outside the checkpoint directory.")
    sources = dict(database=args.database, checkpoints=args.checkpoints, legacy_database=args.legacy_database,
                   checkpoint_encoding=args.checkpoint_encoding)
    if args.release_drain:
        if args.after is not None:
            parser.error("A complete drain assessment starts at the first page.")
        consumer = ExecutionAffinity.from_document(load_inventory_json(args.release_drain.read_bytes()))
        page = sqlite_release_drain(**sources, consumer=consumer, page_size=50 if args.limit is None else args.limit)
    elif args.store_residuals:
        if args.limit is not None or args.after is not None:
            parser.error("Pagination applies only to scoped admissions.")
        page = sqlite_store_residuals(**sources)
    else:
        consumer = ExecutionAffinity.from_document(load_inventory_json(args.consumer_affinity.read_bytes()))
        page = sqlite_inventory_page(**sources, consumer=consumer, after=args.after,
                                    limit=50 if args.limit is None else args.limit, vm_start_deployment=deployment)
    write_inventory_report(args.output, page)


if __name__ == "__main__":
    main()
