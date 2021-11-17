"""Base Stream type which declares more powerful properties."""

from typing import Any, Callable, Optional
from jsonpath_ng.ext import parse as jsonpath_parse

from singer_sdk import typing as th  # JSON Schema typing helpers
from singer_sdk.streams.rest import RESTStream


class Property(th.Property):
    def __init__(
        self,
        name: str,
        type: Any,
        jsonpath_selector: str = None,
        cast: Callable[[Any], Any] = lambda x: x,
        **kwargs,
    ) -> None:
        super().__init__(name, type, **kwargs)
        self.jsonpath_selector = jsonpath_selector or f'$["{name}"]'
        self._selector = jsonpath_parse(self.jsonpath_selector)
        self.cast = cast

    def read_value(self, row: dict) -> Optional[Any]:
        # can't use _helpers.extract_jsonpath as we want to use jsonpath_ng.ext
        # to get filter support
        if isinstance(self.wrapped, th.ObjectType):
            return {p.name: p.read_value(row) for p in self.wrapped.wrapped}

        value = self._selector.find(row)
        if isinstance(self.wrapped, th.ArrayType):
            return [self.cast(v.value) for v in value]
        try:
            return self.cast(value[0].value)
        except IndexError as e:
            raise Exception(
                f"Unable to find property '{self.name}' ",
                f"at jsonpath '{self.jsonpath_selector}'.",
            ) from e


class PropertiesList(th.PropertiesList):
    def __init__(self, *properties: Property) -> None:
        super().__init__(*properties)


class PropertyStream(RESTStream):

    properties: PropertiesList = None
    records_jsonpath: str = "$[*]"

    @property
    def schema(self) -> dict:
        return self.properties.to_dict()

    def post_process(self, row: dict, context: Optional[dict]) -> dict:
        return {k: p.read_value(row) for k, p in self.properties.items()}
