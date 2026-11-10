import sys

if sys.platform == "win32":
    from .windows import *
else:
    from .linux import *
