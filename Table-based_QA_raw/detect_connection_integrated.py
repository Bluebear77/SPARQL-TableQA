#!/usr/bin/env python3

# ============================================================
# HOW TO RUN
# ============================================================
# 1. Install dependencies:
#       pip install requests tqdm
#
# 2. Edit the hardcoded file paths in the CONFIG section below.
#
# 3. Run:
#       python detect_connection_hardcoded_compmix.py
#
# ============================================================
# INPUT CSV
# ============================================================
# Required columns:
#   Entity_1
#   Entity_2
#
# Example:
#   Entity_1,Entity_2
#   Q503034,Q36949
#   Q503034,Q47221
#   Q363402,Q1214882
#   Q1214882,Q363402
#
# ============================================================
# OUTPUT CSV FORMAT
# ============================================================
# Entity_1,
# Entity_2,
# Connection_Path,
# Property_Number,
# Property_list,
# Qualifier_Number,
# Qualifier_list
#
# ============================================================
# SEARCH LOGIC
# ============================================================
# This script is now bi-directional.
#
# Step 1:
#   Search Entity_1's own Wikidata page:
#       Entity_1 -> property -> Entity_2
#       Entity_1 -> property -> main value -> qualifier -> Entity_2
#
# Step 2:
#   If Step 1 finds nothing, check incoming links to Entity_1 using
#   the WhatLinksHere-equivalent MediaWiki API with limit 500.
#
#   Equivalent page:
#       https://www.wikidata.org/w/index.php?title=Special:WhatLinksHere/Q363402&limit=500
#
#   If Entity_2 is one of the pages linking to Entity_1, then scan
#   Entity_2's page for the reverse stored statement:
#       Entity_2 -> property -> Entity_1
#       Entity_2 -> property -> main value -> qualifier -> Entity_1
#
# Step 3:
#   If still nothing is found, use fallback truthy graph search in
#   both directions.
#
# ============================================================
# IMPORTANT
# ============================================================
# The connection path shows the actual Wikidata statement direction.
#
# Example:
#   Input:
#       Stephen Sommers (Q363402), The Mummy (Q1214882)
#
#   Wikidata stores the statement on The Mummy's page:
#       The Mummy -> creator -> Stephen Sommers
#
#   So the output path is:
#       The Mummy (Q1214882)->creator (P170)->Stephen Sommers (Q363402)
#
# This is correct because the relationship exists as an incoming link
# to Stephen Sommers, not as an outgoing statement from Stephen Sommers.
# ============================================================

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from tqdm import tqdm


# ============================================================
# CONFIG
# ============================================================

INPUT_CSV_PATH = "input.csv"

# Hardcoded CompMix JSONL inputs.
# Put these files in the same folder where you run this script,
# or replace each filename with an absolute path.
INPUT_JSON_PATHS: List[str] = []
INPUT_JSONL_PATHS = [
    "CompMix_infobox.jsonl",
    "CompMix_table.jsonl",
    "CompMix_text.jsonl",
    "CompMix_kb.jsonl",
]

# Output files.
OUTPUT_CSV_PATH = "CompMix_connections.csv"
OUTPUT_LABEL_CSV_PATH = "CompMix_connections_label_name.csv"

# True = only run connection detection when both question entity and gold answer are Wikidata QIDs.
# This skips answers like Yes/No, dates, numbers, and plain text strings.
SKIP_NON_QID_PAIRS = True

LABEL_LANGUAGE = "en"

MAX_FALLBACK_HOPS = 2

WHATLINKSHERE_LIMIT = 500

INCLUDE_DEPRECATED_STATEMENTS = False

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
ENTITY_DATA_URL = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"
WBGETENTITIES_API = "https://www.wikidata.org/w/api.php"
MEDIAWIKI_API = "https://www.wikidata.org/w/api.php"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "WikidataBidirectionalPathFinder/5.0 "
                  "(Python requests; contact: your-email@example.com)",
}


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class ConnectionResult:
    property_ids: List[str]
    qualifier_ids: List[str]
    path_steps: List[Tuple[str, str]]
    source: str
    priority: int


# ============================================================
# BASIC PARSING / VALIDATION
# ============================================================

def extract_qid_from_cell(cell_value: str) -> str:
    text = str(cell_value).strip().upper()
    match = re.search(r"Q[1-9]\d*", text)

    if not match:
        raise ValueError(f"Could not find a valid QID in: {cell_value}")

    return match.group(0)


