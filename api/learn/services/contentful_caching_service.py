# a bit more opinionated version of CachingService - use as desired. works well for simple caching and invalidating
# for a single Contentful entry. could maybe be made more generic if needed in the future.
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, TypeVar

from learn.services import caching_service, contentful
from utils import log

T = TypeVar("T")

log = log.logger(__name__)

TTL = 182 * 24 * 60 * 60


class ContentfulCachingService(caching_service.CachingService, Generic[T], ABC):
    def __init__(self, preview: bool = False, user_facing: bool = True):
        super().__init__()
        self.preview = preview
        self.contentful_client = contentful.LibraryContentfulClient(
            preview=preview, user_facing=user_facing
        )

    def get_value(self, identifier_value: str, **kwargs) -> Optional[T]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return self.get_values([identifier_value], **kwargs).get(identifier_value)

    def get_values(self, identifier_values: List[str], **kwargs) -> Dict[str, T]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        # important note: this only works if ALL identifier values correspond to the same kwargs. i.e. you can't
        # query for multiple combinations of identifier value/kwargs within the same call to `get_values`
        # for example:
        # you can query with identifier_values=["my-slug", "my-other-slug"], locale="en-US" and this will (attempt to)
        # return the en-US locale for BOTH slugs
        # you can NOT query with a separate locale for each slug within the same call to `get_values`. you need to make
        # one call per locale
        values = {}
        if not self.preview:
            values = self._get_values_from_cache(identifier_values, **kwargs)
        missing_identifier_values = [
            identifier_value
            for identifier_value in identifier_values
            if identifier_value not in values
        ]
        if missing_identifier_values:
            try:
                values_from_contentful = self._get_values_from_contentful(
                    missing_identifier_values, **kwargs
                )
                values = {**values, **values_from_contentful}

                missing_identifier_values = [
                    identifier_value
                    for identifier_value in identifier_values
                    if identifier_value not in values
                ]
                for identifier_value in missing_identifier_values:
                    log.warn(  # type: ignore[attr-defined] # Module has no attribute "warn"
                        "Value not found on Contentful or in cache",
                        identifier_value=identifier_value,
                    )

                if not self.preview:
                    self.try_to_save_values_in_cache(values_from_contentful, **kwargs)
            except Exception as e:
                log.exception(  # type: ignore[attr-defined] # Module has no attribute "exception"
                    "Error fetching value from Contentful",
                    error=e,
                    missing_identifier_values=missing_identifier_values,
                    class_name=self.__class__.__name__,
                )

        return values

    def save_value_in_cache(self, identifier_value: str, value: T, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if self.redis_client:
            key = self._get_cache_key(identifier_value, **kwargs)
            self.redis_client.set(key, self._serialize_value(value), ex=TTL)
        else:
            raise RuntimeError(
                "Unable to save value in cache. Redis client has not been initialized."
            )

    def remove_value_from_cache(self, entry_id: str) -> None:
        # can't use the other client here because the client parameters are different.
        contentful_client = contentful.LibraryContentfulClient(
            preview=True, user_facing=False
        )
        entry = contentful_client.get_entry_by_id(entry_id)
        self.redis_client.delete(self._get_cache_key(entry.slug))  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "delete"

    def remove_keys_from_cache_by_pattern(self, key_pattern: str) -> None:
        if self.redis_client:
            keys = self.redis_client.keys(key_pattern)
            if keys:
                pipeline = self.redis_client.pipeline()
                for key in keys:
                    pipeline.delete(key)
                pipeline.execute()

    def try_to_save_values_in_cache(self, values_by_identifier: Dict[str, T], **kwargs):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if self.redis_client:
            try:
                pipeline = self.redis_client.pipeline()
                for identifier_value, value in values_by_identifier.items():
                    key = self._get_cache_key(identifier_value, **kwargs)
                    pipeline.set(key, self._serialize_value(value), ex=TTL)
                pipeline.execute()
            except Exception as e:
                log.exception(  # type: ignore[attr-defined] # Module has no attribute "exception"
                    "Error saving values in cache",
                    error=e,
                    values_by_identifier=values_by_identifier,
                    class_name=self.__class__.__name__,
                )

    def _get_values_from_cache(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, identifier_values: List[str], **kwargs
    ) -> Dict[str, T]:
        result: Dict[str, T] = {}
        if self.redis_client:
            pipeline = self.redis_client.pipeline()
            for identifier_value in identifier_values:
                pipeline.get(self._get_cache_key(identifier_value, **kwargs))
            try:
                value_strs = pipeline.execute()

                for index, identifier_value in enumerate(identifier_values):
                    value_str = value_strs[index]
                    if value_str is not None:
                        value = self.__try_to_deserialize_value(
                            value_str, self._get_cache_key(identifier_value, **kwargs)
                        )
                        if value is not None:
                            result[identifier_value] = value
            except Exception as e:
                log.exception(  # type: ignore[attr-defined] # Module has no attribute "exception"
                    "Error fetching value from redis",
                    error=e,
                    class_name=self.__class__.__name__,
                )
        return result

    @abstractmethod
    def _get_values_from_contentful(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, identifier_values: List[str], **kwargs
    ) -> Dict[str, T]:
        """To be overridden by subclass"""

    @abstractmethod
    def _get_cache_key(self, identifier_value: str, **kwargs: Any) -> str:
        """To be overridden by subclass"""

    @staticmethod
    @abstractmethod
    def _serialize_value(value: T) -> str:
        """To be overridden by subclass"""

    @staticmethod
    @abstractmethod
    def _deserialize_value(value_str: str) -> T:
        """To be overridden by subclass"""

    def __try_to_deserialize_value(self, value_str: str, key: str) -> Optional[T]:
        try:
            return self._deserialize_value(value_str)
        except Exception as e:
            log.warn(  # type: ignore[attr-defined] # Module has no attribute "warn"
                "Error deserializing value from redis. This likely means the code model has changed "
                "since the value was cached. Removing the cache entry.",
                error=e,
                key=key,
                value_str=value_str,
                class_name=self.__class__.__name__,
                exc_info=True,
            )
            self.redis_client.delete(key)  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "delete"
            return None
