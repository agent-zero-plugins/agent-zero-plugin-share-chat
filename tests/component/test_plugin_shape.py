"""L1 shape suite — testkit assertions against the share_chat plugin.

Fast (<1s), no A0 boot. Catches typo'd extension points, dead hooks,
blank thumbnails, undeclared deps, fabricated A0 API calls, and
committed secrets between commits.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from a0_plugin_testkit.assertions import (
    assert_extension_at_surface,
    assert_no_dead_plugin_hooks,
    assert_no_stray_extension_folders,
    assert_plugin_has_thumbnail,
)
from a0_plugin_testkit.real.a0_api import audit_a0_api_usage, assert_a0_api_usage_ok
from a0_plugin_testkit.real.deps import audit_dependencies, assert_dependencies_declared
from a0_plugin_testkit.real.validator import assert_validator_clean, static_validate

pytestmark = pytest.mark.component


def test_no_typo_extension_points(plugin_dir: Path) -> None:
    assert_no_stray_extension_folders(plugin_dir)


def test_share_button_wired_to_real_surface(plugin_dir: Path) -> None:
    """The whole plugin is one HTML extension — prove it targets a real surface."""
    assert_extension_at_surface(plugin_dir, "chat-top-end", pattern="*.html")


def test_no_dead_hooks(plugin_dir: Path) -> None:
    assert_no_dead_plugin_hooks(plugin_dir)


def test_thumbnail(plugin_dir: Path) -> None:
    assert_plugin_has_thumbnail(plugin_dir)


def test_static_validator(plugin_dir: Path) -> None:
    assert_validator_clean(static_validate(plugin_dir), allow_warnings=False)


def test_dependencies_declared(plugin_dir: Path) -> None:
    assert_dependencies_declared(audit_dependencies(plugin_dir))


def test_a0_api_usage_valid(plugin_dir: Path) -> None:
    assert_a0_api_usage_ok(audit_a0_api_usage(plugin_dir))


def test_manifest_versions_in_sync(plugin_dir: Path) -> None:
    """plugin.yaml and meta.yaml versions must match (REQ from sibling repos:
    version drift between the two fails the publish gate)."""
    import yaml

    plugin = yaml.safe_load((plugin_dir / "plugin.yaml").read_text())
    meta = yaml.safe_load((plugin_dir / "meta.yaml").read_text())
    assert plugin["version"] == meta["version"], (
        f"version drift: plugin.yaml={plugin['version']} meta.yaml={meta['version']}"
    )


def test_license_declared_apache2(plugin_dir: Path) -> None:
    """REQ-LIC-001: org law — Apache-2.0 declared in the manifest and the repo
    LICENSE is the full canonical text, not a stub."""
    import yaml

    plugin = yaml.safe_load((plugin_dir / "plugin.yaml").read_text())
    assert plugin.get("license") == "Apache-2.0"

    license_file = plugin_dir.parent.parent.parent / "LICENSE"
    text = license_file.read_text()
    assert "Apache License" in text and "Version 2.0" in text
    assert len(text) > 10_000, f"LICENSE is a stub ({len(text)} bytes)"
