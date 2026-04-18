"""설정 로더 테스트."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.config import load_config, get_config_value


class TestLoadConfig:
    """load_config 함수 테스트."""

    def test_load_valid_config(self, tmp_path: Path):
        """유효한 YAML 파일을 정상적으로 로드하는지 확인."""
        config_data = {
            "kis": {"app_key": "test_key", "mode": "paper"},
            "trading": {"mode": "approval", "buy_margin": 0.9},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data), encoding="utf-8")

        result = load_config(config_file)

        assert result["kis"]["app_key"] == "test_key"
        assert result["kis"]["mode"] == "paper"
        assert result["trading"]["buy_margin"] == 0.9

    def test_file_not_found_raises_error(self):
        """존재하지 않는 파일 경로에서 FileNotFoundError 발생 확인."""
        with pytest.raises(FileNotFoundError, match="설정 파일을 찾을 수 없습니다"):
            load_config("/nonexistent/path/config.yaml")

    def test_empty_yaml_returns_empty_dict(self, tmp_path: Path):
        """빈 YAML 파일은 빈 딕셔너리를 반환하는지 확인."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")

        result = load_config(config_file)

        assert result == {}


class TestGetConfigValue:
    """get_config_value 함수 테스트."""

    def test_nested_key_access(self):
        """중첩 키에 정상 접근하는지 확인."""
        config = {"trading": {"mode": "auto", "buy_margin": 0.9}}

        assert get_config_value(config, "trading", "mode") == "auto"
        assert get_config_value(config, "trading", "buy_margin") == 0.9

    def test_missing_key_returns_default(self):
        """존재하지 않는 키에 기본값을 반환하는지 확인."""
        config = {"trading": {"mode": "auto"}}

        assert get_config_value(config, "trading", "nonexistent", default="fallback") == "fallback"
        assert get_config_value(config, "missing_section", "key", default=42) == 42

    def test_missing_key_returns_none_by_default(self):
        """기본값 미지정 시 None을 반환하는지 확인."""
        config = {"a": {"b": 1}}

        assert get_config_value(config, "a", "c") is None
