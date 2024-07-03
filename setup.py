from setuptools import setup, find_packages

setup(
    name='pyjamaz',
    version='0.1.0',
    description='Python JAM implementation',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='JAMdot Technologies',
    author_email='info@jamdot.tech',
    url='https://github.com/JAMdotTech/pyjamaz',
    packages=find_packages(),
    install_requires=[
        'click~=8.1',
        'py-ed25519-zebra-bindings>=1.0,<2',
        'pycryptodome>=3.11.0,<4',
        'py-bip39-bindings>=0.1.9,<1'
    ],
    dependency_links=[
        'git+https://github.com/polkascan/py-scale-codec@az-v2#egg=scalecodec'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'pyjamaz = client.cli:main',
        ],
    },
)
