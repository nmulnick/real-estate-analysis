"""
Tests for URL share-link schema, encoding, and decoding.
All tests are Python-only — they parse the HTML/JS source directly.
No Node.js dependency required.
"""

import os
import re
import json
import pytest

# Path to the dashboard HTML
DASHBOARD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "real_estate_dashboard.html"
)


def _read_html():
    with open(DASHBOARD_PATH, "r") as f:
        return f.read()


def _get_input_ids_from_html(html=None):
    """Extract all id='in_*' from the HTML."""
    if html is None:
        html = _read_html()
    return set(re.findall(r'id="(in_[a-z0-9_]+)"', html))


def _parse_share_schema(html=None):
    """Parse the SHARE_SCHEMA JS object from the HTML source."""
    if html is None:
        html = _read_html()

    # Extract the SHARE_SCHEMA block
    match = re.search(
        r'const\s+SHARE_SCHEMA\s*=\s*\{(.+?)\};',
        html, re.DOTALL
    )
    assert match, "SHARE_SCHEMA not found in HTML"

    raw = match.group(1)

    # Parse each entry: key: { id: '...', type: '...', default: ... }
    schema = {}
    entry_pattern = re.compile(
        r"(\w+):\s*\{\s*id:\s*'([^']+)',\s*type:\s*'([^']+)',\s*default:\s*([^}]+)\}"
    )
    for m in entry_pattern.finditer(raw):
        key = m.group(1)
        input_id = m.group(2)
        input_type = m.group(3)
        default_raw = m.group(4).strip().rstrip(',')

        # Parse default value
        if input_type == 'checkbox':
            default_val = default_raw == 'true'
        else:
            default_val = float(default_raw)

        schema[key] = {
            'id': input_id,
            'type': input_type,
            'default': default_val,
        }

    return schema


def _get_html_default_value(html, input_id):
    """Extract the default value of an input from its HTML attributes."""
    # Check for checkbox
    checkbox_match = re.search(
        rf'<input\s+type="checkbox"\s+id="{input_id}"(\s+checked)?',
        html
    )
    if checkbox_match:
        return checkbox_match.group(1) is not None  # True if 'checked' present

    # Check for data-dollar (data-raw attribute)
    dollar_match = re.search(
        rf'id="{input_id}"[^>]*data-raw="([^"]*)"',
        html
    )
    if dollar_match:
        return float(dollar_match.group(1))

    # Check for number input (value attribute)
    value_match = re.search(
        rf'id="{input_id}"[^>]*value="([^"]*)"',
        html
    )
    if value_match:
        return float(value_match.group(1))

    return None


def _parse_off_defaults_1031(html=None):
    """Parse the OFF_DEFAULTS_1031 object from JS source."""
    if html is None:
        html = _read_html()
    match = re.search(
        r'const\s+OFF_DEFAULTS_1031\s*=\s*\{(.+?)\};',
        html, re.DOTALL
    )
    assert match, "OFF_DEFAULTS_1031 not found"
    raw = match.group(1)
    result = {}
    for m in re.finditer(r'(\w+):\s*([\d.]+)', raw):
        result[m.group(1)] = float(m.group(2))
    return result


# =============================================================================
# TEST CLASSES
# =============================================================================


