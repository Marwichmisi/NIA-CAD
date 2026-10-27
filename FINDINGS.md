# FINDINGS — export 3D GLB via `kicad-cli` ou conversion STEP

Ticket : [Marwichmisi/NIA-CAD#3](https://github.com/Marwichmisi/NIA-CAD/issues/3) (`Part of #1`).
Branche : `research/kicad-glb`. Ticket laissé **ouvert**, aucune PR, aucun merge (mission wayfinder/recherche).

## Réponse courte

**OUI — `kicad-cli` exporte nativement en GLB dans KiCad 10.0.7. Aucune conversion STEP → GLB n'est nécessaire sur cette version.**

- Commande : `kicad-cli pcb export glb -o board.glb board.kicad_pcb`
- `kicad-cli` ne fournit **aucune** sous-commande de conversion STEP → GLB (vérifié via la liste exhaustive des sous-commandes `pcb export`), et la doc CLI officielle ne documente aucun outil de conversion → toute chaîne de conversion externe (assimp, Blender, FreeCAD, CadQuery, …) est marquée **« à vérifier »** (hors sources officielles autorisées).

## Versions (sources)

| Élément | Valeur | Source |
|---|---|---|
| `kicad-cli` local | `10.0.7` (`10.0.7-10.0.7~ubuntu24.04.1, release build`, OCC 7.6.3) | `kicad-cli version` / `kicad-cli version --format about` en local |
| Doc CLI officielle | « *This user manual is based on KiCad 10.0.7* », section **PCB export: GLB** | https://docs.kicad.org/10.0/en/cli/cli.html |
| Version KiCad visée par NIA | **à vérifier** — aucune version KiCad épinglée trouvée dans le repo (ni `AGENTS.md`, ni `docs/agents/`) | inspection du repo à `de31f84` |

## Commandes exactes (vérifié en local, KiCad 10.0.7)

Liste des exports (`kicad-cli pcb export --help`) — extrait pertinent :

```text
Usage: pcb export [--help] {3dpdf,brep,drill,dxf,gencad,gerbers,glb,hpgl,ipc2581,ipcd356,odb,pdf,ply,pos,ps,stats,step,stl,stpz,svg,u3d,vrml,xao}
...
  glb        Export GLB (binary GLTF)
  step       Export STEP
```

Export GLB (`kicad-cli pcb export glb --help`) :

```text
Usage: export glb [--help] [--output OUTPUT_FILE] [--define-var KEY=VALUE]... [--force] [--no-unspecified] [--no-dnp] [--variant VAR]... [--grid-origin] [--drill-origin] [--subst-models] [--board-only] [--cut-vias-in-body] [--no-board-body] [--no-components] [--component-filter VAR] [--include-tracks] [--include-pads] [--include-zones] [--include-inner-copper] [--include-silkscreen] [--include-soldermask] [--fuse-shapes] [--fill-all-vias] [--no-extra-pad-thickness] [--min-distance MIN_DIST] [--net-filter VAR] [--user-origin VAR] INPUT_FILE

Export GLB (binary GLTF)
```

Doc officielle (même usage, section « PCB export: GLB ») :

```text
kicad-cli pcb export glb [--help] [--output OUTPUT_FILE] ... [--user-origin VAR] INPUT_FILE
```

Export STEP de repli (`kicad-cli pcb export step --help`, usage identique + `--no-optimize-step`) :

```text
Usage: export step [--help] [--output OUTPUT_FILE] ... [--no-optimize-step] [--user-origin VAR] INPUT_FILE

Export STEP
```

Invocation minimale recommandée (syntaxe issue du `Usage`, **exécution réelle : à vérifier** — aucun `.kicad_pcb` dans le repo pour tester) :

```sh
kicad-cli pcb export glb -o board.glb board.kicad_pcb
kicad-cli pcb export glb --force -o board.glb board.kicad_pcb   # écraser la sortie
```

## Limites constatées (sources officielles uniquement)

1. Le jeu d'options de `export glb` est **identique** à celui de `export step/stl/ply/brep` (même `--help` au nom près) : aucun réglage de qualité/maillage dédié au GLB n'est exposé. Qualité visuelle / fidélité des matériaux du `.glb` : **à vérifier** (non documenté dans le `--help` ni dans la section GLB de la doc CLI).
2. `--include-tracks`, `--include-pads`, `--include-zones`, `--fuse-shapes` sont signalés « *time consuming* » par la doc officielle : prévoir un coût sur les cartes denses.
3. `--subst-models` : remplace les modèles VRML des empreintes par des STEP/IGS de même nom s'ils existent (utile si des empreintes n'ont que du VRML).
4. `hpgl` est listé mais « *No longer supported as of KiCad 10.0* » — sans rapport avec le GLB, noté pour éviter toute confusion dans la liste des exports.
5. Version d'introduction de `export glb` (8.x ? 9.x ?) : **à vérifier** — constat établi uniquement pour 10.0.7 (local + doc 10.0). Si NIA doit supporter KiCad < 10, refaire `kicad-cli pcb export --help` sur la version cible.
6. Conversion STEP → GLB (plan B si GLB natif indisponible) : **aucun outil officiel KiCad** — `pcb export` ne contient aucun convertisseur, la doc CLI ne mentionne ni assimp, ni Blender, ni FreeCAD, ni CadQuery (recherche par mots-clés dans `cli.html` : 0 occurrence). Outil, commande et qualité de conversion : **à vérifier** dans un ticket séparé si le besoin apparaît.

## Recommandation

- Épingler KiCad **10.0.7+** (ou `10.x`) comme version de référence pour le pipeline 3D et utiliser `kicad-cli pcb export glb` directement.
- Ne pas investir dans une chaîne STEP → GLB tant que la version visée inclut l'export GLB natif.
- Si un test de non-régression est voulu : ajouter un `.kicad_pcb` minimal + job CI `kicad-cli pcb export glb` et contrôle de l'existence/taille du `.glb` (piste, non testée ici).
