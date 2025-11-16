import os

# Compatibility shim: allow importing the package as `backend` even though
# the code lives in the `Backend` directory (case differences on Windows).
# This inserts the real `Backend` folder into the package __path__ so
# `import backend.app` will discover `Backend/app`.
__path__.append(os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'Backend')))
