import os
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tracker.settings")

from tracker.wsgi import application
