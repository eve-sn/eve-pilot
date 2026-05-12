# EVE Pilot Backend

Structure Django initiale produite a partir du schema PostgreSQL V1 d'EVE Pilot.

## Architecture

- `config/` : configuration Django
- `apps/common/` : modeles abstraits partages
- `apps/accounts/` : utilisateur personnalise, roles, permissions, audit
- `apps/references/` : referentiels et parametres
- `apps/hr/` : ressources humaines
- `apps/projects/` : projets, bailleurs, indicateurs
- `apps/activities/` : activites terrain et rapports
- `apps/finance/` : budget, engagements, decaissements
- `apps/reporting/` : modeles de rapports et exports

## Demarrage

1. Creer un environnement virtuel Python.
2. Installer les dependances :

```bash
pip install -r requirements.txt
```

3. Copier `.env.example` en `.env` puis ajuster les parametres PostgreSQL.
4. Exporter les variables d'environnement ou les charger selon votre methode habituelle.
5. Generer les migrations :

```bash
python manage.py makemigrations
python manage.py migrate
```

6. Creer un superutilisateur :

```bash
python manage.py createsuperuser
```

## Suite logique

- ajouter les `admin.py`
- generer les `serializers`, `services` et `views`
- brancher l'authentification et les permissions metier
- produire les migrations initiales a partir de cette structure
