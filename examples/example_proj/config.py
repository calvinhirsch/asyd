from dataclasses import dataclass, field

import sys
sys.path.append('../../src')

from asyd import Config, MultiConfig, ConfigRef, MV, build, yamlize


@dataclass
class DatasetConf(Config):
    img_size: int = MV
    ch: int = MV

    _default_dependencies = {ConfigRef("")}
@dataclass
class PyTorchDatasetConf(DatasetConf):
    name: str = MV
@dataclass
class LocalDatasetConf(DatasetConf):
    path: str = MV

@dataclass
class DatasetMulti(MultiConfig[DatasetConf]):
    _options = {
        "local": LocalDatasetConf,
        "pytorch": PyTorchDatasetConf
    }

@dataclass
class ModelArchConf(Config):
    some_str: str = MV

    _default_dependencies = {ConfigRef("dataset")}
@dataclass
class DCRNArchConf(ModelArchConf):
    some_str = "A"
    some_other_shit: str = ""
@dataclass
class VanillaArchConf(ModelArchConf):
    some_str = "B"
    some_other_other_shit: int = MV

@dataclass
class ModelArchMulti(MultiConfig[ModelArchConf]):
    _options = {
        "dcrn": DCRNArchConf,
        "vanilla": VanillaArchConf
    }

@dataclass
class ModelConf(Config):
    something: int = MV
    arch: ModelArchMulti = MV

@dataclass
class Conf(Config):
    dataset: DatasetMulti = MV
    model: ModelConf = ModelConf()
    something: int = MV

cfg = build(Conf, "config")

print(yamlize(cfg))
