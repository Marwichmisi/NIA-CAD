# PROTOTYPE — maquette interface NIA PCB (throwaway, ne pas merger)

Question : a quoi doit ressembler l'ecran principal (chat + apercu PCB 2D/3D) ?
3 variantes Stitch, projet « NIA PCB — interface locale » (id 9551096813191472550) :

- variante-a-split-classique.html — Variante A « Split classique » (chat 1/3 + apercu 2/3, panneau DRC/ERC + journal bas, barre statut). Screen: screens/07c04d05c4d144d7abba505fea5572bc
- variante-b-studio-central.html — Variante B « Studio central » (apercu plein centre, chat en tiroir droit). Screen: screens/42d6a49465dc4dcb99210ca740c6be3c
- variante-c-pilotage-etapes.html — Variante C « Pilotage par etapes » (pipeline vertical gauche + chat centre + apercu droit). Screen: screens/784b5b3175fc405db898c4181304a2ba

Doublons Stitch sans importance : « AtoStudio - Split Classique » (screens/6ea91720162544e5921a673cc47bcef3), 2e « Variante C » (screens/739e848a78f24969aa9601b3daa715ff).
Ouvrir les .html dans un navigateur (CDN tailwind + fonts en ligne requis).
Decision attendue sur le ticket #10 : variante gagnante ou panachage, puis layout tranche.

## Variante B v2 (retenue avec ajustements)

- Fichier Stitch : screens/580f1aedb5a84e9cab744b05362283ef (« Variante B v2 - Studio central ajusté »), html files/da634d51712c4b7d8d7d27d44afdb470, shot files/e4b7237e77784781b4fdc2096f4abc6c.
- HTML complet re-telechargeable via MCP stitch download_file (non recopie ici, source de verite = projet Stitch « NIA PCB — interface locale », id 9551096813191472550).
- Ajustements appliques vs B : journal SSE sous le canvas (bandeau h-28 « Journal d'actions en direct »), bouton segmente [2D Vue dessus | 3D Rendu temps réel] visible dans la barre d'outils apercu, tiroir chat 420px (w-[420px]) avec diffs .ato + selecteur modele LLM local.
- Verifie dans le HTML : toggle 2D/3D present, bandeau logs SSE present, chat w-[420px] present.
