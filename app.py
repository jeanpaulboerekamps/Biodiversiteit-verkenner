from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import base64
import html
from io import StringIO
import json
import logging
import math
import sys
import threading
import time
import zlib

import folium
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components
from folium.plugins import Draw
from shapely.geometry import Point, shape
from streamlit_folium import st_folium


OBS_API = "https://api.inaturalist.org/v1/observations"
SPECIES_COUNTS_API = "https://api.inaturalist.org/v1/observations/species_counts"
TAXA_API = "https://api.inaturalist.org/v1/taxa"
TAXA_AUTOCOMPLETE_API = "https://api.inaturalist.org/v1/taxa/autocomplete"
MONTHS = {
    1: "januari", 2: "februari", 3: "maart", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "augustus",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}
SPECIES_GROUPS = {
    "Alle soortgroepen": "",
    "Vogels": "Aves",
    "Zoogdieren": "Mammalia",
    "Vissen": "Actinopterygii",
    "Reptielen": "Reptilia",
    "Amfibieën": "Amphibia",
    "Insecten": "Insecta",
    "Spinachtigen": "Arachnida",
    "Weekdieren": "Mollusca",
    "Planten": "Plantae",
    "Schimmels": "Fungi",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("biodiversiteit-verkenner")
REQUEST_LOCK = threading.Lock()
LAST_REQUEST_AT = 0.0
MIN_REQUEST_INTERVAL = 1.02  # iNaturalist asks clients to remain near 60 requests/minute.
MAX_FAST_SPECIES = 3000


def checkpoint(message):
    log.info(message)


st.set_page_config(
    page_title="Biodiversiteit Verkenner",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container {padding-top:1.3rem;padding-bottom:4rem;max-width:1220px}
div.stButton > button, div.stDownloadButton > button {
  min-height:50px;font-size:1.02rem;border-radius:12px;width:100%
}
.release-badge {display:inline-block;padding:.25rem .65rem;border-radius:999px;
  background:#e3f2fd;color:#0d4771;font-weight:700;margin-bottom:.55rem}
.intro {padding:1rem 1.15rem;border-radius:18px;margin:.2rem 0 1rem;
  border:1px solid rgba(30,136,229,.2);background:linear-gradient(135deg,#eef8ff,#f2fbf4)}
.active-area {padding:.7rem .9rem;border-radius:14px;background:rgba(33,150,243,.08);
  border-left:4px solid #2196f3;margin:.2rem 0 .7rem}
.species-grid {display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
  gap:1rem;margin:.75rem 0 1rem}
.species-card {min-width:0;border:1px solid rgba(49,63,72,.18);border-radius:14px;
  overflow:hidden;background:var(--secondary-background-color);box-shadow:0 2px 8px rgba(0,0,0,.08)}
.species-card.unseen {border:3px solid #e53935;box-shadow:0 2px 10px rgba(229,57,53,.24)}
.species-card a {color:inherit;text-decoration:none}
.species-photo {display:block;width:100%;height:178px;object-fit:cover;background:#e5e7e9}
.species-photo-empty {height:178px;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#dce9ef,#edf5e7);font-size:2.2rem}
.species-body {padding:.8rem .85rem .9rem}
.species-name {font-size:1.08rem;font-weight:750;line-height:1.15;margin-bottom:.18rem}
.species-scientific {font-size:.88rem;font-style:italic;opacity:.68;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;margin-bottom:.62rem}
.species-stats {display:flex;gap:.45rem;flex-wrap:wrap;margin-bottom:.55rem}
.species-pill {font-size:.78rem;padding:.2rem .45rem;border-radius:999px;
  background:rgba(33,150,243,.12)}
[data-testid="stFileUploaderDropzone"] {padding:.15rem 0;border:0;background:transparent}
[data-testid="stFileUploaderDropzoneInstructions"] {display:none}
[data-testid="stFileUploaderDropzone"] button {font-size:0;min-height:46px}
[data-testid="stFileUploaderDropzone"] button::after {content:"Kies gebied";font-size:1rem}
[data-testid="stFileUploaderFile"] {display:none}
[data-testid="stCheckbox"] [data-baseweb="checkbox"] > div {border-radius:50% !important}
@media (max-width:768px){.block-container{padding-left:.8rem;padding-right:.8rem}}
@media (max-width:540px){.species-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem}
  .species-photo,.species-photo-empty{height:132px}.species-body{padding:.65rem}
  .species-name{font-size:.95rem}}
</style>
""",
    unsafe_allow_html=True,
)


def init_state():
    defaults = {
        "areas": {},
        "active_area": None,
        "show_area_creator": False,
        "area_species": None,
        "personal_counts": {},
        "personal_families": set(),
        "personal_lineage_ids": set(),
        "personal_loaded_for": None,
        "area_taxonomy_frame": None,
        "taxon_candidates": [],
        "focus_username": True,
        "explore_meta": {},
        "last_area_upload": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_results():
    st.session_state.area_species = None
    st.session_state.personal_counts = {}
    st.session_state.personal_families = set()
    st.session_state.personal_lineage_ids = set()
    st.session_state.personal_loaded_for = None
    st.session_state.area_taxonomy_frame = None
    st.session_state.explore_meta = {}


def remember_area(name, geometry):
    """Keep the active area in the URL so it survives a sleeping app session."""
    try:
        payload = json.dumps({"name": name, "geometry": geometry}, separators=(",", ":"))
        token = base64.urlsafe_b64encode(zlib.compress(payload.encode("utf-8"), 9)).decode().rstrip("=")
        st.query_params["gebied"] = token
    except Exception:
        pass


def restore_remembered_area():
    if st.session_state.areas:
        return
    token = st.query_params.get("gebied")
    if not token:
        return
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(zlib.decompress(base64.urlsafe_b64decode(padded)).decode("utf-8"))
        name, geometry = str(payload["name"]), payload["geometry"]
        restored = shape(geometry)
        if restored.is_empty or not restored.is_valid:
            return
        st.session_state.areas[name] = geometry
        st.session_state.active_area = name
    except Exception:
        pass


def focus_username_once():
    if not st.session_state.focus_username:
        return
    components.html(
        """
        <script>
        let attempts = 0;
        const timer = setInterval(() => {
          attempts += 1;
          try {
            const input = [...window.parent.document.querySelectorAll('input')]
              .find(el => el.getAttribute('aria-label') === 'Openbare iNaturalist-gebruikersnaam');
            if (input) {
              input.focus();
              clearInterval(timer);
            }
          } catch (e) { clearInterval(timer); }
          if (attempts > 20) clearInterval(timer);
        }, 100);
        </script>
        """,
        height=0,
    )
    st.session_state.focus_username = False


def area_geojson(name, geometry):
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": name},
                "geometry": geometry,
            }],
        },
        ensure_ascii=False,
        indent=2,
    )


def area_filename(name):
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_")
    return f"{safe or 'te_verkennen_gebied'}.geojson"


def request_json(url, params, timeout=(10, 45)):
    global LAST_REQUEST_AT
    last_error = None
    for attempt in range(4):
        try:
            with REQUEST_LOCK:
                wait = MIN_REQUEST_INTERVAL - (time.monotonic() - LAST_REQUEST_AT)
                if wait > 0:
                    time.sleep(wait)
                LAST_REQUEST_AT = time.monotonic()
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers={"User-Agent": "Biodiversiteit-Verkenner/1.0"},
            )
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(0.8 * (2 ** attempt))
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(0.6 * (2 ** attempt))
    raise RuntimeError(f"iNaturalist kon niet worden bereikt: {last_error}")


def compact_photo(photo):
    if not photo:
        return ""
    return str(
        photo.get("medium_url")
        or photo.get("url")
        or photo.get("square_url")
        or ""
    ).replace("square", "medium")


def compact_taxon(taxon):
    taxon = taxon or {}
    ancestor_ids = []
    for item in taxon.get("ancestor_ids") or []:
        if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
            ancestor_ids.append(int(item))
    for item in taxon.get("ancestors") or []:
        tid = item.get("id") if isinstance(item, dict) else item
        if tid and str(tid).isdigit():
            ancestor_ids.append(int(tid))
    if taxon.get("id"):
        ancestor_ids.append(int(taxon["id"]))
    return {
        "id": taxon.get("id"),
        "rank": taxon.get("rank"),
        "name": taxon.get("name"),
        "preferred_common_name": taxon.get("preferred_common_name"),
        "ancestor_ids": list(dict.fromkeys(ancestor_ids)),
        "photo": compact_photo(taxon.get("default_photo")),
    }


def compact_observation(observation):
    photos = observation.get("photos") or []
    return {
        "id": observation.get("id"),
        "observed_on": observation.get("observed_on"),
        "geojson": observation.get("geojson"),
        "taxon": compact_taxon(observation.get("taxon")),
        "photo": compact_photo(photos[0]) if photos else "",
    }


@st.cache_data(ttl=86400, show_spinner=False)
def search_orders_and_families(query):
    query = (query or "").strip()
    if len(query) < 2:
        return []
    payload = request_json(TAXA_AUTOCOMPLETE_API, {
        "q": query,
        "per_page": 30,
        "locale": "en",
    })
    results = []
    for taxon in payload.get("results", []):
        if taxon.get("rank") not in {"order", "family"} or not taxon.get("id"):
            continue
        scientific = taxon.get("name") or ""
        common = taxon.get("preferred_common_name") or ""
        title = f"{common} ({scientific})" if common and common != scientific else scientific
        results.append({
            "id": int(taxon["id"]),
            "rank": taxon.get("rank"),
            "label": title,
        })
    return results


def split_bbox(bbox):
    south, west, north, east = bbox
    mid_lat = (south + north) / 2
    mid_lng = (west + east) / 2
    return [
        (south, west, mid_lat, mid_lng),
        (south, mid_lng, mid_lat, east),
        (mid_lat, west, north, mid_lng),
        (mid_lat, mid_lng, north, east),
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_observation_tile(base_params_tuple, bbox, depth=0):
    """Fetch one bbox, recursively splitting before iNaturalist's 10k ceiling."""
    base = dict(base_params_tuple)
    south, west, north, east = bbox
    params = dict(base)
    params.update({
        "swlat": south, "swlng": west, "nelat": north, "nelng": east,
        "page": 1, "per_page": 200,
    })
    first = request_json(OBS_API, params)
    total = int(first.get("total_results", 0) or 0)

    if total > 9500 and depth < 5:
        rows, api_total, truncated = [], 0, False
        for child in split_bbox(bbox):
            child_rows, child_total, child_truncated = fetch_observation_tile(
                base_params_tuple, child, depth + 1
            )
            rows.extend(child_rows)
            api_total += child_total
            truncated = truncated or child_truncated
        return rows, api_total, truncated

    page_count = min(50, max(1, math.ceil(min(total, 10000) / 200)))
    pages = {1: first.get("results", [])}

    def fetch_page(page):
        page_params = dict(params)
        page_params["page"] = page
        return page, request_json(OBS_API, page_params).get("results", [])

    if page_count > 1:
        with ThreadPoolExecutor(max_workers=min(4, page_count - 1)) as executor:
            futures = [executor.submit(fetch_page, page) for page in range(2, page_count + 1)]
            for future in as_completed(futures):
                page, results = future.result()
                pages[page] = results

    rows = [
        compact_observation(item)
        for page in range(1, page_count + 1)
        for item in pages.get(page, [])
    ]
    return rows, total, total > 10000


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_area_species_counts(base_params_tuple, bbox):
    """Fetch aggregated species counts for a bbox in a small number of calls."""
    base = dict(base_params_tuple)
    south, west, north, east = bbox
    def fetch_page(page):
        params = dict(base)
        params.update({
            "swlat": south, "swlng": west, "nelat": north, "nelng": east,
            "page": page, "per_page": 500,
        })
        return request_json(SPECIES_COUNTS_API, params)

    first = fetch_page(1)
    total = int(first.get("total_results", 0) or 0)
    page_count = min(math.ceil(total / 500), math.ceil(MAX_FAST_SPECIES / 500))
    pages = {1: first.get("results", [])}
    if page_count > 1:
        with ThreadPoolExecutor(max_workers=min(6, page_count - 1)) as executor:
            futures = {executor.submit(fetch_page, page): page for page in range(2, page_count + 1)}
            for future in as_completed(futures):
                pages[futures[future]] = future.result().get("results", [])
    raw_rows = [item for page in range(1, page_count + 1) for item in pages.get(page, [])]
    rows = [{
            "count": int(item.get("count") or 0),
            "taxon": compact_taxon(item.get("taxon")),
        } for item in raw_rows]
    return rows[:MAX_FAST_SPECIES], total, total > MAX_FAST_SPECIES


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_taxa_by_ids(ids_tuple, locale="en"):
    ids = sorted({int(x) for x in ids_tuple if x})
    batches = [ids[i:i + 30] for i in range(0, len(ids), 30)]

    def fetch_batch(batch):
        payload = request_json(
            f"{TAXA_API}/" + ",".join(str(x) for x in batch),
            {"per_page": len(batch), "locale": locale},
        )
        out = {}
        for taxon in payload.get("results", []):
            if not taxon.get("id"):
                continue
            out[int(taxon["id"])] = {
                "id": int(taxon["id"]),
                "rank": taxon.get("rank"),
                "name": taxon.get("name"),
                "preferred_common_name": taxon.get("preferred_common_name"),
                "photo": compact_photo(taxon.get("default_photo")),
            }
        return out

    result = {}
    if batches:
        with ThreadPoolExecutor(max_workers=min(6, len(batches))) as executor:
            for future in as_completed([executor.submit(fetch_batch, batch) for batch in batches]):
                result.update(future.result())
    return result


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_leaf_taxonomy(ids_tuple, locale="en"):
    """Fetch leaf taxa; each response already carries its complete ancestors."""
    ids = sorted({int(x) for x in ids_tuple if x})
    batches = [ids[i:i + 30] for i in range(0, len(ids), 30)]

    def add_record(target, taxon):
        if not taxon or not taxon.get("id"):
            return
        target[int(taxon["id"])] = {
            "id": int(taxon["id"]),
            "rank": taxon.get("rank"),
            "name": taxon.get("name"),
            "preferred_common_name": taxon.get("preferred_common_name"),
            "photo": compact_photo(taxon.get("default_photo")),
            "ancestor_ids": [
                int(x) for x in (taxon.get("ancestor_ids") or []) if str(x).isdigit()
            ] + [int(taxon["id"])],
        }

    def fetch_batch(batch):
        payload = request_json(
            f"{TAXA_API}/" + ",".join(str(x) for x in batch),
            {"per_page": len(batch), "locale": locale},
        )
        out = {}
        for taxon in payload.get("results", []):
            add_record(out, taxon)
            for ancestor in taxon.get("ancestors") or []:
                add_record(out, ancestor)
        return out

    result = {}
    if batches:
        with ThreadPoolExecutor(max_workers=min(8, len(batches))) as executor:
            for future in as_completed([executor.submit(fetch_batch, batch) for batch in batches]):
                result.update(future.result())
    return result


def rank_id(taxon, lookup, wanted_rank):
    for tid in reversed(taxon.get("ancestor_ids") or []):
        record = lookup.get(int(tid))
        if record and record.get("rank") == wanted_rank:
            return int(tid)
    if taxon.get("rank") == wanted_rank and taxon.get("id"):
        return int(taxon["id"])
    return None


def rank_names(taxon_id, lookup):
    record = lookup.get(int(taxon_id)) if taxon_id else None
    if not record:
        return None, None
    return record.get("preferred_common_name") or record.get("name"), record.get("name")


def build_area_species(observations, geometry):
    polygon = shape(geometry)
    inside = {}
    ancestor_ids = set()

    for observation in observations:
        geo = observation.get("geojson") or {}
        coordinates = geo.get("coordinates") or []
        if len(coordinates) < 2 or not polygon.covers(Point(coordinates[0], coordinates[1])):
            continue
        oid = observation.get("id")
        if oid is not None:
            inside[int(oid)] = observation
        ancestor_ids.update(observation.get("taxon", {}).get("ancestor_ids") or [])

    lookup = fetch_taxa_by_ids(tuple(sorted(ancestor_ids)))
    grouped = {}
    for observation in inside.values():
        taxon = observation.get("taxon") or {}
        species_id = rank_id(taxon, lookup, "species")
        if not species_id:
            continue
        species = lookup.get(species_id, {})
        family_id = rank_id(taxon, lookup, "family")
        order_id = rank_id(taxon, lookup, "order")
        family_nl, family_scientific = rank_names(family_id, lookup)
        order_nl, order_scientific = rank_names(order_id, lookup)
        row = grouped.setdefault(species_id, {
            "species_id": species_id,
            "Engelse naam": species.get("preferred_common_name") or species.get("name") or taxon.get("preferred_common_name") or taxon.get("name"),
            "Wetenschappelijke naam": species.get("name") or taxon.get("name"),
            "Waarnemingen in gebied": 0,
            "Familie": family_nl or family_scientific or "Onbekend",
            "Familie wetenschappelijk": family_scientific or "Onbekend",
            "family_id": family_id,
            "Orde": order_nl or order_scientific or "Onbekend",
            "Orde wetenschappelijk": order_scientific or "Onbekend",
            "order_id": order_id,
            "Foto": species.get("photo") or taxon.get("photo") or observation.get("photo") or "",
            "iNaturalist": f"https://www.inaturalist.org/taxa/{species_id}",
        })
        row["Waarnemingen in gebied"] += 1
        if not row["Foto"]:
            row["Foto"] = observation.get("photo") or ""

    columns = [
        "species_id", "Engelse naam", "Wetenschappelijke naam",
        "Waarnemingen in gebied", "Familie", "Familie wetenschappelijk", "family_id",
        "Orde", "Orde wetenschappelijk", "order_id", "Foto", "iNaturalist",
    ]
    if not grouped:
        return pd.DataFrame(columns=columns), len(inside)
    frame = pd.DataFrame(grouped.values())
    return frame.sort_values(
        ["Waarnemingen in gebied", "Engelse naam"], ascending=[False, True]
    ).reset_index(drop=True), len(inside)


def build_fast_area_species(count_rows, group_label=""):
    """Build cards without extra API calls; skip leaves not resolved to species."""
    grouped = {}
    for item in count_rows:
        taxon = item.get("taxon") or {}
        rank = taxon.get("rank")
        ancestor_ids = taxon.get("ancestor_ids") or []
        if rank == "species" and taxon.get("id"):
            species_id = int(taxon["id"])
        elif rank in {"subspecies", "variety", "form"} and len(ancestor_ids) >= 2:
            species_id = int(ancestor_ids[-2])
        else:
            species_id = None
        if not species_id:
            continue
        row = grouped.setdefault(species_id, {
            "species_id": species_id,
            "Engelse naam": taxon.get("preferred_common_name") or taxon.get("name"),
            "Wetenschappelijke naam": taxon.get("name"),
            "Waarnemingen in gebied": 0,
            "Familie": "",
            "Familie wetenschappelijk": "",
            "family_id": None,
            "Orde": group_label,
            "Orde wetenschappelijk": group_label,
            "order_id": None,
            "Foto": taxon.get("photo") or "",
            "iNaturalist": f"https://www.inaturalist.org/taxa/{species_id}",
        })
        row["Waarnemingen in gebied"] += int(item.get("count") or 0)
    columns = [
        "species_id", "Engelse naam", "Wetenschappelijke naam",
        "Waarnemingen in gebied", "Familie", "Familie wetenschappelijk", "family_id",
        "Orde", "Orde wetenschappelijk", "order_id", "Foto", "iNaturalist",
    ]
    if not grouped:
        return pd.DataFrame(columns=columns), 0
    frame = pd.DataFrame(grouped.values())
    total_observations = int(frame["Waarnemingen in gebied"].sum())
    return frame.sort_values(
        ["Waarnemingen in gebied", "Engelse naam"], ascending=[False, True]
    ).reset_index(drop=True), total_observations


@st.cache_data(ttl=86400, show_spinner=False)
def enrich_area_taxonomy(frame_json):
    """Resolve family and order only for the overview that actually needs them."""
    frame = pd.read_json(StringIO(frame_json), orient="split")
    lookup = fetch_leaf_taxonomy(tuple(sorted(int(x) for x in frame["species_id"].tolist())))
    for index, row in frame.iterrows():
        species_id = int(row["species_id"])
        taxon = lookup.get(species_id, {})
        family_id = rank_id(taxon, lookup, "family")
        order_id = rank_id(taxon, lookup, "order")
        family_nl, family_scientific = rank_names(family_id, lookup)
        order_nl, order_scientific = rank_names(order_id, lookup)
        frame.at[index, "family_id"] = family_id
        frame.at[index, "Familie"] = family_nl or family_scientific or "Onbekend"
        frame.at[index, "Familie wetenschappelijk"] = family_scientific or "Onbekend"
        frame.at[index, "order_id"] = order_id
        frame.at[index, "Orde"] = order_nl or order_scientific or "Onbekend"
        frame.at[index, "Orde wetenschappelijk"] = order_scientific or "Onbekend"
    return frame


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_personal_lifelist(username, iconic_taxa="", taxon_id=None):
    username = (username or "").strip()
    if not username:
        return {}, set(), 0

    def fetch_page(page):
        params = {
            "user_id": username,
            "per_page": 500,
            "page": page,
            "locale": "en",
        }
        if iconic_taxa:
            params["iconic_taxa"] = iconic_taxa
        if taxon_id:
            params["taxon_id"] = int(taxon_id)
        return request_json(SPECIES_COUNTS_API, params)

    first = fetch_page(1)
    total = int(first.get("total_results", 0) or 0)
    page_count = max(1, math.ceil(total / 500))
    pages = {1: first.get("results", [])}
    if page_count > 1:
        with ThreadPoolExecutor(max_workers=min(8, page_count - 1)) as executor:
            futures = {executor.submit(fetch_page, page): page for page in range(2, page_count + 1)}
            for future in as_completed(futures):
                pages[futures[future]] = future.result().get("results", [])
    rows = [item for page in range(1, page_count + 1) for item in pages.get(page, [])]

    compact = [(compact_taxon(item.get("taxon")), int(item.get("count") or 0)) for item in rows]
    # Exact species need no extra taxonomy request. Only lower-rank leaf taxa
    # (subspecies, varieties, etc.) need their ancestry resolved back to species.
    lower_rank_leaf_ids = {
        int(taxon["id"])
        for taxon, _ in compact
        if taxon.get("rank") != "species" and taxon.get("id")
    }
    lookup = fetch_leaf_taxonomy(tuple(sorted(lower_rank_leaf_ids)))
    counts = {}
    lineage_ids = set()
    for taxon, count in compact:
        species_id = (
            int(taxon["id"])
            if taxon.get("rank") == "species" and taxon.get("id")
            else rank_id(taxon, lookup, "species")
        )
        if not species_id:
            continue
        counts[species_id] = counts.get(species_id, 0) + count
        # Only a record that can be traced to an actual species proves that
        # the observer has seen a species from its family. A family-only or
        # genus-only identification must not make the whole family "known".
        lineage_ids.update(int(tid) for tid in (taxon.get("ancestor_ids") or []))
    return counts, lineage_ids, len(rows)


def pie_frame(frame, max_slices=14):
    if frame.empty:
        return pd.DataFrame(columns=["Soort", "Waarnemingen"])
    grouped = (
        frame.groupby("Engelse naam", dropna=False)["Waarnemingen in gebied"]
        .sum().sort_values(ascending=False)
    )
    if len(grouped) > max_slices:
        top = grouped.iloc[:max_slices].copy()
        top.loc["Overige soorten"] = grouped.iloc[max_slices:].sum()
        grouped = top
    return grouped.rename_axis("Soort").reset_index(name="Waarnemingen")


def show_species_grid(frame, include_personal=False, highlight_unseen=False, key="species"):
    if frame.empty:
        st.info("Binnen deze filters zijn geen soorten gevonden.")
        return
    maximum = min(250, len(frame))
    if maximum == 1:
        shown = 1
    else:
        default = min(50, maximum)
        shown = st.slider(
            "Aantal soorten tonen", 10 if maximum >= 10 else 1, maximum, default,
            key=f"limit_{key}",
        )
    cards = []
    for _, row in frame.head(shown).iterrows():
        name = html.escape(str(row.get("Engelse naam") or row.get("Wetenschappelijke naam") or "Unknown species"))
        scientific = html.escape(str(row.get("Wetenschappelijke naam") or ""))
        photo_url = html.escape(str(row.get("Foto") or ""), quote=True)
        taxon_url = html.escape(str(row.get("iNaturalist") or "#"), quote=True)
        observations = int(row.get("Waarnemingen in gebied") or 0)
        personal = int(row.get("Mijn waarnemingen wereldwijd") or 0)
        card_class = "species-card unseen" if highlight_unseen and personal == 0 else "species-card"
        photo = (
            f'<img class="species-photo" src="{photo_url}" alt="{name}" loading="lazy">'
            if photo_url else '<div class="species-photo-empty">🌿</div>'
        )
        personal_pill = (
            f'<span class="species-pill">Mijn totaal: {personal:,}</span>'
            if include_personal else ""
        )
        cards.append(
            f'<article class="{card_class}">'
            f'<a href="{taxon_url}" target="_blank" rel="noopener">{photo}'
            '<div class="species-body">'
            f'<div class="species-name">{name}</div>'
            f'<div class="species-scientific">{scientific}</div>'
            '<div class="species-stats">'
            f'<span class="species-pill">{observations:,} in gebied</span>{personal_pill}'
            '</div>'
            '</div></a></article>'
        )
    st.markdown('<div class="species-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)
    columns = ["Engelse naam", "Wetenschappelijke naam", "Waarnemingen in gebied"]
    if include_personal:
        columns.append("Mijn waarnemingen wereldwijd")
    columns += ["Familie", "Orde"]
    export_columns = [c for c in columns if c not in {"Foto", "iNaturalist"}]
    st.download_button(
        "⬇️ Tabel downloaden als CSV",
        frame[export_columns].to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{key}.csv",
        mime="text/csv",
        key=f"csv_{key}",
    )


init_state()
restore_remembered_area()

st.markdown('<span class="release-badge">Versie 1.6 · Engelse soortnamen</span>', unsafe_allow_html=True)
st.title("🧭 Biodiversiteit Verkenner")
st.markdown(
    '<div class="intro"><b>Ontdek natuurgebieden waar je nog niet bent geweest.</b><br>'
    'Kies of teken een gebied en bekijk welke soorten daar vaak worden waargenomen, '
    'welke voor jou nieuw zijn en waar zelfs een nieuwe familie op je kan wachten.</div>',
    unsafe_allow_html=True,
)

pick_col, new_col = st.columns([3, 1])
with pick_col:
    uploaded = st.file_uploader(
        "Selecteer een bewaard gebied",
        type=["geojson", "json"],
        key="explorer_area_upload",
    )
with new_col:
    st.write("")
    if st.button("➕ Nieuw gebied maken", key="toggle_area_creator"):
        st.session_state.show_area_creator = not st.session_state.show_area_creator

if uploaded is not None:
    upload_key = (uploaded.name, uploaded.size)
    if st.session_state.last_area_upload != upload_key:
        try:
            payload = json.loads(uploaded.getvalue().decode("utf-8"))
            features = (
                payload.get("features") or []
                if payload.get("type") == "FeatureCollection"
                else [payload] if payload.get("type") == "Feature" else []
            )
            imported = []
            for number, feature in enumerate(features, 1):
                geometry = feature.get("geometry")
                if not geometry:
                    continue
                name = str((feature.get("properties") or {}).get("name") or f"Gebied {number}").strip()
                st.session_state.areas[name] = geometry
                imported.append(name)
            if not imported:
                st.warning("In dit bestand is geen bruikbaar gebied gevonden.")
            else:
                st.session_state.active_area = imported[0]
                st.session_state.last_area_upload = upload_key
                remember_area(imported[0], st.session_state.areas[imported[0]])
                clear_results()
                st.rerun()
        except Exception as exc:
            st.error(f"Dit GeoJSON-bestand kon niet worden geopend: {exc}")

if st.session_state.areas:
    names = list(st.session_state.areas)
    current = st.session_state.active_area if st.session_state.active_area in names else names[0]
    if len(names) > 1:
        selected_area = st.selectbox("Actief gebied", names, index=names.index(current))
        if selected_area != st.session_state.active_area:
            st.session_state.active_area = selected_area
            remember_area(selected_area, st.session_state.areas[selected_area])
            clear_results()
            st.rerun()
    else:
        st.session_state.active_area = current
    st.markdown(
        f'<div class="active-area"><b>Actief gebied:</b> {html.escape(st.session_state.active_area)}</div>',
        unsafe_allow_html=True,
    )
    st.download_button(
        "💾 Actief gebied op schijf bewaren",
        area_geojson(st.session_state.active_area, st.session_state.areas[st.session_state.active_area]),
        area_filename(st.session_state.active_area),
        "application/geo+json",
    )

if st.session_state.show_area_creator:
    with st.container(border=True):
        st.subheader("Nieuw gebied maken")
        area_name = st.text_input("Naam van het gebied", placeholder="Bijvoorbeeld: De Biesbosch")
        center, zoom = [52.1, 5.3], 8
        if st.session_state.active_area in st.session_state.areas:
            current_geometry = shape(st.session_state.areas[st.session_state.active_area])
            center = [current_geometry.centroid.y, current_geometry.centroid.x]
            zoom = 13
        map_object = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap", control_scale=True)
        Draw(
            export=False,
            position="topleft",
            draw_options={
                "polyline": False, "circle": False, "circlemarker": False, "marker": False,
                "polygon": {"allowIntersection": False, "showArea": True}, "rectangle": True,
            },
            edit_options={"edit": True, "remove": True},
        ).add_to(map_object)
        map_state = st_folium(
            map_object, height=520, use_container_width=True,
            key="explorer_draw_map", returned_objects=["all_drawings"],
        )
        drawings = map_state.get("all_drawings") or []
        geometry = drawings[-1].get("geometry") if drawings else None
        clean_name = area_name.strip()
        ready = bool(clean_name and geometry)
        use_col, save_col = st.columns(2)
        with use_col:
            use_area = st.button("✅ Gebied gebruiken", type="primary", key="use_drawn_area")
        with save_col:
            st.download_button(
                "💾 Gebied op schijf bewaren",
                area_geojson(clean_name, geometry) if ready else "",
                area_filename(clean_name),
                "application/geo+json",
                disabled=not ready,
            )
        if use_area:
            if not clean_name:
                st.error("Geef het gebied eerst een naam.")
            elif not geometry:
                st.error("Teken eerst een gebied op de kaart.")
            else:
                st.session_state.areas[clean_name] = geometry
                st.session_state.active_area = clean_name
                remember_area(clean_name, geometry)
                st.session_state.show_area_creator = False
                clear_results()
                st.rerun()

st.divider()
st.subheader("Zoekperiode en persoonlijke vergelijking")
current_year = date.today().year
username_col, years_col = st.columns([1, 1])
with username_col:
    username = st.text_input(
        "Openbare iNaturalist-gebruikersnaam",
        help="Nodig voor soorten die je nog nooit hebt gezien en nieuwe families. Geen wachtwoord nodig.",
    ).strip()
with years_col:
    year_range = st.slider(
        "Jaren", 2008, current_year, (max(2008, current_year - 9), current_year)
    )
focus_username_once()

st.markdown("**Maanden van het jaar**")
month_columns = st.columns(4)
selected_months = []
for month, label in MONTHS.items():
    with month_columns[(month - 1) % 4]:
        if st.checkbox(label.capitalize(), value=False, key=f"month_{month}"):
            selected_months.append(month)
if not selected_months:
    st.caption("Kies minimaal één maand om het gebied te kunnen verkennen.")
quality_label = st.selectbox(
    "Kwaliteit van de waarnemingen",
    ["Research Grade en Needs ID", "Alle kwaliteitsniveaus", "Alleen Research Grade"],
)
quality_value = {
    "Research Grade en Needs ID": "research,needs_id",
    "Alle kwaliteitsniveaus": "",
    "Alleen Research Grade": "research",
}[quality_label]

st.markdown("**Soortgroep vóór het verkennen**")
group_label = st.selectbox("Grote soortgroep", list(SPECIES_GROUPS), label_visibility="collapsed")
taxon_search_col, taxon_button_col = st.columns([3, 1])
with taxon_search_col:
    taxon_query = st.text_input(
        "Orde of familie zoeken (optioneel)",
        placeholder="Bijvoorbeeld: Perciformes, Cyprinidae of uilen",
    )
with taxon_button_col:
    st.write("")
    search_taxon = st.button("Zoeken", key="search_taxon")
if search_taxon:
    with st.spinner("Ordes en families zoeken…"):
        st.session_state.taxon_candidates = search_orders_and_families(taxon_query)
    if not st.session_state.taxon_candidates:
        st.warning("Geen orde of familie gevonden. Probeer een wetenschappelijke naam.")

candidate_options = [None] + st.session_state.taxon_candidates
selected_taxon = st.selectbox(
    "Gekozen orde of familie",
    candidate_options,
    format_func=lambda item: "Geen extra beperking" if item is None else f"{item['label']} · {item['rank']}",
)

active_area = st.session_state.active_area
can_explore = bool(active_area and active_area in st.session_state.areas and selected_months)
if st.button("🔎 Gebied verkennen", type="primary", disabled=not can_explore):
    geometry = st.session_state.areas[active_area]
    bounds = shape(geometry).bounds
    west, south, east, north = bounds
    base_params = {
        "d1": f"{year_range[0]}-01-01",
        "d2": f"{year_range[1]}-12-31",
        "geo": "true",
        "locale": "en",
        "order_by": "observed_on",
        "order": "desc",
    }
    if quality_value:
        base_params["quality_grade"] = quality_value
    if SPECIES_GROUPS[group_label]:
        base_params["iconic_taxa"] = SPECIES_GROUPS[group_label]
    if selected_taxon:
        base_params["taxon_id"] = int(selected_taxon["id"])

    if len(selected_months) < 12:
        base_params["month"] = ",".join(str(month) for month in selected_months)

    api_total, truncated = 0, False
    with st.status("Gebiedssoorten verzamelen…", expanded=True) as status:
        st.write("Geaggregeerde soorten en aantallen ophalen…")
        count_rows, api_total, truncated = fetch_area_species_counts(
            tuple(sorted(base_params.items())), (south, west, north, east)
        )
        st.write(f"Fotokaarten van {len(count_rows):,} gevonden taxa maken…")
        context_label = selected_taxon["label"] if selected_taxon else group_label if group_label != "Alle soortgroepen" else ""
        area_frame, observation_total = build_fast_area_species(count_rows, context_label)

        st.session_state.area_species = area_frame
        st.session_state.personal_counts = {}
        st.session_state.personal_families = set()
        st.session_state.personal_lineage_ids = set()
        st.session_state.personal_loaded_for = None
        st.session_state.area_taxonomy_frame = None
        st.session_state.explore_meta = {
            "area": active_area,
            "username": username,
            "years": year_range,
            "months": selected_months,
            "api_total": api_total,
            "observation_total": observation_total,
            "truncated": truncated,
            "personal_species": 0,
            "group_label": group_label,
            "selected_taxon": selected_taxon,
            "iconic_taxa": SPECIES_GROUPS[group_label],
            "taxon_id": int(selected_taxon["id"]) if selected_taxon else None,
        }
        status.update(label="Verkenning gereed", state="complete")

frame = st.session_state.area_species
if frame is not None:
    meta = st.session_state.explore_meta
    st.divider()
    filtered = frame.copy()
    if meta.get("truncated"):
        st.warning(
            "De veiligheidsgrens voor een zeer soortenrijk gebied is bereikt. De meest "
            "waargenomen soorten staan erin, maar zeldzamere soorten kunnen ontbreken."
        )
    st.caption(
        f"Gebaseerd op {meta.get('observation_total', 0):,} waarnemingen binnen de "
        "kleinste rechthoek om het gekozen gebied in "
        f"{meta.get('years', ('?', '?'))[0]}–{meta.get('years', ('?', '?'))[1]}. "
        "Historische waarnemingen geven een kansbeeld, geen garantie dat een soort aanwezig is."
    )
    chosen_group = meta.get("selected_taxon", {}).get("label") if meta.get("selected_taxon") else meta.get("group_label")
    if chosen_group and chosen_group != "Alle soortgroepen":
        st.info(f"Vooraf geselecteerde soortgroep: **{chosen_group}**")

    st.subheader("Kies een overzicht")
    overview_options = [
        "Gebiedssoorten met mijn totale aantal waarnemingen",
        "Welke soorten heb ik zelf nog nooit gezien?",
        "Verdeling van de waarnemingen",
        "Soorten uit families die voor mij volledig nieuw zijn",
    ]
    overview = st.radio(
        "Overzicht",
        overview_options,
        index=0,
        label_visibility="collapsed",
    )

    personal_overviews = set(overview_options)
    personal_ready = False
    if overview in personal_overviews and username:
        personal_filter_key = (username, meta.get("iconic_taxa") or "", meta.get("taxon_id"))
        if st.session_state.personal_loaded_for != personal_filter_key:
            with st.status("Persoonlijke vergelijking laden…", expanded=True) as personal_status:
                filter_text = chosen_group if chosen_group and chosen_group != "Alle soortgroepen" else "alle soortgroepen"
                st.write(f"Jouw openbare iNaturalist-soortenlijst voor {filter_text} ophalen…")
                counts, lineage_ids, personal_species = fetch_personal_lifelist(
                    username,
                    meta.get("iconic_taxa") or "",
                    meta.get("taxon_id"),
                )
                st.session_state.personal_counts = counts
                st.session_state.personal_lineage_ids = lineage_ids
                st.session_state.personal_loaded_for = personal_filter_key
                st.session_state.explore_meta["personal_species"] = personal_species
                personal_status.update(label="Persoonlijke vergelijking gereed", state="complete")
        personal_ready = st.session_state.personal_loaded_for == personal_filter_key

    personal_counts = st.session_state.personal_counts if personal_ready else {}
    filtered["Mijn waarnemingen wereldwijd"] = (
        filtered["species_id"].map(personal_counts).fillna(0).astype(int)
    )
    unseen = filtered[~filtered["species_id"].isin(personal_counts)].copy()
    new_family = pd.DataFrame(columns=filtered.columns)

    if overview == overview_options[3] and personal_ready:
        if st.session_state.area_taxonomy_frame is None:
            with st.status("Families bepalen…", expanded=True) as family_status:
                st.write("Alleen voor dit overzicht families en ordes ophalen…")
                st.session_state.area_taxonomy_frame = enrich_area_taxonomy(
                    filtered.to_json(orient="split")
                )
                family_status.update(label="Families gereed", state="complete")
        taxonomy_frame = st.session_state.area_taxonomy_frame.copy()
        personal_families = {
            int(x) for x in taxonomy_frame["family_id"].dropna().tolist()
        }.intersection(st.session_state.personal_lineage_ids)
        new_family = taxonomy_frame[
            taxonomy_frame["family_id"].notna()
            & ~taxonomy_frame["family_id"].isin(personal_families)
        ].copy()

    metric_a, metric_b, metric_c, metric_d = st.columns(4)
    metric_a.metric("Soorten in gebied", len(filtered))
    metric_b.metric("Waarnemingen", int(filtered["Waarnemingen in gebied"].sum()))
    metric_c.metric("Nog nooit gezien", len(unseen) if personal_ready else "—")
    metric_d.metric(
        "Nieuwe families",
        new_family["family_id"].nunique() if overview == overview_options[3] and personal_ready else "—",
    )

    if overview == overview_options[0]:
        st.markdown("### Gebiedssoorten met mijn totale aantal waarnemingen")
        if not username:
            st.info("Vul bovenaan je iNaturalist-gebruikersnaam in.")
        else:
            st.caption("Een rode rand betekent dat je deze soort nog nooit hebt waargenomen.")
            show_species_grid(
                filtered,
                include_personal=True,
                highlight_unseen=True,
                key="mijn_ervaring_per_soort",
            )

    elif overview == overview_options[1]:
        st.markdown("### Welke soorten heb ik zelf nog nooit gezien?")
        if not username:
            st.info("Vul bovenaan je iNaturalist-gebruikersnaam in.")
        else:
            show_species_grid(unseen, key="nog_nooit_gezien")

    elif overview == overview_options[2]:
        st.markdown("### Verdeling van de waarnemingen")
        chart_a, chart_b = st.columns(2)
        with chart_a:
            st.markdown("**Alle potentiële soorten**")
            pie_all = pie_frame(filtered)
            if pie_all.empty:
                st.info("Geen gegevens.")
            else:
                st.plotly_chart(
                    px.pie(pie_all, names="Soort", values="Waarnemingen", hole=.32),
                    width="stretch",
                )
        with chart_b:
            st.markdown("**Soorten die ik nog nooit heb gezien**")
            if not username:
                st.info("Vul eerst je iNaturalist-gebruikersnaam in.")
            else:
                pie_unseen = pie_frame(unseen)
                if pie_unseen.empty:
                    st.success("Je hebt alle gevonden soorten al eens waargenomen.")
                else:
                    st.plotly_chart(
                        px.pie(pie_unseen, names="Soort", values="Waarnemingen", hole=.32),
                        width="stretch",
                    )

    elif overview == overview_options[3]:
        st.markdown("### Soorten uit families die voor mij volledig nieuw zijn")
        if not username:
            st.info("Vul bovenaan je iNaturalist-gebruikersnaam in.")
        elif new_family.empty:
            st.success("Binnen deze filters zijn geen volledig nieuwe families gevonden.")
        else:
            st.caption(
                "Van deze families staat nog geen enkele soort op jouw wereldwijde iNaturalist-soortenlijst."
            )
            show_species_grid(new_family, key="nieuwe_families")

st.divider()
st.caption(
    "Biodiversiteit Verkenner 1.6 · openbare gegevens van iNaturalist · "
    "je gebruikersnaam wordt alleen gebruikt om openbare waarnemingen te vergelijken."
)
