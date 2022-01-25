# ASYD

If you have a config structure (configs with nested configs), you should have a
folder structure mirroring this. Each config can then have its own defaults.yaml
that lists defaults for the config's parameters (but not for nested configs).
For example:

```
@dataclass
class NestedConfig(Config):
    some_nested_field: int = MV

@dataclass
class BaseConfig(Config):
    some_field: str = MV
    nested_config: NestedConfig = NestedConfig()
```
... would have the following folder structure:

config/
  defaults.yaml
  nested_config/
    defaults.yaml


You may notice a value of "MV" applied to many parameters. This stands for
"Missing Value" and allows defaults to be defined in the folder structure
instead. Schema-level defaults can also be specified directly in their declarations
(in other words, in the python code declaring the dataclass).

Now, the main benefit of using ASYD is that these defaults.yaml files can have
queries in them to any other part of your configuration. Consider the following
example where the default value for a parameter in nested_config_a relies on the
value of a parameter in nested_config_b:

```
@dataclass
class NestedConfigA(Config):
    field_a: int = MV

@dataclass
class NestedConfigB(Config):
    field_b: int = MV
    _default_dependencies = { ConfigRef{"nested_config_a"} }

@dataclass
class BaseConfig(Config):
    some_field: str = MV
    nested_config_a: NestedConfigA = NestedConfigA()
    nested_config_b: NestedConfigB = NestedConfigB()
```

config/
  nested_config_a/
  nested_config_b/
    defaults.yaml/

nested_config_b/defaults.yaml:
```
?nested_config_a.field_a:
  >50:
    field_b: 51
  <50:
    field_b: 49
  =50:
    field_b: 50
```

Queries add structure to the defaults.yaml files. A query starts by identifying
a target value (in this case, nested_config_a.field_a) which should follow a
question mark (?). Then, nested in this yaml block, should be one or more query
operations (>50, <50, =50) using query operators (>, <, =). Each query should
be two nested layers. However, queries can be nested as desired.

You can always do this under two conditions:
  1. All accessed config objects are added to the _default_dependencies set in
     the schema with a ConfigRef. (in the example, ```_default_dependencies =
     { ConfigRef{"nested_config_a"} }```)
  2. There are no circular dependencies. (Note: Referencing a nested config does
     not necessarily require that the parent config be built already. This means
     that, in this example, the default for some_field could depend on field_a
     or field_b; but field_a cannot depend on field_b if field_b already depends
     on field_a)

You can include a defaults folder instead of or in addition to a defaults.yaml
that works exactly the same way as defaults.yaml where query structure can be
specified either in folder names and file names or in nested defaults.yaml files.
The last example could look like:

config/
  nested_config_a/
  nested_config_b/
    defaults/
      ?nested_config_a.field_a/
        \>50.yaml  # contains "field_b: 51"
        \<50.yaml  # contains "field_b: 49"
        =50.yaml  # contains "field_b: 50"

... and if nested_config_a had a second parameter field_a2 ...
config/
  nested_config_a/
  nested_config_b/
    defaults/
      ?nested_config_a.field_a/
        \>50/
          ?nested_config_a.field_a2/
            \>0.yaml  # contains field_b: 52
            \<=0.yaml  # contains field_b: 51
        \<50/
          ?nested_config_a.field_a2/
            \>0.yaml  # contains field_b: 49
            \<=0.yaml  # contains field_b: 48
        =50.yaml  # contains "field_b: 49"



MultiConfigs:

```
@dataclass
class NestedConfig(Config):
    some_nested_field: int = MV

class NestedMultiConfig(MultiConfig):
    _options = {
        "first": ConfigA,
        "second": ConfigA,
        "third": ConfigB
    }
@dataclass
class ConfigA(Config):
    some_field_a: int = MV
@dataclass
class ConfigB(Config):
    some_field_b: str = MV

@dataclass
class BaseConfig(Config):
    some_field: str = MV
    nested_config: NestedConfig = NestedConfig()
    nested_multi_config: MultiConfig = NestedMultiConfig()
```

config/
  defaults.yaml
  nested_config/
    defaults.yaml
  nested_multi_config/
    first/
      defaults.yaml
    second/
      defaults.yaml
    third/
      defaults.yaml
