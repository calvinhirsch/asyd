from dataclasses import dataclass, field
from asyd import Config, ConfigRef, MV, build, yamlize
import pathlib


@dataclass
class BaseConfig(Config):
    field_a: int = MV
    field_b: int = MV
