from typing import Type, cast, Union, Dict, Callable
from .config import Config, MultiConfig
import yaml


def dictize(config: Config) -> Dict:
    d = {}
    for k, v in config.__dict__.items():
        if (k[0] == "_") or isinstance(v, Callable):
            pass
        elif isinstance(v, Config):
            d[k] = dictize(v)
        elif isinstance(v, MultiConfig):
            d[k] = dictize(v._config)
            d[k]["_selected"] = v._selected
        else:
            d[k] = v
    return d

def yamlize(config: Config) -> str:
    return yaml.dump(dictize(config))
