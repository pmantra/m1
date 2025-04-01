import dataclasses


@dataclasses.dataclass
class CTA:
    __slots__ = ("text", "url")
    text: str
    url: str
