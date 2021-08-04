import builtins
import datetime
import json
import dataclasses
import uuid
from typing import Optional

import jsonschema as jsonschema


@dataclasses.dataclass(frozen=True)
class Configuration:
    discriminator_field: Optional[str] = None

    def with_discriminator(self, field_name: str) -> 'Configuration':
        data = dataclasses.asdict(self)
        data['discriminator_field'] = field_name
        return Configuration(**data)


default = Configuration()


_FIELDS = "__codec_params__"


# A sentinel object to detect if a parameter is supplied or not.  Use
# a class to give it a better repr.
class _MISSING_TYPE:
    pass


MISSING = _MISSING_TYPE()


def _create_fn(name, args, body, *, doc=None, locals=None, globals=None, return_type: type = MISSING):
    if locals is None:
        locals = {}

    if 'BUILTINS' not in locals:
        locals['BUILTINS'] = builtins

    return_annotation = ''
    if return_type is not MISSING:
        locals['_return_type'] = return_type
        return_annotation = ' -> _return_type'

    args = ','.join(args)
    body = '\n'.join(f'  {b}' for b in body)

    # Compute the text of the entire function.
    txt = f' def {name}({args}){return_annotation}:\n{body}'
    local_vars = ', '.join(locals.keys())
    txt = f"def __create_fn__({local_vars}):\n{txt}\n return {name}"

    # Evaluate it and create the function.
    ns = {}
    exec(txt, globals, ns)
    f = ns['__create_fn__'](**locals)
    if doc:
        f.__doc__ = doc
    return f


def _mk_property_schema(field: dataclasses.Field):
    if field.type == int:
        return '''{"type": "integer"}'''
    elif field.type == bool:
        return '''{"type": "boolean"}'''
    elif field.type == str:
        return '''{"type": "string"}'''
    elif field.type == float:
        return '''{"type": "number"}'''
    elif field.type == uuid.UUID:
        return '''{"type": "string", "format": "uuid"}'''
    elif field.type == datetime.datetime:
        return '''{"type": "string", "format": "date-time"}'''
    elif field.type == datetime.date:
        return '''{"type": "string", "format": "full-date"}'''
    else:
        raise TypeError(f"Field {field.name} has unknown type: {field.type}")


def _field_value(field: dataclasses.Field):
    field_name = field.name
    if field.type == int:
        return f"int(self.{field_name})"
    elif field.type == str:
        return f"str(self.{field_name})"
    elif field.type == bool:
        return f"str(self.{field_name}).lower()"
    elif field.type == float:
        return f"float(self.{field_name})"
    elif field.type == uuid.UUID:
        return f"str(self.{field_name})"
    elif field.type == datetime.datetime:
        if 'json_codec' in field.metadata:
            format = field.metadata['json_codec']['strftime']
            return f"self.{field_name}.strftime('{format}')"
        else:
            return f"self.{field_name}.isoformat()"
    else:
        return f"self.{field_name}"


def _mk_schema(config: Configuration, klass: type, fields: list[dataclasses.Field]):
    locals = {}
    doc = ["The JSON schema for this data type."]
    body_lines = [
        '''result = {"type":"object", "properties": {}, "required": []}'''
    ]

    if config.discriminator_field:
        body_lines += [
            '''subtype_discriminators = [klass.__name__ for klass in cls.__subclasses__()]''',
            f'''result['properties']['{config.discriminator_field}'] = '''
            '''{"type": "string"}''',
            '''if subtype_discriminators:''',
            f'''  result['properties']['{config.discriminator_field}']['enum'] = subtype_discriminators'''
        ]

    for field in fields:
        property_name = field.name
        property_schema = _mk_property_schema(field)
        body_lines.append(
            f'''result['properties']['{property_name}'] = {property_schema}'''
        )
        if field.default == dataclasses.MISSING and field.default_factory == dataclasses.MISSING:
            body_lines.append(
                f'''result['required'].append('{property_name}')'''
            )

    body_lines.append("return result")
    return classmethod(_create_fn(
        'json_schema',
        ['cls'],
        body_lines,
        locals=locals,
        return_type=dict,
        doc="\n".join(doc)
    ))


