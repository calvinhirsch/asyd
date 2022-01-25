from dataclasses import dataclass, field, Field
from typing import List, Dict, TypeVar, Type, Callable, Any, cast, ClassVar, Union, Generic, Optional, get_args, Set, get_type_hints
from typing_extensions import Protocol
from .config_utils import MV, ABCMeta, abstract_attribute
from .exceptions import InvalidOptionException, RequiredReferenceException, InvalidPathException, InconsistentReferenceTypeException
import inspect
import copy


class Config:
    _default_dependencies: ClassVar[Set["ConfigRef"]] = {}
    __dataclass_fields__: ClassVar[Dict[str, Any]]

class MultiMeta(ABCMeta):
    def __call__(cls, selection: str, *args, **kwargs):
        instance = super().__call__(*args, **kwargs)
        instance._select(selection)
        return instance

S = TypeVar("S", bound=Config)
class MultiConfig(Generic[S], metaclass=MultiMeta):
    _options: ClassVar[Dict[str, Type[S]]] = abstract_attribute()
    _config: Config
    _selected: str
    __orig_bases__: List

    def _select(self, selection: str):
        if selection in self._options:
            self._config = self._options[selection]()
            self._selected = selection
        else:
            raise InvalidOptionException("Selected option '{}' does not exist in MultiConfig. Options are {}".format(option, self._options.keys()))

    @classmethod
    def superschema(cls) -> Type[S]:
        return get_args(cls.__orig_bases__[0])[0]

class ConfigRef:
    def __init__(self, path: str, optional: bool = False):
        self.optional: bool = optional
        self.path: str = path

    def __hash__(self):
        return hash(self.path)

    def __repr__(self):
        return "ConfigRef(" + self.path + ")"

    def __eq__(self, other):
        if isinstance(other, ConfigRef):
            return (self.path == other.path)
        else:
            return False

class ValidConfigRef(ConfigRef):
    def __init__(self, ref: ConfigRef, schema: Union[Type[Config], Type[MultiConfig]]):
        self.optional: bool = ref.optional
        self.path: str = ref.path
        self.schema: Union[Type[Config], Type[MultiConfig]] = schema

    def __repr__(self):
        return "Valid" + super().__repr__()

def validate_ref(ref: ConfigRef, base_schema: Type[Config]):
    return_type = None
    def validate_ref_helper(path: List[str], cls: Type[Any]) -> ValidConfigRef:
        next_path = path[1:] if len(path) > 1 else []
        vr = None

        if len(path) > 0:
            if issubclass(cls, MultiConfig):
                if inspect.isabstract(cls):
                    raise NotImplementedError("Field {} assigned abstract class {}.".format(field.name, cls))

                ss = cls.superschema()
                if path[0] in ss.__dataclass_fields__:
                    vr = validate_ref_helper(next_path, ss.__dataclass_fields__[path[0]].type)

                num_valid = 0
                for choice, choice_cls in cls._options.items():
                    if path[0] in choice_cls.__dataclass_fields__:
                        num_valid += 1
                        vr = validate_ref_helper(next_path, choice_cls.__dataclass_fields__[path[0]].type)
                    else:
                        if not ref.optional:
                            raise RequiredReferenceException("Reference to {} is not optional but is not valid when {} is {}. Pass optional=True to ConfigRef to make optional.".format(ref.path, cls, choice))
                if num_valid < 1:
                    raise InvalidPathException("Reference to {} in MultiConfig {} not valid for any choice. (full path: {})".format(path, cls, ref.path))
            elif issubclass(cls, Config):
                if path[0] in cls.__dataclass_fields__:
                    vr = validate_ref_helper(next_path, cls.__dataclass_fields__[path[0]].type)
                else:
                    raise InvalidPathException("Reference to {} in Config {} not valid for any choice. (full path: {})".format(path, cls, ref.path))
            else:
                raise InvalidPathException("Path {} continues past {}, which has type {} (not Config or MultiConfig).".format(ref.path, path[0], cls))
        else:
            if issubclass(cls, Config) or issubclass(cls, MultiConfig):
                nonlocal return_type
                if return_type is None:
                    return_type = cls
                else:
                    if return_type != rt:
                        raise InconsistentReferenceTypeException("Schema at path {} differs ({} and {}) depending on different MultiConfig choices along path.".format(ref.path, return_type, rt))

                vr = ValidConfigRef(ref, cls)
            else:
                raise InvalidPathException("Path {} ends at non-schema class {}. Dependencies (ConfigRefs) should end on a schema (Config or MultiConfig).".format(ref.path, cls))

        return vr

    return validate_ref_helper([] if ref.path == "" else ref.path.split("."), base_schema)

def validate_refs(base_schema: Type[Config]) -> None:
    def validate_refs_helper(schema: Type[Config], path=".") -> None:
        for name, field in schema.__dataclass_fields__.items():
            next_path = path + name + "."
            if issubclass(field.type, Config):
                validate_refs_helper(field.type, next_path)
            else:
                if issubclass(field.type, MultiConfig):
                    if inspect.isabstract(field.type):
                        raise NotImplementedError("Field {} assigned abstract class {}.".format(field.name, field.type))

                    validate_refs_helper(field.type.superschema(), next_path)
                    for cls in field.type._options.values():
                        validate_refs_helper(cls, next_path)
                    field.type.superschema()._default_dependencies.add(ValidConfigRef(ConfigRef(path), schema))

        new_dd = set()
        for ref in schema._default_dependencies:
            new_dd.add(validate_ref(ref, base_schema))
        schema._default_dependencies = new_dd

    return validate_refs_helper(base_schema)
