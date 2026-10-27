# Recherche — Bonnes pratiques placement PCB et keepout radio

- Ticket : Marwichmisi/NIA-CAD#12 (« Quelles regles de placement initial figer dans le pipeline ? »)
- Date de consultation des sources : 2026-10-27 (UTC)
- Sources : **primaires uniquement** (docs fabricants, app notes, docs outils). Toute valeur sans source primaire est marquée « à vérifier ».
- Branche : `research/placement` — fichier `FINDINGS.md` (worktree isolé, aucun merge, aucune PR).

## Sources primaires consultées

| # | Source | URL / référence | Contenu exploité |
|---|--------|-----------------|------------------|
| S1 | Espressif — ESP32 Hardware Design Guidelines, chap. « PCB Layout Design » (doc officiel, consulté en ligne) | https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/pcb-layout-design.html | Empilements 2/4 couches, alim + découplage, quartz, RF 50 Ω, placement module + keepout, UART/SDIO |
| S2 | Espressif — ESP32-WROOM-32E / 32UE Datasheet v1.6 + ESP32-WROOM-32 Datasheet v3.8 (PDF fabricant) | https://cdn.sparkfun.com/assets/4/3/1/7/6/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en_v1-6.pdf ; https://documentation.espressif.com/esp32-wroom-32_datasheet_en.pdf | Zone antenne (dimensions), marquage keepout, renvoi placement vers S1 |
| S3 | TI — SZZA009 « PCB Design Guidelines For Reduced EMI » (nov. 1999, PDF, texte intégral extrait) | https://www.ti.com/lit/pdf/szza009 | Microcomputer ground, gridding 2 couches, bypass/ferrite, star, zoning, quartz (1 inch), connecteurs/ESD |
| S4 | ST — AN2867 « Guidelines for oscillator design on STM8/STM32 » Rév. 19 (PDF via miroir ECS, §5.7 + fig. 13/14) | https://www.ecsxtal.com/store/pdf/stm32-microcontroller-application-note.pdf (miroir du doc ST) | Quartz au plus près du MCU, pistes courtes, anneau de garde, plan de masse local dédié |
| S5 | NXP — AN14518 « Crystal Oscillator Design Guide » Rév. 6.0 (avr. 2026, PDF, §6) | https://www.nxp.com/docs/en/application-note/AN14518.pdf | Cibles chiffrées quartz : pistes ≤ 5 mm, espacement ≥ 0,5 mm, largeur ≤ 0,15 mm, sans vias, keep-out, condos proches |
| S6 | ADI — lignée MT-031/MT-101 via Porley, « Basic Guidelines for Mixed-Signal PCB Layout Design » (Electronic Design, avr. 2023 ; cite MT-031, MT-101, Data Conversion Handbook) | https://www.electronicdesign.com/technologies/analog/article/21263439/analog-devices-basic-guidelines-for-mixed-signal-pcb-layout-design | Floorplan, découplage (0,01–0,1 µF au plus près, bulk 10–100 µF ≤ 1 inch), stackup 4 couches, plan de masse unique vs split + star |
| S7 | KiCad — PCB Editor Reference Manual 9.0, sections rule areas / board setup / custom rules / DRC | https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html | Rule areas (= keepouts), contraintes, net classes, custom rules, DRC |
| S8 | atopile — site + blog + repo GitHub (docs langage dans l'éditeur app.atopile.io) | https://atopile.io/ ; https://github.com/atopile/atopile ; https://docs.atopile.io/ | Checks à chaque build, règles de fabrication/layout, KiCad reste l'outil de layout |
| S9 | IPC-2221 — sommaire officiel IPC-2221A (TOC gratuit) + fiche boutique IPC-2221C | https://www.electronics.org/TOC/IPC-2221A.pdf ; https://shop.electronics.org/ipc-2221/ipc-2221-standard-only | Périmètre : §8 placement (§8.1.2), §6.3 distrib. V/GND, §9 trous/anneaux, §10 largeurs/espacements. **Texte intégral payant → valeurs chiffrées « à vérifier »** |

## R1 — Découplage au plus près des broches (FIGER)

- **R1.1.** Placer un condensateur de découplage HF (céramique, typ. 0,01–0,1 µF) **au plus près de chaque broche d'alimentation**, relié au plan de masse par via ou trace courte pour minimiser l'inductance série ; ajouter un réservoir bulk (typ. 10 µF côté Espressif, 10–100 µF côté ADI) **à l'entrée d'alim et à ≤ 1 inch de la broche**. (S1 §Power ; S6 §Decoupling Techniques)
- **R1.2.** Vias de masse **au plus près du pad GND du condensateur** (court chemin de retour) ; pastille thermique sous puce (QFN/ESP32) connectée par **≥ 9 vias** au plan de masse ; contact franc des pads au cuivre GND (pas de liaison par trace fine). (S1 §Four-Layer PCB Design)
- **R1.3.** Ramifier l'alim en **étoile** après le bulk d'entrée pour limiter le couplage entre broches ; boucle de bypass la plus petite possible (règle 3:1 longueur/largeur, TI) ; perle ferrite sur +V uniquement (jamais sur GND) avec 0,1/0,01 µF côté puce et ~1000 pF côté alim (filtre en π). (S1 §Power ; S3 §2.2.4)
- **R1.4.** Sur E/S lentes (fronts > 100 ns) : R série 50–100 Ω (sorties) / 35–50 Ω (entrées) **au plus près du MCU** + capa 1000 pF côté récepteur ; ne jamais appliquer ces filtres aux broches d'oscillateur. (S3 §2.2.5)
- Conditions : **toutes couches (1/2/4)**. En 1–2 couches sans plan complet, ajouter l'îlot « microcomputer ground » sous le MCU (dépassant ~1/4 inch du boîtier, S3 §2.1.3) et mailler (gridding) le GND (S3 §2.2.3).

## R2 — Module radio pré-certifié en bord de carte + keepout cuivre (FIGER)

- **R2.1.** Placer le module de sorte que **l'antenne PCB dépasse du bord de la carte de base, point d'alimentation au plus près du bord** (positions ✓ de S1). Si l'antenne reste au-dessus de la carte : **évider la carte de base des deux côtés de l'antenne et en dessous**, jamais de module au centre entouré de cuivre. (S1 §Positioning a Module on a Base Board ; S2 §10.2)
- **R2.2.** **Aucun cuivre (toutes couches), aucune piste, aucun composant** dans la zone d'antenne du module + dégagement ; garder **≥ 15 mm de clearance dans toutes les directions** à l'intérieur du boîtier produit fini. Cuivre GND + vias denses **autour** (pas dedans) de la zone côté carte de base. (S1 §Module + §RF ; S2 plan « Antenna Area / Keepout Zone »)
- **R2.3.** Variante connecteur d'antenne externe (ex. ESP32-WROOM-32UE) : **pas de keepout** (S2 §3.1 : « 32UE has no keepout zone ») — la règle keepout ne s'applique qu'aux modules à antenne PCB intégrée.
- **R2.4.** Tenir RF/HF à l'écart : RF 50 Ω sur couche externe **sans via**, courte, largeur constante, coudes à 135°/arcs, vias de garde denses ; USB/UART et quartz **loin de l'antenne et de la trace RF** (UART entouré de cuivre GND + vias). Valider le produit fini par **test débit/portée**. (S1 §RF)
- Conditions : **1/2/4 couches** (le keepout s'applique à toutes les couches quel que soit l'empilement).

## R3 — Connecteurs en bord de carte (FIGER)

- **R3.1.** Placer les **connecteurs au bord de la carte** (principe de floorplan, S6 §Component Placement) ; regrouper les fonctions par zones : logique rapide près de l'alim, circuits lents plus loin, analogique le plus loin (S3 §2.3).
- **R3.2.** À chaque fil qui entre/sort du boîtier : **capa de filtrage < 1000 pF (typ. ~470 pF) vers une zone de masse locale reliée au blindage**, liaison large et courte (règle 3:1), vissée en ≥ 2 points ; jamais de trace bruyante en bordure extérieure. (S3 §2.5.4, §2.5.5, §3.3 ; S3 §2.4.1)
- **R3.3.** Retours : 1 GND pour ≤ 9 signaux (1:5 à haut débit, 1:4 si câble > 1 ft) ; idéalement 1 retour par signal en paire torsadée. (S3 §2.5.3)
- Conditions : **toutes couches** ; en 1–2 couches, soigner la liaison masse carte↔blindage (étrier métallique si 2 cartes, S3 §2.5.3).

## R4 — Quartz / horloge au plus près du MCU (FIGER)

- **R4.1.** Monter le quartz **au plus près des broches OSC du MCU, pistes les plus courtes possibles** (cible NXP : **≤ 5 mm**, largeur **≤ 0,15 mm**, espacement XTAL1/XTAL2 **≥ 0,5 mm**, symétriques, **sans vias**) ; composants série côté puce ; capas de charge **de chaque côté du quartz, au plus près** (C0G/NP0, tol. ≤ 2–5 %), pads GND des capas proches de celui du quartz. (S4 §5.7 ; S5 §6 ; S1 §Crystal)
- **R4.2.** **Anneau de garde** relié à la masse autour des connexions d'oscillateur ; **plan de masse local dédié sous l'oscillateur** (distinct du plan applicatif, relié à la masse MCU la plus proche) ; aucun boîtier métallique de quartz relié à cette masse locale. (S4 §5.7 + fig. 13/14)
- **R4.3.** **Aucune piste HF ni aucun signal sous le quartz** ; pistes d'alim latérales éloignées, entourées de cuivre GND ; aucun composant étranger à **< 1 inch** du quartz (TI) ; tenir inductances et aimants à l'écart ; router quartz + boucle à la main, **jamais à l'autorouteur**. (S1 §Crystal ; S3 §2.4.1, §2.6.3 ; S5 §6)
- Cas particulier ESP32 : S1 impose en outre **≥ 2,7 mm entre le quartz et la broche d'horloge**, vias GND denses autour de la piste d'horloge, et **aucun via sur les traces d'horloge IN/OUT**. (S1 §Crystal — valeur ESP32, ne pas généraliser telle quelle)
- Conditions : **2/4 couches** (plan de référence obligatoire). Les cotes S5 (5 mm / 0,5 mm / 0,15 mm) viennent d'un guide NFC : **applicables comme cibles par défaut en IoT basse fréquence, « à vérifier » au cas du MCU exact**.

## R5 — Plans GND et retours de courant (FIGER)

- **R5.1.** Empilement recommandé **4 couches : TOP signal / L2 GND complet (aucun signal) / L3 PWR (+ quelques signaux, GND sous RF et quartz) / BOT quelques signaux, pas de composants**. En **2 couches : TOP signaux, BOT minimum de pistes, plan GND complet conservé sous puce + RF + quartz**. (S1 §General Principles)
- **R5.2.** L'alim ne transporte que du **courant continu de recharge** des capas ; le courant HF de commutation vient des capas de bypass, pas du régulateur (S3 §2.1). Ne jamais fendre le plan (pas de slot, pas de trace enterrée dans GND ; pastilles 100 mil reliées par brins de cuivre, pas par fente). (S3 §2.1.1, §2.1.7)
- **R5.3.** **Un seul plan de masse solide** pour les systèmes mixtes à faible courant numérique (cas IoT typique à 1 ADC/DAC) ; ne splitter AGND/DGND (jonction **star en un point unique**, tracés larges) que pour les systèmes multi-convertisseurs à fort courant numérique ; vérifier la reco de masse de chaque datasheet. (S6 §Ground Plane ; lignée MT-031)
- **R5.4.** En 2 couches sans plan : **gridding** (treillis de masse orthogonal + remplissages reliés aux 2 bouts + vias nombreux) pour émuler le plan et offrir un retour sous chaque signal ; point unique reliant régulateur + masse micro + batterie + blindage. (S3 §2.2.1–§2.2.3)
- Conditions : 4 couches recommandées dès qu'il y a de la radio ; 2 couches acceptables avec GND complet local + gridding ; **1 couche : pas de plan possible → « à vérifier » (déconseillé avec radio, filtrage agressif requis)**.

## R6 — Ordre de placement / floorplan pipeline (FIGER comme checklist)

1. MCU **à côté du régulateur**, lui-même **à côté de l'entrée VBatt**, nappes de masse larges entre les trois = point unique de masse + reprise blindage. (S3 §2.3)
2. Bloc d'alim **isolé du reste mais proche des charges**, routage court et large. (S6 §Power-Supply Block)
3. Placer d'abord quartz + découplage + RF/antenne, puis connecteurs de bord, puis le reste en suivant le **chemin du signal du schéma**. (S6 §Component Placement ; S3 §2.3)
4. Signaux sensibles (reset, interrupts, osc) traités comme la RF (petites boucles, éloignés du bruit). (S3 §2.6.2)

## Traduction pipeline agentique (KiCad / atopile)

- **Keepout radio → rule area KiCad** (ancien nom « keepout ») : restreint placement + remplissage de zones, avec **custom rules DRC** pour l'appliquer par net/classe ; les violations sortent au DRC. (S7 §Rule areas, §Custom Rules, §Design rules checking)
- **Contraintes JLCPCB + stackup** déjà figées dans `research/jlcpcb-rules` : les reporter en **Board Setup → Constraints / Net Classes** (les minima Board Setup sont absolus, S7).
- **Proximité découplage/quartz → checklist de revue**, pas de DRC natif : les longueurs/tensions ne sont pas contraignables par les rule areas standards. Piste : règle custom ou script `kicad-cli pcb` — **« à vérifier »** (étude scripting KiCad non faite ici).
- **atopile** : le compilateur rejoue des **checks à chaque build** (règles fabrication + layout, S8 blog 0.16.15) et KiCad reste l'outil de layout ; la liste exacte des 15 types de règles versionnée est **« à vérifier »** contre la version atopile utilisée.

## Points « à vérifier » (pas de source primaire confirmée)

1. **IPC-2221 chiffré** : §8 placement, §10 routage/espacements, §6.3 V/GND, §9 anneaux/thermal relief — texte intégral payant (S9). Ne rien figer de chiffré au nom d'IPC-2221 sans l'acheter.
2. **1 couche + radio** : aucune source primaire ne valide un placement radio propre sur simple face.
3. **Cotes NXP S5** (5 mm / 0,5 mm / 0,15 mm) hors contexte NFC : cibles par défaut raisonnables, à confirmer par le datasheet du MCU retenu.
4. **Automatisation DRC de la proximité** (découplage/quartz) via custom rules ou scripting KiCad.
5. **Liste versionnée des checks atopile** réellement actifs sur notre version.
6. **ESD stylet/boîtier et tests CEM** : hors périmètre de cette recherche (S1/S3 donnent les principes, pas de plan de test).

## Conséquence pratique (règles minimales à figer maintenant)

- Découplage HF au plus près + bulk à l'entrée + vias GND courts + étoile ; keepout radio total toutes couches + antenne en bord (≥ 15 mm en boîtier) + test portée ; connecteurs en bord + filtrage < 1000 pF vers blindage ; quartz collé au MCU + anneau de garde + plan local + zero HF dessous ; 4 couches TOP/GND/PWR/BOT dès qu'il y a de la radio (2 couches tolérées avec GND complet + gridding) ; floorplan MCU–régulateur–VBatt groupés.