def validate_qid(qid: str) -> str:
    qid = str(qid).strip().upper()

    if not re.fullmatch(r"Q[1-9]\d*", qid):
        raise ValueError(f"Invalid QID: {qid}")

    return qid


def extract_last_path_segment(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def unique_preserve_order(values: List[str]) -> List[str]:
    seen: Set[str] = set()
    output: List[str] = []

    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)

    return output


# ============================================================
# NETWORK HELPERS
# ============================================================

_entity_json_cache: Dict[str, Dict[str, Any]] = {}
_whatlinkshere_cache: Dict[str, Set[str]] = {}


def get_entity_json(qid: str, timeout: int = 30, retries: int = 2) -> Dict[str, Any]:
    if qid in _entity_json_cache:
        return _entity_json_cache[qid]

    url = ENTITY_DATA_URL.format(qid)
    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            _entity_json_cache[qid] = data
            return data

        except Exception as exc:
            last_error = exc

            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise RuntimeError(f"Could not fetch EntityData for {qid}: {exc}") from exc

    raise RuntimeError(f"Could not fetch EntityData for {qid}: {last_error}")


def entity_exists(qid: str) -> bool:
    try:
        data = get_entity_json(qid)
        return qid in data.get("entities", {})
    except Exception:
        return False


def get_whatlinkshere_qids(target_qid: str, limit: int = WHATLINKSHERE_LIMIT) -> Set[str]:
    """
    Get up to 500 Wikidata item pages that link to target_qid.

    This uses the MediaWiki API equivalent of:

        https://www.wikidata.org/w/index.php?title=Special:WhatLinksHere/Q363402&limit=500

    API equivalent:

        action=query
        list=backlinks
        bltitle=Q363402
        blnamespace=0
        bllimit=500

    Returns only titles that look like QIDs.
    """
    target_qid = validate_qid(target_qid)

    if target_qid in _whatlinkshere_cache:
        return _whatlinkshere_cache[target_qid]

    params = {
        "action": "query",
        "list": "backlinks",
        "bltitle": target_qid,
        "blnamespace": 0,
        "bllimit": min(limit, 500),
        "format": "json",
    }

    try:
        response = requests.get(
            MEDIAWIKI_API,
            params=params,
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        backlinks = data.get("query", {}).get("backlinks", [])
        qids: Set[str] = set()

        for item in backlinks:
            title = str(item.get("title", "")).strip().upper()
            if re.fullmatch(r"Q[1-9]\d*", title):
                qids.add(title)

        _whatlinkshere_cache[target_qid] = qids
        return qids

    except Exception as exc:
        print(
            f"Warning: could not fetch WhatLinksHere for {target_qid}: {exc}",
            file=sys.stderr,
        )
        _whatlinkshere_cache[target_qid] = set()
        return set()


def run_sparql(query: str, timeout: int = 45, retries: int = 2) -> Dict[str, Any]:
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": HEADERS["User-Agent"],
    }

    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            response = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()

        except Exception as exc:
            last_error = exc

            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise RuntimeError(f"SPARQL query failed: {exc}") from exc

    raise RuntimeError(f"SPARQL query failed: {last_error}")


# ============================================================
# LABEL HELPERS
# ============================================================

_label_cache: Dict[Tuple[str, str], str] = {}


