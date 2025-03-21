import os

if os.getenv('GITHUB_REF') and os.getenv('GITHUB_REF').startswith('refs/tags/v'):
    __version__ = os.getenv('GITHUB_REF').replace('refs/tags/v', '')
else:
    __version__ = '0.0.0'
