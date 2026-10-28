"""Point d'entrée du serveur. La base vit dans NIA_DATABASE, sinon data/nia.sqlite."""

import os
from pathlib import Path

from nia_pcb.app import create_app
from nia_pcb.llm import model_from_environment

app = create_app(
    Path(os.environ.get("NIA_DATABASE", "data/nia.sqlite")),
    model=model_from_environment(),
)
