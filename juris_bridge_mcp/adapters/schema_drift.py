"""The error an adapter raises when a Source's answer no longer has the shape it maps."""


class SchemaDrift(Exception):  # noqa: N818 - names the situation, not an error class
    """The upstream document no longer matches the shape this adapter expects."""
