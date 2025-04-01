import abc
from typing import Any, Dict, List

from payer_accumulator.edi.constants import (
    DATA_ELEMENT_SEPARATOR,
    NEW_LINE_SEPARATOR,
    SEGMENT_TERMINATOR,
)
from utils.log import logger

log = logger(__name__)


class X12FileParser(abc.ABC):
    def __init__(self, edi_content: str):
        self.edi_content = edi_content
        self.segments = []
        self.component_element_separator: str = ""
        self.repetition_separator: str = ""
        self.parse_file()

    def parse_file(self) -> None:
        self.segments = (
            self.edi_content.replace(NEW_LINE_SEPARATOR, "")
            .strip()
            .split(SEGMENT_TERMINATOR)
        )

    def extract_segments(self) -> List[Dict[str, Any]]:
        parsed_segments = []
        for segment in self.segments:
            parts = segment.split(DATA_ELEMENT_SEPARATOR)
            segment_id = parts[0].strip()
            parsed_segments.append({"segment_id": segment_id, "elements": parts[1:]})
        return parsed_segments

    @abc.abstractmethod
    def get_data(self) -> Any:
        pass
