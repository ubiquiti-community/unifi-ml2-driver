# -*- coding: utf-8 -*-
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys

sys.path.insert(0, os.path.abspath('../..'))
# -- General configuration ----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinxcontrib.apidoc',
    'openstackdocstheme'
]

# openstackdocstheme options
openstackdocs_repo_name = 'ubiquity-community/unifi-ml2-driver'
openstackdocs_pdf_link = True
openstackdocs_use_storyboard = False

# autodoc generation is a bit aggressive and a nuisance when doing heavy
# text edit cycles.
# execute "export SPHINX_DEBUG=1" in your terminal to disable

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
copyright = '2025, Ubiquity Community'

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'native'

# -- Options for HTML output --------------------------------------------------

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
# html_theme_path = ["."]
# html_static_path = ['static']

html_theme = 'openstackdocs'

# Output file base name for HTML help builder.
htmlhelp_basename = 'unifi-ml2-driverdoc'

latex_use_xindy = False

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto/manual]).
latex_documents = [
    ('index',
     'doc-unifi-ml2-driver.tex',
     'UniFi ML2 Driver Documentation',
     'Ubiquity Community', 'manual'),
]

# Example configuration for intersphinx: refer to the Python standard library.
#intersphinx_mapping = {'http://docs.python.org/': None}

# -- sphinxcontrib.apidoc configuration --------------------------------------

apidoc_module_dir = '../../unifi_ml2_driver'
apidoc_output_dir = 'contributor/api'
apidoc_excluded_paths = [
    'tests',
]
