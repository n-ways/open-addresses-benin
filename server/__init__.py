"""N-Ways Addressing for Benin: the registry server.

A small HTTP service that serves the published registry (registry/) from a
SQLite database and, where a deployment is designated as the issuer, issues
new codes by the same rules as the N-Ways issuer. Python 3.9+ standard library
only; the address logic comes from the reference engine (engine/reference/).
"""
import os

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SERVER_DIR)

COUNTRY = 'BJ'
COUNTRY_NAME = 'Benin'
CREDIT = 'N-Ways Addressing for Benin, © N-WAYS LIMITED (nways.ng)'
CREDIT_URL = 'https://github.com/n-ways/open-addresses-benin'
SPEC = 'engine/SPEC.md 1.0'
LICENCES = {
    'data': 'ODbL 1.0 (LICENSE-DATA)',
    'code': 'Apache License 2.0 (LICENSE, NOTICE)',
    'documents': 'CC BY 4.0 (LICENSE-DOCS)',
}
