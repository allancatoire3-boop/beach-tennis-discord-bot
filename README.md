# Bot Discord — tournois de Beach Tennis

Ce projet vérifie chaque jour les nouveaux tournois publiés sur Ten'Up dans un rayon d'environ 200 km autour de Montpellier. Il envoie uniquement les nouveaux tournois dans un salon Discord.

## 1. Créer le webhook Discord

1. Ouvre ton serveur Discord.
2. Clique sur la roue dentée du salon qui doit recevoir les notifications.
3. Va dans **Intégrations** puis **Webhooks**.
4. Clique sur **Nouveau webhook**.
5. Donne-lui un nom, par exemple `Tournois Beach Tennis`.
6. Vérifie le salon choisi.
7. Clique sur **Copier l'URL du webhook**.

Ne publie jamais cette URL dans un fichier ou un message public : elle permet d'écrire dans ton salon.

## 2. Ajouter le webhook comme secret GitHub

1. Dans ce dépôt, ouvre **Settings**.
2. Dans la colonne de gauche, ouvre **Secrets and variables** puis **Actions**.
3. Clique sur **New repository secret**.
4. Dans **Name**, écris exactement : `DISCORD_WEBHOOK_URL`
5. Dans **Secret**, colle l'URL copiée depuis Discord.
6. Clique sur **Add secret**.

## 3. Autoriser GitHub Actions à mémoriser les tournois

1. Dans **Settings**, ouvre **Actions** puis **General**.
2. Descends jusqu'à **Workflow permissions**.
3. Choisis **Read and write permissions**.
4. Clique sur **Save**.

Cette autorisation sert uniquement à mettre à jour `seen_tournaments.json`.

## 4. Faire le premier test

1. Ouvre l'onglet **Actions** du dépôt.
2. Clique sur **Vérifier les tournois Beach Tennis**.
3. Clique sur **Run workflow**, puis encore sur **Run workflow**.
4. Ouvre l'exécution pour vérifier que toutes les étapes deviennent vertes.

Le premier lancement est volontairement silencieux : il mémorise les tournois déjà présents sans envoyer des dizaines de messages. Les exécutions suivantes annonceront seulement les nouveaux tournois.

## Fonctionnement

- Source : API publique utilisée par la recherche Ten'Up.
- Zone : coordonnées de Montpellier, rayon de 199 km.
- Pratique : Beach Tennis.
- Période : aujourd'hui jusqu'à environ trois mois.
- Fréquence : une fois par jour vers 05:17 UTC.
- Identifiant de déduplication : `idHomologation`.
- Stockage : `seen_tournaments.json`.

## Lancer le bot sur son ordinateur

Avec Python 3.11 ou plus récent :

```bash
python -m pip install -r requirements.txt
```

Définis ensuite la variable d'environnement `DISCORD_WEBHOOK_URL`, puis lance :

```bash
python bot.py
```

## Dépannage

Dans l'onglet **Actions**, ouvre l'exécution rouge puis l'étape en erreur. Les causes habituelles sont :

- secret `DISCORD_WEBHOOK_URL` absent ou mal nommé ;
- webhook supprimé dans Discord ;
- permission d'écriture du workflow non autorisée ;
- modification temporaire de l'API Ten'Up.
