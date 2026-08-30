"""Coverage harness — the piece that stops this project publishing a wrong number.

A sibling project published four different coverage figures for the same portal
(43%, 13%, 27%, 89%). None was a lie; all four came from measuring badly. The
rules that came out of that are enforced here rather than left to whoever runs
the measurement:

1. **Invoke the registered tool, not the internal HTTP client.** A number that
   does not come out of the function the model actually calls is not a number
   about the tool. This module resolves the tool through the server's own tool
   manager, so if the tool breaks, the sweep breaks with it.
2. **Count rows returned, never catalogue flags.** CKAN's `datastore_active` is
   wrong often enough to matter — in the sibling project 37 of 59 resources it
   marked queryable answered 404. A dataset counts as covered here only when the
   tool actually returned at least one row.
3. **Take few datasets from many pages, never all from a few.** A CKAN catalogue
   is not randomly ordered: 144 contiguous cartographic packages in one portal
   swung the same measurement between 46% and 75%. Sampling whole pages follows
   those blocks; sampling one dataset from many offsets follows the population.
4. **Count datasets, not resources.** A dataset with twenty shapefiles and one
   CSV is opened by that CSV. Per resource it looks like 5%; per dataset it is
   100%, and the dataset is the thing a person asked for.

Usage:

    uv run python -m opendata_latam_mcp.sweep --countries AR,CL,MX,PA,UY \\
        --per-country 40 --seed 42
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
from dataclasses import dataclass, field

from . import adapters
from .countries import all_codes, normalize_country_code

# Politeness: never more than this many in-flight requests per portal.
CONCURRENCY = 4
# Resources tried per dataset before giving up on it. A dataset is covered as
# soon as one of them returns rows, so this bounds the cost of a dataset that
# publishes twenty unreadable layers.
MAX_RESOURCES_PER_DATASET = 3


@dataclass
class CountryResult:
    country: str
    portal: str = ""
    catalogue_total: int = 0
    offsets: set[int] = field(default_factory=set)
    datasets_sampled: int = 0
    datasets_with_rows: int = 0
    rows_returned: int = 0
    no_datastore: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        if not self.datasets_sampled:
            return 0.0
        return 100.0 * self.datasets_with_rows / self.datasets_sampled

    def line(self) -> str:
        return (
            f"  {self.country}  {self.portal[:34]:<34} "
            f"offsets={len(self.offsets):<4} "
            f"sampled={self.datasets_sampled:<4} "
            f"with_rows={self.datasets_with_rows:<4} "
            f"rows={self.rows_returned:<6} "
            f"coverage={self.coverage:5.1f}%"
        )


def _resolve_tool():
    """Return the registered `read_resource_rows` tool function.

    Deliberately routed through the server's tool manager rather than importing
    the module-level function: this is what asserts the thing being measured is
    the thing the model calls.
    """
    from .server import mcp

    tool = mcp._tool_manager.get_tool("read_resource_rows")
    if tool is None:  # pragma: no cover — registration is asserted by the suite
        raise RuntimeError("read_resource_rows is not registered on the server")
    return tool.fn


async def sweep_country(code: str, per_country: int, rng: random.Random) -> CountryResult:
    res = CountryResult(country=code)
    tool = _resolve_tool()
    adapter = adapters.get_adapter(code)
    res.portal = adapter.PORTAL_NAME

    try:
        head = await adapter.search_datasets(query=None, limit=1)
        res.catalogue_total = int(head.get("total") or 0)
    except Exception as e:
        res.errors.append(f"catalogue unreachable: {type(e).__name__}: {e}")
        return res

    if res.catalogue_total <= 0:
        res.errors.append("catalogue reports zero datasets")
        return res

    # Rule 3: one dataset per offset, offsets spread across the whole catalogue.
    # When the catalogue is smaller than the sample, walk it whole — cheaper than
    # arguing about a sample.
    span = max(res.catalogue_total - 1, 1)
    if res.catalogue_total <= per_country:
        offsets = list(range(res.catalogue_total))
    else:
        offsets = rng.sample(range(span), per_country)
    res.offsets = set(offsets)

    sem = asyncio.Semaphore(CONCURRENCY)

    async def one_offset(off: int) -> None:
        async with sem:
            try:
                page = await adapter.search_datasets(query=None, limit=1, offset=off)
            except Exception as e:
                res.errors.append(f"offset {off}: {type(e).__name__}")
                return
            datasets = page.get("datasets") or []
            if not datasets:
                return
            res.datasets_sampled += 1
            ident = datasets[0].get("id") or datasets[0].get("name")
            if not ident:
                return
            try:
                full = await adapter.get_dataset(ident)
            except Exception as e:
                res.errors.append(f"get_dataset {ident}: {type(e).__name__}")
                return
            resources = (full.get("resources") or [])[:MAX_RESOURCES_PER_DATASET]
            for r in resources:
                rid = r.get("id")
                if not rid:
                    continue
                # Rule 1: the registered tool, with the same arguments a model
                # would pass. Rule 2: what counts is the rows it hands back.
                out = await tool(country=code, resource_id=rid, limit=5)
                if isinstance(out, dict) and out.get("rows"):
                    res.datasets_with_rows += 1
                    res.rows_returned += len(out["rows"])
                    return
                if isinstance(out, dict) and "no DataStore table" in str(out.get("error", "")):
                    res.no_datastore += 1

    await asyncio.gather(*[one_offset(o) for o in offsets])
    return res


async def run(codes: list[str], per_country: int, seed: int) -> int:
    print(
        f"Sweep · {len(codes)} countries · {per_country} datasets each "
        f"· seed {seed} · route: CKAN DataStore"
    )
    print(
        "Counting datasets (not resources) for which the registered "
        "read_resource_rows tool returned at least one row.\n"
    )
    results = []
    for code in codes:
        rng = random.Random(f"{seed}:{code}")
        r = await sweep_country(code, per_country, rng)
        results.append(r)
        print(r.line(), flush=True)

    print()
    total_sampled = sum(r.datasets_sampled for r in results)
    total_rows = sum(r.datasets_with_rows for r in results)
    print(
        f"  TOTAL  sampled={total_sampled}  with_rows={total_rows}  "
        f"coverage={100.0 * total_rows / total_sampled if total_sampled else 0:.1f}%"
    )
    for r in results:
        if r.errors:
            print(f"  {r.country} errors ({len(r.errors)}): {r.errors[0]}")

    await adapters.registry.close_all()
    # Non-zero when any requested country produced nothing, so CI can gate on it.
    return 0 if all(r.datasets_with_rows > 0 for r in results) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="opendata_latam_mcp.sweep",
        description="Measure how much of each portal the row-reading tool can actually read.",
    )
    ap.add_argument(
        "--countries",
        default=",".join(all_codes()),
        help="Comma-separated ISO alpha-2 codes (default: every supported country).",
    )
    ap.add_argument("--per-country", type=int, default=40, help="Datasets sampled per country.")
    ap.add_argument("--seed", type=int, default=42, help="Sampling seed, so a run is reproducible.")
    args = ap.parse_args(argv)

    # The server logs every request at INFO on stderr, which is right for a
    # stdio server and useless here — it buries the table this exists to print.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("opendata-latam-mcp").setLevel(logging.WARNING)

    codes = [normalize_country_code(c.strip()) for c in args.countries.split(",") if c.strip()]
    return asyncio.run(run(codes, args.per_country, args.seed))


if __name__ == "__main__":
    sys.exit(main())