def get_entity_or_property_label(entity_id: str, language: str = LABEL_LANGUAGE) -> str:
    cache_key = (entity_id, language)

    if cache_key in _label_cache:
        return _label_cache[cache_key]

    params = {
        "action": "wbgetentities",
        "ids": entity_id,
        "props": "labels",
        "languages": language,
        "format": "json",
    }

    label = entity_id

    try:
        response = requests.get(
            WBGETENTITIES_API,
            params=params,
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        entity_data = data.get("entities", {}).get(entity_id, {})
        labels = entity_data.get("labels", {})

        if language in labels:
            label = labels[language]["value"]

    except Exception:
        label = entity_id

    _label_cache[cache_key] = label
    return label


def readable_entity(qid: str, language: str = LABEL_LANGUAGE) -> str:
    return f"{get_entity_or_property_label(qid, language)} ({qid})"


def readable_property(pid: str, language: str = LABEL_LANGUAGE) -> str:
    return f"{get_entity_or_property_label(pid, language)} ({pid})"


def readable_cell_entity(original_value: str, language: str = LABEL_LANGUAGE) -> str:
    try:
        qid = extract_qid_from_cell(original_value)
        return readable_entity(qid, language)
    except Exception:
        return str(original_value)


def readable_pid_list(raw_value: str, language: str = LABEL_LANGUAGE) -> str:
    raw_value = str(raw_value or "").strip()

    if not raw_value:
        return ""

    groups = [part.strip() for part in raw_value.split(";") if part.strip()]
    readable_groups: List[str] = []

    for group in groups:
        pids = re.findall(r"P[1-9]\d*", group.upper())

        if not pids:
            continue

        readable_groups.append(
            " / ".join(readable_property(pid, language) for pid in pids)
        )

    return ";".join(readable_groups)


def build_path_string(
    path_steps: List[Tuple[str, str]],
    readable: bool,
    language: str = LABEL_LANGUAGE,
) -> str:
    parts: List[str] = []

    for kind, value in path_steps:
        if kind == "entity":
            parts.append(readable_entity(value, language) if readable else value)
        elif kind == "property":
            parts.append(readable_property(value, language) if readable else value)
        elif kind == "qualifier":
            parts.append(readable_property(value, language) if readable else value)
        else:
            parts.append(value)

    return "->".join(parts)


def readable_raw_connection_path(raw_path: str, language: str = LABEL_LANGUAGE) -> str:
    raw_path = str(raw_path or "").strip()

    if not raw_path:
        return ""

    readable_paths: List[str] = []

    for one_path in raw_path.split("\n"):
        one_path = one_path.strip()

        if not one_path:
            continue

        path_prefix = ""

        # Preserve prefixes like:
        #   Path1:
        #   Path2:
        prefix_match = re.match(r"^(Path\d+:\s*)(.*)$", one_path)

        if prefix_match:
            path_prefix = prefix_match.group(1)
            one_path = prefix_match.group(2)

        tokens = [token.strip() for token in one_path.split("->") if token.strip()]
        readable_tokens: List[str] = []

        for token in tokens:
            if re.fullmatch(r"Q[1-9]\d*", token):
                readable_tokens.append(readable_entity(token, language))
            elif re.fullmatch(r"P[1-9]\d*", token):
                readable_tokens.append(readable_property(token, language))
            else:
                readable_tokens.append(token)

        readable_paths.append(path_prefix + "->".join(readable_tokens))

    return "\n".join(readable_paths)
# ============================================================
# WIKIDATA JSON HELPERS
# ============================================================

def qid_from_snak(snak: Dict[str, Any]) -> Optional[str]:
    if not isinstance(snak, dict):
        return None

    if snak.get("snaktype") != "value":
        return None

    datavalue = snak.get("datavalue")

    if not isinstance(datavalue, dict):
        return None

    value = datavalue.get("value")

    if not isinstance(value, dict):
        return None

    entity_type = value.get("entity-type")
    numeric_id = value.get("numeric-id")

    if entity_type != "item" or numeric_id is None:
        return None

    return f"Q{numeric_id}"


def get_claims_from_entity_json(
    entity_json: Dict[str, Any],
    qid: str,
) -> Dict[str, List[Dict[str, Any]]]:
    entity_data = entity_json.get("entities", {}).get(qid, {})
    claims = entity_data.get("claims", {})

    if not isinstance(claims, dict):
        return {}

    return claims


# ============================================================
# PAGE SCAN LOGIC
# ============================================================

def find_connections_on_source_page(
    source_qid: str,
    target_qid: str,
    source_name: str,
    priority: int,
) -> List[ConnectionResult]:
    """
    Search inside source_qid's own Wikidata EntityData JSON for target_qid.

    Direct case:
        source_qid -> property -> target_qid

    Qualifier case:
        source_qid -> property -> main value -> qualifier -> target_qid
    """
    data = get_entity_json(source_qid)
    claims = get_claims_from_entity_json(data, source_qid)

    results: List[ConnectionResult] = []

    for property_id, statements in claims.items():
        if not re.fullmatch(r"P[1-9]\d*", property_id):
            continue

        if not isinstance(statements, list):
            continue

        for statement in statements:
            if not isinstance(statement, dict):
                continue

            rank = statement.get("rank")

            if rank == "deprecated" and not INCLUDE_DEPRECATED_STATEMENTS:
                continue

            mainsnak = statement.get("mainsnak", {})
            main_value_qid = qid_from_snak(mainsnak)

            # Direct main-statement value:
            #   source -> property -> target
            if main_value_qid == target_qid:
                results.append(
                    ConnectionResult(
                        property_ids=[property_id],
                        qualifier_ids=[],
                        path_steps=[
                            ("entity", source_qid),
                            ("property", property_id),
                            ("entity", target_qid),
                        ],
                        source=source_name,
                        priority=priority,
                    )
                )

            # Qualifier value:
            #   source -> property -> main value -> qualifier -> target
            qualifiers = statement.get("qualifiers", {})

            if not isinstance(qualifiers, dict):
                continue

            for qualifier_id, qualifier_snaks in qualifiers.items():
                if not re.fullmatch(r"P[1-9]\d*", qualifier_id):
                    continue

                if not isinstance(qualifier_snaks, list):
                    continue

                for qualifier_snak in qualifier_snaks:
                    qualifier_value_qid = qid_from_snak(qualifier_snak)

                    if qualifier_value_qid != target_qid:
                        continue

                    if main_value_qid:
                        path_steps = [
                            ("entity", source_qid),
                            ("property", property_id),
                            ("entity", main_value_qid),
                            ("qualifier", qualifier_id),
                            ("entity", target_qid),
                        ]
                    else:
                        path_steps = [
                            ("entity", source_qid),
                            ("property", property_id),
                            ("qualifier", qualifier_id),
                            ("entity", target_qid),
                        ]

                    results.append(
                        ConnectionResult(
                            property_ids=[property_id],
                            qualifier_ids=[qualifier_id],
                            path_steps=path_steps,
                            source=source_name,
                            priority=priority + 1,
                        )
                    )

    return deduplicate_connections(results)


# ============================================================
# FALLBACK TRUTHY GRAPH SEARCH
# ============================================================

def build_fallback_truthy_path_query(qid1: str, qid2: str, max_hops: int) -> str:
    if max_hops < 1:
        raise ValueError("max_hops must be >= 1")

    union_blocks: List[str] = []

    union_blocks.append(f"""
    {{
      wd:{qid1} ?p1 wd:{qid2} .
      FILTER(STRSTARTS(STR(?p1), "http://www.wikidata.org/prop/direct/"))
    }}
    """)

    if max_hops >= 2:
        union_blocks.append(f"""
        {{
          wd:{qid1} ?p1 ?n1 .
          ?n1 ?p2 wd:{qid2} .

          FILTER(STRSTARTS(STR(?p1), "http://www.wikidata.org/prop/direct/"))
          FILTER(STRSTARTS(STR(?p2), "http://www.wikidata.org/prop/direct/"))
          FILTER(STRSTARTS(STR(?n1), "http://www.wikidata.org/entity/Q"))

          FILTER(?n1 != wd:{qid1})
          FILTER(?n1 != wd:{qid2})
        }}
        """)

    query = """
SELECT DISTINCT ?p1 ?n1 ?p2 WHERE {
"""
    query += "\nUNION\n".join(union_blocks)
    query += """
}
ORDER BY ?p1 ?p2 ?n1
"""
    return query


def find_fallback_truthy_paths(
    qid1: str,
    qid2: str,
    priority: int,
) -> List[ConnectionResult]:
    query = build_fallback_truthy_path_query(qid1, qid2, MAX_FALLBACK_HOPS)
    data = run_sparql(query)
    bindings = data.get("results", {}).get("bindings", [])

    results: List[ConnectionResult] = []

    for row in bindings:
        p1 = extract_last_path_segment(row["p1"]["value"])

        if "p2" not in row:
            results.append(
                ConnectionResult(
                    property_ids=[p1],
                    qualifier_ids=[],
                    path_steps=[
                        ("entity", qid1),
                        ("property", p1),
                        ("entity", qid2),
                    ],
                    source="fallback_truthy_path",
                    priority=priority,
                )
            )
            continue

        p2 = extract_last_path_segment(row["p2"]["value"])
        n1 = extract_last_path_segment(row["n1"]["value"])

        results.append(
            ConnectionResult(
                property_ids=[p1, p2],
                qualifier_ids=[],
                path_steps=[
                    ("entity", qid1),
                    ("property", p1),
                    ("entity", n1),
                    ("property", p2),
                    ("entity", qid2),
                ],
                source="fallback_truthy_path",
                priority=priority,
            )
        )

    return deduplicate_connections(results)


# ============================================================
# CONNECTION SELECTION
# ============================================================

def deduplicate_connections(connections: List[ConnectionResult]) -> List[ConnectionResult]:
    seen: Set[Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[Tuple[str, str], ...]]] = set()
    output: List[ConnectionResult] = []

    for conn in connections:
        key = (
            tuple(conn.property_ids),
            tuple(conn.qualifier_ids),
            tuple(conn.path_steps),
        )

        if key not in seen:
            seen.add(key)
            output.append(conn)

    return output


