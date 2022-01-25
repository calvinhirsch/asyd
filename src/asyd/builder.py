from typing import Type, TypeVar, Dict, List, Callable, Union, Optional
from .config import Config, MultiConfig, ConfigRef, validate_refs
from .config_utils import MV
from .dependencies import generate_acyclic_traveral
from .argparsing import parse
from .exceptions import EverythingHasBrokenException, RedundantDefaultException, InvalidDefaultFileException
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
def build(base_schema: Type[T], directory: str, args: List[str] = []) -> T:
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

    # Ensure dependencies are not cyclic and create build order
    build_order = generate_acyclic_traveral(base_schema)

    # Get command line args
    args = parse(base_schema, args)

    # Build config
    path = Path(directory)
    if not path.is_dir():
        raise NotADirectoryError("Provided configuration base directory {} is not a folder.".format(directory))

    config = base_schema()

    base_dir = Path(directory)
    for schema_path in build_order:
        build_config(config, schema_path, base_dir, args)

    return config

def build_config(base_config: T, schema_path: str, base_dir: Path, args: Dict) -> None:
    '''
    Builds a single config object (and not any nested config objects) at a
    specified schema_path from the base schema using command line arguments and
    defaults.

            Parameters:
                    base_config (T): Base config object that contains a schema
                        at schema_path that will be initialized and filled in
                        this function.
                    schema_path (str): Path from the base schema to the target
                        schema
                    base_dir (Path): Directory to base schema configuration
                        folder
                    args (Dict): Command line arguments


            Returns:
                    None
    '''

    #local_args = {k[len(schema_path):].split(".")[0]: v for k, v in args.items() if k.startswith(schema_path) and not "." in k[len(schema_path)+1:] and len(k) > len(schema_path) + 1}
    local_args = {}
    for k, v in args.items():
        if k.startswith(schema_path):
            lk = k[len(schema_path):]
            if len(lk) > 1:
                lk = lk[1:] if lk.startswith(".") else lk
                if not "." in lk:
                    local_args[lk] = v


    config, dir = traverse_to_config(base_config, base_dir, [] if schema_path == "" else schema_path.split("."))

    defaults_tree = get_defaults_tree(dir)


    dependencies = {r.path: get_config(base_config, [] if r.path == "" else r.path.split(".")) for r in config._default_dependencies}
    defaults = {}
    build_defaults(defaults, defaults_tree, dependencies)

    # Execute overrides
    for k, v in defaults.items():
        if k[-1] == "!":
            defaults[k[:-1]] = v
            del defaults[k]

    # Set default values in config based on defaults and args
    for k, v in local_args.items():
        val = MV
        if not v is None:
            val = local_args[k]
        elif k in defaults:
            val = defaults[k]

        if issubclass(config.__dataclass_fields__[k].type, MultiConfig):
            val = config.__dataclass_fields__[k].type(val)

        setattr(config, k, val)

def traverse_to_config(config: Config, dir: Path, schema_path: List[str]) -> (Config, Path):
    '''
    Traverses to a specified schema_path given a path through the nested schemas
    and returns the config once reached. Initializes any parts of the config in
    the path that have not yet been initialized. Also traverses through the
    folder structure to the corresponding folder for the config and returns the
    directory for this. This function allows building nested configs before
    their parents and vice versa.

            Parameters:
                    config (Config): Config object where schema_path starts.
                    dir (Path): Directory of defaults folder for 'config'
                    schema_path (List[str]): A path starting at 'config' that
                        ends at the desired config object. The first item in the
                        list should be the name of the Config or MultiConfig
                        parameter in 'config' that contains the desired nested
                        config object.

            Returns:
                    config (Config): Reference to the config at the requested
                        schema_path
                    dir (Path): Directory of the corresponding defaults folder

    '''
    # print("  traverse to",schema_path)

    if len(schema_path) < 1:
        return config, dir
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
        next_dir = dir / field if field in field_val.superschema().__dataclass_fields__ else dir / field_val._selected / field
        return traverse_to_config(field_val._config, next_dir, next_path)
    elif isinstance(field_val, Config):
        return traverse_to_config(getattr(config, field), dir / field, next_path)
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

def get_defaults_tree(config_dir: Path) -> Dict:
    '''
    Reads all default yaml files (either defaults.yaml or others in the defaults
    directory for the given config directory) and combines them into a single
    dictionary. Does not yet process queries, just merges all of them into
    a single tree.

            Parameters:
                    config_dir (Path): Directory of config folder

            Returns:
                    defaults (Dict): Tree of all defaults

    '''
    defaults = {}

    defaults_yaml = config_dir / "defaults.yaml"
    if defaults_yaml.exists() and not defaults_yaml.is_dir():
        with defaults_yaml.open() as f:
            defaults = yaml.load(f, Loader=yaml.CLoader)

    defaults_dir = config_dir / "defaults"
    if defaults_dir.exists() and defaults_dir.is_dir():
        fill_in_defaults(defaults, defaults_tree_from_dir(defaults, defaults_dir))

    return defaults

def defaults_tree_from_dir(base_config: T, dir: Path) -> Dict:
    '''
    Creates a defaults tree from a given folder.

            Parameters:
                    base_config: Base level config
                    dir: Target folder directory

            Returns:
                    None

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
                        d[name] = yaml.load(file, Loader=yaml.CLoader)
                    break

            if name is None:
                raise warnings.warn("Unknown file {} found in config folder. Ignoring.".format(str(f)))

    return d

def fill_in_defaults(defaults: Dict, new_defaults: Dict) -> None:
    '''
    Helper function for merging two defaults trees together.

            Parameters:
                    defaults (Dict): Starting defaults tree
                    new_defaults (Dict): Defaults tree from a new source to be
                        added to 'defaults'.

            Returns:
                    None

    '''
    for k in new_defaults.keys():
        if k in defaults:
            if isinstance(defaults[k], Dict):
                fill_in_defaults(defaults[k], new_defaults[k])
            else:
                raise EverythingHasBrokenException("Something has gone terribly wrong!")

def build_defaults(defaults: Dict, defaults_tree: Dict, dependencies: Dict[str, Union[Config, MultiConfig]]) -> None:
    '''
    Takes a defaults tree and a list of references to already-processed
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