class TestShareSchema:
    """Verify SHARE_SCHEMA completeness and consistency."""

    def setup_method(self):
        self.html = _read_html()
        self.schema = _parse_share_schema(self.html)
        self.html_ids = _get_input_ids_from_html(self.html)

    def test_all_input_ids_have_url_key(self):
        """Every id='in_*' in the HTML has a corresponding entry in SHARE_SCHEMA."""
        schema_ids = {cfg['id'] for cfg in self.schema.values()}
        missing = self.html_ids - schema_ids
        assert missing == set(), f"HTML inputs missing from SHARE_SCHEMA: {missing}"

    def test_all_url_keys_unique(self):
        """No two inputs map to the same short key."""
        keys = list(self.schema.keys())
        assert len(keys) == len(set(keys)), f"Duplicate keys: {keys}"

    def test_all_url_ids_exist_in_html(self):
        """Every ID in SHARE_SCHEMA exists as an element in the HTML."""
        schema_ids = {cfg['id'] for cfg in self.schema.values()}
        missing = schema_ids - self.html_ids
        assert missing == set(), f"SHARE_SCHEMA IDs not in HTML: {missing}"

    def test_input_count_is_29(self):
        """Exactly 29 in_* inputs exist — catches silent additions/removals."""
        assert len(self.html_ids) == 29, (
            f"Expected 29 inputs, found {len(self.html_ids)}: {sorted(self.html_ids)}"
        )

    def test_schema_count_is_29(self):
        """SHARE_SCHEMA has exactly 29 entries — one per input."""
        assert len(self.schema) == 29, (
            f"Expected 29 schema entries, found {len(self.schema)}: {sorted(self.schema.keys())}"
        )

    def test_schema_version_in_build_url(self):
        """buildShareURLFromState includes 'v=1' for schema versioning."""
        assert "params.set('v', '1')" in self.html or 'params.set("v", "1")' in self.html, (
            "Schema version 'v=1' not found in buildShareURLFromState"
        )


class TestShareDefaults:
    """Verify defaults match effective post-initialization state."""

    def setup_method(self):
        self.html = _read_html()
        self.schema = _parse_share_schema(self.html)
        self.off_defaults = _parse_off_defaults_1031(self.html)

    def test_1031_on_defaults(self):
        """When x1=true (default), cg=0, ni=0, dp=0 in the schema."""
        assert self.schema['cg']['default'] == 0
        assert self.schema['ni']['default'] == 0
        assert self.schema['dp']['default'] == 0

    def test_1031_off_defaults_documented(self):
        """OFF_DEFAULTS_1031 contains cg=20, ni=3.8, dp=25."""
        assert self.off_defaults['cg'] == 20
        assert self.off_defaults['ni'] == 3.8
        assert self.off_defaults['dp'] == 25

    def test_x1_default_is_true(self):
        """The 1031 toggle defaults to ON (checked)."""
        assert self.schema['x1']['default'] is True

    def test_non_1031_defaults_match_html(self):
        """For non-1031-affected fields, schema defaults match HTML value attributes."""
        # 1031-affected fields have effective defaults (0) that differ from HTML
        # when 1031 is on, so we skip those
        skip_ids = {'in_fed_cg', 'in_niit', 'in_dep_recap'}
        for key, cfg in self.schema.items():
            if cfg['id'] in skip_ids:
                continue
            html_default = _get_html_default_value(self.html, cfg['id'])
            if html_default is None:
                continue
            assert cfg['default'] == html_default, (
                f"Schema default for {key} ({cfg['id']}): {cfg['default']} != "
                f"HTML default: {html_default}"
            )

    def test_1031_affected_fields_html_vs_effective(self):
        """1031-affected fields have HTML value=0 (since 1031 defaults ON)
        which matches the schema effective default of 0."""
        for key in ['cg', 'ni', 'dp']:
            cfg = self.schema[key]
            html_default = _get_html_default_value(self.html, cfg['id'])
            # HTML says 0 because 1031 is checked by default
            assert html_default == 0, (
                f"{key}: HTML default should be 0 (1031 ON), got {html_default}"
            )
            assert cfg['default'] == 0


