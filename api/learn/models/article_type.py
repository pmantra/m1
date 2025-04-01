import enum


class ArticleType(str, enum.Enum):
    HTML = "html"
    RICH_TEXT = "rich_text"

    def __str__(self) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # so that marshmallow uses the values
        return self.value
