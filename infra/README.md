# Déploiement

Ce template déploie **dans** le resource group existant
(`<votre-resource-group>`). Il ne crée jamais de
resource group.

## Option A — recommandée : build via GitHub Actions, déploiement manuel

Un rôle limité (par ex. "Resource access" sur le RG) permet de déployer
directement avec votre propre compte via `az login`, sans créer de service
principal. C'est le chemin le plus simple et le plus fiable :

```bash
# 0. Prérequis : az cli installé (https://aka.ms/installazurecliwindows),
#    connecté avec le compte Azure concerné
az login
az account set --subscription <votre-subscription-id>

RG=<votre-resource-group>
```

**1. Construire et publier l'image.** Deux façons, choisissez selon ce que
vous avez sous la main :

- **Sans Docker Desktop installé** (le plus simple) : poussez le code sur
  GitHub (dépôt privé). Le job `build-and-push` de
  `.github/workflows/ci-cd.yml` construit et publie automatiquement l'image
  sur GHCR à chaque push sur `main` — **aucun secret Azure requis pour cette
  étape**, seulement les permissions par défaut de GitHub Actions. Récupérez
  ensuite le tag exact dans l'onglet *Actions* du dépôt (ou dans *Packages*),
  généralement `ghcr.io/<votre-user>/cv-search:latest` (en minuscules).

- **Avec Docker Desktop installé**, en local :
  ```powershell
  docker build -t ghcr.io/<votre-user>/cv-search:latest .
  echo $env:GITHUB_TOKEN | docker login ghcr.io -u <votre-user> --password-stdin
  docker push ghcr.io/<votre-user>/cv-search:latest
  ```
  (`$env:GITHUB_TOKEN` = un *Personal Access Token* GitHub avec la portée
  `write:packages`, créé depuis github.com > Settings > Developer settings.)

**2. Déployer.** La clé APIM ne doit jamais être en dur dans un fichier
committé — elle passe en paramètre de la commande, pas dans
`main.parameters.json` :

```bash
az deployment group create \
  -g "$RG" \
  -f infra/main.bicep \
  -p infra/main.parameters.json \
  -p containerImage="ghcr.io/<votre-user>/cv-search:latest" \
  -p apimSubscriptionKey="<votre-clé-apim>"
```

**3. Récupérer l'URL publique :**

```bash
az deployment group show -g "$RG" -n main --query properties.outputs.appUrl.value -o tsv
```

**4. Vérifier que ça répond :**

```bash
curl https://<url-retournée>/health
```

**5. Pour une démo**, passer temporairement à 1 réplica
minimum (évite le cold start au premier appel) :

```bash
az containerapp update -n cvsearch-api -g "$RG" --min-replicas 1
```
Repassez à 0 après la démo pour ne pas consommer le budget inutilement.

## Option B — automatisation complète (CI/CD bout en bout)

Pour que le job `deploy` du workflow s'exécute aussi automatiquement, il faut
un service principal Azure avec un rôle Contributor sur le RG, ce qui
nécessite généralement des droits d'application Azure AD que un rôle limité ne donne pas toujours. Si votre compte a ces droits :

```bash
az ad sp create-for-rbac --name "cvsearch-github-actions" \
  --role Contributor \
  --scopes /subscriptions/<votre-subscription-id>/resourceGroups/<votre-resource-group> \
  --sdk-auth
```
Copiez la sortie JSON dans le secret GitHub `AZURE_CREDENTIALS`, ajoutez le
secret `APIM_SUBSCRIPTION_KEY` et la variable de dépôt (*Variables*, pas
*Secrets*) `AZURE_RESOURCE_GROUP=<votre-resource-group>`. Si la
commande échoue par manque de droits, restez sur l'Option A — ce n'est pas
bloquant.

## Limites connues / hypothèses

- `minReplicas: 0` (scale-to-zero) minimise le coût mais introduit un cold
  start de quelques secondes au premier appel après une période d'inactivité.
  Pour une démo, passer temporairement `minReplicas: 1`.
- L'index (`/app/index`) et le cache (`/app/cache`) sont stockés dans le
  système de fichiers éphémère du conteneur : ils sont perdus à chaque
  redéploiement ou restart. Pour cette démo (petit corpus, réingestion rapide via
  `make ingest` ou l'endpoint `/cvs`), c'est un compromis acceptable. En
  production : monter un Azure Files share sur le Container App, ou migrer
  vers Azure AI Search / Qdrant managé (voir README principal, section
  "Passage en production").
- Pas de rôle IAM créé par ce template (la création de *role assignments*
  nécessite souvent des droits qu'un rôle limité ne donne pas). Le
  workflow CI/CD utilise donc un service principal avec secret GitHub plutôt
  que l'OIDC + managed identity qui serait le choix de production.