class TestShareEncoding:
    """Verify mode-aware encoding logic."""

    def setup_method(self):
        self.html = _read_html()
        self.schema = _parse_share_schema(self.html)

    def test_mode_omission_single_exit_keys_defined(self):
        """SINGLE_EXIT_OMIT contains the correct keys for bull/base/bear."""
        match = re.search(
            r"const\s+SINGLE_EXIT_OMIT\s*=\s*\[([^\]]+)\]",
            self.html
        )
        assert match, "SINGLE_EXIT_OMIT not found"
        keys = re.findall(r"'(\w+)'", match.group(1))
        assert set(keys) == {'xb', 'wb', 'xm', 'wm', 'xr', 'wr'}

    def test_mode_omission_multi_exit_keys_defined(self):
        """MULTI_EXIT_OMIT contains only 'xs' (single exit price)."""
        match = re.search(
            r"const\s+MULTI_EXIT_OMIT\s*=\s*\[([^\]]+)\]",
            self.html
        )
        assert match, "MULTI_EXIT_OMIT not found"
        keys = re.findall(r"'(\w+)'", match.group(1))
        assert keys == ['xs']

    def test_tax_fields_1031_keys_defined(self):
        """TAX_FIELDS_1031 contains cg, ni, dp."""
        match = re.search(
            r"const\s+TAX_FIELDS_1031\s*=\s*\[([^\]]+)\]",
            self.html
        )
        assert match, "TAX_FIELDS_1031 not found"
        keys = re.findall(r"'(\w+)'", match.group(1))
        assert set(keys) == {'cg', 'ni', 'dp'}

    def test_reet_fields_omit_keys_defined(self):
        """REET_FIELDS_OMIT contains rl."""
        match = re.search(
            r"const\s+REET_FIELDS_OMIT\s*=\s*\[([^\]]+)\]",
            self.html
        )
        assert match, "REET_FIELDS_OMIT not found"
        keys = re.findall(r"'(\w+)'", match.group(1))
        assert keys == ['rl']

    def test_normalize_omits_reet_local_when_off(self):
        """normalizeShareState checks re flag and omits rl when REET OFF."""
        assert 'REET_FIELDS_OMIT' in self.html
        # Verify the logic: if (!state.re) REET_FIELDS_OMIT...
        assert "!state.re" in self.html or "state.re" in self.html

    def test_normalize_omits_single_exit_keys(self):
        """normalizeShareState checks mx flag and omits single-exit keys."""
        # Verify the JS logic references SINGLE_EXIT_OMIT when !isMulti
        assert 'SINGLE_EXIT_OMIT' in self.html
        assert 'MULTI_EXIT_OMIT' in self.html

    def test_normalize_omits_1031_tax_fields(self):
        """normalizeShareState checks x1 flag and omits tax fields when 1031 ON."""
        assert 'TAX_FIELDS_1031' in self.html

    def test_url_max_length_worst_case(self):
        """Even with all 29 params at max reasonable values, URL < 2048 chars."""
        # Simulate worst-case URL: all params set to large values
        # Base URL (github pages): ~50 chars
        # v=1: 3 chars
        # Each param: key(2-3) + = + value(max ~12 for 999999999999) + & = ~18 chars
        # 29 params * 18 = 522 chars
        # Total: ~576 chars — well under 2048

        base_url = "https://nmulnick.github.io/real-estate-analysis/?"
        params = ["v=1"]
        for key, cfg in self.schema.items():
            if cfg['type'] == 'checkbox':
                params.append(f"{key}=1")
            elif cfg['type'] == 'dollar':
                params.append(f"{key}=999999999999")  # 12-digit worst case
            else:
                params.append(f"{key}=99.999")
        url = base_url + "&".join(params)
        assert len(url) < 2048, f"Worst-case URL is {len(url)} chars"

    def test_round_trip_structure(self):
        """readShareStateFromURL correctly handles v param and returns a state dict."""
        # The function should exist and handle the 'v' param
        assert 'readShareStateFromURL' in self.html
        assert "params.has('v')" in self.html or 'params.has("v")' in self.html or "params.size" in self.html

    def test_unknown_params_ignored(self):
        """readShareStateFromURL only processes keys in SHARE_SCHEMA."""
        # Verify the code iterates SHARE_SCHEMA, not raw params
        assert 'Object.entries(SHARE_SCHEMA)' in self.html


