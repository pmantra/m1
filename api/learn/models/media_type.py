import enum


class MediaType(str, enum.Enum):
    ARTICLE = "article"
    COURSE = "course"
    ON_DEMAND_CLASS = "on_demand_class"
    VIDEO = "video"
