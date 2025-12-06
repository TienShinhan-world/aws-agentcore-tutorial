# Article 2 : Exposer votre agent via API REST avec AWS AgentCore

> **Série : Agent de Support Backoffice avec AWS AgentCore**
> **Étape 2** | [English version](../en/article-02-gateway.md)

## Table des matières

1. [Introduction](#introduction)
2. [Architecture](#architecture)
3. [Prérequis](#prérequis)
4. [Invocation directe de l'agent](#invocation-directe-de-lagent)
5. [Infrastructure webhook avec CDK](#infrastructure-webhook-avec-cdk)
6. [Déploiement de l'infrastructure](#déploiement-de-linfrastructure)
7. [Configuration post-déploiement](#configuration-post-déploiement)
8. [Tests et validation](#tests-et-validation)
9. [Dépannage](#dépannage)
10. [Prochaines étapes](#prochaines-étapes)

---

## Introduction

Dans l'[Article 1](article-01-runtime.md), nous avons déployé notre agent de support avec AWS AgentCore Runtime. L'agent fonctionne et peut être invoqué via le CLI `agentcore invoke`.

Mais comment permettre à des systèmes externes (comme ServiceNow) d'appeler notre agent ? C'est ce que nous allons résoudre dans cet article.

### Ce que vous allez construire

Dans cet article, nous allons :
- ✅ Comprendre comment invoquer l'agent via l'API AWS `bedrock-agentcore`
- ✅ Déployer une infrastructure webhook complète avec AWS CDK
- ✅ Créer une API REST sécurisée avec API Gateway
- ✅ Configurer une Lambda qui fait le pont entre l'API et l'agent
- ✅ Tester l'ensemble avec curl

### Temps estimé
⏱️ **30-45 minutes** pour compléter ce tutoriel.

---

## Architecture

### Vue d'ensemble

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│  Client HTTP    │────▶│  API Gateway    │────▶│     Lambda      │────▶│  AgentCore      │
│  (curl, app)    │     │  + API Key      │     │  (handler.py)   │     │  Runtime        │
│                 │◀────│                 │◀────│                 │◀────│                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │
                              │                        │
                              ▼                        ▼
                        CloudWatch              Secrets Manager
                          Logs                  (credentials)
```

### Pourquoi cette architecture ?

1. **API Gateway** : Point d'entrée sécurisé avec authentification par API Key, throttling, et logging
2. **Lambda** : Logique de transformation entre le format de requête HTTP et le format attendu par AgentCore
3. **AgentCore Runtime** : Notre agent déployé dans l'Article 1
4. **Secrets Manager** : Stockage sécurisé des credentials (utilisé dans l'Article 3)

### Flux de données

1. Un client envoie une requête POST à `/webhook/servicenow` avec les données d'un ticket
2. API Gateway valide l'API Key et transmet à Lambda
3. Lambda parse le payload, construit le prompt, et appelle AgentCore
4. AgentCore exécute l'agent qui analyse le ticket
5. La réponse remonte jusqu'au client

---

## Prérequis

### Depuis l'Article 1

- ✅ Agent déployé avec `agentcore launch`
- ✅ ARN de l'agent disponible dans `.bedrock_agentcore.yaml`

### Nouveaux prérequis

1. **Node.js et npm** (pour AWS CDK)
   ```bash
   node --version  # v18.x ou supérieur recommandé
   npm --version
   ```

2. **AWS CDK CLI**
   ```bash
   npm install -g aws-cdk
   cdk --version
   ```

3. **Docker** (pour le build Lambda)
   ```bash
   docker --version
   ```

---

## Invocation directe de l'agent

Avant de construire l'infrastructure, comprenons comment invoquer l'agent programmatiquement.

### Le client `bedrock-agentcore`

AWS fournit un client boto3 spécifique pour AgentCore :

```python
import boto3
import json

# Créer le client bedrock-agentcore
client = boto3.client('bedrock-agentcore', region_name='eu-central-1')

# Préparer le payload
payload = json.dumps({
    "prompt": "Analyze this ticket: INC0001234 - VPN connection issues"
})

# Invoquer l'agent
response = client.invoke_agent_runtime(
    agentRuntimeArn='arn:aws:bedrock-agentcore:eu-central-1:ACCOUNT_ID:runtime/AGENT_ID',
    runtimeSessionId='unique-session-id-minimum-33-characters',
    payload=payload,
    qualifier="DEFAULT"
)

# Lire la réponse
response_body = response['response'].read()
response_data = json.loads(response_body)
print("Agent Response:", response_data)
```

### Paramètres importants

| Paramètre | Description | Contraintes |
|-----------|-------------|-------------|
| `agentRuntimeArn` | ARN complet de l'agent déployé | Format : `arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/AGENT_ID` |
| `runtimeSessionId` | Identifiant de session unique | **Minimum 33 caractères** |
| `payload` | Données à envoyer à l'agent | JSON stringifié avec clé `prompt` |
| `qualifier` | Version de l'agent | `DEFAULT` pour la version active |

### Récupérer l'ARN de votre agent

L'ARN se trouve dans le fichier `.bedrock_agentcore.yaml` généré lors du déploiement :

```bash
grep "agent_arn" .bedrock_agentcore.yaml
```

Exemple de sortie :
```
agent_arn: arn:aws:bedrock-agentcore:eu-central-1:653783183133:runtime/agent_level_one_triage-9rGFpG5ZFx
```

---

## Infrastructure webhook avec CDK

Maintenant, créons l'infrastructure qui exposera notre agent via une API REST.

### Structure du projet CDK

```
infrastructure/
└── cdk/
    ├── bin/
    │   └── app.ts              # Point d'entrée CDK
    ├── lib/
    │   └── servicenow-webhook-stack.ts  # Définition de la stack
    ├── package.json
    ├── tsconfig.json
    └── cdk.json
```

### La stack CDK

Voici les composants principaux de notre stack (`lib/servicenow-webhook-stack.ts`) :

#### 1. Rôle IAM pour Lambda

```typescript
const lambdaRole = new iam.Role(this, 'WebhookLambdaRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
  managedPolicies: [
    iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
  ],
});

// Permission pour invoquer AgentCore
lambdaRole.addToPolicy(
  new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: ['bedrock-agentcore:InvokeAgentRuntime'],
    resources: ['arn:aws:bedrock-agentcore:eu-central-1:ACCOUNT_ID:runtime/*'],
  })
);
```

**Important :** La permission `bedrock-agentcore:InvokeAgentRuntime` est spécifique à AgentCore. Ne pas confondre avec `bedrock:InvokeAgent` qui est pour les Bedrock Agents classiques.

#### 2. Fonction Lambda

```typescript
const webhookHandler = new lambda.Function(this, 'WebhookHandler', {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: 'handler.lambda_handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../../src/webhook')),
  role: lambdaRole,
  timeout: cdk.Duration.seconds(300),  // 5 minutes pour laisser le temps à l'agent
  memorySize: 512,
  environment: {
    LOG_LEVEL: 'INFO',
  },
});
```

#### 3. API Gateway avec API Key

```typescript
const api = new apigateway.RestApi(this, 'ServiceNowWebhookApi', {
  restApiName: 'ServiceNow Webhook API',
  deployOptions: {
    stageName: 'prod',
    loggingLevel: apigateway.MethodLoggingLevel.INFO,
  },
});

// API Key pour sécuriser l'accès
const apiKey = new apigateway.ApiKey(this, 'ServiceNowApiKey', {
  apiKeyName: 'servicenow-webhook-api-key',
  enabled: true,
});

// Route POST /webhook/servicenow
const webhookResource = api.root.addResource('webhook');
const servicenowResource = webhookResource.addResource('servicenow');
servicenowResource.addMethod('POST', new apigateway.LambdaIntegration(webhookHandler), {
  apiKeyRequired: true,
});
```

### Le handler Lambda

Le fichier `src/webhook/handler.py` fait le pont entre l'API et AgentCore :

```python
import boto3
import json
import os
import uuid

# Client AgentCore
bedrock_agentcore = boto3.client("bedrock-agentcore", region_name="eu-central-1")
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")

def generate_session_id(incident_number: str) -> str:
    """Génère un session ID de 33+ caractères"""
    base = f"servicenow-{incident_number}-{uuid.uuid4().hex}"
    return base[:50]

def lambda_handler(event, context):
    # Parser le body de la requête
    body = json.loads(event.get("body", "{}"))

    # Extraire les données du ticket
    incident_number = body.get("number", "UNKNOWN")

    # Construire le prompt
    prompt = f"""Analyze the following ServiceNow incident:
    Ticket Number: {incident_number}
    Description: {body.get("description", "")}
    Priority: {body.get("priority", "")}
    """

    # Invoquer l'agent
    response = bedrock_agentcore.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=generate_session_id(incident_number),
        payload=json.dumps({"prompt": prompt}),
        qualifier="DEFAULT"
    )

    # Retourner la réponse
    response_body = response["response"].read()
    return {
        "statusCode": 200,
        "body": json.dumps({
            "success": True,
            "analysis": json.loads(response_body)
        })
    }
```

---

## Déploiement de l'infrastructure

### 1. Installer les dépendances CDK

```bash
cd infrastructure/cdk
npm install
```

### 2. Bootstrap CDK (première fois uniquement)

```bash
npm run cdk bootstrap
```

Cette commande crée les ressources nécessaires à CDK dans votre compte AWS.

### 3. Déployer la stack

```bash
npm run cdk deploy
```

Le déploiement prend environ 2-3 minutes. À la fin, vous verrez les outputs :

```
Outputs:
ServiceNowWebhookStack.WebhookURL = https://xxxxxx.execute-api.eu-central-1.amazonaws.com/prod/webhook/servicenow
ServiceNowWebhookStack.ApiKeyId = xxxxxxxxxx
ServiceNowWebhookStack.LambdaFunctionName = ServiceNowWebhookStack-WebhookHandler-xxxxx
ServiceNowWebhookStack.GetApiKeyCommand = aws apigateway get-api-key --api-key xxxxxxxxxx --include-value --query 'value' --output text
```

### 4. Récupérer l'API Key

```bash
aws apigateway get-api-key --api-key <API_KEY_ID> --include-value --query 'value' --output text
```

Notez cette valeur, vous en aurez besoin pour les tests.

---

## Configuration post-déploiement

### Configurer l'ARN de l'agent

La Lambda a besoin de connaître l'ARN de votre agent. Configurez la variable d'environnement :

```bash
aws lambda update-function-configuration \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --environment "Variables={AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:eu-central-1:ACCOUNT_ID:runtime/AGENT_ID,LOG_LEVEL=INFO}"
```

**Remplacez :**
- `<LAMBDA_FUNCTION_NAME>` : Le nom de la fonction Lambda (voir output CDK)
- `ACCOUNT_ID` : Votre ID de compte AWS
- `AGENT_ID` : L'ID de votre agent (depuis `.bedrock_agentcore.yaml`)

### Vérifier la configuration

```bash
aws lambda get-function-configuration \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --query 'Environment.Variables'
```

---

## Tests et validation

### Test avec curl

```bash
curl --location 'https://YOUR_API_GATEWAY_URL/prod/webhook/servicenow' \
  --header 'x-api-key: YOUR_API_KEY' \
  --header 'Content-Type: application/json' \
  --data '{
    "number": "INC0001234",
    "short_description": "Cannot access email",
    "description": "User cannot send or receive emails since this morning",
    "urgency": "2",
    "impact": "2",
    "priority": "2",
    "category": "Email",
    "assignment_group": "IT Support Level 1"
}'
```

### Réponse attendue

```json
{
  "success": true,
  "incident_number": "INC0001234",
  "analysis": "**Summary of the issue:**\nUser cannot send or receive emails since this morning...",
  "message": "Incident analyzed successfully"
}
```

### Vérifier les logs CloudWatch

```bash
# Trouver le log group
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/ServiceNowWebhookStack

# Voir les derniers logs
aws logs tail /aws/lambda/ServiceNowWebhookStack-WebhookHandler-xxxxx --follow
```

---

## Dépannage

### Erreur : "not authorized to perform bedrock-agentcore:InvokeAgentRuntime"

**Cause :** Le rôle IAM de la Lambda n'a pas la permission.

**Solution :** Vérifiez que la stack CDK inclut bien :
```typescript
actions: ['bedrock-agentcore:InvokeAgentRuntime'],
```

Et redéployez avec `npm run cdk deploy`.

### Erreur : "AGENT_RUNTIME_ARN environment variable not set"

**Cause :** La variable d'environnement n'est pas configurée.

**Solution :** Exécutez la commande `aws lambda update-function-configuration` de la section Configuration.

### Erreur : "runtimeSessionId must be at least 33 characters"

**Cause :** Le session ID est trop court.

**Solution :** Le handler génère automatiquement un ID de 50 caractères. Si vous testez manuellement, assurez-vous d'utiliser un ID assez long.

### Erreur : "Response ended prematurely"

**Cause :** Problème de connexion avec Bedrock (généralement temporaire).

**Solution :** Retestez après quelques secondes. Si le problème persiste, vérifiez :
- La région de l'agent
- Les quotas Bedrock
- L'état du service Bedrock

### Erreur 403 Forbidden

**Cause :** API Key manquante ou invalide.

**Solution :** Vérifiez que vous incluez le header `x-api-key` avec la bonne valeur.

---

## Prochaines étapes

Félicitations ! 🎉 Votre agent est maintenant accessible via une API REST sécurisée.

Dans le **prochain article (Article 3)**, nous allons :

🔜 **Connecter ServiceNow à notre API** via Business Rules et REST Messages
🔜 **Modifier l'agent pour mettre à jour ServiceNow** avec de vrais appels API
🔜 **Configurer les credentials** dans AWS Secrets Manager
🔜 **Tester le flux complet** : création de ticket → analyse automatique → mise à jour

**Branche Git :** `step-03-servicenow-integration`

---

## Ressources

### Documentation
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/latest/guide/)
- [API Gateway Developer Guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/)
- [Lambda Developer Guide](https://docs.aws.amazon.com/lambda/latest/dg/)

### Code source
- [Repository GitHub](https://github.com/votre-username/aws-agentcore-tutorial)
- Branch : `step-02-servicenow-integration`

---

**Auteur :** Anthony PINTO
**Date :** Décembre 2025
**Série :** Agent de Support Backoffice avec AWS AgentCore (2/5)

*Cet article fait partie d'une série sur AWS AgentCore.*
