from typing import Type, TypeVar, Dict, List, Callable, Union, Optional
from argparse import ArgumentParser
from .config import Config, MultiConfig, ConfigRef, validate_refs
from .config_utils import MV
from .dependencies import generate_acyclic_traveral
from .argparsing import parse
from .exceptions import EverythingHasBrokenException, RedundantDefaultException, InvalidDefaultFileException, InvalidLoadedConfigException
from pathlib import Path
import yaml
import warnings


YAML_EXTS: List[int] = [".yml", ".yaml"]
QUERY_OPS: Dict[str, Callable[[str, str], bool]] = {
    "=": lambda target_val, x: target_val == x,
    "!=": lambda target_val, x: target_val != x,
    ">": lambda target_val, x: target_val > x,
    "<": lambda target_val, x: target_val < x,
    ">=": lambda target_val, x: target_val >= x,
    "<=": lambda target_val, x: target_val <= x,
    # TO-DO: Add more
}


T = TypeVar("T", bound=Config)
def build(base_schema: Type[T], directory: str,  parser: Optional[ArgumentParser] = None, args: List[str] = [], load_path: str = None) -> T:
    '''
    This is the main function that calls everything else. Validates the
    references in a schema (a class that inherits from Config), generates a
    build order that satisfies all default dependencies, creates an
    ArgumentParser with all values in the schema, then initializes and fills
    the config object based on defaults from the configuration directory and
    command line arguments.

            Parameters:
                    base_schema (Type[T]): Schema to be built
                    directory (str): Directory holding defaults for base_schema

            Returns:
                    config (T): Initialized base_schema with values filled in
    '''

    # Validate schemas and their dependencies
    validate_refs(base_schema)

    print(base_schema)

    # Get command line args
    args = parse(base_schema, parser, args)

    # Load config if provided
    load_path = args["load_path"] if load_path is None else load_path
    loaded_config = None
    if not load_path is None:
        path = Path(load_path)
        if not path.exists():
            raise FileNotFoundError(f"Load path {load_path} does not exist.")
        if path.is_dir():
            raise IsADirectoryError(f"Load path {load_path} should be a yaml file but it is a directory.")

        with path.open() as f:
            loaded_config = yaml.load(f, Loader=yaml.CLoader)

    # Check provided directory
    path = Path(directory)
    if not path.is_dir():
        raise NotADirectoryError("Provided configuration base directory {} is not a folder.".format(directory))

    # Build defaults tree
    defaults_tree = build_defaults_tree(base_schema, path)

    # Ensure dependencies are not cyclic and create build order
    build_order = generate_acyclic_traveral(base_schema)

    # Build config
    config = base_schema()

    for schema_path in build_order:
        build_config(config, defaults_tree, schema_path, path, args, loaded_config=None if loaded_config is None else get_loaded_config(loaded_config, schema_path))

    return config


def build_defaults_tree(schema: Type[T], dir: Path):
    '''
    Builds the defaults tree for a schema with a corresponding directory. First
    parses the defaults.yaml file and the defaults folder and merges them, then
    recursively builds defaults trees for nested configs and merges the original
    tree with them. In the case of a multiconfig, defaults from the parent
    directory get copied to all the option directories.

            Parameters:
                    schema (Type[T]): The schema to build the defaults tree for
                    dir (Path): The directory corresponding to the schema

            Returns:
                    tree (Dict): The constructed defaults tree

    '''
    tree = {}
    if not dir.exists():
        return tree

    possible_defaults_files = [dir / ("defaults" + ext) for ext in YAML_EXTS]
    for df in possible_defaults_files:
        if df.exists():
            with open(df) as f:
                tree = yaml.load(f, Loader=yaml.CLoader)
            break

    folder_tree = parse_defaults_dir(dir / "defaults") if (dir / "defaults").exists() else {}
    if len(tree) < 1:
        tree = folder_tree
    elif len(folder_tree) < 1:
        pass
    else:
        merge_defaults_trees(tree, folder_tree, override=True) # override to maintain standard of more nested folders have higher priority

    if issubclass(schema, MultiConfig):
        parent_tree = tree
        tree = {}

        # Parse individual option schemas and copy parent schema into each
        for option, option_schema in schema._options.items():
            tree[option] = build_defaults_tree(option_schema, dir / option)
            merge_defaults_trees(tree[option], parent_tree)
    else:
        # Recursively build tree for nested configs/folders and then merge
        for field, v in schema.__dataclass_fields__.items():
            if issubclass(v.type, Config) or issubclass(v.type, MultiConfig):
                subdir = dir / field
                if subdir.exists():
                    subtree = build_defaults_tree(v.type, subdir)
                    if field in tree:
                        merge_defaults_trees(tree[field], subtree)
                    else:
                        tree[field] = subtree

    return tree

