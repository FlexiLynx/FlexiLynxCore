#!/bin/python3

__all__ = ('Manifest', 'base', 'content', 'crypt', 'exceptions', 'file', 'parts', 'upstream',
           'BareContentManifest', 'ContentManifest')

#> Package
from .base import Manifest
from . import base
from . import content
from . import crypt
from . import exceptions
from . import file
from . import parts
from . import upstream
#</Package

#> Header >/
BareContentManifest = base.ManifestType('BareContentManifest',
    content=parts.ContentManifestPart)
ContentManifest = base.ManifestType('ContentManifest', BareContentManifest,
    metadata=parts.MetadataManifestPart,
    cascade=parts.extended.KeyCascadePart)
