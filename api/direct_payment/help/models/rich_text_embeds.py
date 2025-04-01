import dataclasses
import enum
from typing import List, Optional

from direct_payment.help.models.image import Image


class EmbeddedEntryType(str, enum.Enum):
    ACCORDION = "accordion"
    EMBEDDED_IMAGE = "embeddedImage"


@dataclasses.dataclass
class EmbeddedItem:
    id: str
    entry_type = EmbeddedEntryType


@dataclasses.dataclass
class AccordionItem:
    __slots__ = ("title", "rich_text")
    title: str
    rich_text: str


@dataclasses.dataclass
class Accordion(EmbeddedItem):
    entry_type = EmbeddedEntryType.ACCORDION.value  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "EmbeddedItem" defined the type as "Type[EmbeddedEntryType]")
    heading_level: str
    items: List[AccordionItem]


@dataclasses.dataclass
class EmbeddedImage(EmbeddedItem):
    entry_type = EmbeddedEntryType.EMBEDDED_IMAGE.value  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "EmbeddedItem" defined the type as "Type[EmbeddedEntryType]")
    image: Image
    caption: Optional[str] = None
