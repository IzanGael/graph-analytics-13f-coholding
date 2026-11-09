# Démo Neo4j pour la soutenance (tribus de co-conviction)

Démo exploration/visualisation uniquement pour la soutenance orale — ne fait pas partie du pipeline
noté (`s01`-`s04`, `src/regimes/`) et ne touche ni `data/`, ni `results/`. Voir `docs/STATUS.md`
(section "Neo4j defense demo built") et `docs/AI_USE.md` pour le contexte complet.

## Contenu de ce dossier

| Fichier | Rôle |
|---|---|
| `build_demo_data.py` | Recalcule le graphe de conviction (2022Q2, 2026Q2) et génère les CSV dans `export/`. Déjà exécuté — les CSV sont prêts à charger. |
| `export/*.csv` | Les 5 fichiers à copier dans le dossier `import` de Neo4j : `stocks.csv`, `managers.csv`, `tribes.csv`, `co_bet.csv`, `bets_on.csv`. |
| `load.cypher` | Crée les contraintes et charge les 5 CSV (nœuds Stock/Manager/Tribe/Sector, relations BETS_ON/CO_BET/IN_TRIBE/IN_SECTOR). À copier-coller tel quel dans Neo4j Browser. |
| `scenes.cypher` | Les 4 requêtes des scènes de la présentation (le hook, un lien, la carte des tribus, 2022 vs 2026), chacune avec le texte à dire. À copier-coller une par une, puis sauvegarder en Favori (⭐). |
| `screenshots/` | Captures de secours de chaque scène, à coller dans les slides si Neo4j ou le wifi lâche le jour J. |
| `RESTART.md` | Notes pour l'instance Neo4j qui tournait sous WSL (ancienne mise en place) — pour Neo4j Desktop, ce fichier ne s'applique pas, voir ci-dessous à la place. |

Aucun de ces fichiers n'est modifié par la mise en place ci-dessous : `load.cypher` et `scenes.cypher`
restent la seule source des requêtes, copiez-collez leur contenu directement.

## Mise en place sur Neo4j Desktop (Windows)

### 1. Installer Neo4j Desktop
Télécharger depuis neo4j.com/download, installer, activer avec la clé gratuite fournie sur la page de
téléchargement.

### 2. Créer un DBMS local
**New** → **Local DBMS** → nommer (ex. `tribus-13f`) → choisir une version récente (5.26) → définir un
mot de passe → **Create**, puis **Start**.

Contrairement à l'instance de test sous WSL utilisée plus tôt, ce DBMS a l'authentification **activée**
par défaut : notez le mot de passe choisi, vous en aurez besoin à l'étape 6 (nom d'utilisateur `neo4j`).

### 3. Localiser le dossier `import` de ce DBMS précis
Clic sur les `...` à côté du DBMS **démarré** (vert) → **Open folder** → **Import**. Une fenêtre
Explorateur s'ouvre sur ce dossier exact — c'est le seul endroit où Neo4j ira chercher les CSV.

### 4. Copier les 5 CSV
Dans une autre fenêtre Explorateur, ouvrir :
```
\\wsl.localhost\Ubuntu-24.04\home\ryanebanda\workspace\graph-analytics-13f-coholding\neo4j\export
```
Copier les 5 fichiers (`stocks.csv`, `managers.csv`, `tribes.csv`, `co_bet.csv`, `bets_on.csv`)
**directement** à la racine du dossier `import` ouvert à l'étape 3 (pas dans un sous-dossier).

### 5. Vérifier (optionnel mais recommandé)
Ouvrir Neo4j Browser (bouton **Open** sur le DBMS), se connecter (étape 6), puis lancer :
```
CALL dbms.listConfig('server.directories.import') YIELD name, value RETURN name, value;
```
Le chemin renvoyé doit correspondre à celui ouvert à l'étape 3. Si ce n'est pas le cas, c'est que
Browser est connecté à un autre DBMS que celui où les fichiers ont été copiés.

### 6. Se connecter à Neo4j Browser
Bouton **Open** sur le DBMS démarré → Browser s'ouvre dans le navigateur Windows normal.
Si une fenêtre de connexion apparaît : **Authentication type = Username / Password**, nom
d'utilisateur `neo4j`, mot de passe choisi à l'étape 2 (pas "No authentication" cette fois).

### 7. Charger les données
Ouvrir `load.cypher` (chemin ci-dessous) avec le Bloc-notes, copier tout son contenu, le coller dans
la barre de requête de Browser, exécuter (▶). Ça crée les contraintes et charge les 5 CSV.
```
\\wsl.localhost\Ubuntu-24.04\home\ryanebanda\workspace\graph-analytics-13f-coholding\neo4j\load.cypher
```
Vérification rapide :
```
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC;
```
Attendu : Stock (261), Tribe (19), Sector (12), Manager (9).

### 8. Charger les 4 scènes et les sauvegarder en Favoris
Ouvrir `scenes.cypher` (même dossier), copier-coller chaque bloc `SCENE 1` à `SCENE 4` un par un
(le commentaire `//` au-dessus de chaque requête peut rester, il sert de titre au Favori), exécuter,
puis cliquer l'étoile ☆ à droite de la barre de requête pour sauvegarder. Les 4 apparaissent ensuite
dans le panneau Favoris (icône étoile, colonne de gauche), dans l'ordre de la présentation.

## Dépannage

- **`22N43 ... unable to load external resource`** : le fichier n'est pas au bon endroit. Refaire
  l'étape 5 pour confirmer le dossier `import` exact, puis l'étape 4.
- **Fenêtre de connexion qui boucle / "Connecting..."** : mauvais mot de passe, ou authentification
  réglée sur "No authentication" alors que ce DBMS en a besoin — repasser sur "Username / Password".
- **Les favoris ne s'affichent pas en graphe mais en tableau** : cliquer l'icône "Graph" dans la
  colonne de gauche du résultat (à côté de "Table" et "Text").

## Le jour J

- Démarrer le DBMS dans Neo4j Desktop *avant* la soutenance (ça prend quelques secondes).
- Ouvrir Browser, cliquer les 4 Favoris dans l'ordre pendant les 8 minutes — rien à taper en direct.
- Secours : les captures dans `screenshots/` si Neo4j ou le wifi lâche.
