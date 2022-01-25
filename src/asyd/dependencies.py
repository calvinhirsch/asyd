from dataclasses import Field
from typing import Type, List, Dict, Tuple, Set, Union
from .config import Config, MultiConfig, ConfigRef, ValidConfigRef
from .exceptions import CyclicDependencyException
import inspect

# def print_deps(schema: Type[Config], tab: int = 0):
#     print(*[" "*tab], schema._default_dependencies)
#     for name, field in schema.__dataclass_fields__.items():
#         print(*[" "*tab], name, ":", _default_dependencies(field))
#         if inspect.isclass(field.type):
#             if issubclass(field.type, Config):
#                 print_deps(field.type)
#             elif issubclass(field.type, MultiConfig):
#                 for cls in field.type._options.values():
#                     print_deps(cls, tab=tab+3)

def generate_acyclic_traveral(schema: Type[Config]) -> List[str]:
    return traverse_all(schema, set(), "")[0]

def traverse_all(schema: Type[Config], visited: Set[str], path: str) -> Tuple[List[str], Set[str]]:
    order, v = dfs_deps(path[:-1], schema, visited)
    visited.update(v)

    for field in schema.__dataclass_fields__.values():
        if inspect.isclass(field.type):
            if issubclass(field.type, Config):
                o, v = traverse_all(field.type, visited, path + field.name + ".")
                order += o
                visited.update(v)
            else:
                if issubclass(field.type, MultiConfig):
                    for opt_cls in field.type._options.values():
                        if issubclass(opt_cls, Config):
                            ord, vis = traverse_all(opt_cls, visited, path + field.name + ".")
                            order += ord
                            visited.update(v)

    return order, visited

def dfs_deps(path: str, schema: Union[Type[Config], Type[MultiConfig]], visited_before: Set[str], visited_in_branch: Set[str] = set()) -> Tuple[List[str], Set[str]]:
    if path in visited_before:
        return ([], set())
    if path in visited_in_branch:
        raise CyclicDependencyException("Cycle detected in dependencies")

    if issubclass(schema, Config):
        deps = schema._default_dependencies
    elif issubclass(schema, MultiConfig):
        deps = schema.superschema()._default_dependencies.union(*[c._default_dependencies for c in schema._options.values()])

    if len(deps) < 1:
        return ([path], {path})

    visited = set()
    order = []

    for dep in deps:
        o, v = dfs_deps(dep.path, dep.schema, visited_before.union(visited), visited_in_branch.union({path}))
        visited.update(v)
        order += o

    order += [path]
    visited.add(path)
    return order, visited
