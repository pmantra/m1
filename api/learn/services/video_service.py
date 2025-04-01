import dataclasses
import json
from typing import Any, Dict, List

from learn.models.video import Video
from learn.services import contentful_caching_service


class VideoService(contentful_caching_service.ContentfulCachingService[Video]):
    def _get_cache_key(self, identifier_value: str, **kwargs: Any) -> str:
        return f"video:{identifier_value}"

    @staticmethod
    def _serialize_value(value: Video) -> str:
        return json.dumps(dataclasses.asdict(value))

    @staticmethod
    def _deserialize_value(value_str: str) -> Video:
        video_dict = json.loads(value_str)
        return Video.from_dict(video_dict)

    def _get_values_from_contentful(
        self, identifier_values: List[str], **kwargs: Any
    ) -> Dict[str, Video]:
        video_entries = self.contentful_client.get_video_entries_by_slugs(
            slugs=identifier_values
        )
        dict_of_videos = {
            video.slug: Video.from_contentful_entry(video) for video in video_entries
        }
        return dict_of_videos
