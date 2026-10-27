# Recherche — Capacités et règles JLCPCB à jour

- Ticket : Marwichmisi/NIA-CAD#5 (« Quelles sont les capacites et regles de fabrication JLCPCB a jour ? »)
- Date de consultation des sources : 2026-10-27 (UTC)
- Sources : **site officiel JLCPCB uniquement**. Toute valeur sans source officielle est marquée « à vérifier ».
- Branche : `research/jlcpcb-rules` — fichier `FINDINGS.md` (worktree isolé, aucun merge).

## Sources officielles consultées

| # | Page | URL | Contenu exploité |
|---|------|-----|------------------|
| S1 | Rigid PCB Manufacturing Capabilities | https://jlcpcb.com/capabilities/pcb-capabilities | Pistes, perçages, vias, pastilles, masque, sérigraphie, découpe, épaisseurs, cuivre, dimensions, matériaux, impédance ±10 % |
| S2 | Controlled Impedance PCB Layer Stackup | https://jlcpcb.com/impedance | Empilements 4 couches (famille JLC04161H-…) et 6 couches, constantes diélectriques prepreg/core/masque, exigences min. trace/via/BGA pour impédance |
| S3 | User Guide to the JLCPCB Impedance Calculator | https://jlcpcb.com/help/article/user-guide-to-the-jlcpcb-impedance-calculator | Paramètres de calcul (mise à jour affichée : 16 sept. 2026), matériaux core Nan Ya NP-155F (4–8 couches) / SYTECH S1000-2M (10+ couches), schéma de nommage des stackups |

## 1. Largeurs / espacements minimaux (S1)

Toutes les valeurs ci-dessous viennent de la section « Traces » de S1.

| Cuivre fini (couche externe) | Min. largeur / espacement | Couches concernées |
|---|---|---|
| 1 oz | 0,10 / 0,10 mm (4 / 4 mil) | 1 et 2 couches |
| 1 oz | 0,09 / 0,09 mm (3,5 / 3,5 mil) ; 3 mil accepté localement en fan-out BGA | Multicouche |
| 2 oz | 0,16 / 0,16 mm (6,5 / 6,5 mil) | 2 couches |
| 2 oz | 0,15 / 0,15 mm (6 / 6 mil) | Multicouche |
| 2,5 oz | 0,20 / 0,20 mm (8 / 8 mil) | 2 couches |
| 3,5 oz | 0,25 / 0,25 mm (10 / 10 mil) | 2 couches |
| 4,5 oz | 0,30 / 0,30 mm (12 / 12 mil) | 2 couches |

- Tolérance largeur de piste : **± 20 %** (ex. piste dessinée 0,10 mm → 0,08–0,12 mm accepté). (S1)
- HDI (S1) : min. piste/isol. **3 / 3 mil**, extrême **2,7 / 2,7 mil** ; pastilles laser 0,075–0,15 mm ; enterrés standard 0,15–0,55 mm (extrême 0,10 mm si diélectrique traversé ≤ 1,0 mm).
- Bobines de pistes (trace coils, 1 oz) : 0,15/0,15 mm si recouvertes de masque ; 0,25/0,25 mm si NON recouvertes (ENIG uniquement, risque de court-circuit avec HASL). (S1)
- Grille hachurée largeur/espacement : 0,25 mm. Espacement même net : 0,25 mm. (S1)

### Clairières (clearances, S1, cuivre 1 oz sauf mention)

- Pastille → piste : **0,10 mm** (rester nettement au-dessus si possible ; 0,09 mm min. localement pour pastilles BGA).
- Pastilles CMS entre elles (nets différents) : **0,15 mm** ; pastille CMS min. 0,25 × 0,25 mm.
- Trou de via → piste : **0,20 mm**.
- PTH → piste : **0,28 mm min. (0,35 mm recommandé)**.
- NPTH → piste : **0,20 mm**.
- Couche interne : trou de via → cuivre **0,20 mm** ; trou pastille PTH → cuivre **0,30 mm**.
- Anneau annulaire PTH : 2 couches 1 oz **≥ 0,25 mm recommandé, 0,18 mm min. absolu** ; multicouche 1 oz **≥ 0,20 mm recommandé, 0,15 mm min. absolu** ; 2 oz **≥ 0,254 mm**. NPTH : **≥ 0,45 mm recommandé**.
- BGA : pastilles Ø 0,20–0,25 mm **exigent ENIG** ; clairière pastille BGA → piste ≥ 0,10 mm (0,09 mm min. multicouche) ; vias remplis/capuchonnés autorisés dans les pastilles.

## 2. Vias et perçages (S1)