def parse_defaults_dir(dir: Path):
    '''
    Parses a defaults directory into a single defaults tree/dictionary.
    Basically just converts folder structure to dictionary structure.

            Parameters:
                    dir (Path): The defaults directory

            Returns:
                    tree (Dict): The constructed defaults tree

    '''
    d = {}
    for f in dir.iterdir():
        name = None

        if f.is_dir():
            name = f
            d[name] = defaults_tree_from_dir(base_config, f)
        else:
            for ext in YAML_EXTS:
                if str(f).endswith(ext):
                    name = str(f).split(".")[0]
                    with f.open() as file:
                        if name in d:
                            if name[-1] != "!":
                                raise RedundantDefaultException(f"Field {name} appeared in the defaults tree multiple times. Use override (!) at the end of field name to allow.")
                        else:
                            d[name] = yaml.load(file, Loader=yaml.CLoader)
                    break

            if name is None:
                raise warnings.warn(f"Unknown file {str(f)} found in defaults folder {dir}. Ignoring.")

    return d

def merge_defaults_trees(tree: Dict, new_tree: Dict, override=False):
    '''
    Merges new_tree into tree without overriding. Raises
    RedundantDefaultException if a value appears twice that is not marked as an
    override (!). Modifies tree.

            Parameters:
                    tree (Dict): First defaults tree
                    new_tree (Dict): Second defaults tree

            Returns:
                    None
    '''
    for k, v in new_tree.items():
        if k in tree:
            if isinstance(v, Dict):
                merge_defaults_trees(tree[k], v)
            else:
                if k[-1] != "!":
                    raise RedundantDefaultException(f"Field {k} appeared in the defaults tree multiple times. Use override (!) at the end of field name to allow.")
                elif override:
                    tree[k] = v
        else:
            tree[k] = v


def build_config(base_config: T, base_defaults_tree: Dict, schema_path: str, base_dir: Path, args: Dict, loaded_config: Optional[Dict]) -> None:
    '''
    Builds a single config object (and not any nested config objects) at a
    specified schema_path from the base schema using command line arguments and
    defaults.

            Parameters:
                    base_config (T): Base config object that contains a schema
                        at schema_path that will be initialized and filled in
                        this function.
                    base_defaults_tree (Dict): Base defaults tree containing all
                        defaults, must be traversed to get local defaults tree
                    schema_path (str): Path from the base schema to the target
                        schema
                    base_dir (Path): Directory to base schema configuration
                        folder
                    args (Dict): Command line arguments


            Returns:
                    None
    '''

    local_args = {}
    for k, v in args.items():
        if k.startswith(schema_path):
            lk = k[len(schema_path):]
            if len(lk) > 1:
                lk = lk[1:] if lk.startswith(".") else lk
                if not "." in lk:
                    local_args[lk] = v
    if "load_path" in local_args:
        del local_args["load_path"]

    config, defaults_tree = traverse_to_config(base_config, base_defaults_tree, [] if schema_path == "" else schema_path.split("."))

    # Remove nested configs from defaults tree
    local_defaults_tree = {}
    for field, v in defaults_tree.items():
        type = config.__dataclass_fields__[field].type
        if not issubclass(type, Config) and not issubclass(type, MultiConfig):
            local_defaults_tree[field] = v

    dependencies = {r.path: get_config(base_config, [] if r.path == "" else r.path.split(".")) for r in config._default_dependencies}
    defaults = {}
    build_defaults(defaults, local_defaults_tree, dependencies)

    # Execute overrides
    for k, v in defaults.items():
        if k[-1] == "!":
            defaults[k[:-1]] = v
            del defaults[k]

    # Set default values in config based on defaults and args
    for k in config.__dataclass_fields__.keys():
        is_mc = issubclass(config.__dataclass_fields__[k].type, MultiConfig)
        is_c = not is_mc and issubclass(config.__dataclass_fields__[k].type, Config)
        val = MV
        no_val = False

        # First, check command line args
        if not is_c and not local_args[k] is None:
            val = local_args[k]
        else:
            # Second, check loaded config
            if not loaded_config is None:
                if not k in loaded_config:
                    raise InvalidLoadedConfigException(f"Field {k} not in loaded config.")  # Does not throw this error if missing value is specified in local_args

                if not loaded_config[k] is None:
                    if is_mc:
                        if type(loaded_config[k]) is dict:
                            if "_selected" in loaded_config[k]:
                                val = loaded_config[k]["_selected"]
                            else:
                                raise InvalidLoadedConfigException(f"Field {k} should be MultiConfig but loaded config is not formatted properly for this (no _selected)")
                        else:
                            raise InvalidLoadedConfigException(f"Field {k} should be a MultiConfig but loaded config is not formatted properly for this (no nested data)")
                    else:
                        val = loaded_config[k]

            # Third, check defaults
            elif k in defaults:
                val = defaults[k]

            else:
                no_val = True

        if is_mc:
            if no_val:
                pass
            else:
                val = config.__dataclass_fields__[k].type(val)

        setattr(config, k, val)

