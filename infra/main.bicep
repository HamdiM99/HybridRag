// Déploiement de l'API CV Search sur Azure Container Apps.
// Cible un resource group EXISTANT (existant) : ce template ne
// crée jamais de resource group, seulement les ressources à l'intérieur.
// Déployer avec : az deployment group create -g <rg> -f infra/main.bicep
//                   -p infra/main.parameters.json
//                   -p apimSubscriptionKey=<secret>

@description('Nom court du projet, utilisé comme préfixe des ressources.')
param projectName string = 'cvsearch'

@description('Région Azure (doit correspondre à celle du resource group existant).')
param location string = resourceGroup().location

@description('URL de base de la gateway APIM à utiliser.')
param apimBaseUrl string

@secure()
@description('Clé d\'abonnement APIM. Ne jamais committer une valeur réelle.')
param apimSubscriptionKey string

@description('Déploiement chat (ex: gpt-5).')
param chatDeployment string = 'gpt-5'

@description('Déploiement embeddings (ex: text-embedding-3-large).')
param embedDeployment string = 'text-embedding-3-large'

@description('Image du conteneur, publiée sur GHCR (évite le coût fixe d\'un ACR).')
param containerImage string

@description('Nombre minimal de réplicas. 0 = scale-to-zero (coût minimal, cold start au premier appel).')
@minValue(0)
@maxValue(2)
param minReplicas int = 0

var logAnalyticsName = '${projectName}-logs'
var envName = '${projectName}-env'
var appName = '${projectName}-api'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30 // minimum : suffisant pour un test, réduit le coût de stockage
  }
}

resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
      }
      secrets: [
        { name: 'apim-subscription-key', value: apimSubscriptionKey }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            // Minimum autorisé par Container Apps : suffisant pour cette démo,
            // limite le coût en cas de minReplicas > 0.
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'APIM_BASE_URL', value: apimBaseUrl }
            { name: 'APIM_SUBSCRIPTION_KEY', secretRef: 'apim-subscription-key' }
            { name: 'CHAT_DEPLOYMENT', value: chatDeployment }
            { name: 'EMBED_DEPLOYMENT', value: embedDeployment }
            { name: 'CACHE_DIR', value: '/app/cache' }
            { name: 'INDEX_DIR', value: '/app/index' }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 1 // budget limité : pas de montée en charge automatique au-delà de 1
      }
    }
  }
}

output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
