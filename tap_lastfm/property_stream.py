"""Base Stream type which declares more powerful properties."""

from typing import Any, Callable, Generic, List, Optional, Tuple, Type, Union, cast
from xmlrpc.client import Boolean

from jsonpath_ng.ext import parse as jsonpath_parse
from singer_sdk import typing as th  # JSON Schema typing helpers
from singer_sdk.streams.rest import RESTStream


class Property(th.Property, Generic[th.W]):
    """Wrapper for `th.Property` which adds declarative transformations."""

    def __init__(
        self,
        name: str,
        wrapped: Union[th.W, Type[th.W]],
        jsonpath_selector: str = None,
        cast: Callable[[Any], Any] = lambda x: x,
        ignore_missing: Boolean = False,
        **kwargs,
    ) -> None:
        """Construct a new Property.

        Args:
        ----
            name: Property name.
            wrapped: JSON Schema type of the property.
            jsonpath_selector: A path to read the property from. Defaults to the
                name of the property.
            cast: A lambda or method to convert the json value to the expected
                type. Defaults to a no-op.
            ignore_missing: If the property is not included in the data, ignore it
                and set to `None`. Defaults to `False`.
            kwargs: The rest of the arguments are consistent with the parent class.

        """
        super().__init__(name, wrapped, **kwargs)
        self.jsonpath_selector = jsonpath_selector or f'$["{name}"]'
        self._selector = jsonpath_parse(self.jsonpath_selector)
        self.cast = cast
        self.ignore_missing = ignore_missing

    def read_value(self, row: dict) -> Optional[Any]:
        """Read and cast the value from the row.

        Args:
            row: the raw data from the source.

        Returns
        -------
            The extracted and casted value of the property.

        Raises
        ------
            Exception if the property does not exist.

        """
        # can't use _helpers.extract_jsonpath as we want to use jsonpath_ng.ext
        # to get filter support
        if isinstance(self.wrapped, th.ObjectType):
            props = cast(List[Property], self.wrapped.wrapped)
            return {p.name: p.read_value(row) for p in props}

        value = self._selector.find(row)
        if isinstance(self.wrapped, th.ArrayType):
            return [self.cast(v.value) for v in value]
        try:
            return self.cast(value[0].value)
        except IndexError as e:
            if self.ignore_missing:
                return None
            raise Exception(
                f"Unable to find property '{self.name}' ",
                f"at jsonpath '{self.jsonpath_selector}'.",
            ) from e


class PropertyStream(RESTStream):
    """A stream which can automatically remap properties.

    Assumes all properties in `properties` are `Property`
    (the type above which supports additional declarations).
    """

    properties: th.PropertiesList
    records_jsonpath: str = "$[*]"

    @property
    def schema(self) -> dict:
        """Get schema.

        Returns
        -------
            JSON Schema dictionary for this stream.

        """
        return self.properties.to_dict()

    def post_process(self, row: dict, context: Optional[dict] = None) -> Optional[dict]:
        """Remap and cast properties by jsonpath."""
        props = cast(List[Tuple[str, Property]], self.properties.items())
        return {k: p.read_value(row) for k, p in props}
