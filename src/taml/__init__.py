from ruamel.yaml import *  # pyright: ignore[reportWildcardImportFromLibrary] # noqa: F403
from .version import __version__ as __version__  # pylint: disable=useless-import-alias

from .main import TAML, taml  # noqa: F401

__all__ = ['taml']
