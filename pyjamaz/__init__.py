import os

if os.getenv('GITHUB_REF'):
    if not os.getenv('GITHUB_REF').startswith('refs/tags/v'):
        raise ValueError('Incorrect tag format {}'.format(os.getenv('GITHUB_REF')))
    __version__ = os.getenv('GITHUB_REF').replace('refs/tags/v', '')
else:
    __version__ = '0.0.0'
