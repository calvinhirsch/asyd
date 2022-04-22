from dataclasses import dataclass, field
from asyd import Config, MCMeta, ConfigRef, MV, build, yamlize
import pathlib


@dataclass
class ConfigA(Config):
    field_a: int = MV

@dataclass
class ConfigB(Config):
    field_b: str = MV

class SomeMulti(metaclass=MCMeta,
                options = {
                    "first": ConfigA,
                    "second": ConfigA,
                    "third": ConfigB
                }):
    pass

@dataclass
class BaseConfig(Config):
    some_field: str = MV
    some_multi: SomeMulti = MV
