Python JSON
===========

This is a small library to implement JSON codecs for Python dataclasses.

There are _n_ goals:

1. Provide a simple, consistent interface to JSON de-/serialisation of 
   dataclasses.

2. Eliminate as much boilerplate code as possible when defining and using
   classes.

3. Making safety the default, with validation and type enforcement by default.

4. Support standard approaches to encoding algebraic data types. 

Examples
--------

```
import json

from dataclasses import dataclass, field
from datetime import datetime
from json_codec import codec, default


@codec(config=default)
@dataclass(frozen=True)
class Example:
  name: str
  age: int = field(default=99)
  created: datetime = field(default_factory=datetime.utcnow, metadata=codec.datetime(format="XXX%Y-%m-%dYYY%H:%M:%S.%fZZZ"))
  
obj1 = Example.from_json({'name': "thsutton"})

obj2 = Example.from_json(json.loads(obj1.to_jsons()))

assert obj1 == obj2
```