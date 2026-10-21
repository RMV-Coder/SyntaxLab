from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from syntaxlab_api.engines.base import EngineConfigError
from syntaxlab_api.engines.registry import available_engines, resolve_engine
from syntaxlab_api.languages.config import ConfigError, load_languages_file
from syntaxlab_api.languages.registry import LanguageRegistry
from syntaxlab_api.schemas.analysis import Capability, StructureKind
from syntaxlab_api.settings import SERVICE_ROOT, Settings
from tests.conftest import SCHEMES, language, write_config
from tests.support.engines import WhitespaceTestEngine


def registry(tmp_path: Path, languages: list[dict[str, Any]], **settings: Any) -> LanguageRegistry:
    path = write_config(tmp_path, languages)
    return LanguageRegistry.from_config(
        load_languages_file(path), Settings(languages_file=path, **settings)
    )


class TestLanguagesFile:
    def test_shipped_configuration_is_valid(self) -> None:
        cfg = load_languages_file(SERVICE_ROOT / "config" / "languages.yaml")
        english = next(lang for lang in cfg.languages if lang.code == "en")
        assert english.engine == "stanza"
        assert english.schemes[Capability.DEPENDENCY] == "ud-2"
        assert english.schemes[Capability.CONSTITUENCY] == "ptb-revised"

    def test_duplicate_code_or_alias_rejected(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, [language("aa", aliases=["zz"]), language("zz")])
        with pytest.raises(ConfigError, match="'zz'"):
            load_languages_file(path)

    def test_undeclared_scheme_rejected(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, [language("aa", schemes={"dependency": "nope"})])
        with pytest.raises(ConfigError, match="not declared"):
            load_languages_file(path)

    def test_invalid_code_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError):
            load_languages_file(write_config(tmp_path, [language("English")]))

    def test_unknown_field_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError):
            load_languages_file(write_config(tmp_path, [language("aa", engin="typo")]))

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_languages_file(tmp_path / "absent.yaml")

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("languages: [", encoding="utf-8")
        with pytest.raises(ConfigError, match="YAML"):
            load_languages_file(path)


class TestRegistry:
    def test_language_resolved_by_code_and_alias_case_insensitively(self, tmp_path: Path) -> None:
        reg = registry(tmp_path, [language("aa", aliases=["AAA"])])
        assert reg.get("aa") is reg.get("AA") is reg.get("aaa")

    def test_capabilities_come_from_engine(self, tmp_path: Path) -> None:
        reg = registry(tmp_path, [language("aa", engine_options={"structures": ["dependency"]})])
        runtime = reg.get("aa")
        assert runtime.structures == {StructureKind.DEPENDENCY}
        assert Capability.CONSTITUENCY not in runtime.capabilities

    def test_structure_without_scheme_rejected(self, tmp_path: Path) -> None:
        lang = language("aa")
        lang["schemes"] = {"dependency": "test-dep"}  # constituency produced but undeclared
        with pytest.raises(ConfigError, match="no scheme is configured"):
            registry(tmp_path, [lang])

    def test_scheme_for_missing_capability_rejected(self, tmp_path: Path) -> None:
        lang = language("aa", engine_options={"structures": ["dependency"]})
        lang["schemes"] = {"dependency": "test-dep", "constituency": "test-con"}
        with pytest.raises(ConfigError, match="does not provide"):
            registry(tmp_path, [lang])

    def test_disabled_and_filtered_languages_skipped(self, tmp_path: Path) -> None:
        reg = registry(
            tmp_path,
            [language("aa"), language("bb", enabled=False), language("cc")],
            enabled_languages=["aa"],
        )
        assert [r.code for r in reg] == ["aa"]

    def test_unknown_enabled_language_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="unknown/disabled"):
            registry(tmp_path, [language("aa")], enabled_languages=["zz"])

    def test_per_language_limits_override_defaults(self, tmp_path: Path) -> None:
        reg = registry(tmp_path, [language("aa", limits={"max_chars": 50})], default_max_words=7)
        limits = reg.get("aa").limits
        assert (limits.max_chars, limits.max_words) == (50, 7)


class TestEngineResolution:
    def test_builtin_stanza_engine_registered_as_entry_point(self) -> None:
        assert "stanza" in available_engines()

    def test_module_reference(self) -> None:
        assert resolve_engine("tests.support.engines:WhitespaceTestEngine") is WhitespaceTestEngine

    def test_unknown_engine_lists_installed(self) -> None:
        with pytest.raises(EngineConfigError, match=r"installed engines: .*stanza"):
            resolve_engine("does-not-exist")

    @pytest.mark.parametrize(
        "reference",
        ["tests.support.missing:Engine", "tests.support.engines:Nope", "yaml:safe_load"],
    )
    def test_bad_references(self, reference: str) -> None:
        with pytest.raises(EngineConfigError):
            resolve_engine(reference)


def test_schemes_fixture_matches_yaml_shape(tmp_path: Path) -> None:
    path = write_config(tmp_path, [language("aa")])
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["schemes"] == SCHEMES
