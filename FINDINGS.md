# Recherche — passage PCB vers Freerouting (export DSN, import SES)

Ticket : [#4 — Recherche — passage PCB vers Freerouting DSN SES](https://github.com/Marwichmisi/NIA-CAD/issues/4).
Date : 2026-10-27. Méthode : docs officielles KiCad + Freerouting uniquement.
Tout ce qui n'est pas confirmé par une source primaire est marqué « à vérifier ».

## Réponse courte

- **`kicad-cli` (10.0.7, vérifié localement) : NON.** `pcb export` ne propose aucun
  sous-format DSN/Specctra et `pcb import` n'accepte pas le SES.
  Les docs CLI officielles 9.0 et 10.0 ne mentionnent ni « specctra » ni « dsn ».
- **API Python `pcbnew` : OUI (vérifié localement sur KiCad 10.0.7).**
  `pcbnew.ExportSpecctraDSN(...)` et `pcbnew.ImportSpecctraSES(...)` existent,
  mais ne sont pas documentées dans le guide de scripting officiel → usage CI
  headless « à vérifier ».
- **GUI KiCad : OUI (voie documentée).** `Fichier → Exporter → Specctra DSN…`
  puis `Fichier → Importer → Specctra Session…`.
- **Freerouting : OUI.** Entrée `.dsn`, sortie `.ses`, en GUI comme en CLI
  (`-de` / `-do`), plus plugin KiCad officiel via le PCM (KiCad ≥ 6.0).

## 1. Côté KiCad — GUI (voie documentée)

Source : manuel PCB officiel KiCad 10.0 (basé sur 10.0.7, révision doc `efa5960e`),
sections `Specctra DSN` et `Importing Specctra session files`.

- Export : `File → Export → Specctra DSN…`.
  Citation doc : « The Specctra DSN exporter creates a file suitable for importing
  into certain third-party autorouter software. … There are no configurable options. »
- Import : `File → Import → Specctra Session…`.
  Workflow doc : exporter DSN → autorouter externe → fichier `.ses` → réimporter.
- Limites documentées :
  - l'import SES n'ajoute que le routage (tracks + vias) sur le board existant ;
  - les empreintes, les nets et le contour doivent correspondre à l'export
    d'origine, sinon l'import échoue ;
  - aucune option configurable côté export DSN.

## 2. Côté KiCad — `kicad-cli` : pas de DSN/SES en 10.0.7

Vérifié localement (`kicad-cli version` → `10.0.7`) :

```
kicad-cli pcb export   # 3dpdf brep drill dxf gencad gerbers glb hpgl ipc2581
                       # ipcd356 odb pdf ply pos ps stats step stl stpz svg
                       # u3d vrml xao   ← pas de dsn/specctra
kicad-cli pcb import --format  # auto pads altium eagle cadstar fabmaster
                               # pcad solidworks  ← pas de specctra/ses
```

Sources concordantes : pages CLI officielles `docs.kicad.org/10.0/en/cli/cli.html`
et `docs.kicad.org/9.0/en/cli/cli.html` — zéro occurrence de « specctra » / « dsn ».

⚠️ Nuance « à vérifier » : le **source amont (master, doxygen consulté le
2026-10-27)** contient bien `PCB_EXPORT_SPECCTRA_COMMAND` (« specctra »,
« Export the PCB as a Specctra DSN file (.dsn) », job `JOB_EXPORT_PCB_SPECCTRA_DSN`,
fichier `command_pcb_export_specctra.cpp`, câblé dans la liste des sous-commandes
de `pcb export`). Ce n'est présent ni en 9.0 ni en 10.0.7 → probable ajout
post-10.0.7 (nightly / future release), à re-vérifier à chaque montée de version.
Même en master, **aucune commande CLI d'import SES** : `pcb import` reste limité
aux formats CAO tiers.

## 3. Côté KiCad — API Python `pcbnew` : la voie scriptable

Vérifié localement (KiCad 10.0.7, `python3 -c "import pcbnew"`) :

```
pcbnew.ExportSpecctraDSN(wxString aFullFilename) -> bool
pcbnew.ExportSpecctraDSN(BOARD aBoard, wxString aFullFilename) -> bool
pcbnew.ImportSpecctraSES(wxString aFullFilename) -> bool
pcbnew.ImportSpecctraSES(BOARD aBoard, wxString aFullFilename) -> bool
```

Implémentation C++ sous-jacente (doxygen officiel, sources primaires) :

- `DSN::ExportBoardToSpecctraFile(BOARD *aBoard, const wxString &aFullFilename,
  REPORTER *aReporter)` — `pcbnew/specctra_import_export/specctra_export.cpp` ;
- `DSN::ImportSpecctraSession(BOARD *aBoard, const wxString &fullFileName,
  COMMIT &aCommit, REPORTER *aReporter, int *aSkippedCount)` —
  `pcbnew/specctra_import_export/specctra_import.cpp`.

Réserve : le guide de scripting officiel (`docs.kicad.org/10.0/en/scripting/`)
ne mentionne ni « specctra » ni « .dsn » ni ces deux fonctions. L'API existe et
fonctionne, mais son usage en CI 100 % headless (sans serveur X, gestion du
`BOARD` courant, sauvegarde) est « à vérifier » par un test réel avant de
l'inscrire dans un pipeline.

## 4. Côté Freerouting (sources : repo officiel `freerouting/freerouting`)

- Principe (README officiel) : « Freerouting is an advanced autorouter for all PCB
  programs that support the standard Specctra or Electra DSN interface. It imports
  `.dsn` files … and exports routed `.ses` session files. »
- GUI : `File > Open…` (.dsn) → icône baguette (autoroute) → `File > Save as…`
  (.ses).
- CLI (README + `docs/command_line_arguments.md`) :

  ```
  java -jar path/to/freerouting.jar -de MyBoard.dsn -do MyBoard.ses -inc GND,VCC
  ```

  `-de` = design d'entrée (`.dsn` obligatoire ; `.ses`/`.rules` optionnels,
  combinables par `+`), `-do` = sortie (`.ses`/`.dsn`/`.scr` selon l'extension),
  `-inc` = net classes ignorées, plus `-mp` (passes), `-mt` (threads), etc.
- Intégration KiCad (`docs/integrations.md`, rubrique KiCad) : plugin via
  `Tools / Plugin and Content Manager` (KiCad ≥ 6.0), puis `Tools / External
  Plugins` dans le PCB Editor ; le plugin orchestre export DSN → routage →
  réimport du design routé.
- Repères version (à re-vérifier à l'implémentation) : dernière release **v2.5.0**
  publiée le 2026-10-05 ; JRE 25 requis ; image Docker
  `ghcr.io/freerouting/freerouting` (:latest préconisé).

## 5. Workflow complet recommandé (état de la recherche)

```
KiCad (.kicad_pcb)
  │  pcbnew.ExportSpecctraDSN(board, "board.dsn")   # scriptable, à valider en CI
  ▼
Freerouting : java -jar freerouting.jar -de board.dsn -do board.ses
  │  (ou plugin KiCad PCM, ou GUI)
  ▼
KiCad : pcbnew.ImportSpecctraSES(board, "board.ses")  # ajoute tracks + vias
  │  (ou File → Import → Specctra Session…)
  ▼
DRC + revue manuelle obligatoires
```

Alternative sans code : 100 % GUI des deux côtés (menus ci-dessus).

## 6. Points « à vérifier » avant implémentation

1. Comportement réel de `pcbnew.ExportSpecctraDSN` / `ImportSpecctraSES` en
   contexte headless (CI) : board à charger/sauvegarder explicitement ?
2. Disponibilité de `kicad-cli pcb export specctra` dans les futures releases
   (présent en master amont, absent en 10.0.7).
3. Version Freerouting à épingler (v2.5.0 au 2026-10-05) + prérequis Java du
   runner CI.
4. Couverture DRC après import SES + stratégie pour les zones cuivre
   (re-remplissage après import) — non couvert par les docs officielles
   consultées.

## Sources primaires consultées

- https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html (`#specctra_dsn`, `#specctra-session-import`)
- https://docs.kicad.org/10.0/en/cli/cli.html et https://docs.kicad.org/9.0/en/cli/cli.html
- https://docs.kicad.org/10.0/en/scripting/scripting.html (absence de mention = constat)
- https://docs.kicad.org/doxygen/specctra__export_8cpp.html,
  `specctra__import_8cpp.html`, `command__pcb__export__specctra_8cpp_source.html`,
  `kicad__cli_8cpp_source.html` (doxygen généré du master, consulté 2026-10-27)
- `kicad-cli` 10.0.7 + `python3 -c "import pcbnew"` locaux (sorties citées verbatim)
- https://github.com/freerouting/freerouting (README),
  `docs/command_line_arguments.md`, `docs/integrations.md` (master, consultés 2026-10-27)