def choose_best_connections(connections: List[ConnectionResult]) -> List[ConnectionResult]:
    if not connections:
        return []

    best_priority = min(conn.priority for conn in connections)
    best = [conn for conn in connections if conn.priority == best_priority]

    best.sort(
        key=lambda c: (
            len(c.property_ids),
            len(c.qualifier_ids),
            c.property_ids,
            c.qualifier_ids,
            c.path_steps,
        )
    )

    return best


def find_best_connections_bidirectional(qid1: str, qid2: str) -> List[ConnectionResult]:
    """
    Bi-directional search.

    1. Try Entity_1 page:
           qid1 -> qid2

    2. If not found, use WhatLinksHere on Entity_1.
       If Entity_2 links to Entity_1, scan Entity_2 page:
           qid2 -> qid1

    3. If not found, fallback graph search:
           qid1 -> qid2
           qid2 -> qid1
    """

    # --------------------------------------------------------
    # Step 1: existing logic, Entity_1 page first.
    # --------------------------------------------------------
    forward_page_results = find_connections_on_source_page(
        source_qid=qid1,
        target_qid=qid2,
        source_name="entity1_page_forward",
        priority=1,
    )

    if forward_page_results:
        return choose_best_connections(forward_page_results)

    # --------------------------------------------------------
    # Step 2: WhatLinksHere-style incoming links to Entity_1.
    #
    # Equivalent page:
    #   https://www.wikidata.org/w/index.php?title=Special:WhatLinksHere/Q363402&limit=500
    #
    # If Entity_2 is listed there, then Entity_2 links to Entity_1,
    # so scan Entity_2's page for the reverse stored statement.
    # --------------------------------------------------------
    incoming_to_qid1 = get_whatlinkshere_qids(qid1, WHATLINKSHERE_LIMIT)

    if qid2 in incoming_to_qid1:
        reverse_page_results = find_connections_on_source_page(
            source_qid=qid2,
            target_qid=qid1,
            source_name="whatlinkshere_reverse_entity2_page",
            priority=10,
        )

        if reverse_page_results:
            return choose_best_connections(reverse_page_results)

    # --------------------------------------------------------
    # Step 3: fallback graph search in both directions.
    # This catches cases where the backlink API did not include the
    # relevant page in the first 500, or where the relationship is
    # discoverable through truthy graph paths.
    # --------------------------------------------------------
    fallback_forward = find_fallback_truthy_paths(
        qid1=qid1,
        qid2=qid2,
        priority=100,
    )

    if fallback_forward:
        return choose_best_connections(fallback_forward)

    fallback_reverse = find_fallback_truthy_paths(
        qid1=qid2,
        qid2=qid1,
        priority=110,
    )

    if fallback_reverse:
        return choose_best_connections(fallback_reverse)

    return []


