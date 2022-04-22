from dataclasses import dataclass, field
from asyd import Config, MultiConfig, ConfigRef, MV, build, yamlize
import pathlib


@dataclass
class BaseConfig(Config):
    some_field: str = MV