| Paramètre | Valeur officielle |
|---|---|
| Ø perçage, 1 couche | 0,3 – 6,3 mm (NPTH uniquement pour les vias : 0,3 mm trou / 0,5 mm diamètre) |
| Ø perçage, 2 couches et multicouche | 0,15 – 6,3 mm (microvias 0,10 mm **uniquement** si épaisseur ≤ 1 mm **et** finition ENIG/OSP, surcoût) ; trous ≥ 6,3 mm réalisés par fraisage |
| Via min. trou/diamètre, 2 couches et multicouche | **0,15 / 0,25 mm** (0,10/0,20 mm uniquement si épaisseur ≤ 1 mm + ENIG/OSP, surcoût) ; le diamètre doit dépasser le trou de **0,10 mm (0,15 mm préféré)** ; trou de via préféré ≥ 0,20 mm ; surcoût si trou 0,10–0,15 mm quel que soit le diamètre, ou trou 0,20–0,25 mm avec diamètre < 0,45 mm |
| Tolérance trous traversants | **+0,13 / −0,08 mm** (ex. trou 0,60 mm → 0,52–0,73 mm accepté) ; trous press-fit **± 0,05 mm** (trous finis 0,55–2,0 mm, multicouche ENIG, trous ronds uniquement, à signaler en remarque) |
| Épaisseur moyenne cuivre dans trou | 18 µm |
| Tolérance position des trous | ± 0,075 mm |
| Recommandation PTH | Ø ≥ 0,50 mm pour éviter masque/étain coincé dans le trou |
| Slots plaqués min. | largeur 0,50 mm (2 couches) / 0,35 mm (multicouche), longueur ≥ 2× largeur ; tolérance +0,13/−0,08 mm |
| Slots non plaqués min. | largeur 1,0 mm (dessin en couche mécanique), tolérance ± 0,20 mm ; NPTH min. 0,50 mm |
| Espacements trous | via-à-via 0,20 mm ; pastille-à-pastille (trous) 0,45 mm |
| Trous crénelés (castellated) | Ø ≥ 0,50 mm, trou→bord ≥ 1 mm, trou→trou ≥ 0,50 mm, PCB min. 10 × 10 mm, épaisseur min. 0,6 mm |
| Bords plaqués | PCB min. 10 × 10 mm, épaisseur min. 0,6 mm, ≥ 3 attaches ; HASL non supporté (ENIG) |
| Slots borgnes / backdrill | Formalisés en S1 (2–32 couches, ép. ≥ 0,8 mm) — voir page source pour les 6 paramètres chacun ; trous/slots rectangulaires sans congés : **non supportés** |

## 3. Empilements 1 / 2 / 4 couches

### 3.1. 1 couche (S1) — « à vérifier » pour le détail prépreg/âme