def summarize_connections(
    connections: List[ConnectionResult],
    readable: bool,
    language: str = LABEL_LANGUAGE,
) -> Dict[str, Any]:
    if not connections:
        return {
            "Connection_Path": "",
            "Property_Number": "",
            "Property_list": "",
            "Qualifier_Number": "",
            "Qualifier_list": "",
        }

    path_strings: List[str] = []
    property_ids: List[str] = []
    qualifier_ids: List[str] = []

    for conn in connections:
        path_strings.append(
            build_path_string(
                conn.path_steps,
                readable=readable,
                language=language,
            )
        )

        property_ids.extend(conn.property_ids)
        qualifier_ids.extend(conn.qualifier_ids)

    property_ids = unique_preserve_order(property_ids)
    qualifier_ids = unique_preserve_order(qualifier_ids)
    path_strings = unique_preserve_order(path_strings)

    # New formatting:
    # One path:
    #   Q1->P1->Q2
    #
    # Multiple paths:
    #   Path1: Q1->P1->Q2
    #   Path2: Q1->P2->Q3->P3->Q2
    if len(path_strings) == 1:
        connection_path = path_strings[0]
    else:
        connection_path = "\n".join(
            f"Path{i + 1}: {path}"
            for i, path in enumerate(path_strings)
        )

    if readable:
        property_list = ";".join(
            readable_property(pid, language) for pid in property_ids
        )
        qualifier_list = ";".join(
            readable_property(pid, language) for pid in qualifier_ids
        )
    else:
        property_list = ";".join(property_ids)
        qualifier_list = ";".join(qualifier_ids)

    return {
        "Connection_Path": connection_path,
        "Property_Number": len(property_ids) if property_ids else "",
        "Property_list": property_list,
        "Qualifier_Number": len(qualifier_ids) if qualifier_ids else "",
        "Qualifier_list": qualifier_list,
    }


