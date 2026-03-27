"""Coverage for share-link and print setup against the current dashboard."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "index.html"
INDEX_TEXT = INDEX_HTML.read_text()


def _extract_block(name: str) -> str:
    match = re.search(rf"const\s+{name}\s*=\s*\{{(.*?)\}};", INDEX_TEXT, re.DOTALL)
    assert match, f"{name} block not found"
    return match.group(1)


def _extract_array(name: str) -> list[str]:
    match = re.search(rf"const\s+{name}\s*=\s*\[([^\]]*)\];", INDEX_TEXT)
    assert match, f"{name} array not found"
    return re.findall(r"'([^']+)'", match.group(1))


def _extract_number_constants() -> dict[str, float]:
    block = _extract_block("OFF_DEFAULTS_1031")
    return {match.group(1): float(match.group(2)) for match in re.finditer(r"(\w+):\s*([\d.]+)", block)}


def _extract_share_schema() -> dict[str, dict[str, object]]:
    block = _extract_block("SHARE_SCHEMA")
    schema: dict[str, dict[str, object]] = {}
    pattern = re.compile(
        r"(\w+)\s*:\s*\{\s*id:\s*'([^']+)'\s*,\s*type:\s*'([^']+)'\s*,\s*default:\s*([^}]+?)\s*\}",
        re.DOTALL,
    )
    for match in pattern.finditer(block):
        key, input_id, input_type, raw_default = match.groups()
        raw_default = raw_default.strip().rstrip(",")
        if input_type == "checkbox":
            default: object = raw_default == "true"
        else:
            default = float(raw_default)
        schema[key] = {"id": input_id, "type": input_type, "default": default}
    assert schema, "Parsed SHARE_SCHEMA is empty"
    return schema


class InputCollector(HTMLParser):
    """Collect all in_* input attributes from the dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self.inputs: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "input":
            return
        attr_map = dict(attrs)
        input_id = attr_map.get("id")
        if input_id and input_id.startswith("in_"):
            self.inputs[input_id] = attr_map


SCHEMA = _extract_share_schema()
SCHEMA_KEYS = list(SCHEMA.keys())
OFF_DEFAULTS_1031 = _extract_number_constants()
SINGLE_EXIT_OMIT = _extract_array("SINGLE_EXIT_OMIT")
MULTI_EXIT_OMIT = _extract_array("MULTI_EXIT_OMIT")
TAX_FIELDS_1031 = _extract_array("TAX_FIELDS_1031")

collector = InputCollector()
collector.feed(INDEX_TEXT)
HTML_INPUTS = collector.inputs


def base_defaults() -> dict[str, float | bool]:
    return {key: entry["default"] for key, entry in SCHEMA.items()}


def effective_state(partial: dict[str, float | bool] | None = None) -> dict[str, float | bool]:
    state = base_defaults()
    partial = partial or {}
    if partial.get("x1") is False:
        state["cg"] = OFF_DEFAULTS_1031["cg"]
        state["ni"] = OFF_DEFAULTS_1031["ni"]
        state["dp"] = OFF_DEFAULTS_1031["dp"]
    state.update(partial)
    return state


def serialize_share_state(state: dict[str, float | bool]) -> dict[str, float | bool]:
    full_state = effective_state(state)
    is_multi = bool(full_state["mx"])
    is_1031 = bool(full_state["x1"])
    encoded: dict[str, float | bool] = {}

    for key, entry in SCHEMA.items():
        if not is_multi and key in SINGLE_EXIT_OMIT:
            continue
        if is_multi and key in MULTI_EXIT_OMIT:
            continue
        if is_1031 and key in TAX_FIELDS_1031:
            continue

        default_value = entry["default"]
        if not is_1031 and key in TAX_FIELDS_1031:
            default_value = OFF_DEFAULTS_1031[key]

        value = full_state[key]
        if entry["type"] == "checkbox":
            if bool(value) != bool(default_value):
                encoded[key] = bool(value)
        else:
            if abs(float(value) - float(default_value)) > 1e-9:
                encoded[key] = value

    return encoded


def build_query(state: dict[str, float | bool]) -> str:
    params: list[tuple[str, str]] = [("v", "1")]
    for key, value in serialize_share_state(state).items():
        entry = SCHEMA[key]
        if entry["type"] == "checkbox":
            params.append((key, "1" if value else "0"))
        else:
            numeric = float(value)
            if abs(numeric - round(numeric)) < 1e-9:
                params.append((key, str(int(round(numeric)))))
            else:
                params.append((key, str(numeric)))
    return urlencode(params)


def parse_query(query: str) -> dict[str, float | bool] | None:
    params = dict(parse_qsl(query.lstrip("?"), keep_blank_values=True))
    if not params:
        return None

    state = base_defaults()
    has_1031 = "x1" in params
    is_1031_off = has_1031 and params["x1"] in {"0", "false"}
    if is_1031_off:
        state["x1"] = False
        state["cg"] = OFF_DEFAULTS_1031["cg"]
        state["ni"] = OFF_DEFAULTS_1031["ni"]
        state["dp"] = OFF_DEFAULTS_1031["dp"]

    for key, entry in SCHEMA.items():
        if key not in params:
            continue
        raw = params[key]
        if entry["type"] == "checkbox":
            state[key] = raw in {"1", "true"}
        else:
            state[key] = float(raw)

    return state


