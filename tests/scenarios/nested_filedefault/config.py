from dataclasses import dataclass, field
from asyd import Config, ConfigRef, MV, build, yamlize
import pathlib


@dataclass
class NestedConfig(Config):
    some_nested_field: int = MV

@dataclass
class BaseConfig(Config):
    some_field: str = MV
    nested_config: NestedConfig = NestedConfig()