- S1 liste : FR4 1 couche (606 × 510 mm max.), aluminium 1 couche, cuivre 1 couche, min. 3 × 3 mm (FR4), 5 × 5 mm (alu/cuivre).
- Cuivre externe 2 couches : 1 / 2 / 2,5 / 3,5 / 4,5 oz (le tableau S1 regroupe « 2-layer » ; la ligne 1 couche n'y détaille pas le poids cuivre).
- **À vérifier** : build-up exact 1 couche (ép. core + cuivre) — non publié sur S1/S2/S3 ; passer par le devis instantané ou le support.

### 3.2. 2 couches (S1 + S3)

- Construction standard : **1 âme (core) FR-4 + 2 feuilles cuivre**, pas de prepreg (implicite du standard ; constantes S1 : **Dk 4,5 pour PCB 2 couches** ; prepregs 7628 → 4,4 / 3313 → 4,1 / 2116 → 4,16 / 1080 → 3,91 d'après S2).
- Épaisseurs finies FR4 standard : 0,4 / 0,6 / 0,8 / 1,0 / 1,2 / 1,6 / 2,0 mm (S1).
- Cuivre fini externe : 1 / 2 / 2,5 / 3,5 / 4,5 oz (S1).
- Dimensions max. FR4 2 couches : 670 × 600 mm (ép. ≥ 0,8 mm) ; jusqu'à 1020 × 600 mm en longueur rallongée ; min. 3 × 3 mm (ép. ≥ 0,6 mm).
- **À vérifier** : empilement 2 couches précis par épaisseur (réf. core) — S2 ne tabule que le 4 couches et au-delà ; utiliser le calculateur d'impédance S3 / la page devis.

### 3.3. 4 couches (S1 + S2 + S3) — standard `JLC04161H-*`

- Principe : Top Cu / Prepreg(s) / L2–L3 (core + Cu interne) / Prepreg(s) / Bottom Cu. Ordre type : **SIG / GND / PWR / SIG** (usage recommandé, pas imposé par S1).
- Cuivre : externe 1 ou 2 oz ; interne 0,5 / 1 / 2 oz (défaut 0,5 oz). Dimensions max. FR4 4 couches : 663 × 593 mm (jusqu'à 1016 × 596 mm en rallongé).
- Exemple le plus courant — **JLC04161H-7628, 1,6 mm, 1 oz ext. / 0,5 oz int.** (S2) :
  - Top Cu 0,035 mm / Prepreg 7628×1 0,2104 mm / L2–L3 core 1,065 mm (1,1 mm avec cuivre 0,5 oz) / Prepreg 7628×1 0,2104 mm / Bottom Cu 0,035 mm.
- Variantes courantes (S2, même structure, seuls prepreg/core changent) : `JLC04161H-3313` (3313×1 0,0994 mm + core 1,265/1,3 mm), `JLC04161H-1080` (1080×1 0,0764 mm + core 1,265/1,3 mm), `JLC04161H-2116` (2116×1 0,1164 mm + core 1,265/1,3 mm). 19 déclinaisons `JLC04161H-*` listées en S2 selon épaisseur finie (0,8 / 1,0 / 1,2 / 1,6 / 2,0 mm) et type de prepreg.
- Matériaux (S3) : core **Nan Ya NP-155F** (4–8 couches), **SYTECH S1000-2M** au-delà de 10 couches ; Dk core **4,6**, masque **3,8** (S2). Cuivre interne 0,5 oz = 15,2 µm effectif (S3).
- Impédance contrôlée : couches 4/6/8/…/32 (S1) ; tolérance **±10 %** standard, ±5 % sur demande spéciale (FAQ S1).

## 4. Tolérances et finitions (S1 sauf mention)

| Paramètre | Valeur |
|---|---|
| Épaisseur carte | ±10 % si ≥ 1,0 mm (1,6 mm → 1,44–1,76 mm) ; ±0,1 mm si < 1,0 mm (0,8 mm → 0,7–0,9 mm) |
| Dimensions / découpe | CNC ±0,2 mm régulier / ±0,1 mm précision ; V-score ±0,4 mm ; garde cuivre→bord fraisé ≥ 0,2 mm ; cuivre→rainure V-cut ≥ 0,4 mm ; V-cut : ép. ≥ 0,6 mm, panneau 70×70 à 475×475 mm, angle 25°, espacement inter-rainures ≥ 2 mm (3 mm recommandé) |
| Masque (soldermask) | LPI ; depuis la bascule LDI de juin 2025, ouverture 1:1 ; garder ≥ 0,09 mm entre ouvertures et pistes voisines ; pont (bridge) 0,10 mm (vert/rouge/jaune/bleu/violet 1 oz), 0,13 mm (noir/blanc 1 oz), 0,20 mm (2 oz toutes couleurs) ; vias bouchés ≤ 0,50 mm Ø, à ≥ 0,35 mm des autres ouvertures ; Via-in-Pad résine/pâte Cu + capuchonnage, standard dès 6 couches, Ø 0,15–0,55 mm |
| Sérigraphie | trait ≥ 0,15 mm ; hauteur texte ≥ 40 mil (1,0 mm) ; ratio l/h 1:6 (y c. caractères évidés) ; pastille→sérigraphie ≥ 0,15 mm |
| Finitions | HASL (plombé/sans plomb), ENIG, OSP — **sauf** : alu → HASL uniquement ; pas de HASL sur FR4/HDI ≥ 6 couches, ép. ≤ 0,4 mm, hyperfréquences, cuivre, FPC ; pas d'OSP sur FR4 simple face, FPC, alu |
| Matériau | FR-4 grade A (Nan Ya, KB, Shengyi…) ; RF : Rogers/PTFE 2 couches 1 oz ; alu/cuivre 1 couche (S1) |

## 5. Points « à vérifier » (pas de source officielle trouvée)

1. Build-up **1 couche** exact (core + cuivre par épaisseur).
2. Build-up **2 couches** exact par épaisseur (référence core du devis).
3. Règles fines **assemblage CMS** (espacements composants, panelisation outillée 5 mm / trous 2 mm / fiducials — mentionnées dans la section mouse-bites de S1 mais relever les cotes PCBA sur la page PCBA, hors périmètre de S1).
4. Toute valeur issue de blogs/forums (ex. guides « 5 mil 2L / 3,5 mil 4–6L », min. via 0,45/0,2 mm) : utile comme recoupement mais **non retenue** tant que S1/S2/S3 ne la confirment pas.

## 6. Conséquence pratique pour nos règles

- Règle de base sûre (1 oz) : **0,127 mm (5 mil) mini** en 2 couches avec marge (le 4 mil étant le plancher S1), **0,09 mm (3,5 mil)** en multicouche ; clairières ≥ 0,10–0,15 mm ; via préféré **≥ 0,20 mm trou / ≥ 0,35–0,45 mm pastille** (plancher 0,15/0,25 mm = surcoût/risque) ; PTH ≥ 0,50 mm ; anneaux et gardes bord ci-dessus ; impédance ±10 % avec stackup `JLC04161H-*` imposé par le calculateur.
