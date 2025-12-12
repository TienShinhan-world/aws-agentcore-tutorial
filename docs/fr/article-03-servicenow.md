# Article 3 : Intégration ServiceNow avec AgentCore Gateway

> **Série : Agent de Support Backoffice avec AWS AgentCore**
> **Étape 3** | [English version](../en/article-03-servicenow.md)

## Table des matières

1. [Introduction](#introduction)
2. [Architecture réelle](#architecture-réelle)
3. [Prérequis](#prérequis)
4. [Partie 1 : Déployer l'infrastructure CDK](#partie-1--déployer-linfrastructure-cdk)
5. [Partie 2 : Configurer AgentCore Gateway](#partie-2--configurer-agentcore-gateway)
6. [Partie 3 : Connecter l'agent au Gateway](#partie-3--connecter-lagent-au-gateway)
7. [Partie 4 : Configuration ServiceNow](#partie-4--configuration-servicenow)
8. [Tests et diagnostic](#tests-et-diagnostic)
9. [Pièges courants et solutions](#pièges-courants-et-solutions)
10. [Prochaines étapes](#prochaines-étapes)

---

## Introduction

Dans l'[Article 2](article-02-gateway.md), nous avons déployé l'infrastructure de base. Maintenant, nous allons établir une **connexion bidirectionnelle réelle** avec ServiceNow via **AgentCore Gateway**.

> **Avertissement** : Cette intégration comporte plusieurs pièges subtils. Cet article est basé sur une implémentation réelle et documente les erreurs que vous risquez de rencontrer.

### Ce que vous allez construire

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE BIDIRECTIONNELLE RÉELLE                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────┐      ┌────────────┐     ┌────────────────┐     ┌──────────────┐  │
│  │ ServiceNow │───▶ │API Gateway │────▶│ Webhook Lambda │────▶│  AgentCore   │  │
│  │  (ticket)  │      │  + API Key │     │                │     │   Runtime    │  │
│  └────────────┘      └────────────┘     └────────────────┘     └──────┬───────┘  │
│        ▲                                                             │          │
│        │                                                             ▼          │
│        │            ┌────────────┐     ┌────────────────┐     ┌──────────────┐  │
│        │            │ ServiceNow │◀────│  ServiceNow    │◀────│  AgentCore   │  │
│        └────────────│   (mise à  │     │  API Lambda    │     │   Gateway    │  │
│                     │   jour)    │     │                │     │  (MCP/OAuth) │  │
│                     └────────────┘     └────────────────┘     └──────────────┘  │
│                                               │                                  │
│                                               ▼                                  │
│                                        ┌────────────┐                           │
│                                        │  Secrets   │                           │
│                                        │  Manager   │                           │
│                                        └────────────┘                           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Pourquoi AgentCore Gateway ?

L'agent AgentCore Runtime ne peut pas appeler directement des API externes. Il faut passer par **AgentCore Gateway** qui :
- Expose des fonctions Lambda comme des **outils MCP** (Model Context Protocol)
- Gère l'authentification OAuth via **Cognito**
- Permet à l'agent d'appeler des services externes de manière sécurisée

### Temps estimé
⏱️ **60-90 minutes** - Comptez plus si c'est votre première fois avec AgentCore Gateway.

---

## Architecture réelle

### Composants déployés

| Composant | Rôle | Service AWS |
|-----------|------|-------------|
| **Webhook Lambda** | Reçoit les tickets de ServiceNow | Lambda |
| **ServiceNow API Lambda** | Exécute les opérations ServiceNow | Lambda |
| **AgentCore Gateway** | Expose la Lambda comme outils MCP | Bedrock AgentCore |
| **Cognito User Pool** | Authentification OAuth M2M | Cognito |
| **Secrets Manager** | Stocke les credentials ServiceNow | Secrets Manager |

### Flux de données

**Entrée (ServiceNow → Agent)** :
1. Ticket créé dans ServiceNow
2. Business Rule déclenche webhook HTTP
3. API Gateway reçoit avec API Key
4. Webhook Lambda invoque AgentCore Runtime
5. Agent analyse le ticket

**Sortie (Agent → ServiceNow)** :
1. Agent appelle outil `update_servicenow_ticket`
2. Requête HTTP JSON-RPC vers AgentCore Gateway
3. Gateway authentifie via token Cognito
4. Gateway invoque ServiceNow API Lambda
5. Lambda met à jour le ticket via API ServiceNow

---

## Prérequis

### Depuis les articles précédents
- ✅ Agent déployé sur AgentCore Runtime (Article 1)
- ✅ AWS CLI configuré avec les bonnes permissions

### Nouveaux prérequis

1. **Instance ServiceNow** avec accès admin
   - PDI gratuite : [developer.servicenow.com](https://developer.servicenow.com/)

2. **Node.js 18+** pour le CDK
   ```bash
   node --version  # >= 18.0.0
   ```

3. **AWS CDK installé**
   ```bash
   npm install -g aws-cdk
   cdk --version
   ```

---

## Partie 1 : Déployer l'infrastructure CDK

### 1.1 Installer les dépendances

```bash
cd infrastructure/cdk
npm install
```

### 1.2 Bootstrap CDK (première fois uniquement)

```bash
cdk bootstrap aws://ACCOUNT_ID/eu-central-1
```

### 1.3 Déployer le stack

```bash
npm run cdk deploy
```

> **Note** : Le déploiement prend environ 5-10 minutes. Notez les **Outputs** affichés à la fin.

### 1.4 Outputs importants à noter

```
ServiceNowWebhookStack.WebhookURL = https://xxx.execute-api.eu-central-1.amazonaws.com/prod/webhook/servicenow
ServiceNowWebhookStack.ServiceNowApiLambdaArn = arn:aws:lambda:eu-central-1:xxx:function:ServiceNowApiHandler
ServiceNowWebhookStack.CognitoUserPoolId = eu-central-1_XXXXXXX
ServiceNowWebhookStack.CognitoAppClientId = xxxxxxxxxxxxxxxxxxxx
ServiceNowWebhookStack.CognitoTokenEndpoint = https://agentcore-gateway-xxx.auth.eu-central-1.amazoncognito.com/oauth2/token
ServiceNowWebhookStack.GatewayRoleArn = arn:aws:iam::xxx:role/AgentCoreGatewayServiceNowRole
```

### 1.5 Configurer les credentials ServiceNow

```bash
aws secretsmanager update-secret \
  --secret-id servicenow/credentials \
  --secret-string '{
    "instance_url": "https://YOUR_INSTANCE.service-now.com",
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD"
  }'
```

---

## Partie 2 : Configurer AgentCore Gateway

### 2.1 Exécuter le script de setup

```bash
python scripts/setup_gateway.py \
  --lambda-arn <ServiceNowApiLambdaArn> \
  --role-arn <GatewayRoleArn> \
  --user-pool-id <CognitoUserPoolId> \
  --client-id <CognitoAppClientId> \
  --region eu-central-1
```

Le script crée :
- Un Gateway MCP avec authentification OAuth
- Un target Lambda avec 3 outils définis
- Un fichier `gateway_config.json` avec la configuration

### 2.2 Récupérer le Client Secret Cognito

> **Important** : Le client secret n'est PAS dans les outputs CDK. Vous devez le récupérer manuellement.

```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id <CognitoUserPoolId> \
  --client-id <CognitoAppClientId> \
  --query 'UserPoolClient.ClientSecret' \
  --output text
```

**Notez ce secret** - vous en aurez besoin pour lancer l'agent.

### 2.3 Vérifier la configuration Gateway

Le fichier `gateway_config.json` devrait contenir :

```json
{
  "gateway_url": "https://xxx.gateway.bedrock-agentcore.eu-central-1.amazonaws.com/mcp",
  "gateway_id": "xxx",
  "target_name": "servicenow-tools",
  "tools": [
    "update_servicenow_ticket",
    "create_servicenow_comment",
    "resolve_servicenow_ticket"
  ],
  "oauth": {
    "token_endpoint": "https://agentcore-gateway-xxx.auth.eu-central-1.amazoncognito.com/oauth2/token",
    "scope": "agentcore-gateway/tools.invoke"
  }
}
```

---

## Partie 3 : Connecter l'agent au Gateway

### 3.1 Variables d'environnement requises

L'agent a besoin de **4 variables d'environnement** pour se connecter au Gateway :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `AGENTCORE_GATEWAY_URL` | URL du Gateway MCP | `https://xxx.gateway.bedrock-agentcore.eu-central-1.amazonaws.com/mcp` |
| `COGNITO_TOKEN_ENDPOINT` | URL pour obtenir le token | `https://agentcore-gateway-xxx.auth.eu-central-1.amazoncognito.com/oauth2/token` |
| `COGNITO_CLIENT_ID` | ID du client Cognito | `rj66pt7uiro8o62lth2s45km8` |
| `COGNITO_CLIENT_SECRET` | Secret du client (récupéré en 2.2) | `193vd3ggmv3ptb544f76q0qv38...` |

### 3.2 Lancer l'agent avec les variables

```bash
agentcore launch \
  --env "AGENTCORE_GATEWAY_URL=https://xxx.gateway.bedrock-agentcore.eu-central-1.amazonaws.com/mcp" \
  --env "COGNITO_TOKEN_ENDPOINT=https://agentcore-gateway-xxx.auth.eu-central-1.amazoncognito.com/oauth2/token" \
  --env "COGNITO_CLIENT_ID=xxx" \
  --env "COGNITO_CLIENT_SECRET=xxx"
```

> **ATTENTION - Piège fréquent** : Vérifiez qu'il n'y a pas d'espace dans les URLs. Une erreur courante est un espace dans `eu-central-1` copié depuis un terminal avec retour à la ligne.

❌ **Mauvais** : `eu-central-  1` (espace avant le 1)
✅ **Bon** : `eu-central-1`

---

## Partie 4 : Configuration ServiceNow

### 4.1 Créer un REST Message

1. **System Web Services → Outbound → REST Message**
2. **New** avec :
   - **Name** : `AWS AgentCore Webhook`
   - **Endpoint** : L'URL du webhook (output `WebhookURL`)

### 4.2 Ajouter la méthode POST

1. Onglet **HTTP Methods** → **New**
2. Configuration :
   - **Name** : `POST Incident`
   - **HTTP method** : `POST`

3. **HTTP Headers** :

| Name | Value |
|------|-------|
| `Content-Type` | `application/json` |
| `x-api-key` | Votre API Key (voir outputs CDK) |

4. **Content** :
```json
{
    "number": "${number}",
    "short_description": "${short_description}",
    "description": "${description}",
    "priority": "${priority}",
    "category": "${category}",
    "sys_id": "${sys_id}"
}
```

### 4.3 Créer la Business Rule

1. **System Definition → Business Rules** → **New**
2. Configuration :
   - **Name** : `Trigger AWS Agent`
   - **Table** : `Incident [incident]`
   - **When** : `after`
   - **Insert** : ✅
   - **Advanced** : ✅

3. **Script** :
```javascript
(function executeRule(current, previous) {
    try {
        var r = new sn_ws.RESTMessageV2('AWS AgentCore Webhook', 'POST Incident');

        r.setStringParameterNoEscape('number', current.getValue('number'));
        r.setStringParameterNoEscape('short_description', current.getValue('short_description'));
        r.setStringParameterNoEscape('description', current.getValue('description'));
        r.setStringParameterNoEscape('priority', current.getValue('priority'));
        r.setStringParameterNoEscape('category', current.getValue('category'));
        r.setStringParameterNoEscape('sys_id', current.getValue('sys_id'));

        var response = r.execute();
        gs.info('AWS Agent [' + response.getStatusCode() + ']: ' + response.getBody());
    } catch (ex) {
        gs.error('AWS Agent Error: ' + ex.getMessage());
    }
})(current, previous);
```

---

## Tests et diagnostic

### Script de diagnostic

Un script de test est fourni pour valider chaque composant :

```bash
# Définir les variables
export AGENTCORE_GATEWAY_URL="https://xxx.gateway.bedrock-agentcore.eu-central-1.amazonaws.com/mcp"
export COGNITO_TOKEN_ENDPOINT="https://agentcore-gateway-xxx.auth.eu-central-1.amazoncognito.com/oauth2/token"
export COGNITO_CLIENT_ID="xxx"
export COGNITO_CLIENT_SECRET="xxx"

# Lancer les tests
python scripts/test_gateway_integration.py
```

### Test 1 : Token Cognito

```bash
python scripts/test_gateway_integration.py --test token
```

**Résultat attendu** :
```
[OK] Token acquired successfully (expires in 3600s)
```

**Si échec** : Vérifiez `COGNITO_CLIENT_SECRET` et `COGNITO_TOKEN_ENDPOINT`.

### Test 2 : Liste des outils Gateway

```bash
python scripts/test_gateway_integration.py --test list
```

**Résultat attendu** :
```
Found 4 tools:
  - x_amz_bedrock_agentcore_search
  - servicenow-tools___create_servicenow_comment
  - servicenow-tools___resolve_servicenow_ticket
  - servicenow-tools___update_servicenow_ticket
[OK] Successfully listed 4 tools
```

### Test 3 : Appel d'outil

```bash
python scripts/test_gateway_integration.py --test call --ticket INC0010466
```

**Résultat attendu** :
```json
{
  "success": true,
  "ticket_number": "INC0010466",
  "message": "Ticket updated successfully"
}
```

---

## Pièges courants et solutions

### Piège 1 : Espace dans les URLs des variables d'environnement

**Symptôme** : Erreur de connexion au token endpoint ou au gateway.

**Cause** : Copier-coller depuis un terminal avec retour à la ligne automatique.

**Solution** : Vérifiez chaque URL caractère par caractère.

```bash
# Mauvais (espace caché)
COGNITO_TOKEN_ENDPOINT=https://agentcore-gateway-xxx.auth.eu-central-  1.amazoncognito.com/oauth2/token

# Bon
COGNITO_TOKEN_ENDPOINT=https://agentcore-gateway-xxx.auth.eu-central-1.amazoncognito.com/oauth2/token
```

### Piège 2 : Format de réponse MCP non parsé

**Symptôme** : L'agent reçoit une réponse vide ou mal formatée du Gateway.

**Cause** : Le protocole MCP encapsule les réponses dans une structure `content`.

**Format réel de la réponse** :
```json
{
  "jsonrpc": "2.0",
  "result": {
    "isError": false,
    "content": [
      {
        "type": "text",
        "text": "{\"success\":true,\"ticket_number\":\"INC001\"}"
      }
    ]
  }
}
```

**Solution** : Le parsing doit extraire `result.content[0].text` puis le parser en JSON.

### Piège 3 : Nom des outils avec préfixe target

**Symptôme** : Erreur "tool not found" lors de l'appel.

**Cause** : Les outils Gateway ont un préfixe `{target-name}___`.

**Solution** : Utilisez le nom complet :
```python
# Mauvais
tool_name = "update_servicenow_ticket"

# Bon
tool_name = "servicenow-tools___update_servicenow_ticket"
```

### Piège 4 : Format de réponse Lambda

**Symptôme** : Le Gateway retourne une erreur même si la Lambda s'exécute.

**Cause** : AgentCore Gateway attend un format spécifique.

**Format attendu par le Gateway** :
```python
return {
    "statusCode": 200,
    "body": json.dumps({"success": True, ...})
}
```

**Pas** :
```python
return {"success": True, ...}  # Manque statusCode et body
```

### Piège 5 : Client Secret non récupéré

**Symptôme** : Erreur 401 lors de la demande de token.

**Cause** : Le client secret n'est pas dans les outputs CDK.

**Solution** :
```bash
aws cognito-idp describe-user-pool-client \
  --user-pool-id <pool-id> \
  --client-id <client-id> \
  --query 'UserPoolClient.ClientSecret' \
  --output text
```

### Piège 6 : Scope OAuth incorrect

**Symptôme** : Token obtenu mais rejeté par le Gateway.

**Cause** : Le scope demandé ne correspond pas à celui configuré.

**Scope correct** : `agentcore-gateway/tools.invoke`

---

## Vérification finale

Checklist avant de considérer l'intégration comme fonctionnelle :

- [ ] CDK déployé avec succès
- [ ] Credentials ServiceNow dans Secrets Manager
- [ ] Gateway setup exécuté
- [ ] Client secret Cognito récupéré
- [ ] Test token : OK
- [ ] Test list tools : OK (4 outils)
- [ ] Test call tool : OK (ticket mis à jour)
- [ ] Agent lancé avec les 4 variables d'environnement
- [ ] Business Rule ServiceNow configurée
- [ ] Test end-to-end : création ticket → mise à jour automatique

---

## Prochaines étapes

Félicitations ! Vous avez maintenant une intégration ServiceNow bidirectionnelle fonctionnelle via AgentCore Gateway.

Dans le **prochain article (Article 4)**, nous allons :

- Remplacer la KB simulée par **AWS Bedrock Knowledge Bases**
- Implémenter la **recherche sémantique** avec embeddings
- Connecter à vos **vrais documents** (PDF, Confluence)

**Branche Git** : `step-04-knowledge-base`

---

## Ressources

### Scripts utiles
- `scripts/setup_gateway.py` - Configuration du Gateway
- `scripts/test_gateway_integration.py` - Tests de diagnostic

### Fichiers de configuration
- `gateway_config.json` - Configuration Gateway générée
- `infrastructure/cdk/` - Infrastructure CDK

### Documentation
- [AgentCore Gateway - AWS Samples](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/02-AgentCore-gateway)
- [MCP Protocol](https://modelcontextprotocol.io/)
- [ServiceNow REST API](https://developer.servicenow.com/dev.do#!/reference/api/tokyo/rest/)

---

**Auteur :** Anthony PINTO
**Date :** Décembre 2025
**Série :** Agent de Support Backoffice avec AWS AgentCore (3/5)

*Cet article est basé sur une implémentation réelle et documente les erreurs courantes rencontrées.*