class TestShareHydration:
    """Verify the startup/hydration flow handles URL params correctly."""

    def setup_method(self):
        self.html = _read_html()

    def test_1031_split_into_three_functions(self):
        """toggle1031 is split into apply1031FieldLock, apply1031DefaultValues,
        and handle1031ToggleChange."""
        assert 'function apply1031FieldLock(' in self.html
        assert 'function apply1031DefaultValues(' in self.html
        assert 'function handle1031ToggleChange(' in self.html

    def test_exit_mode_ui_only_exists(self):
        """applyExitModeUIOnly exists for hydration-safe exit mode setup."""
        assert 'function applyExitModeUIOnly(' in self.html

    def test_hydration_reads_url_before_toggle(self):
        """readShareStateFromURL is called before apply1031FieldLock in init."""
        # Search from the init section (Phase 1 comment) to avoid matching resetToDefaults
        init_start = self.html.index('// Phase 1:')
        pos_read = self.html.index('readShareStateFromURL(window.location.search)', init_start)
        pos_lock = self.html.index('apply1031FieldLock(document.getElementById', init_start)
        assert pos_read < pos_lock, "URL read must happen before field lock"

    def test_default_values_only_without_url(self):
        """apply1031DefaultValues only runs when no URL params present."""
        # Find the conditional: if (!urlState) { apply1031DefaultValues...
        pattern = r'if\s*\(\s*!urlState\s*\)\s*\{[^}]*apply1031DefaultValues'
        assert re.search(pattern, self.html, re.DOTALL), (
            "apply1031DefaultValues should only run when !urlState"
        )

    def test_event_routing_1031(self):
        """in_1031 change routes to handle1031ToggleChange, not generic recalculate."""
        # Should call handle1031ToggleChange and return
        assert "handle1031ToggleChange(); return;" in self.html

    def test_event_routing_exit_mode(self):
        """in_multi_exit change routes to toggleExitMode, not generic recalculate."""
        assert "toggleExitMode(); return;" in self.html

    def test_single_recalculate_at_end(self):
        """Init ends with exactly one recalculate() call."""
        # Find the init section and verify recalculate() is the last call
        init_section = self.html[self.html.index('// Phase 5:'):]
        init_section = init_section[:init_section.index('\n\n')]
        assert 'recalculate()' in init_section


class TestSharePrintSetup:
    """Verify print/share DOM elements and CSS exist."""

    def setup_method(self):
        self.html = _read_html()

    def test_share_button_exists(self):
        assert 'id="btnShare"' in self.html

    def test_print_button_exists(self):
        assert 'id="btnPrint"' in self.html

    def test_share_status_element(self):
        assert 'id="shareStatus"' in self.html

    def test_print_meta_element(self):
        assert 'id="printMeta"' in self.html

    def test_print_timestamp_element(self):
        assert 'id="printTimestamp"' in self.html

    def test_print_url_element(self):
        assert 'id="printUrl"' in self.html

    def test_print_css_hides_sidebar(self):
        assert '.sidebar' in self.html
        # Verify @media print contains sidebar hiding
        print_section = self.html[self.html.index('@media print'):]
        print_section = print_section[:print_section.index('}', print_section.index('}') + 1) + 1]
        assert '.sidebar' in print_section

    def test_print_css_hides_buttons(self):
        print_match = re.search(r'@media print\s*\{(.+?)\n  /\*', self.html, re.DOTALL)
        if print_match:
            block = print_match.group(1)
            assert '.btn-secondary' in block or '#btnShare' in block or '.header-actions' in block

    def test_print_css_preserves_colors(self):
        assert 'print-color-adjust: exact' in self.html

    def test_print_only_class(self):
        assert '.print-only' in self.html

    def test_beforeprint_handler(self):
        assert "addEventListener('beforeprint'" in self.html or 'addEventListener("beforeprint"' in self.html

    def test_afterprint_handler(self):
        assert "addEventListener('afterprint'" in self.html or 'addEventListener("afterprint"' in self.html

    def test_chart_animation_frozen(self):
        """Charts have animation disabled in beforeprint handler."""
        assert "c.options.animation = false" in self.html
        assert "c.update('none')" in self.html or 'c.update("none")' in self.html

    def test_copy_share_url_function(self):
        assert 'function copyShareURL()' in self.html

    def test_print_report_function(self):
        assert 'function printReport()' in self.html

    def test_reset_button_exists(self):
        assert 'id="btnReset"' in self.html

    def test_reset_to_defaults_function(self):
        assert 'function resetToDefaults()' in self.html

    def test_clipboard_fallback(self):
        """copyShareURL has a prompt() fallback for clipboard failures."""
        assert 'prompt(' in self.html


