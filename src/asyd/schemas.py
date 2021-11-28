from dataclasses import dataclass, field, Field
from typing import List, Dict, Generic, TypeVar, Type, Callable, Any, cast, ClassVar
from .schema_utils import MV, ABCMeta, abstract_attribute

class Schema:
    default_dependencies: ClassVar[List["SchemaRef"]] = []

class MultiSchema(metaclass=ABCMeta):
    options: ClassVar[Dict[str, Any]] = abstract_attribute() # TO-DO: Change Any
    selected: Schema = MV

    def select(self, val):
        if val in self.options:
            self.selected = self.options[val]()
        else:
            raise Exception("Selected option '{}' does not exist. Options are {}".format(val, self.options.keys()))

class SchemaRef:
    _base_schema = None

    def __init__(self, path, optional=False):
        self.optional = optional
        self.path = path
        self.return_type = None
        self.schema = None

    @classmethod
    def set_base_schema(self, val):
        if issubclass(val, Schema):
            self._base_schema = val
        else:
            raise Exception("Base schema for SchemaRef must be a subclass of Schema.")

    def validate(self):
        self.validate_path(self.path, self._base_schema)

    def validate_path(self, path, cls):
        p = self.path.split(".")
        next_p = p[1:] if len(p) > 1 else []

        if len(p) > 0:
            if issubclass(cls, MultiSchema):
                num_valid = 0
                for choice, choice_cls in MultiSchema.options.items():
                    if p[0] in choice_cls.__dataclass_fields__:
                        num_valid += 1
                        self.validate_path(next_p, choice_cls.__dataclass_fields__[p[0]].type)
                    else:
                        if not self.optional:
                            raise Exception("Reference to {} is not optional but is not valid when {} is {}. Pass optional=True to SchemaRef to make optional.".format(self.path, cls, choice))
                if num_valid < 1:
                    raise Exception("Reference to {} in MultiSchema {} not valid for any choice. (full path: {})".format(path, cls, self.path))
            elif issubclass(cls, Schema):
                if p[0] in cls.__dataclass_fields__:
                    self.validate_path(next_p, cls.__dataclass_fields__[p[0]].type)
            else:
                raise Exception("Path {} does not exist for type {}. (full path: {})".format(path, cls, self.path))
        else:
            if issubclass(cls, Schema):
                raise Exception("Path cannot end on a Schema, must end on a value or MultiSchema. ({})".format(self.path))
            else:
                rt = str if issubclass(cls, MultiSchema) else cls
                if self.return_type is None:
                    self.return_type = rt
                else:
                    if self.return_type != rt:
                        raise Exception("Value at path {} has different types depending on different MultiSchema choices: {} and {}.".format(self.path, self.return_type, rt))


def validate(schema):
    for ref in schema.default_dependencies:
        ref.validate()

    for field in schema.__dataclass_fields__.values():
        if issubclass(field.type, Schema):
            validate(field.type)
        if issubclass(field.type, MultiSchema):
            for cls in field.type.options.values():
                validate(cls)

def register(base_schema, directory):
    # Validate schema dependencies before parsing
    SchemaRef.set_base_schema(base_schema)
    validate(base_schema)

    # Ensure dependencies are not cyclic and create construction order
    # TO-DO
    construct_order = [
        ""
    ]

    # Construct config
    # TO-DO
