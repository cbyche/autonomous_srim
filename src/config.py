"""
설정 파일 로더.
config/config.yaml 파일을 읽어서 딕셔너리로 반환한다.
"""

import os
from pathlib import Path
from typing import Any

import yaml


# 프로젝트 루트 디렉토리 (src/ 의 상위)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 기본 설정 파일 경로
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """
    YAML 설정 파일을 로드하여 딕셔너리로 반환한다.

    Args:
        config_path: 설정 파일 경로. None이면 기본 경로 사용.

    Returns:
        설정 딕셔너리.

    Raises:
        FileNotFoundError: 설정 파일이 존재하지 않을 때.
        yaml.YAMLError: YAML 파싱 에러.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    if not path.exists():
        raise FileNotFoundError(
            f"설정 파일을 찾을 수 없습니다: {path}\n"
            f"config/config.example.yaml을 config/config.yaml로 복사한 후 값을 입력하세요."
        )

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


def get_config_value(config: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    중첩된 설정 값을 안전하게 가져온다.

    사용 예:
        get_config_value(config, "trading", "mode", default="approval")

    Args:
        config: 설정 딕셔너리.
        *keys: 중첩 키 경로.
        default: 키가 없을 때 반환할 기본값.

    Returns:
        설정 값 또는 기본값.
    """
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