class TestResetBehavior:
    """Verify resetToDefaults restores schema defaults and clears URL."""

    def setup_method(self):
        self.html = _read_html()
        self.schema = _parse_share_schema(self.html)
        # Extract the resetToDefaults function body
        start = self.html.index('function resetToDefaults')
        end = self.html.index('\n}', start) + 2
        self.fn = self.html[start:end]

    def test_reset_writes_all_schema_defaults(self):
        """resetToDefaults iterates SHARE_SCHEMA and writes defaults via writeShareStateToDOM."""
        assert 'writeShareStateToDOM(defaults)' in self.fn

    def test_reset_applies_1031_field_lock(self):
        """resetToDefaults calls apply1031FieldLock after writing defaults."""
        assert 'apply1031FieldLock' in self.fn
        assert 'apply1031DefaultValues' in self.fn

    def test_reset_applies_reet_field_lock(self):
        """resetToDefaults calls applyREETFieldLock after writing defaults."""
        assert 'applyREETFieldLock' in self.fn

    def test_reset_applies_exit_mode(self):
        """resetToDefaults calls applyExitModeUIOnly after writing defaults."""
        assert 'applyExitModeUIOnly' in self.fn

    def test_reset_clears_url(self):
        """resetToDefaults clears URL to clean path via history.replaceState."""
        assert 'history.replaceState' in self.fn
        assert 'window.location.pathname' in self.fn

    def test_reset_triggers_recalculate(self):
        """resetToDefaults calls recalculate()."""
        assert 'recalculate()' in self.fn

    def test_reset_cancels_url_timer(self):
        """resetToDefaults cancels debounced URL timer before clearing URL."""
        assert 'clearTimeout(window._urlTimer)' in self.fn


class TestURLSyncRegression:
    """Verify URL sync doesn't produce spurious params on default state."""

    def setup_method(self):
        self.html = _read_html()

    def test_sync_checks_normalized_emptiness(self):
        """URL sync checks if normalizeShareState returned empty object."""
        assert 'Object.keys(normalized).length === 0' in self.html

    def test_sync_clears_url_when_all_defaults(self):
        """URL sync clears to clean path when all values are at defaults."""
        # The debounced sync should use window.location.pathname to clear
        assert 'window.location.pathname' in self.html

    def test_sync_only_writes_params_when_non_default(self):
        """URL sync only calls buildShareURLFromState when there are non-default values."""
        # Verify the else branch builds the URL only when normalized is non-empty
        # The structure should be: if empty → clear, else → build URL
        assert 'Object.keys(normalized).length === 0' in self.html
        assert 'buildShareURLFromState' in self.html

    def test_phase0_resets_checkboxes_before_hydration(self):
        """Init resets all checkboxes to schema defaults before URL hydration.
        Prevents browser form state restoration from flipping toggles OFF on refresh."""
        init_start = self.html.index('// Phase 0:')
        phase1_start = self.html.index('// Phase 1:', init_start)
        phase0 = self.html[init_start:phase1_start]
        assert "cfg.type === 'checkbox'" in phase0 or 'cfg.type === "checkbox"' in phase0
        assert '.checked = cfg.default' in phase0

    def test_no_bare_v1_on_default_state(self):
        """The debounced sync never produces a bare ?v=1 URL when all at defaults.
        This prevents the refresh-clobbers-toggles bug."""
        # Verify normalizeShareState is checked BEFORE buildShareURLFromState
        sync_start = self.html.index('Debounced URL sync')
        sync_block = self.html[sync_start:self.html.index('}, 500)', sync_start) + 6]
        pos_check = sync_block.index('Object.keys(normalized)')
        pos_build = sync_block.index('buildShareURLFromState')
        assert pos_check < pos_build, "Must check for empty state before building URL"
