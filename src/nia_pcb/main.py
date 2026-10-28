"""Point d'entrée du serveur. La base vit dans NIA_DATABASE, sinon data/nia.sqlite."""

import os
from pathlib import Path

from nia_pcb.app import create_app

app = create_app(Path(os.environ.get("NIA_DATABASE", "data/nia.sqlite")))