class TestShareSchema:
    """Verify the schema and HTML inputs stay in sync."""

    def test_all_inputs_are_covered(self) -> None:
        schema_ids = {entry["id"] for entry in SCHEMA.values()}
        assert len(HTML_INPUTS) == 27
        assert schema_ids == set(HTML_INPUTS)

    def test_schema_keys_are_unique(self) -> None:
        assert len(SCHEMA_KEYS) == len(set(SCHEMA_KEYS))

    def test_off_defaults_and_omit_sets_exist(self) -> None:
        assert OFF_DEFAULTS_1031 == {"cg": 20.0, "ni": 3.8, "dp": 25.0}
        assert set(SINGLE_EXIT_OMIT) == {"xb", "wb", "xm", "wm", "xr", "wr"}
        assert MULTI_EXIT_OMIT == ["xs"]
        assert set(TAX_FIELDS_1031) == {"cg", "ni", "dp"}

    def test_markup_defaults_match_schema(self) -> None:
        for key, entry in SCHEMA.items():
            attrs = HTML_INPUTS[entry["id"]]
            if entry["type"] == "checkbox":
                actual = "checked" in attrs
            elif entry["type"] == "dollar":
                actual = float(attrs["data-raw"])
            else:
                actual = float(attrs["value"])
            assert actual == entry["default"], key


class TestShareEncoding:
    """Verify URL encoding/decoding matches current main-branch semantics."""

    def test_default_state_encodes_only_version(self) -> None:
        assert build_query({}) == "v=1"

    def test_1031_off_encodes_mode_without_tax_fields(self) -> None:
        params = dict(parse_qsl(build_query({"x1": False})))
        assert params["v"] == "1"
        assert params["x1"] == "0"
        assert "cg" not in params
        assert "ni" not in params
        assert "dp" not in params

    def test_multi_exit_mode_omits_single_exit(self) -> None:
        params = dict(parse_qsl(build_query({
            "mx": True,
            "xb": 260_000_000,
            "xm": 210_000_000,
            "xr": 150_000_000,
        })))
        assert params["mx"] == "1"
        assert "xs" not in params
        assert params["xb"] == "260000000"

    def test_round_trip_partial_state(self) -> None:
        original = {"gs": 125_000_000, "hy": 12, "x1": False, "wa": True, "oi": 39}
        assert parse_query(build_query(original)) == effective_state(original)

    def test_round_trip_multi_exit_state(self) -> None:
        original = {
            "gs": 95_000_000,
            "mx": True,
            "xb": 275_000_000,
            "wb": 30,
            "xm": 215_000_000,
            "wm": 45,
            "xr": 135_000_000,
            "wr": 25,
            "x1": False,
            "cg": 18,
            "ni": 3.8,
            "dp": 20,
            "wa": True,
            "cd": 1_250_000,
        }
        assert parse_query(build_query(original)) == effective_state(original)

    def test_unknown_params_are_ignored(self) -> None:
        state = parse_query("v=1&foo=bar&gs=125000000")
        assert state is not None
        assert state["gs"] == 125_000_000
        assert "foo" not in state

    def test_url_length_stays_reasonable(self) -> None:
        query = build_query({
            "gs": 123_456_789,
            "cb": 9_876_543,
            "hy": 15,
            "rr": 8.5,
            "dr": 9.5,
            "mx": True,
            "xb": 333_000_000,
            "wb": 40,
            "xm": 222_000_000,
            "wm": 35,
            "xr": 111_000_000,
            "wr": 25,
            "cc": 1_500_000,
            "ce": 4.5,
            "n1": 850_000,
            "n2": 3_200_000,
            "p1": 4.5,
            "tn": 10,
            "tf": 3,
            "x1": False,
            "cg": 20,
            "ni": 3.8,
            "dp": 25,
            "cd": 2_250_000,
            "wa": True,
            "oi": 39,
        })
        assert len(query) < 2048


class TestHydrationAndPrintSetup:
    """Verify the feature wiring exists in index.html."""

    def test_expected_functions_exist(self) -> None:
        for snippet in [
            "function buildShareURLFromState(",
            "function readShareStateFromURL(",
            "function copyShareURL(",
            "function printReport(",
            "function apply1031FieldLock(",
            "function apply1031DefaultValues(",
            "function handle1031ToggleChange(",
            "function applyExitModeUIOnly(",
        ]:
            assert snippet in INDEX_TEXT

    def test_print_and_share_elements_exist(self) -> None:
        for element_id in ["btnShare", "btnPrint", "shareStatus", "printMeta", "printTimestamp", "printUrl"]:
            assert f'id="{element_id}"' in INDEX_TEXT

    def test_beforeprint_and_afterprint_handlers_exist(self) -> None:
        assert "window.addEventListener('beforeprint'" in INDEX_TEXT
        assert "window.addEventListener('afterprint'" in INDEX_TEXT

    def test_init_reads_url_before_ui_only_setup(self) -> None:
        init_start = INDEX_TEXT.index("const urlState = readShareStateFromURL(window.location.search);")
        init_section = INDEX_TEXT[init_start:]
        pos_lock = init_section.index("apply1031FieldLock(document.getElementById('in_1031').checked);")
        pos_exit = init_section.index("applyExitModeUIOnly();")
        assert pos_lock < pos_exit

    def test_print_css_hides_sidebar_and_buttons(self) -> None:
        assert ".sidebar, .btn-secondary, .share-status, .btn-recalc" in INDEX_TEXT
        assert "print-color-adjust: exact" in INDEX_TEXT

    def test_clipboard_and_prompt_fallback_exist(self) -> None:
        assert "navigator.clipboard.writeText(url)" in INDEX_TEXT
        assert "prompt('Copy this link:', url);" in INDEX_TEXT
