from typing import Type, Dict, Any, Set, Optional, List
from argparse import ArgumentParser
from .serialization import dictize
from .config import Config, MultiConfig

def parse(schema: Type[Config], args: List[str] = []):
    parser = ArgumentParser()
    parse_helper(schema, parser, "", set())

    return vars(parser.parse_args(args))

def parse_helper(schema: Type[Config], parser: ArgumentParser, prefix: str, already_added: Set):
    for name, field in schema.__dataclass_fields__.items():
        if issubclass(field.type, Config):
            parse_helper(field.type, parser, prefix + name + ".", already_added)
        elif issubclass(field.type, MultiConfig):
            add_to_parser("--" + prefix + name, str, parser, already_added, choices=field.type.choices.keys())

            for cls in field.type._options.values():
                parse_helper(cls, parser, prefix + name + ".", already_added)
        else:
            add_to_parser("--" + prefix + name, field.type, parser, already_added)

def add_to_parser(field_name: str, field_type: Type[Any], parser: ArgumentParser, already_added: Set, choices=None):
    # Necessary to check if an argument is already added because of different MultiConfig branches converging to the same field_name
    if field_name in already_added:
        return

    parser.add_argument(field_name, type=field_type, choices=choices, default=None)
    already_added.add(field_name)