# ============================================================
# JSON QA ENTITY EXTRACTION
# ============================================================

def is_wikidata_qid(value: Any) -> bool:
    return bool(re.fullmatch(r"Q[1-9]\d*", str(value or "").strip().upper()))

def normalize_label(value: Any) -> str:
    return str(value or "").strip()

def build_qa_pair(question: str, answer: str) -> str:
    return f"Q: {normalize_label(question)} | A: {normalize_label(answer)}"

def split_input_paths(paths: List[str]) -> List[str]:
    """Accept both separate paths and comma-separated path strings."""
    output: List[str] = []

    for item in paths:
        for part in str(item).split(","):
            part = part.strip()
            if part:
                output.append(part)

    return output


def iter_json_records(json_path: str) -> List[Dict[str, Any]]:
    with open(json_path, "r", encoding="utf-8-sig") as infile:
        data = json.load(infile)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "questions", "records", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"Unsupported JSON structure in {json_path}; expected a list of QA records.")


def iter_jsonl_records(jsonl_path: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []

    with open(jsonl_path, "r", encoding="utf-8-sig") as infile:
        for line_number, line in enumerate(infile, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {jsonl_path}: {exc}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Unsupported JSONL record on line {line_number} of {jsonl_path}; "
                    "expected one JSON object per line."
                )

            records.append(record)

    return records

def read_json_qa_rows(json_paths: List[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    skipped_non_qid = 0
    for json_path in split_input_paths(json_paths):
        records = iter_json_records(json_path)
        for record_index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            question = normalize_label(record.get("question"))
            answer_text = normalize_label(record.get("answer_text"))
            question_id = normalize_label(record.get("question_id"))
            convmix_question_id = normalize_label(record.get("convmix_question_id"))
            domain = normalize_label(record.get("domain"))
            entities = record.get("entities") or []
            answers = record.get("answers") or []
            if not isinstance(entities, list):
                entities = []
            if not isinstance(answers, list):
                answers = []
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                entity_id = normalize_label(entity.get("id"))
                entity_label = normalize_label(entity.get("label"))
                if not is_wikidata_qid(entity_id):
                    skipped_non_qid += 1
                    continue
                for answer in answers:
                    if not isinstance(answer, dict):
                        continue
                    answer_id = normalize_label(answer.get("id"))
                    answer_label = normalize_label(answer.get("label"))
                    gold_answer = answer_text or answer_label or answer_id
                    if not is_wikidata_qid(answer_id):
                        skipped_non_qid += 1
                        if SKIP_NON_QID_PAIRS:
                            continue
                    rows.append({
                        "Source_JSON": json_path,
                        "Record_Index": str(record_index),
                        "Question_ID": question_id,
                        "Convmix_Question_ID": convmix_question_id,
                        "Domain": domain,
                        "Question": question,
                        "Gold_Answer": gold_answer,
                        "QA-Pairs": build_qa_pair(question, gold_answer),
                        "Entity_1": entity_id,
                        "Entity_1_Label": entity_label,
                        "Entity_2": answer_id,
                        "Entity_2_Label": answer_label,
                    })
    if skipped_non_qid:
        print(f"Skipped {skipped_non_qid} non-QID entity/answer values. Set SKIP_NON_QID_PAIRS=False if you want them kept with blank paths.", file=sys.stderr)
    return rows


def read_jsonl_qa_rows(jsonl_paths: List[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    skipped_non_qid = 0

    for jsonl_path in split_input_paths(jsonl_paths):
        records = iter_jsonl_records(jsonl_path)

        for record_index, record in enumerate(records):
            question = normalize_label(record.get("question"))
            answer_text = normalize_label(record.get("answer_text"))
            question_id = normalize_label(record.get("question_id"))
            convmix_question_id = normalize_label(record.get("convmix_question_id"))
            domain = normalize_label(record.get("domain"))
            entities = record.get("entities") or []
            answers = record.get("answers") or []

            if not isinstance(entities, list):
                entities = []
            if not isinstance(answers, list):
                answers = []

            for entity in entities:
                if not isinstance(entity, dict):
                    continue

                entity_id = normalize_label(entity.get("id"))
                entity_label = normalize_label(entity.get("label"))

                if not is_wikidata_qid(entity_id):
                    skipped_non_qid += 1
                    continue

                for answer in answers:
                    if not isinstance(answer, dict):
                        continue

                    answer_id = normalize_label(answer.get("id"))
                    answer_label = normalize_label(answer.get("label"))
                    gold_answer = answer_text or answer_label or answer_id

                    if not is_wikidata_qid(answer_id):
                        skipped_non_qid += 1
                        if SKIP_NON_QID_PAIRS:
                            continue

                    rows.append({
                        "Source_JSON": jsonl_path,
                        "Record_Index": str(record_index),
                        "Question_ID": question_id,
                        "Convmix_Question_ID": convmix_question_id,
                        "Domain": domain,
                        "Question": question,
                        "Gold_Answer": gold_answer,
                        "QA-Pairs": build_qa_pair(question, gold_answer),
                        "Entity_1": entity_id,
                        "Entity_1_Label": entity_label,
                        "Entity_2": answer_id,
                        "Entity_2_Label": answer_label,
                    })

    if skipped_non_qid:
        print(
            f"Skipped {skipped_non_qid} non-QID entity/answer values. "
            "Set SKIP_NON_QID_PAIRS=False if you want them kept with blank paths.",
            file=sys.stderr,
        )

    return rows


# ============================================================
# CSV PROCESSING
# ============================================================

def read_input_rows(input_csv_path: str) -> List[Dict[str, str]]:
    with open(input_csv_path, "r", encoding="utf-8-sig", newline="") as infile:
        reader = csv.DictReader(infile)

        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header row.")

        required = {"Entity_1", "Entity_2"}
        missing = required - set(reader.fieldnames)

        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

        return list(reader)


def process_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    processed_rows: List[Dict[str, str]] = []
    existence_cache: Dict[str, bool] = {}

    for row in tqdm(rows, desc="Processing rows", unit="row"):
        raw_entity_1 = row.get("Entity_1", "")
        raw_entity_2 = row.get("Entity_2", "")

        output_row = {
            "Source_JSON": row.get("Source_JSON", ""),
            "Record_Index": row.get("Record_Index", ""),
            "Question_ID": row.get("Question_ID", ""),
            "Convmix_Question_ID": row.get("Convmix_Question_ID", ""),
            "Domain": row.get("Domain", ""),
            "Question": row.get("Question", ""),
            "Gold_Answer": row.get("Gold_Answer", ""),
            "QA-Pairs": row.get("QA-Pairs", ""),
            "Entity_1": raw_entity_1,
            "Entity_1_Label": row.get("Entity_1_Label", ""),
            "Entity_2": raw_entity_2,
            "Entity_2_Label": row.get("Entity_2_Label", ""),
            "Connection_Path": "",
            "Property_Number": "",
            "Property_list": "",
            "Qualifier_Number": "",
            "Qualifier_list": "",
        }

        try:
            qid1 = validate_qid(extract_qid_from_cell(raw_entity_1))
            qid2 = validate_qid(extract_qid_from_cell(raw_entity_2))

            if qid1 not in existence_cache:
                existence_cache[qid1] = entity_exists(qid1)

            if qid2 not in existence_cache:
                existence_cache[qid2] = entity_exists(qid2)

            if not existence_cache[qid1]:
                raise ValueError(f"Entity_1 does not exist on Wikidata: {qid1}")

            if not existence_cache[qid2]:
                raise ValueError(f"Entity_2 does not exist on Wikidata: {qid2}")

            connections = find_best_connections_bidirectional(qid1, qid2)

            summary = summarize_connections(
                connections,
                readable=False,
                language=LABEL_LANGUAGE,
            )

            output_row.update(summary)

        except Exception as exc:
            print(
                f"Warning: could not process row "
                f"({raw_entity_1}, {raw_entity_2}): {exc}",
                file=sys.stderr,
            )

        processed_rows.append(output_row)

    return processed_rows


def write_output_csv(output_csv_path: str, rows: List[Dict[str, str]]) -> None:
    fieldnames = [
        "Source_JSON",
        "Record_Index",
        "Question_ID",
        "Convmix_Question_ID",
        "Domain",
        "Question",
        "Gold_Answer",
        "QA-Pairs",
        "Entity_1",
        "Entity_1_Label",
        "Entity_2",
        "Entity_2_Label",
        "Connection_Path",
        "Property_Number",
        "Property_list",
        "Qualifier_Number",
        "Qualifier_list",
    ]

    with open(output_csv_path, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_output_label_csv(
    output_label_csv_path: str,
    rows: List[Dict[str, str]],
    language: str,
) -> None:
    fieldnames = [
        "Source_JSON",
        "Record_Index",
        "Question_ID",
        "Convmix_Question_ID",
        "Domain",
        "Question",
        "Gold_Answer",
        "QA-Pairs",
        "Entity_1",
        "Entity_1_Label",
        "Entity_2",
        "Entity_2_Label",
        "Connection_Path",
        "Property_Number",
        "Property_list",
        "Qualifier_Number",
        "Qualifier_list",
    ]

    readable_rows: List[Dict[str, str]] = []

    for row in tqdm(rows, desc="Writing readable labels", unit="row"):
        readable_row = {
            "Source_JSON": row.get("Source_JSON", ""),
            "Record_Index": row.get("Record_Index", ""),
            "Question_ID": row.get("Question_ID", ""),
            "Convmix_Question_ID": row.get("Convmix_Question_ID", ""),
            "Domain": row.get("Domain", ""),
            "Question": row.get("Question", ""),
            "Gold_Answer": row.get("Gold_Answer", ""),
            "QA-Pairs": row.get("QA-Pairs", ""),
            "Entity_1": readable_cell_entity(row.get("Entity_1", ""), language),
            "Entity_1_Label": row.get("Entity_1_Label", ""),
            "Entity_2": readable_cell_entity(row.get("Entity_2", ""), language),
            "Entity_2_Label": row.get("Entity_2_Label", ""),
            "Connection_Path": readable_raw_connection_path(
                row.get("Connection_Path", ""),
                language,
            ),
            "Property_Number": row.get("Property_Number", ""),
            "Property_list": readable_pid_list(
                row.get("Property_list", ""),
                language,
            ),
            "Qualifier_Number": row.get("Qualifier_Number", ""),
            "Qualifier_list": readable_pid_list(
                row.get("Qualifier_list", ""),
                language,
            ),
        }

        readable_rows.append(readable_row)

    with open(output_label_csv_path, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(readable_rows)


# ============================================================
# MAIN
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract question/answer entity pairs from QA JSON files and detect "
            "Wikidata connections between each pair."
        )
    )
    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument(
        "--input-json",
        nargs="+",
        default=None,
        help="One or more train/test/dev JSON files, e.g. train_set.json test_set.json dev_set.json.",
    )
    input_group.add_argument(
        "--input-jsonl",
        nargs="+",
        default=None,
        help="One or more JSONL files, e.g. CompMix_infobox.jsonl CompMix_table.jsonl.",
    )
    input_group.add_argument(
        "--input-csv",
        default=None,
        help="Existing CSV with Entity_1 and Entity_2 columns.",
    )
    parser.add_argument("--output-csv", default=OUTPUT_CSV_PATH)
    parser.add_argument("--output-label-csv", default=OUTPUT_LABEL_CSV_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.input_json:
            rows = read_json_qa_rows(args.input_json)
        elif args.input_jsonl:
            rows = read_jsonl_qa_rows(args.input_jsonl)
        elif args.input_csv:
            rows = read_input_rows(args.input_csv)
        elif INPUT_JSONL_PATHS:
            rows = read_jsonl_qa_rows(INPUT_JSONL_PATHS)
        else:
            rows = read_json_qa_rows(INPUT_JSON_PATHS)

        processed_rows = process_rows(rows)

        write_output_csv(args.output_csv, processed_rows)
        write_output_label_csv(args.output_label_csv, processed_rows, language=LABEL_LANGUAGE)

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Done.")
    print(f"Rows processed: {len(processed_rows)}")
    print(f"Raw output written to: {args.output_csv}")
    print(f"Readable-label output written to: {args.output_label_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())