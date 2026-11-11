import atexit
import os
import shutil
import tempfile

_app = None


def load_app():
    """Imports app.py once for all the tests, with its database in a temporary folder"""
    global _app
    if _app is None:
        # app.py picks its database and its CORS settings when it is imported
        os.environ['FLASK_DEBUG'] = '1'
        workdir = tempfile.mkdtemp()
        atexit.register(shutil.rmtree, workdir, True)
        previous_cwd = os.getcwd()
        os.chdir(workdir)
        try:
            import app as flask_app
        finally:
            os.chdir(previous_cwd)
        _app = flask_app
    return _app
