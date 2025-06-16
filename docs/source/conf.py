import os
import sys
sys.path.insert(0, os.path.abspath('../../mediso_packages'))  # Adds my_project/ to path

project = 'MPython'
copyright = '2025, Mediso'
author = 'Mediso Ltd.'
release = '1.0.0.'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',  # For Google and NumPy-style docstrings
    'sphinx.ext.viewcode',
    # 'm2r',
    'sphinx_rtd_dark_mode',
    # 'sphinxcontrib.plantuml',
    # 'sphinxcontrib.datatemplates',
    # 'sphinxcontrib.drawio'
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
