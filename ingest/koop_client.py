"""Low-level client for the KOOP SRU endpoint (Officiele Bekendmakingen, CC0).

Searches gemeenteblad (gmb) records for a date and fetches each notice's
full document XML to extract plain-text body. No model calls, no filtering
decisions - this module only talks to KOOP and returns parsed Notice dicts
(CONTRACTS.md SS1) with an internal `_xml_doc_url` field the caller must pop.
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta

SRU_BASE_URL = "https://repository.overheid.nl/sru"

NS = {
    "sru": "http://docs.oasis-open.org/ns/search-ws/sruResponse",
    "gzd": "http://standaarden.overheid.nl/sru",
    "ow": "http://standaarden.overheid.nl/wetgeving/",
    "dcterms": "http://purl.org/dc/terms/",
}

RUBRIEK_SCHEME = "OVERHEIDop.Rubriek"
REQUEST_TIMEOUT_S = 20
PAGE_SIZE = 200


def _http_get(url: str, retries: int = 3, backoff_s: float = 0.6) -> bytes:
    """GET with retry + exponential backoff. KOOP rate-limits/hiccups under burst
    load; a bare try/except that swallows failures silently corrupts body text
    (see incident: 76% empty bodies from an unthrottled 5k-notice batch)."""
    req = urllib.request.Request(url, headers={"User-Agent": "ReguLine/1.0 (hackathon, contact: team)"})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 - network layer, anything can surface here
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff_s * (2**attempt))
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_err}") from last_err


def _build_query(target_date: str) -> str:
    """CQL query for gemeenteblad notices published on target_date (YYYY-MM-DD)."""
    year = target_date[:4]
    return (
        "c.product-area==officielepublicaties and "
        f'c.content-area=="officielepublicaties/gmb/{year}" and '
        f"dt.date={target_date}"
    )


def _search_url(query: str, start_record: int, max_records: int) -> str:
    params = {
        "version": "2.0",
        "operation": "searchRetrieve",
        "x-connection": "oep",
        "startRecord": str(start_record),
        "maximumRecords": str(max_records),
        "query": query,
    }
    return f"{SRU_BASE_URL}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"


def _text(el: ET.Element, path: str) -> str | None:
    node = el.find(path, NS)
    # Some source records are double HTML-escaped upstream (e.g. business names
    # like "Bagels & Beans" survive as "Bagels &amp; Beans" post XML-parse).
    # unescape is a no-op on already-clean text, so this is safe either way.
    return html.unescape(node.text.strip()) if node is not None and node.text else None


def _parse_record(record: ET.Element) -> dict | None:
    meta = record.find(".//ow:owmskern", NS)
    mantel = record.find(".//ow:owmsmantel", NS)
    tpmeta = record.find(".//ow:tpmeta", NS)
    if meta is None:
        return None

    identifier = _text(meta, "dcterms:identifier")
    title = _text(meta, "dcterms:title")
    municipality = _text(meta, "dcterms:creator")

    rubriek = None
    for type_el in meta.findall("dcterms:type", NS):
        if type_el.get("scheme") == RUBRIEK_SCHEME:
            rubriek = (type_el.text or "").strip()
            break

    published_on = _text(mantel, "dcterms:date") if mantel is not None else None

    source_url = None
    if mantel is not None:
        hv = mantel.find("dcterms:hasVersion", NS)
        if hv is not None:
            source_url = hv.get("resourceIdentifier")

    lat = lng = None
    if tpmeta is not None:
        punt = tpmeta.find(".//ow:locatiepunt", NS)
        if punt is not None and punt.text:
            parts = punt.text.strip().split()
            if len(parts) == 2:
                try:
                    lat, lng = float(parts[0]), float(parts[1])
                except ValueError:
                    lat = lng = None

    xml_doc_url = None
    for item_url in record.findall(".//gzd:itemUrl", NS):
        if item_url.get("manifestation") == "xml":
            xml_doc_url = item_url.text
            break

    if not identifier or not xml_doc_url:
        return None

    return {
        "id": identifier,
        "source_url": source_url or f"https://zoek.officielebekendmakingen.nl/{identifier}.html",
        "title": title or "",
        "published_on": published_on,
        "municipality": municipality,
        "rubriek": rubriek,
        "lat": lat,
        "lng": lng,
        "_xml_doc_url": xml_doc_url,
    }


def _strip_body(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""
    text = " ".join(t.strip() for t in root.itertext() if t and t.strip())
    return html.unescape(re.sub(r"\s+", " ", text).strip())


def fetch_body(xml_doc_url: str) -> str:
    """Fetch a notice's full document XML and return plain-text body."""
    return _strip_body(_http_get(xml_doc_url))


def search_gmb_records(target_date: str, limit: int | None = None) -> list[dict]:
    """Search gemeenteblad SRU records for a date. Metadata only, no body text."""
    query = _build_query(target_date)
    results: list[dict] = []
    start = 1
    total = None
    while True:
        if limit is not None and len(results) >= limit:
            break
        page_size = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - len(results))
        url = _search_url(query, start, page_size)
        raw = _http_get(url)
        root = ET.fromstring(raw)
        if total is None:
            n = root.find("sru:numberOfRecords", NS)
            total = int(n.text) if n is not None and n.text else 0
        records = root.findall(".//sru:record", NS)
        if not records:
            break
        for rec in records:
            parsed = _parse_record(rec)
            if parsed:
                results.append(parsed)
        start += len(records)
        if start > total:
            break
    return results


def fetch_gmb_notices(
    target_date: str,
    limit: int | None = None,
    body_delay_s: float = 0.08,
) -> list[dict]:
    """Search + fetch full body text for each gemeenteblad notice on target_date.

    Returns Notice dicts per CONTRACTS.md SS1, body populated as plain text.
    body_delay_s throttles the per-notice document fetch (KOOP rate-limits
    unthrottled bursts, which previously produced silently empty bodies).
    A notice whose body still fails after _http_get's internal retries keeps
    body="" but is reported via stderr and returned separately for reprocessing.
    """
    records = search_gmb_records(target_date, limit=limit)
    notices = []
    failed_ids = []
    for rec in records:
        xml_doc_url = rec.pop("_xml_doc_url")
        try:
            body = fetch_body(xml_doc_url)
        except Exception as e:
            body = ""
            failed_ids.append(rec["id"])
            print(f"WARNING: body fetch failed for {rec['id']}: {e}", file=sys.stderr)
        rec["body"] = body
        notices.append(rec)
        if body_delay_s:
            time.sleep(body_delay_s)
    if failed_ids:
        print(f"WARNING: {len(failed_ids)}/{len(notices)} notices have empty body after retries: {failed_ids}", file=sys.stderr)
    return notices


def date_range_today_yesterday() -> list[str]:
    today = date.today()
    yesterday = today - timedelta(days=1)
    return [yesterday.isoformat(), today.isoformat()]
