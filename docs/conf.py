# Configuration file for the Sphinx documentation builder.

project = "AIPPT"
copyright = "2026"
author = "Matt"

import os, sys
sys.path.insert(0, os.path.abspath(".."))
from aippt import __version__
version = __version__
release = __version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx_rtd_theme",
    "myst_parser",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

html_theme = "sphinx_rtd_theme"

# Only top-level docs/*.md pages (e.g. sharepoint-setup) are part of the
# toctree. Working notes under superpowers/ and use-cases/ are excluded
# wholesale so they don't bloat the build or trigger orphan warnings.
exclude_patterns = ["_build", "plans", "superpowers", "use-cases"]
