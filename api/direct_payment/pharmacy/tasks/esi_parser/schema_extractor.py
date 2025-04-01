from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class FixedWidthSchema:
    __slots__ = ("name", "start", "length", "data_type")
    name: str
    start: int
    length: int
    data_type: str


@dataclass
class Column:
    normalized: str
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.normalized


class SchemaExtractor:
    """
    Extracts column, start, and length columns from schema rows. Once
    instantiated, each time the instance is called with a row, a
    ``(column,start,length)`` tuple will be returned based on values in that
    row and the constructor kwargs.
    """

    DEFAULT_COLUMNS = [
        Column(normalized="column"),
        Column(normalized="start"),
        Column(normalized="length"),
        Column(normalized="data_type"),
    ]

    start = None
    length = None
    column = None
    data_type = None
    one_based = None

    def __init__(self, header, columns: List[Column] = None, one_based: bool = True):  # type: ignore[no-untyped-def,assignment] # Function is missing a type annotation for one or more arguments #type: ignore[assignment] # Incompatible default for argument "columns" (default has type "None", argument has type "List[Column]")
        """
        Constructs a schema row extractor.
        """
        self.one_based = one_based
        column_list = columns or self.DEFAULT_COLUMNS
        for column in column_list:
            try:
                setattr(self, column.normalized, header.index(column.name))
            except ValueError:
                raise ValueError(
                    f'A column named "{column.name}" must exist in the schema file.'
                )
        self._validate()

    def _validate(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        for col in self.DEFAULT_COLUMNS:
            if getattr(self, col.normalized) is None:
                raise ValueError(
                    f"Column {col.normalized} must be provided to proper initialize schema decoder"
                )

    def __call__(self, row) -> FixedWidthSchema:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """
        Return a tuple (column, start, length, data_type) based on this instance's
        parameters. If the first time this is called, the row's 'start'
        value is 1, then all 'start' values including the first will be one
        less than in the actual input data, to adjust for one-based
        specifications.  Values for 'start' and 'length' will be cast to
        integers.
        """
        if self.one_based is None:
            self.one_based = int(row[self.start]) == 1

        if self.one_based:
            adjusted_start = int(row[self.start]) - 1
        else:
            adjusted_start = int(row[self.start])

        return FixedWidthSchema(
            str(row[self.column].strip()),
            adjusted_start,
            int(row[self.length]),
            str(row[self.data_type].strip()),
        )
