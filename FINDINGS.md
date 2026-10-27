# FINDINGS — `ato build` : sorties et commandes exactes

- Date de recherche : 2026-10-27 (UTC).
- Question (ticket #2, part of #1) : que génère exactement `ato build` aujourd'hui
  (Gerber, BOM, positions, GLB, STEP, SVG, netlistes ?) et sous quelles commandes
  exactes + versions atopile ?
- Méthode (skill `research`) : sources primaires uniquement — code source officiel
  `atopile/atopile` (branche `main`), `pyproject.toml`, API Releases GitHub, API JSON
  PyPI, README officiel. CLI locale tentée (`ato --help`, `ato build --help`) mais
  `ato` non installé (voir § Versions). Aucune source secondaire (blog, tuto) retenue.
- Worktree : `research/ato-build`, fichier `FINDINGS.md` (ce fichier).

## 1. Réponse courte (vérifié sur `main`)

- `ato build` **sans `-t`** = cible virtuelle `default` (alias `__default__`) :
  `bom` + `manifest` + `variable-report` + `datasheets`, **plus** mise à jour du
  layout KiCad (`elec/layout/<build>.kicad_pcb`). Ne produit **pas** par défaut :
  Gerber, positions, DXF, GLB, STEP, PNG, SVG.
- Pour la fab : `ato build -t mfg-data` (Gerber + positions + DXF + testpoints +
  résumé PCB + copie `.kicad_pcb`) et/ou `ato build -t all` (`default` + `mfg-data` +
  `3d-models` = GLB + STEP). Images 2D/3D (`2d-image`, `3d-image`) **seulement** sur
  demande explicite `-t`.
- Pas de cible `netlist` / `.net` dans le registre des targets : le champ `netlist`
  existe dans la config mais **aucun target muster ne l'écrit** (à vérifier, voir § 6).
- Pas de `STEP`/`GLB`/`SVG`/`Gerber` sans `kicad-cli` : tag `REQUIRES_KICAD`, skip si
  implicite, erreur `UserToolNotAvailableError("kicad-cli not found")` si demandé
  explicitement.

## 2. Versions (avec dates)

| Fait | Valeur | Source + date de consultation |
|---|---|---|
| CLI locale `ato` | **non installé** : `ato: commande introuvable` (`ato --version`, `ato --help`, `ato build --help` impossibles) ; Python env 3.12.3, `pip show atopile` vide | terminal local, 2026-10-27 |
| `requires-python` atopile | `>=3.14,<3.15` → explique l'impossibilité d'installer sur Python 3.12 local | `pyproject.toml` sur `main`, consulté 2026-10-27 via `https://raw.githubusercontent.com/atopile/atopile/main/pyproject.toml` |
| Commit `main` audité | `619eda7f777558a3e500dbad9cc2941712881495` — « Fix: circular import crash when FBRK_LOG_DIR is set (#1791) », 2026-03-11T14:16:01-07:00 | `git log -1`, `git ls-remote`, 2026-10-27 |
| PyPI `atopile` latest | `0.15.9`, upload `2026-09-12T00:11:14`, 171 releases ; queue récente : `0.15.0`–`0.15.9`, `0.12.6` (2026-08-07) | `https://pypi.org/pypi/atopile/json`, 2026-10-27 |
| GitHub Releases (API, 100 dernières) | `v0.14.0` (2026-01-31) … `v0.14.1004` (2026-02-12) ; `v0.12.5` (2026-01-20) avant | `https://api.github.com/repos/atopile/atopile/releases?per_page=100`, 2026-10-27 |
| Divergence à noter | PyPI connaît `0.15.x` (09/2026) alors que l'API Releases listée s'arrête à `v0.14.1004` (02/2026) sur les 100 premières entrées ; ne pas en déduire l'absence de releases `0.15.x` côté GitHub sans paginer | constat 2026-10-27, **à vérifier** par pagination complète |
| Version projet (`ato.yaml`) | champ `requires-atopile` (défaut `^<installed>`), alias `requires_atopile` ; ancien `ato-version` **deprecated** (erreur explicite) ; seuil migration `0.14.0` (`MIGRATION_THRESHOLD`) | `src/atopile/config.py` (~l.849–912), `src/atopile/version.py`, 2026-10-27 |
| Docs versionnées | snippets indexés `docs.atopile.io/atopile-0.14.x/...` (config `builds.targets`, changelog `0.14.0`, essentials `6-layout`) mais **fetch direct 404 le 2026-10-27** (`/reference/config`, `/reference/config.md`, `/reference/config/`, `/guides/install`) ; homepage `docs.atopile.io/` dit « The docs live in the editor now » | `webfetch` + `websearch`, 2026-10-27 — **à vérifier** par lecture in-editor/extension |

## 3. Commande exacte `ato build` (source : `src/atopile/cli/build.py`, `main` @ `619eda7`)

Signature (typer) :

```text
ato build [ENTRY] [--build/-b ...] [--target/-t ...] [--exclude-target/-x ...]
  [--frozen] [--keep-picked-parts] [--keep-net-names] [--keep-designators]
  [--standalone] [--open] [--all] [--jobs/-j N] [--verbose/-v]
```

- `ENTRY` (argument optionnel) : dossier projet ou adresse cible `"path/to.ato:Module"`.
- `--build/-b` (env `ATO_BUILD`) : filtre les builds `ato.yaml` à lancer.
- `--target/-t` (env `ATO_TARGET`) : targets muster à inclure (ex. `mfg-data`, `all`, `bom`, `glb`, `step`, `2d-image`, `3d-image`, `datasheets`, `variable-report`, `manifest`, `power-tree`).
- `--exclude-target/-x` (env `ATO_EXCLUDE_TARGET`) : à soustraire après inclusion.
- `--frozen` (env `ATO_FROZEN`) : échoue si le layout devrait changer (utile CI) ; écrit `.original.kicad_pcb` + `.updated.kicad_pcb` en cas de diff.
- `--keep-picked-parts` / `--keep-net-names` / `--keep-designators` (envs `ATO_KEEP_*`).
- `--open` (env `ATO_OPEN_LAYOUT`) : ouvre le layout après build.
- `--all` : découvre récursivement tous les `ato.yaml` (hors `.ato/modules`) et build tout.
- `--jobs/-j` (défaut `os.cpu_count() or 4`), `--verbose/-v` (séquentiel + streaming).
- Résolution effective (`src/atopile/buildutil.py`, `run_build_targets`) :
  `targets = ({generate_default.name} | set(config.build.targets)) - set(exclude)`.

Autres commandes constatées (contexte, `src/atopile/cli/cli.py`) :
`ato --version`, `ato --semver`, `ato validate <file.ato>`, `ato create …`,
`ato sync|add|remove`, `ato view`, `ato serve`, `ato package …`, `ato dependencies …`.
Seul `ato build` répond à la question ; le `--help` exact reste **à vérifier**
sur machine avec `ato` installé (Python ≥ 3.14 + `kicad-cli`).

Exemples vérifiés (README officiel + code) :

```bash
ato build                          # build(s) par défaut du projet courant
ato build -t all                   # default + mfg-data + 3d-models (fab + 3D)
ato build --target my_target path/to/source.ato:module.path
ato build --all                    # tous projets sous CWD
ato build -b <nom_build> -t mfg-data -x bom
```

## 4. Targets muster (source : `src/atopile/build_steps.py`, `main` @ `619eda7`)

Ordre amont (toujours exécuté avant `build-design`) :
`init-build-context` → `modify-typegraph` → `instantiate-app` → `prepare-build` →
`post-instantiation-graph-check` → `post-instantiation-setup` →
`post-instantiation-design-check` → `load-pcb` → `picker` → `prepare-nets` →
`post-solve-checks` → `update-pcb` → `post-pcb-checks` → `build-design` (virtuel).

| Target (alias) | Virtuel ? | `REQUIRES_KICAD` ? | Sorties exactes (suffixes sur `output_base`) |
|---|---|---|---|
| `bom` | non | non | `<base>.bom.csv` (JLCPCB) + `<base>.bom.json` (panneau BOM VSCode, avec `build_id`) |
| `glb` (`3d-model`) | non | oui | `<base>.pcba.glb` |
| `glb-only` (`3d-model-only`, sans dépendance `build-design`) | non | oui | `<base>.pcba.glb` depuis layout existant ; erreur si layout absent (« Run a full build first ») |
| `step` | non | oui | `<base>.pcba.step` |
| `3d-models` (dépend `glb` + `step`) | oui | hérité | GLB + STEP ci-dessus |
| `3d-image` | non | oui | `<base>.pcba.png` (rendu 3D) |
| `2d-image` | non | oui | `<base>.pcba.svg` (`flip_board=False`) |
| `mfg-data` (dépend `glb` + `step` + `post_pcb_checks`) | non | oui | `<base>.pcba.dxf`, `<base>.gerber.zip`, `<base>.pick_and_place.csv` (natif KiCad), `<base>.jlcpcb_pick_and_place.csv` (converti JLCPCB), `<base>.testpoints.json`, `<base>.pcb_summary.json`, `<base>.kicad_pcb` (copie du layout githashé) |
| `manifest` | non | non | `build/manifest.json` (+ `<base>.layouts.json` référencé par layout) |
| `variable-report` | non | non | `<base>.variables.json` (avec `build_id`) |
| `power-tree` | non | non | `<output_dir>/power_tree.md` (Mermaid) — **non inclus** dans `default` (ligne commentée) |
| `datasheets` | non | non | `<base-dir>/documentation/datasheets/` (via `export_datasheets`) |
| `default` (alias `__default__`) | oui | non | = `bom` + `manifest` + `variable-report` + `datasheets` |
| `all` (alias `*`) | oui | hérité | = `default` + `mfg-data` + `3d-models` (donc GLB+STEP, **pas** `3d-image`/`2d-image`/`power-tree`/`glb-only` sauf demande explicite) |
| `i2c-tree` | n'existe pas (code commenté) | — | — |

Points vérifiés dans le code :
- `mfg-data` sans `kicad-cli` : `raise UserExportError` par export (`DXF`, `Gerber`, `PnP`) ; en mode implicite le target est skippé avec warning, en mode explicite erreur `UserToolNotAvailableError("kicad-cli not found")` (`buildutil.py`).
- `update-pcb` écrit le layout **sur place** (`kicad.dumps(pcb_file, config.build.paths.layout)`), après backup horodaté dans `<base-parent>/backups/<nom>.YYYYMMDD-HHMMSS.kicad_pcb` ; apparence imposée (soldermask noir mat, ENIG) — écrase les réglages utilisateur (`ensure_board_appearance`).
- `post-pcb-checks` = DRC (`F.PCB.requires_drc_check.DrcException` → `UserException("Detected DRC violations…")`).

## 5. Chemins (source : `src/atopile/config.py`, `main` @ `619eda7`)

Défauts projet (`ProjectPaths`) :

```text
root          = dossier contenant ato.yaml
src           = <root>/elec/src
parts         = <src>/parts
layout        = <root>/elec/layout
build         = <root>/build
manifest      = <build>/manifest.json
modules       = <root>/.ato/modules
```

Par build (`BuildTargetPaths`, `name` = nom du build `ato.yaml`) :

```text
layout        = elec/layout/<name>.kicad_pcb  (via find_layout ; .kicad_pro sibling)
output_base   = build/builds/<name>/<name>    (sans extension, préfixe de tous les artefacts § 4)
documentation = build/builds/<name>/documentation
netlist       = <output_base>/<name>.net      (valeur par défaut ; voir § 6)
kicad_project = <layout>.kicad_pro
fp_lib_table  = <layout-dir>/fp-lib-table
```

`ato.yaml` minimal :

```yaml
requires-atopile: ^0.14.0
builds:
  default:
    entry: path/to.ato:App
    targets: [bom, mfg-data]        # défaut ["__default__"] si absent
    exclude_targets: [mfg-data]     # ex. modules non-fabriqués / CI
```

## 6. Explicitement « à vérifier » (non confirmé par sources primaires le 2026-10-27)

1. Texte exact de `ato --help` / `ato build --help` (CLI non installable ici : `requires-python >=3.14` vs Python 3.12 local).
2. Contenu Gerber du `.gerber.zip` (couches incluses), colonnes exactes `.bom.csv` / `.pick_and_place.csv` / `.jlcpcb_pick_and_place.csv`, schéma `.bom.json` / `.variables.json` / `.testpoints.json` / `.pcb_summary.json` : nécessite un build réel avec `kicad-cli`.
3. Fichier netlist `.net` : champ `netlist` défaut présent en config mais **aucune écriture trouvée** dans `build_steps.py` audité ; vérifier si écrit par `faebryk`/`kicad` ailleurs ou reliquat.
4. Export SVG : `export_svg(..., flip_board=False)` — face avant/arrière exacte à confirmer par sortie réelle ; de même rendu `.pcba.png`.
5. Datasheets : formats exacts sous `documentation/datasheets/` (PDF ? noms ?) — `export_datasheets` non audité en détail.
6. Version KiCad / `kicad-cli` minimale requise : non trouvée dans les fichiers audités.
7. Docs `docs.atopile.io/atopile-0.14.x/...` : snippets moteur (`builds.targets: [bom, mfg-data]`, `exclude_targets: [mfg-data]`, quickstart `ato build`, layout `ato build → .kicad_pro`) cohérents avec le code, mais fetch direct 404 le 2026-10-27 (docs « live in the editor now ») — à relire via workspace/extension.
8. Divergence Releases GitHub vs PyPI (`0.15.x` sur PyPI, top-100 Releases arrêté à `v0.14.1004`) — à vérifier par pagination API complète.
9. Comportement `--frozen` / `--keep-*` / `--all` / `-j` au-delà des docstrings : à vérifier par exécution.

## 7. Sources (URLs + dates)

- Code (consulté 2026-10-27, `main` @ `619eda7`, 2026-03-11) :
  - `https://github.com/atopile/atopile/blob/619eda7f777558a3e500dbad9cc2941712881495/src/atopile/build_steps.py` (l.385–1202 : registre muster, § 4)
  - `https://github.com/atopile/atopile/blob/619eda7f777558a3e500dbad9cc2941712881495/src/atopile/buildutil.py` (l.105–168 : `run_build_targets`, résolution `default | targets - exclude`)
  - `https://github.com/atopile/atopile/blob/619eda7f777558a3e500dbad9cc2941712881495/src/atopile/config.py` (l.200–344 : `ProjectPaths`, `BuildTargetPaths` ; l.849–912 : `requires-atopile`)
  - `https://github.com/atopile/atopile/blob/619eda7f777558a3e500dbad9cc2941712881495/src/atopile/cli/build.py` (l.318–399 : signature `ato build`)
  - `https://github.com/atopile/atopile/blob/619eda7f777558a3e500dbad9cc2941712881495/src/atopile/cli/cli.py` (l.51–218 : `ato --version/--semver`, sous-commandes)
  - `https://github.com/atopile/atopile/blob/619eda7f777558a3e500dbad9cc2941712881495/pyproject.toml` (`requires-python >=3.14,<3.15`, `project.scripts ato`)
- Méta :
  - `https://github.com/atopile/atopile` (README : « `ato build` », « Build outputs — BOM, fabrication and assembly data, reports », install via extension), consulté 2026-10-27
  - `https://api.github.com/repos/atopile/atopile/releases?per_page=100`, consulté 2026-10-27
  - `https://pypi.org/pypi/atopile/json` (`0.15.9`, 2026-09-12), consulté 2026-10-27
  - `https://raw.githubusercontent.com/atopile/atopile/main/pyproject.toml`, consulté 2026-10-27
- Docs (index moteur uniquement, fetch direct 404 le 2026-10-27) :
  - `https://docs.atopile.io/atopile-0.14.x/reference/config` (via snippet : `builds.targets: [bom, mfg-data]`)
  - `https://docs.atopile.io/atopile-0.14.x/essentials/6-layout` (via snippet : `ato build` génère `.kicad_pro`, plugin sync)
  - `https://docs.atopile.io/` (homepage : « docs live in the editor now »)
