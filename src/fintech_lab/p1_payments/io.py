"""Parquet export + manifest (seed, schema, row counts, checksums) for P1 datasets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml

from fintech_lab.p1_payments.generator import GENERATOR_VERSION, TABLES
from fintech_lab.shared.provenance import DataOrigin

MONEY_COLUMNS = {
    "dim_acquirer": ["fee_fixed_local"],
    "fact_payment": ["amount"],
    "fact_attempt": ["processing_cost"],
    "fact_settlement": ["gross_amount", "fee", "net_amount"],
}
RATE_COLUMNS = {"dim_fx_rate": ["rate_to_brl"]}


def content_hash(df: pd.DataFrame) -> str:
    """Order-sensitive SHA-256 of a DataFrame's values (independent of Parquet writer bytes)."""
    h = hashlib.sha256()
    h.update(",".join(f"{c}:{df[c].dtype}" for c in df.columns).encode())
    h.update(pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes())
    return h.hexdigest()


def config_hash(cfg: dict[str, Any]) -> str:
    return hashlib.sha256(yaml.safe_dump(cfg, sort_keys=True).encode()).hexdigest()


def _to_arrow(name: str, df: pd.DataFrame, meta: dict[str, str]) -> pa.Table:
    table = pa.Table.from_pandas(df, preserve_index=False)
    for cols, typ in (
        (MONEY_COLUMNS.get(name, []), pa.decimal128(18, 2)),
        (RATE_COLUMNS.get(name, []), pa.decimal128(18, 8)),
    ):
        for col in cols:
            i = table.schema.get_field_index(col)
            arr = table.column(i).cast(pa.float64())
            table = table.set_column(i, col, pc.cast(arr, typ, safe=False))
    return table.replace_schema_metadata({**meta, "table": name})


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_dataset(
    tables: dict[str, pd.DataFrame],
    out_dir: str | Path,
    cfg: dict[str, Any],
    kind: str = "clean",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write one Parquet per table plus ``manifest.json``. Returns the manifest."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "data_origin": DataOrigin.SYNTHETIC.value,
        "generator_version": GENERATOR_VERSION,
        "seed": str(cfg["seed"]),
        "dataset_kind": kind,
    }
    manifest: dict[str, Any] = {
        "data_origin": DataOrigin.SYNTHETIC.value,
        "notice": "Synthetic data. Not real payments; parameters are not real-world benchmarks.",
        "dataset_kind": kind,
        "generator_version": GENERATOR_VERSION,
        "seed": cfg["seed"],
        "target_attempts": cfg["target_attempts"],
        "config_sha256": config_hash(cfg),
        "tables": {},
    }
    dataset_h = hashlib.sha256()
    for name in TABLES:
        df = tables[name]
        path = out / f"{name}.parquet"
        table = _to_arrow(name, df, meta)
        pq.write_table(table, path, compression="zstd")
        ch = content_hash(df)
        dataset_h.update(ch.encode())
        manifest["tables"][name] = {
            "rows": int(len(df)),
            "schema": {f.name: str(f.type) for f in table.schema},
            "file_sha256": _sha256_file(path),
            "content_sha256": ch,
        }
    manifest["dataset_content_sha256"] = dataset_h.hexdigest()
    if extra:
        manifest.update(extra)
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=_json), encoding="utf-8"
    )
    return manifest


def _json(o: Any) -> Any:
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    return str(o)
