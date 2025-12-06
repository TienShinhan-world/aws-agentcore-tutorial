# Article 3 : Intégration ServiceNow bidirectionnelle

> **Série : Agent de Support Backoffice avec AWS AgentCore**
> **Étape 3** | [English version](../en/article-03-servicenow.md)

## Table des matières

1. [Introduction](#introduction)
2. [Architecture bidirectionnelle](#architecture-bidirectionnelle)
3. [Prérequis](#prérequis)
4. [Partie 1 : ServiceNow vers Agent (Webhook)](#partie-1--servicenow-vers-agent-webhook)
5. [Partie 2 : Agent vers ServiceNow (API)](#partie-2--agent-vers-servicenow-api)
6. [Partie 3 : Configuration des credentials](#partie-3--configuration-des-credentials)
7. [Partie 4 : Modification de l'agent](#partie-4--modification-de-lagent)
8. [Tests de bout en bout](#tests-de-bout-en-bout)
9. [Sécurité et bonnes pratiques](#sécurité-et-bonnes-pratiques)
10. [Dépannage](#dépannage)
11. [Prochaines étapes](#prochaines-étapes)

---

## Introduction

Dans l'[Article 2](article-02-gateway.md), nous avons exposé notre agent via une API REST. Maintenant, nous allons établir une **connexion réelle et bidirectionnelle** avec ServiceNow :

- ✅ **ServiceNow → Agent** : ServiceNow déclenche automatiquement notre agent via webhook
- ✅ **Agent → ServiceNow** : L'agent met à jour les tickets directement dans ServiceNow
- ✅ **Credentials sécurisés** : Utilisation d'AWS Secrets Manager
- ✅ **Flux complet** : Création de ticket → Analyse automatique → Mise à jour

### Ce que vous allez construire

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLUX BIDIRECTIONNEL                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐        │
│   │  ServiceNow  │────────▶│    Agent     │────────▶│  ServiceNow  │        │
│   │              │  HTTP   │   AgentCore  │   API   │              │        │
│   │ (Nouveau     │  POST   │              │  REST   │ (Mise à jour │        │
│   │  ticket)     │         │  (Analyse)   │         │  ticket)     │        │
│   └──────────────┘         └──────────────┘         └──────────────┘        │
│         │                         │                        ▲                │
│         │    Business Rule        │    Work Notes          │                │
│         └─────────────────────────┼────────────────────────┘                │
│                                   │                                         │
│                            AWS Secrets                                      │
│                             Manager                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Temps estimé
⏱️ **45-60 minutes** pour compléter ce tutoriel.

---

## Architecture bidirectionnelle

### Composants

| Direction | Source | Destination | Mécanisme |
|-----------|--------|-------------|-----------|
| **Entrée** | ServiceNow | Agent | Business Rule → REST Message → API Gateway → Lambda → AgentCore |
| **Sortie** | Agent | ServiceNow | Tool `update_servicenow_ticket` → ServiceNow REST API |

### Flux détaillé

1. **Déclencheur** : Un nouveau ticket est créé dans ServiceNow
2. **Business Rule** : Déclenche automatiquement à la création
3. **REST Message** : Envoie les données du ticket à notre API Gateway
4. **Lambda** : Reçoit le webhook, invoque l'agent AgentCore
5. **Agent** : Analyse le ticket, recherche dans la KB
6. **Tool ServiceNow** : Met à jour le ticket avec les work notes
7. **ServiceNow** : Affiche l'analyse de l'agent dans le ticket

---

## Prérequis

### Depuis les articles précédents

- ✅ Agent déployé (Article 1)
- ✅ Infrastructure webhook déployée (Article 2)
- ✅ API Gateway fonctionnel avec API Key

### Nouveaux prérequis

1. **Instance ServiceNow**
   - Instance de développement (PDI) : [developer.servicenow.com](https://developer.servicenow.com/)
   - Ou instance de production avec accès admin

2. **Utilisateur ServiceNow avec permissions API**
   - Rôle `rest_api_explorer` ou équivalent
   - Accès à la table `incident`

3. **Credentials ServiceNow**
   - URL de l'instance (ex: `https://devXXXXX.service-now.com`)
   - Username et password (ou OAuth token)

---

## Partie 1 : ServiceNow vers Agent (Webhook)

### 1.1 Créer un REST Message dans ServiceNow

1. **Naviguer vers** : System Web Services → Outbound → REST Message
2. **Cliquer sur** : New
3. **Remplir** :
   - **Name** : `AWS AgentCore Webhook`
   - **Endpoint** : `https://YOUR_API_GATEWAY_URL/prod/webhook/servicenow`
   - **Authentication** : `No authentication` (on utilise API Key dans le header)

4. **Sauvegarder**

### 1.2 Ajouter une HTTP Method

1. Dans le REST Message créé, aller à l'onglet **HTTP Methods**
2. **Cliquer sur** : New
3. **Remplir** :
   - **Name** : `POST Incident`
   - **HTTP method** : `POST`
   - **Endpoint** : Laisser vide (hérite du parent)

4. **HTTP Headers** : Ajouter les headers suivants :

| Name | Value |
|------|-------|
| `Content-Type` | `application/json` |
| `x-api-key` | `YOUR_API_KEY` |

5. **HTTP Query Parameters** : Aucun

6. **Content** (Request Body) :
```json
{
    "number": "${number}",
    "short_description": "${short_description}",
    "description": "${description}",
    "urgency": "${urgency}",
    "impact": "${impact}",
    "priority": "${priority}",
    "category": "${category}",
    "subcategory": "${subcategory}",
    "assignment_group": "${assignment_group}",
    "caller_id": "${caller_id}",
    "sys_id": "${sys_id}",
    "sys_created_on": "${sys_created_on}"
}
```

7. **Variable Substitutions** : Les variables `${...}` seront substituées automatiquement

8. **Sauvegarder**

### 1.3 Créer une Business Rule

1. **Naviguer vers** : System Definition → Business Rules
2. **Cliquer sur** : New
3. **Remplir** :
   - **Name** : `Trigger AWS Agent on Incident Create`
   - **Table** : `Incident [incident]`
   - **Active** : Checked
   - **Advanced** : Checked

4. **When to run** :
   - **When** : `after`
   - **Insert** : Checked
   - **Update** : Unchecked (optionnel : cocher si vous voulez aussi sur les mises à jour)

5. **Filter Conditions** (optionnel) :
   - Par exemple : `Priority is 1 - Critical` pour ne traiter que les tickets critiques

6. **Script** :
```javascript
(function executeRule(current, previous /*null when async*/) {
    try {
        // Créer le REST Message
        var r = new sn_ws.RESTMessageV2('AWS AgentCore Webhook', 'POST Incident');

        // Substituer les variables
        r.setStringParameterNoEscape('number', current.getValue('number'));
        r.setStringParameterNoEscape('short_description', current.getValue('short_description'));
        r.setStringParameterNoEscape('description', current.getValue('description'));
        r.setStringParameterNoEscape('urgency', current.getValue('urgency'));
        r.setStringParameterNoEscape('impact', current.getValue('impact'));
        r.setStringParameterNoEscape('priority', current.getValue('priority'));
        r.setStringParameterNoEscape('category', current.getValue('category'));
        r.setStringParameterNoEscape('subcategory', current.getValue('subcategory'));
        r.setStringParameterNoEscape('assignment_group', current.getValue('assignment_group'));
        r.setStringParameterNoEscape('caller_id', current.getValue('caller_id'));
        r.setStringParameterNoEscape('sys_id', current.getValue('sys_id'));
        r.setStringParameterNoEscape('sys_created_on', current.getValue('sys_created_on'));

        // Exécuter la requête
        var response = r.execute();
        var responseBody = response.getBody();
        var httpStatus = response.getStatusCode();

        // Logger la réponse
        gs.info('AWS Agent Response [' + httpStatus + ']: ' + responseBody);

    } catch (ex) {
        gs.error('Error calling AWS Agent: ' + ex.getMessage());
    }

})(current, previous);
```

7. **Sauvegarder**

### 1.4 Tester le webhook

1. **Créer un incident de test** dans ServiceNow
2. **Vérifier les logs** : System Logs → System Log → All
3. **Chercher** : `AWS Agent Response`

---

## Partie 2 : Agent vers ServiceNow (API)

### 2.1 Client ServiceNow

Le client ServiceNow (`src/servicenow/client.py`) permet à l'agent de mettre à jour les tickets.

**Méthodes principales :**

```python
class ServiceNowClient:
    def get_incident(self, number: str) -> Dict[str, Any]:
        """Récupère un incident par numéro"""

    def update_incident(self, sys_id: str, updates: Dict) -> Dict[str, Any]:
        """Met à jour un incident"""

    def add_work_notes(self, number: str, notes: str, state: str = None) -> Dict:
        """Ajoute des work notes et change optionnellement l'état"""

    def resolve_incident(self, number: str, notes: str) -> Dict:
        """Marque un incident comme résolu"""
```

### 2.2 Configuration

Le fichier `src/servicenow/config.py` gère la configuration :

```python
@dataclass
class ServiceNowConfig:
    instance_url: str          # https://devXXXXX.service-now.com
    username: Optional[str]    # Basic auth
    password: Optional[str]    # Basic auth
    oauth_token: Optional[str] # OAuth alternative
```

---

## Partie 3 : Configuration des credentials

### 3.1 Créer un secret dans AWS Secrets Manager

```bash
aws secretsmanager create-secret \
    --name servicenow/credentials \
    --description "ServiceNow API credentials for AgentCore" \
    --secret-string '{
        "instance_url": "https://YOUR_INSTANCE.service-now.com",
        "username": "YOUR_USERNAME",
        "password": "YOUR_PASSWORD"
    }'
```

### 3.2 Mettre à jour le secret (si déjà existant)

```bash
aws secretsmanager update-secret \
    --secret-id servicenow/credentials \
    --secret-string '{
        "instance_url": "https://YOUR_INSTANCE.service-now.com",
        "username": "YOUR_USERNAME",
        "password": "YOUR_PASSWORD"
    }'
```

### 3.3 Vérifier le secret

```bash
aws secretsmanager get-secret-value \
    --secret-id servicenow/credentials \
    --query 'SecretString' \
    --output text | jq .
```

### 3.4 Configurer les permissions IAM

L'agent doit avoir la permission de lire le secret. Ajoutez cette politique au rôle d'exécution :

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:eu-central-1:ACCOUNT_ID:secret:servicenow/*"
        }
    ]
}
```

---

## Partie 4 : Modification de l'agent

### 4.1 Modifier l'outil `update_servicenow_ticket`

Dans `src/agent/agent_level_one_triage.py`, remplacez l'outil simulé par un vrai appel API :

```python
import os
import boto3
import json

def get_servicenow_credentials():
    """Récupère les credentials depuis Secrets Manager"""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='servicenow/credentials')
    return json.loads(response['SecretString'])

@tool
def update_servicenow_ticket(ticket_number: str, resolution_notes: str) -> str:
    """
    Update ServiceNow ticket with resolution notes.
    Makes real API call to ServiceNow.
    """
    try:
        # Récupérer les credentials
        creds = get_servicenow_credentials()

        # Créer le client ServiceNow
        from servicenow.client import ServiceNowClient
        from servicenow.config import ServiceNowConfig

        config = ServiceNowConfig(
            instance_url=creds['instance_url'],
            username=creds['username'],
            password=creds['password']
        )
        client = ServiceNowClient(config)

        # Ajouter les work notes
        result = client.add_work_notes(
            number=ticket_number,
            work_notes=f"[AI Agent Analysis]\n\n{resolution_notes}",
            state="2"  # 2 = In Progress
        )

        return json.dumps({
            "success": True,
            "ticket_number": ticket_number,
            "message": "Ticket updated in ServiceNow",
            "state": "In Progress"
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)
```

### 4.2 Redéployer l'agent

```bash
agentcore launch
```

---

## Tests de bout en bout

### Test 1 : Créer un ticket dans ServiceNow

1. Allez dans ServiceNow → Incident → Create New
2. Remplissez :
   - **Short description** : `Cannot connect to VPN from home`
   - **Description** : `User reports VPN connection timeout when working from home`
   - **Category** : `Network`
   - **Priority** : `3 - Moderate`
3. Soumettez le ticket

### Test 2 : Vérifier le déclenchement

1. **Logs ServiceNow** : System Logs → System Log → All
   - Cherchez `AWS Agent Response`
   - Vérifiez le status HTTP 200

2. **Logs CloudWatch** :
   ```bash
   aws logs tail /aws/lambda/ServiceNowWebhookStack-WebhookHandler-xxx --follow
   ```

### Test 3 : Vérifier la mise à jour du ticket

1. Retournez au ticket dans ServiceNow
2. Vérifiez l'onglet **Activity** ou **Work Notes**
3. Vous devriez voir les notes de l'agent avec :
   - Résumé du problème
   - Causes potentielles
   - Étapes de résolution recommandées
   - Articles KB pertinents

---

## Sécurité et bonnes pratiques

### 1. Ne jamais hardcoder les credentials

❌ **Mauvais** :
```python
password = "my_secret_password"
```

✅ **Bon** :
```python
creds = get_servicenow_credentials()  # Depuis Secrets Manager
```

### 2. Valider les payloads webhook

```python
def validate_payload(body: dict) -> bool:
    required_fields = ['number', 'short_description']
    return all(field in body for field in required_fields)
```

### 3. Limiter les permissions IAM

- Principe du moindre privilège
- Scoper les ressources spécifiquement
- Utiliser des conditions si possible

### 4. Monitorer les appels API

- Activer CloudWatch Logs
- Configurer des alertes sur les erreurs
- Tracker les métriques (latence, taux d'erreur)

### 5. Rate limiting

ServiceNow a des limites d'API. Implémentez :
- Retry avec backoff exponentiel
- Queue pour les pics de charge
- Cache pour les données statiques

---

## Dépannage

### Erreur : "SERVICENOW_INSTANCE_URL not found"

**Cause** : Le secret n'existe pas ou est mal configuré.

**Solution** :
```bash
aws secretsmanager get-secret-value --secret-id servicenow/credentials
```

### Erreur : "401 Unauthorized" de ServiceNow

**Cause** : Credentials invalides.

**Solution** :
1. Vérifiez username/password dans Secrets Manager
2. Testez les credentials manuellement :
   ```bash
   curl -u "username:password" \
     "https://YOUR_INSTANCE.service-now.com/api/now/table/incident?sysparm_limit=1"
   ```

### Erreur : "Business Rule not firing"

**Cause** : La règle n'est pas active ou les conditions ne matchent pas.

**Solution** :
1. Vérifiez que la règle est **Active**
2. Vérifiez les conditions de filtre
3. Testez avec un incident qui matche les conditions

### Erreur : "REST Message failed"

**Cause** : Configuration du REST Message incorrecte.

**Solution** :
1. Testez le REST Message manuellement dans ServiceNow
2. Vérifiez l'API Key dans les headers
3. Vérifiez l'URL de l'endpoint

---

## Prochaines étapes

Félicitations ! 🎉 Vous avez maintenant une intégration ServiceNow bidirectionnelle complète.

Dans le **prochain article (Article 4)**, nous allons :

🔜 **Remplacer la KB simulée** par AWS Bedrock Knowledge Bases
🔜 **Implémenter la recherche sémantique** avec embeddings
🔜 **Connecter à vos vrais documents** (PDF, Confluence, SharePoint)
🔜 **Optimiser les réponses** avec RAG (Retrieval-Augmented Generation)

**Branche Git :** `step-04-knowledge-base`

---

## Ressources

### Documentation ServiceNow
- [REST API Guide](https://developer.servicenow.com/dev.do#!/reference/api/tokyo/rest/)
- [Business Rules](https://docs.servicenow.com/bundle/tokyo-application-development/page/script/business-rules/concept/c_BusinessRules.html)
- [REST Message](https://docs.servicenow.com/bundle/tokyo-application-development/page/integrate/outbound-rest/concept/c_OutboundRESTMessage.html)

### Documentation AWS
- [Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

### Code source
- [Repository GitHub](https://github.com/votre-username/aws-agentcore-tutorial)
- Branch : `step-03-servicenow-integration`

---

**Auteur :** Anthony PINTO
**Date :** Décembre 2025
**Série :** Agent de Support Backoffice avec AWS AgentCore (3/5)

*Cet article fait partie d'une série sur AWS AgentCore.*
