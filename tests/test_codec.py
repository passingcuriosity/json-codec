import json
from dataclasses import dataclass, field
from datetime import datetime

from json_codec import codec, Configuration


def test_codec():
    example = Configuration().with_discriminator(field_name="type")

    @codec(config=example)
    @dataclass
    class Example:
        an_int: int
        a_str: str = field(default="hello")
        created: datetime = field(default_factory=datetime.now)

    obj = Example(an_int=12, a_str="world")
    assert isinstance(obj, Example)

    json_string = obj.to_jsons()
    json_data = json.loads(json_string)
    obj2 = Example.from_json(json_data)

    assert obj2 == obj