def traverse_to_config(config: Config, tree: Dict, schema_path: List[str]) -> (Config, Path):
    '''
    Traverses to a specified schema_path given a path through the nested schemas
    and returns the config once reached. Initializes any parts of the config in
    the path that have not yet been initialized. Also traverses through the
    defaults tree structure. This function allows building nested configs before
    their parents and vice versa.

            Parameters:
                    config (Config): Config object where schema_path starts.
                    tree (Path): Defaults tree at config
                    schema_path (List[str]): A path starting at 'config' that
                        ends at the desired config object. The first item in the
                        list should be the name of the Config or MultiConfig
                        parameter in 'config' that contains the desired nested
                        config object.

            Returns:
                    config (Config): Reference to the config at the requested
                        schema_path
                    tree (Dict): Defaults tree for returned config

    '''
    if len(schema_path) < 1:
        return config, tree
    field = schema_path[0]
    next_path = schema_path[1:] if len(schema_path) > 1 else []

    if getattr(config, field) == MV:
        cls = config.__dataclass_fields__[field].type
        if issubclass(cls, Config):
            setattr(config, field, cls())
        elif issubclass(cls, MultiConfig):
            setattr(config, field, cls(next(iter(cls._options.keys()))))
            warnings.warn("Neither default nor manual option set for {}, automatically picking first option.".format(cls))
        else:
            raise EverythingHasBrokenException("Something has gone terribly wrong!")

    field_val = getattr(config, field)
    if isinstance(field_val, MultiConfig):
        next_tree = tree[field][field_val._selected] if field in tree and field_val._selected in tree[field] else {}
        return traverse_to_config(field_val._config, next_tree, next_path)
    elif isinstance(field_val, Config):
        return traverse_to_config(getattr(config, field), tree[field] if field in tree else {}, next_path)
    else:
        raise EverythingHasBrokenException("Something has gone terribly wrong!")

def get_config(config: Config, schema_path: List[str]) -> Config:
    '''
    Similar to traverse_to_config but should only be called when the target
    config at the end of schema_path is guaranteed to already exist. This
    function is used to get configs that have already been built that other
    configs which are later in the build order might need for default values.

            Parameters:
                    config (Config): Config object where schema_path starts.
                    schema_path (List[str]): A path starting at 'config' that
                        ends at the desired config object. The first item in the
                        list should be the name of the Config or MultiConfig
                        parameter in 'config' that contains the desired nested
                        config object.

            Returns:
                    config (Config): Reference to the config at the requested
                        schema_path

    '''
    if len(schema_path) < 1:
        return config
    field = schema_path[0]

    return get_config(getattr(config, field), schema_path[1:] if len(schema_path) > 1 else [])

def get_loaded_config(loaded_config: Dict, schema_path: List[str]) -> Dict:
    if len(schema_path) < 1:
        return loaded_config
    field = schema_path[0]

    if field in loaded_config:
        return get_loaded_config(loaded_config[field], schema_path[1:] if len(schema_path) > 1 else [])
    else:
        raise InvalidLoadedConfigException(f"Loaded config does not contain field {field}.")

def build_defaults(defaults: Dict, defaults_tree: Dict, dependencies: Dict[str, Union[Config, MultiConfig]]) -> None:
    '''
    Takes a defaults tree for only this  and a list of references to already-processed
    dependencies for a single config object and determines a final list of
    defaults based on query results.

            Parameters:
                    defaults (Dict): Flat dictionary of default values for target
                        config object, starts empty on first call
                    defaults_tree (Dict): Defaults tree containing queries
                    dependencies (Dict[str, Union[Config, MultiConfig]])):
                        For each ConfigRef added to _default_dependencies,
                        contains the path string specified and a reference to
                        the Config or MultiConfig object at that path.

            Returns:
                    None

    '''

    dict_keys = [k for k, v in defaults_tree.items() if isinstance(v, Dict)]
    nondict_keys = [k for k, v in defaults_tree.items() if not isinstance(v, Dict)]

    # Queries
    for k in dict_keys:
        v = defaults_tree[k]
        last_dot_ind = k.rfind(".")
        dependency_key = k[:last_dot_ind]

        if not dependency_key in dependencies:
            raise InvalidDefaultFileException(f"Default file contains reference to dependency {k} which was not specified in _default_dependencies.")
        config = dependencies[dependency_key]
        target_val = getattr(config, k[last_dot_ind+1:])

        for qk, qv in v.items():
            for op_str, op in QUERY_OPS.items():
                if qk.startswith(op_str) and op(target_val, qk[len(opt_str):]):
                    build_defaults(defaults, qv, dependencies)

    # Default values
    for k in nondict_keys:
        if k in defaults:
            if k[-1] != "!":
                raise RedundantDefaultException("Field {} appeared in the defaults tree multiple times. Use override (!) at the end of field name to allow.".format(k))
        else:
            defaults[k] = defaults_tree[k]