def _mk_to_json(config: Configuration, fields: list[dataclasses.Field]):
    locals = {}
    body_lines = [
        "result = {}"
    ]

    doc = ["Generate a JSON-like dictionary representation of this object."]

    if config.discriminator_field:
        body_lines.append(
            f"result['{config.discriminator_field}'] = type(self).__name__"
        )

    for field in fields:
        field_name = field.name
        field_value = _field_value(field)
        body_lines.append(f"result['{field_name}'] = {field_value}")

    body_lines.append("return result")
    return _create_fn('to_json', ["self"], body_lines, locals=locals, return_type=dict, doc="\n".join(doc))


def _parse_value(field: dataclasses.Field, expr: str):
    """Wrap expr in logic to parse the value."""
    if field.type == str:
        return f'''str({expr})'''
    elif field.type == int:
        return f'''int({expr})'''
    elif field.type == float:
        return f'''float({expr})'''
    elif field.type == uuid.UUID:
        return f'''uuid.UUID(hex={expr})'''
    elif field.type == datetime.datetime:
        if 'json_codec' in field.metadata:
            format = field.metadata['json_codec']['strptime']
            return f'''datetime.datetime.strptime({expr}, '{format}')'''
        else:
            return f'''datetime.datetime.fromisoformat({expr})'''
    else:
        return expr


def _mk_from_json(cls, config: Configuration, fields: list[dataclasses.Field]):
    locals = {
        'jsonschema': jsonschema,
        'uuid': uuid
    }
    doc = ["Parse dictionary of JSON data."]
    body_lines = [
        '''jsonschema.validate(data, cls.json_schema())''',
        '''kwargs = {}''',
    ]

    if config.discriminator_field:
        body_lines += [
             '''subtype_discriminators = [klass.__name__ for klass in cls.__subclasses__()]''',
             '''if subtype_discriminators:''',
             '''  for klass in cls.__subclasses__():''',
            f'''    if klass.__name__ == data['{config.discriminator_field}']:''',
             '''      return klass.from_json(data)'''
        ]

    # Build [code to build] a dictionary of constructor arguments.
    for field in fields:
        field_name = field.name
        property_name = field.name
        value = _parse_value(field, expr=f'''data['{field_name}']''')
        if field.default == dataclasses.MISSING and field.default_factory == MISSING:
            body_lines.append(f'''kwargs['{property_name}'] = {value}''')
        else:
            body_lines += [
                f'''if '{field_name}' in data:''',
                f'''  kwargs['{property_name}'] = {value}'''
            ]

    # Call the constructor with those arguments.
    body_lines.append(f'''return cls(**kwargs)''')

    return classmethod(_create_fn('from_json', ['cls', 'data'], body_lines, return_type=cls, locals=locals, doc="\n".join(doc)))


def _mk_to_jsons(config: Configuration, fields: list[dataclasses.Field]):
    locals = {"json": json}
    doc = ["Generate a JSON string representation of this object."]
    body_lines = [
        "return json.dumps(self.to_json())"
    ]
    return _create_fn('to_jsons', ["self"], body_lines, locals=locals, return_type=str, doc="\n".join(doc))


class JsonCodec:
    """Extend the wrapped class with JSON codec methods."""

    def _process_class(self, cls, config: Configuration):
        if not dataclasses.is_dataclass(cls):
            raise TypeError("codec() should be called on dataclass instances")

        fs = dataclasses.fields(cls)

        setattr(cls, 'json_schema', _mk_schema(config=config, klass=cls, fields=fs))
        setattr(cls, 'to_json', _mk_to_json(config=config, fields=fs))
        setattr(cls, 'to_jsons', _mk_to_jsons(config=config, fields=fs))
        setattr(cls, 'from_json', _mk_from_json(cls, config=config, fields=fs))

        return cls

    def __call__(self, cls=None, /, *, config=default):
        """Process a class or return the decorator function to do so."""

        def wrap(cls):
            return self._process_class(config=config, cls=cls)

        if cls is None:
            return wrap

        return wrap(cls)

    @staticmethod
    def datetime(format: str):
        """"""
        return {
            'json_codec': {'type': 'string', 'strptime': format, 'strftime': format}
        }


codec = JsonCodec()
