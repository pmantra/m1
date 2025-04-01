import dataclasses


@dataclasses.dataclass(frozen=True)
class Pagination:
    current_page: int
    total_pages: int
    page_size: int
    has_previous: bool
    has_next: bool
