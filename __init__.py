# experiencebuffers/__init__.py

# Expose submodules for easier access
from . import core
from . import devices
from . import util

# Optional: expose key entry point if needed
from .core.BufferServer import main
