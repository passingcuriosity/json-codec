import uuid

from dataclasses import dataclass, field
from datetime import datetime

from json_codec import Configuration, codec


example = Configuration()\
    .with_discriminator(field_name="type")


@codec(config=example)
@dataclass
class Example:
    id: int
    version: uuid.UUID
    created: datetime


@codec(config=example)
@dataclass
class Another(Example):
    name: str


obj1 = Another(id=1, version=uuid.uuid4(), created=datetime.now(), name="thsutton")

obj1_json = obj1.to_json()

print(obj1_json)

obj2 = Example.from_json(obj1_json)

print(obj1)
print(obj2)

print("Round trip successful" if obj1 == obj2 else "Boo")

