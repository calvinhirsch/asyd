from dataclasses import dataclass, field
from asyd import Config, MultiConfig, ConfigRef, MV, build, yamlize
import pathlib

@dataclass
class ParentConfig(Config):
    pass

@dataclass
class ConfigA(ParentConfig):
    field_a: int = MV

@dataclass
class ConfigB(ParentConfig):
    field_b: str = MV

class SomeMulti(MultiConfig[ParentConfig]):
    _options = {
        "first": ConfigA,
        "second": ConfigA,
        "third": ConfigB
    }

@dataclass
class BaseConfig(Config):
    some_field: str = MV
    some_multi: SomeMulti = MV
