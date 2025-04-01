import dataclasses
from typing import Dict, List


@dataclasses.dataclass
class ArticleEntry:
    __slots__ = ("title", "rich_text", "rich_text_includes", "id")
    title: str
    rich_text: Dict
    rich_text_includes: List[Dict]
    id: str
