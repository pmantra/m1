from dataclasses import dataclass


@dataclass
class ProviderLanguagesServiceResponse:
    id: int
    name: str


@dataclass
class ProviderLanguagesClientResponseElement:
    id: int
    display_name: str


@dataclass
class ProvidersLanguagesClientResponseStruct:
    data: list[ProviderLanguagesServiceResponse]
