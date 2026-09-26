"""Taxonomic grouping and a reusable, per-taxon cache on disk."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3


TAXONOMY_RANKS = (
    ("kingdom", "Rijk"),
    ("phylum", "Stam"),
    ("class", "Klasse"),
    ("order", "Orde"),
    ("family", "Familie"),
    ("genus", "Geslacht"),
)


class TaxonomyCache:
    """Store complete leaf records with their ancestors, independently of searches."""

    def __init__(self, path=None):
        cache_dir = Path(os.environ.get(
            "BIODIVERSITEIT_CACHE_DIR", str(Path(__file__).resolve().parent / ".cache")
        ))
        self.path = Path(path) if path is not None else cache_dir / "taxonomy.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS taxonomy_v1 ("
                "locale TEXT NOT NULL, taxon_id INTEGER NOT NULL, payload TEXT NOT NULL, "
                "PRIMARY KEY (locale, taxon_id))"
            )

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def get_many(self, ids, locale):
        result = {}
        with closing(self.connect()) as connection:
            # Stay below SQLite's parameter limit even for large species lists.
            for start in range(0, len(ids), 400):
                batch = ids[start:start + 400]
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    f"SELECT taxon_id, payload FROM taxonomy_v1 "
                    f"WHERE locale = ? AND taxon_id IN ({placeholders})",
                    [locale, *batch],
                )
                for taxon_id, payload in rows:
                    result[taxon_id] = json.loads(payload)
        return result

    def put_many(self, taxa, locale):
        rows = [
            (locale, int(taxon["id"]), json.dumps(taxon, ensure_ascii=False))
            for taxon in taxa
            if taxon.get("id") and taxon.get("name") and taxon.get("rank")
            and isinstance(taxon.get("ancestors"), list)
        ]
        with closing(self.connect()) as connection, connection:
            connection.executemany(
                "INSERT OR REPLACE INTO taxonomy_v1 (locale, taxon_id, payload) "
                "VALUES (?, ?, ?)", rows,
            )


def load_leaf_taxonomy(ids_tuple, fetch_batch, locale="en", cache_path=None):
    """Fetch only uncached taxa; save each successful batch immediately."""
    ids = sorted({int(value) for value in ids_tuple if value})
    if not ids:
        return {}
    cache = TaxonomyCache(cache_path)
    taxa = cache.get_many(ids, locale)
    missing = [taxon_id for taxon_id in ids if taxon_id not in taxa]
    batches = [missing[start:start + 30] for start in range(0, len(missing), 30)]
    if batches:
        with ThreadPoolExecutor(max_workers=min(8, len(batches))) as executor:
            futures = [executor.submit(fetch_batch, batch, locale) for batch in batches]
            for future in as_completed(futures):
                records = future.result()
                cache.put_many(records, locale)
                taxa.update({int(taxon["id"]): taxon for taxon in records if taxon.get("id")})

    lookup = {}
    for taxon in taxa.values():
        for ancestor in taxon.get("ancestors") or []:
            if ancestor.get("id"):
                lookup[int(ancestor["id"])] = ancestor
    # Full requested records take precedence over the shorter ancestor records.
    for taxon_id, taxon in taxa.items():
        record = {key: value for key, value in taxon.items() if key != "ancestors"}
        record["ancestor_ids"] = list(dict.fromkeys([
            *record.get("ancestor_ids", []),
            *(int(item["id"]) for item in taxon.get("ancestors") or [] if item.get("id")),
            taxon_id,
        ]))
        lookup[taxon_id] = record
    return lookup


def rank_id(taxon, lookup, wanted_rank):
    if taxon.get("rank") == wanted_rank and taxon.get("id"):
        return int(taxon["id"])
    for taxon_id in reversed(taxon.get("ancestor_ids") or []):
        record = lookup.get(int(taxon_id))
        if record and record.get("rank") == wanted_rank:
            return int(taxon_id)
    return None


def rank_names(taxon_id, lookup):
    record = lookup.get(int(taxon_id)) if taxon_id else None
    if not record:
        return None, None
    return record.get("preferred_common_name") or record.get("name"), record.get("name")


def enrich_species_taxonomy(frame, lookup):
    frame = frame.copy()
    for index, row in frame.iterrows():
        taxon = lookup.get(int(row["species_id"]), {})
        for rank, label in TAXONOMY_RANKS:
            taxon_id = rank_id(taxon, lookup, rank)
            common, scientific = rank_names(taxon_id, lookup)
            frame.at[index, label] = common or scientific or "Onbekend"
            frame.at[index, f"{label} wetenschappelijk"] = scientific or "Onbekend"
            if rank in {"family", "order"}:
                frame.at[index, f"{rank}_id"] = taxon_id
        # Counts may have started with a subspecies; use the resolved species name.
        if taxon.get("name"):
            frame.at[index, "Wetenschappelijke naam"] = taxon["name"]
    return frame


def sort_species_overview(frame, sort_by):
    """Sort within each successive taxonomic rank; unknown names go last."""
    if sort_by == "Aantal waarnemingen":
        return frame.sort_values(
            ["Waarnemingen in gebied", "Engelse naam"], ascending=[False, True]
        ).reset_index(drop=True)

    sorted_frame = frame.copy()
    keys = []
    columns = [f"{label} wetenschappelijk" for _, label in TAXONOMY_RANKS]
    columns.append("Wetenschappelijke naam")
    for column in columns:
        if column in sorted_frame:
            names = sorted_frame[column].fillna("").astype(str).str.strip().str.casefold()
        else:
            names = sorted_frame["species_id"].map(lambda _: "")
        missing = names.eq("") | names.eq("onbekend")
        missing_key = f"_missing_{len(keys)}"
        name_key = f"_name_{len(keys)}"
        sorted_frame[missing_key] = missing
        sorted_frame[name_key] = names.mask(missing, "")
        keys.extend((missing_key, name_key))
    return sorted_frame.sort_values(keys + ["species_id"], kind="stable").drop(
        columns=keys
    ).reset_index(drop=True)
