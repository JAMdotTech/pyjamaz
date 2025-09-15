"""
Setup script for building Numba AOT compiled modules.
Run with: python setup.py build_ext --inplace
"""

from setuptools import setup, Extension
from numba.pycc import CC
import numpy as np
import os

# Get numpy include directory
numpy_include = np.get_include()

# Build configurations
extra_compile_args = []
extra_link_args = []

# Platform-specific flags
import platform
if platform.system() == 'Darwin':  # macOS
    extra_compile_args = ['-O3', '-march=native']
elif platform.system() == 'Linux':
    extra_compile_args = ['-O3', '-march=native', '-ffast-math']
elif platform.system() == 'Windows':
    extra_compile_args = ['/O2']

def build_aot_modules():
    """Build all AOT modules using numba.pycc"""
    modules = ['pvm_numba_aot.py', 'pvm_numba_aot2.py']
    
    for module in modules:
        if os.path.exists(module):
            print(f"Building {module}...")
            os.system(f"python {module}")
        else:
            print(f"Warning: {module} not found")

# Custom command to build AOT modules
from setuptools import Command

class BuildAOT(Command):
    description = "Build Numba AOT compiled modules"
    user_options = []
    
    def initialize_options(self):
        pass
    
    def finalize_options(self):
        pass
    
    def run(self):
        build_aot_modules()

# Setup configuration
setup(
    name='pvm_numba_aot',
    version='1.0',
    description='AOT compiled PVM interpreter functions',
    cmdclass={
        'build_aot': BuildAOT,
    },
    include_dirs=[numpy_include],
    zip_safe=False,
)

if __name__ == '__main__':
    # If run directly, just build the AOT modules
    import sys
    if len(sys.argv) == 1:
        print("Building AOT modules...")
        build_aot_modules()
        print("Done! AOT modules built successfully.")