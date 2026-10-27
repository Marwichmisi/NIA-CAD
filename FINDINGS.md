# Recherche — source légale pièces / stock / prix JLCPCB + LCSC (v1)

- Ticket : [#6 — Recherche — source legale pieces stock prix JLCPCB LCSC](https://github.com/Marwichmisi/NIA-CAD/issues/6) (ouvert, non fermé par ce travail)
- Carte parente : #1 (non touchée)
- Branche : `research/parts-source` — aucun merge, aucune PR
- Date de recherche : 2026-10-27
- Question tranchée : comment obtenir pièces, stock, prix et type Basic/Extended de manière **légale et stable** (API officielle, endpoints, quotas, CGU, cache) chez JLCPCB/LCSC en v1 ?
- Règle de marquage : tout ce qui n'est pas confirmé par une source officielle ci-dessous est marqué « **à vérifier** ».

## Réponse courte (méthode recommandée v1)

1. **Source prix/stock/fiches pièces = API officielle LCSC** (`lcsc.com/docs`, 8 services). C'est la seule API documentée publiquement avec endpoints, auth et CGU explicites.
2. **Type Basic/Extended et prix d'assemblage = JLCPCB officiel** : pages Help Center (définitions + grille tarifaire) **+ demande d'accès à la « Parts/Components API »** via `api.jlcpcb.com` (accès sur dossier, documentation derrière compte — endpoints exacts **à vérifier** après inscription).
3. **Ne pas scraper** `jlcpcb.com/parts` ni les endpoints web non documentés (y compris les endpoints CSRF cités par `jlcparts/LCSC-API.md`) : contraire aux CGU (voir §5), fragile (coupure historique constatée en nov. 2022 côté communauté — confirmation officielle **à vérifier**).
4. **Cache local v1** : SQLite/mémoire avec TTL court, jamais redistribué ni agrégé en service public (CGU LCSC l'interdisent), attribution « source : LCSC » conservée.

## 1. JLCPCB — API officielle (JLCAPI)

Sources primaires :
- [JLCPCB Online API Access Application](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now) (Help Center, màj 2026-09-09)
- [Plateforme JLC API](https://api.jlcpcb.com/) (page d'accueil + [docs](https://api.jlcpcb.com/docs/start), accès après inscription)

Constats :
- JLCPCB expose **4 API** : **PCB**, **SMT Stencil**, **3D Printing**, **Parts (dite aussi « Components API »)**.
  - « Parts API : Provides access to component data from JLCPCB's parts library … specifications, availability, and pricing, to support BOM management and component selection. » ([source](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now))
  - « Components API … gives you access to millions of components … real-time pricing, inventory data, and component specifications » ([source](https://api.jlcpcb.com/))
- **Accès sur candidature uniquement** : inscription via `api.jlcpcb.com`, « not all applications will be approved; each application undergoes a review based on the partner's previous orders at JLCPCB, company and business situation » ; compte JLCPCB requis ; support `support@jlcpcb.com`, pas de revue de code fournie ([source](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now)).
- **Contraintes partenaires** : interdiction d'utiliser la marque JLCPCB sur son site, d'inclure « JLC » dans ses URL, d'utiliser le logo en publicité — suspension immédiate en cas de violation ([source](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now)).
- **Endpoints exacts, quotas, modèle d'auth de la Parts API : à vérifier** — la documentation détaillée est derrière inscription/connexion (la page `/docs/start` ne liste publiquement que les 4 produits). Ne pas inventer d'URL d'endpoints JLCPCB.
- Étapes v1 : créer le compte → candidater sur `api.jlcpcb.com` → créer une app → intégrer selon la doc fournie après approbation (parcours « 3 steps » de la plateforme, [source](https://api.jlcpcb.com/)).

## 2. LCSC — API officielle (documentée publiquement)

Sources primaires :
- [LCSC API Instruction](https://www.lcsc.com/docs/index.html) (vue d'ensemble, auth, erreurs, CGU)
- [LCSC OpenAPI](https://www.lcsc.com/docs/openapi/index.html) (endpoints, paramètres)
- [LCSC API Solutions / agent](https://www.lcsc.com/agent/) (porte d'entrée : compte + dossier + clé via `support@lcsc.com`)
- [LCSC API FAQ](https://www.lcsc.com/help-center/api) et [API characteristics](https://www.lcsc.com/help-center/api/api-characteristics) (contexte)

### 2.1 Obtention de l'accès
1. Créer un compte sur `LCSC.COM`.
2. Déposer un dossier (site web d'entreprise, licence business ou équivalent, coordonnées, volume de commande estimé, mode de coopération).
3. Demander la clé API à `support@lcsc.com` ([source](https://www.lcsc.com/docs/index.html)).

### 2.2 Authentification (chaque appel)
Paramètres obligatoires : `key` (user ID), `nonce` (aléatoire 16 caractères), `timestamp`, `signature` ; le `secret` ne transite jamais en paramètre ([source](https://www.lcsc.com/docs/index.html)).
Formule officielle : `signature = sha1(key=xxx&nonce=xxx&secret=xxxx&timestamp=xxx)`, vérifiée côté serveur ; **requête refusée si `timestamp` vieux de plus de 60 s** ([source](https://www.lcsc.com/docs/index.html)).

### 2.3 Endpoints (base `rest/wmsc2agent/…`, méthode GET/POST selon cas)
| Usage v1 | Endpoint (chemin relatif doc) | Notes |
|---|---|---|
| Catégories | `GET rest/wmsc2agent/category` | arbre catégories + sous-catégories |
| Fabricants | `GET rest/wmsc2agent/brand` | infos fabricants |
| Liste par catégorie | `GET rest/wmsc2agent/category/product/{category_id}` | `page_size` défaut 100 ; filtre `is_available`, `is_pre_sale`, devises |
| Détail pièce (+ prix/stock) | `GET rest/wmsc2agent/product/info/{product_number}` | `product_number` = réf LCSC ; devises USD/CNY/EUR/HKD |
| Recherche mot-clé | `GET rest/wmsc2agent/search/product` | `keyword` (SKU/MPN/catégorie/fabricant), `match_type` exact/fuzzy, `limit` 1–500, `offset` ≥ 0 ; la description annonce « maximum 30 parts per page » alors que `page_size` défaut = 100 → **à vérifier** |
| Création commande | `POST rest/wmsc2agent/submit/order` | max 50 produits/appel, 500/panier |
| Suivi commande | `GET rest/wmsc2agent/select/order/page` | max 10 codes/requête |
| Expédition | `POST rest/wmsc2agent/get/shipment` | devis transport par pays/état |

([source](https://www.lcsc.com/docs/openapi/index.html) ; limites `limit`/`offset`/devises confirmées par les [codes d'erreur 4010–4028](https://www.lcsc.com/docs/index.html))

### 2.4 Quotas et erreurs
- Codes rate-limit documentés : **429** (trop de requêtes/minute) et **430** (quota journalier dépassé) — **les seuils chiffrés ne sont pas publiés → à vérifier** auprès de LCSC ([source](https://www.lcsc.com/docs/index.html)).
- Autres erreurs : auth (5003/4001–4006), validation (4010–4038), IP non whitelistée (403/5002), système (5001).
- Réponse uniforme : `{ success, code, message, result }`, succès = `code 200` ([source](https://www.lcsc.com/docs/index.html)).

### 2.5 CGU API LCSC (bloquantes pour v1 — citations de la source)
Par l'usage des API LCSC, l'utilisateur accepte notamment ([source](https://www.lcsc.com/docs/index.html), « API Terms of Use ») :
- pas de **capture massive** (« bulk data capture ») ;
- pas d'**hébergement ni fourniture à un tiers** du matériel récupéré (datasheets, images) ;
- pas de **vente** des informations ni de dérivés ;
- pas de **partage** d'`uuid`/`apikey` hors entreprise, pas de cession ;
- pas d'**agrégation** des données dans d'autres API/services commerciaux publics ;
- **attribution obligatoire** : identifier LCSC comme source ;
- pas de partage de la doc technique, **pas de reverse engineering** ;
- pas de menace sur l'intégrité/perf/fiabilité des API (tests de charge interdits) ;
- LCSC peut modifier les conditions à tout moment ; révocation d'accès en cas de manquement.
- Conséquence v1 : **cache strictement local/privé**, pas de miroir public, pas de revente de données, attribution conservée, pas de stress-test.

## 3. Basic / Extended / Preferred — définitions et tarifs (JLCPCB officiel)

Sources primaires :
- [PCB Assembly FAQs](https://jlcpcb.com/help/article/pcb-assembly-faqs) (màj 2026-09-09)
- [PCB Assembly Cost](https://jlcpcb.com/help/article/pcb-assembly-price) (màj 2026-10-22 ; prix « may vary slightly due to exchange rate »)
- [Basic & Promotional Extended Components](https://jlcpcb.com/parts/basic_parts) (liste ; 1 586 articles affichés le 2026-10-27)

Constats :
- **Basic** : pièces d'usage fréquent déjà chargées sur les machines P&P (ex. résistances/condensateurs puce) — pas de changement de feeder, **pas de coût de main-d'œuvre** ([source FAQ Q6](https://jlcpcb.com/help/article/pcb-assembly-faqs)).
- **Extended** : le opérateur doit monter les feeders manuellement → surcoût ([source FAQ Q6](https://jlcpcb.com/help/article/pcb-assembly-faqs)).
- **Preferred Extended** : ex-Basic reclassées Extended mais **chargées manuellement sur les P&P** ; avantage = **exemption du « Feeder Loading fee » en Economic PCBA** (FAQ Q7). La page `basic_parts` regroupe « Basic & Promotional Extended » à **0 $ de Feeder Loading Fees en Economic PCBA** ([source](https://jlcpcb.com/parts/basic_parts)).
- Tarifs feeder (grille 2026-10-22) : **Economic PCBA = 3,07 $ par Extended** ; **Standard PCBA = 1,53 $ par Basic/Extended** ([source](https://jlcpcb.com/help/article/pcb-assembly-price)). La FAQ (2026-09-09) cite encore « $3 per extended component » : écart de 0,07 $ probablement lié au change/à la màj — **retenir la grille du 2026-10-22, à re-vérifier à l'usage**.
- Volumes catalogue : la FAQ annonce « about 40k+ kinds … including 698 kinds of basic components and 300k+ extended components » — chiffres **incohérents entre eux (40k vs 300k) → à vérifier** ; la page `basic_parts` affiche 1 586 articles Basic/Promo le 2026-10-27 (constat d'affichage, pas une spec).
- Fichiers requis pour un ordre PCBA : Gerber + BOM + CPL (voir FAQ Q8) — utile pour cadrer la v1 (BOM Tool manuel en fallback : [Bom Tool](https://jlcpcb.com/parts/bom-tool)).

## 4. Voies NON officielles — à exclure de la v1 (ou usage hors CGU)

- **CSV/XLS historique JLCPCB + `yaqwsx/jlcparts`** (MIT, recherche paramétrique, cache SQLite/IndexedDB) : le README décrit un pipeline « Travis CI download XLS spreadsheet from the JLC PCB page » ([source](https://github.com/yaqwsx/jlcparts)). Un fil d'entraide JLCPCB rapporte une coupure de la fourniture de données le 2022-11-25 (« JLC stopped providing part data ») — **témoignage d'utilisateur, sans réponse officielle visible sur la page → à vérifier**, mais le risque de rupture unilatérale est avéré par construction. Usage v1 : **non recommandé** (ni légal-stable, ni contractuel).
- **Endpoints web LCSC non documentés** (`lcsc.com/api/global/additional/search`, `lcsc.com/api/products/search` avec CSRF + cookies) décrits dans [`jlcparts/LCSC-API.md`](https://github.com/yaqwsx/jlcparts/blob/master/LCSC-API.md) : **non officiel**, contourne l'auth par clé, fragile et contraire aux CGU API (bulk capture / reverse engineering) → **à exclure**.
- **Endpoints EasyEDA évoqués sur le forum** ([ex.](https://easyeda.com/forum/topic/LCSC-Search-API-4e8fefbdbdd24c3ca20395ae46d7b6)) : pas de doc officielle trouvée → **à vérifier / à exclure** en v1.
- **Agrégateurs tiers payants** (ex. scraping Apify « LCSC BOM Checker ») : ni officiel ni gratuit, CGU LCSC interdisant la revente/agrégation → **à exclure**.
- **CGU générales JLCPCB** ([Terms & Conditions](https://jlcpcb.com/help/article/Terms-%26-Conditions), effet 2025-11-17) : contenus du site propriété JLCPCB/licenciés, usage autorisé « for personal, informational and noncommercial purposes only », interdiction de copier/distribuer/transmettre/reproduire/publier sans autorisation (section VI « Copyright and Ownership ») ; droit applicable Hong Kong, arbitrage HKIAC. **Interprétation prudente** : le scraping automatisé de `jlcpcb.com/parts` n'est pas couvert par ces CGU → ne pas le faire sans accord écrit ; point juridique fin **à vérifier** avec un juriste si besoin, mais la voie API partenaire existe donc il faut l'utiliser.

## 5. Recommandation cache v1 (compatible CGU)
- **Couche 1 — temps réel** : appels API officielle LCSC (détail/recherche) + Parts API JLCPCB (après approbation) pour stock/prix/disponibilité au moment du devis.
- **Couche 2 — cache local privé** : SQLite/champ `updated_at`, TTL court (ex. 24 h pour prix/stock — valeur d'implémentation **à vérifier/à calibrer**, pas une exigence fournisseur), clé = réf LCSC + devise ; **jamais exposé publiquement, jamais revendu, attribution LCSC conservée**.
- **Couche 3 — fallback manuel** : BOM Tool JLCPCB + pages `parts`/`basic_parts` consultées à la main (pas de robot).
- **Garde-fous** : backoff sur 429/430, respect du `timestamp` 60 s LCSC, `signature` SHA-1 exacte, pagination (`limit`/`offset`), pas de tests de charge.
- **Secrets** : aucune clé dans le repo ni dans ce document (aucune clé n'a été demandée ni stockée pendant cette recherche).

## 6. Points « à vérifier » restants (avant d'implémenter)
1. Endpoints, auth et quotas exacts de la **JLCPCB Parts/Components API** (doc derrière compte `api.jlcpcb.com`) + délai/conditions d'approbation du dossier.
2. Seuils chiffrés des quotas LCSC (429/minute, 430/jour) et politique IP whitelist.
3. Contradiction `search/product` : « max 30 parts per page » vs `page_size` défaut 100.
4. Chiffres catalogue FAQ (40k+ vs 300k+ extended) et périmètre exact « 6.4M+ verified part numbers » de la page marketing ([source](https://jlcpcb.com/parts)).
5. Statut officiel de la coupure de données de nov. 2022 (le fil Q&R n'affiche pas de réponse officielle).
6. Qualification juridique fine du scraping sous CGU JLCPCB si un jour nécessaire (voie API à privilégier, rend ce point non bloquant).

## 7. Sources (toutes consultées le 2026-10-27, sans clé)
1. https://jlcpcb.com/help/article/jlcpcb-online-api-available-now
2. https://api.jlcpcb.com/ et https://api.jlcpcb.com/docs/start
3. https://jlcpcb.com/help/article/pcb-assembly-faqs
4. https://jlcpcb.com/help/article/pcb-assembly-price
5. https://jlcpcb.com/parts/basic_parts et https://jlcpcb.com/parts
6. https://jlcpcb.com/help/article/Terms-%26-Conditions
7. https://jlcpcb.com/help/answers/detail/19-API-Data-JLC-Part-Library (témoignage utilisateur, pas une position officielle)
8. https://www.lcsc.com/docs/index.html
9. https://www.lcsc.com/docs/openapi/index.html
10. https://www.lcsc.com/agent/
11. https://www.lcsc.com/help-center/api (FAQ) — page consultée (contenu catalogue, pas d'endpoint)
12. https://github.com/yaqwsx/jlcparts (README) + https://github.com/yaqwsx/jlcparts/blob/master/LCSC-API.md (voies non officielles, citées pour les exclure)
