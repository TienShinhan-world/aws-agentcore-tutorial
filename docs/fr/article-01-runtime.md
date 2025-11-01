# Article 1 : Déployer un agent de support avec AWS AgentCore Runtime

> **Série : Agent de Support Backoffice avec AWS AgentCore**
> **Étape 1 sur 5** | [English version](../en/article-01-runtime.md)

## Table des matières

1. [Introduction](#introduction)
2. [Qu'est-ce qu'AWS AgentCore Runtime ?](#quest-ce-quaws-agentcore-runtime)
3. [Prérequis](#prérequis)
4. [Configuration de l'environnement](#configuration-de-lenvironnement)
5. [Création de l'agent](#création-de-lagent)
6. [Tests locaux](#tests-locaux)
7. [Déploiement sur AWS](#déploiement-sur-aws)
8. [Invocation de l'agent](#invocation-de-lagent)
9. [Observabilité](#observabilité)
10. [Prochaines étapes](#prochaines-étapes)

---

## Introduction

Lorsqu'un ticket arrive dans ServiceNow, l'équipe de support doit analyser le problème, rechercher dans la base de connaissances, et préparer une réponse. Ce processus manuel prend du temps et retarde la résolution.

Dans cette série d'articles, nous allons construire un **agent de support backoffice intelligent** qui :
- ✅ Reçoit automatiquement les tickets ServiceNow via webhook
- ✅ Analyse les données de tickets reçues
- ✅ Recherche des solutions dans une base de connaissances
- ✅ Met à jour directement les tickets dans ServiceNow
- ✅ Aide l'équipe de support à traiter les tickets plus rapidement

### Ce que vous allez construire dans cet article

Dans ce premier article, nous allons créer un prototype fonctionnel avec **AWS AgentCore Runtime**. Cet agent :
- Reçoit les données de tickets comme entrée (via webhook dans l'Article 2)
- Parse et extrait les informations pertinentes des tickets
- Recherche dans une base de connaissances simulée
- Prépare des mises à jour de tickets

**Important :** Pour valider le concept rapidement, nous utilisons des données simulées (hard-coded). Dans l'Article 2, nous déploierons l'infrastructure webhook complète avec API Gateway + Lambda, et connecterons l'agent à la vraie API ServiceNow.

### Temps estimé
⏱️ **30-45 minutes** pour compléter ce tutoriel.

---

## Qu'est-ce qu'AWS AgentCore Runtime ?

**AWS AgentCore Runtime** est un service qui permet de déployer, exécuter et mettre à l'échelle des agents IA de manière sécurisée. Il offre :

### Isolation de session
Chaque session utilisateur s'exécute dans son propre environnement protégé, empêchant les fuites de données - une exigence critique pour les applications manipulant des données sensibles.

### Environnement serverless
- Pas de serveurs à gérer
- Mise à l'échelle automatique
- Facturation à l'utilisation

### Compatibilité avec tous les frameworks
AgentCore Runtime fonctionne avec :
- ✅ **Strands Agents** (que nous utilisons dans cette série)
- ✅ CrewAI
- ✅ LangGraph
- ✅ LlamaIndex
- ✅ Tout framework ou agent personnalisé

### Configurations réseau

AgentCore Runtime supporte différentes configurations réseau :

**Public** (que nous utilisons dans cet article)
- Exécution avec accès Internet géré
- Parfait pour les prototypes et les tests

**VPC-only** (disponible prochainement)
- Accès aux ressources hébergées dans votre VPC
- Connexion via AWS PrivateLink
- Idéal pour la production avec des exigences de sécurité strictes

---

## Prérequis

### Compte et outils AWS

1. **Compte AWS actif**
   - Accès à Amazon Bedrock dans votre région (eu-central-1)
   - Permissions IAM pour créer des rôles et des repositories ECR

2. **AWS CLI configuré**
   ```bash
   aws configure
   # Vérifiez la configuration
   aws sts get-caller-identity
   ```

3. **Python 3.9 ou supérieur**
   ```bash
   python --version
   # Devrait afficher Python 3.9.x ou supérieur
   ```

4. **Git**
   ```bash
   git --version
   ```

### Connaissances recommandées

- Bases de Python
- Compréhension des concepts d'agents IA
- Familiarité avec AWS (IAM, services de base)

---

## Configuration de l'environnement

### 1. Cloner le repository

```bash
git clone https://github.com/votre-username/aws-agentcore-tutorial.git
cd aws-agentcore-tutorial

# Basculer sur la branche step-01 (si disponible)
git checkout step-01-runtime-deployment
```

### 2. Créer et activer un environnement virtuel Python

```bash
# Créer l'environnement virtuel
python -m venv .venv

# Activer l'environnement
# Sur Linux/Mac :
source .venv/bin/activate

# Sur Windows :
.venv\Scripts\activate
```

Votre prompt devrait maintenant commencer par `(.venv)`.

### 3. Installer les dépendances

Le fichier `requirements.txt` contient toutes les dépendances nécessaires :

```txt
strands-agents
strands-agents-tools
bedrock-agentcore
bedrock-agentcore-starter-toolkit
```

Installez-les avec :

```bash
pip install -r requirements.txt
```

**Vérification :**
```bash
# Vérifiez que les packages sont installés
pip list | grep -E "strands|bedrock"
```

Vous devriez voir :
```
bedrock-agentcore              x.x.x
bedrock-agentcore-starter-toolkit x.x.x
strands-agents                 x.x.x
strands-agents-tools          x.x.x
```

### 4. Vérifier l'accès au CLI AgentCore

L'installation du package `bedrock-agentcore-starter-toolkit` vous donne accès au CLI AgentCore :

```bash
agentcore --help
```

Vous devriez voir l'aide du CLI avec les commandes disponibles.

---

## Création de l'agent

### Structure du projet

Voici la structure de notre projet :

```
aws-agentcore-tutorial/
├── src/
│   └── agent/
│       └── agent_level_one_triage.py          # Notre agent principal
├── requirements.txt
└── .bedrock_agentcore.yaml      # Configuration (généré automatiquement)
```

### Code de l'agent

Ouvrons `src/agent/agent_level_one_triage.py` pour comprendre la structure.

#### Import des modules

```python
import json
from strands import Agent, tool
from strands_tools import calculator, current_time
from bedrock_agentcore.runtime import BedrockAgentCoreApp
```

**Explications :**
- `strands` : Framework pour créer des agents IA
- `@tool` : Décorateur pour définir des outils que l'agent peut utiliser
- `BedrockAgentCoreApp` : Classe principale pour créer une application AgentCore

#### Configuration de l'agent

```python
SYSTEM_PROMPT = """
You are a helpful backoffice support assistant for ServiceNow ticket management.
Your role is to:
1. Parse and analyze ticket data received from webhooks
2. Search the knowledge base for relevant solutions
3. Update ServiceNow tickets with proposed resolutions
4. Provide clear, professional responses to support staff

When analyzing a ticket:
- Parse the ticket data JSON to extract key information
- Search the knowledge base for similar issues
- Propose a resolution based on available information
- Update the ServiceNow ticket with work notes and resolution

You receive complete ticket data via webhook.
Always be concise and professional in your responses.
"""
```

Le **System Prompt** définit :
- La personnalité de l'agent
- Son rôle et ses responsabilités
- Comment il doit se comporter

C'est l'élément clé qui guide le comportement de l'agent.

#### Définition des outils (Tools)

Les outils permettent à l'agent d'interagir avec des systèmes externes. Définissons trois outils pour notre agent de support.

**Outil 1 : Parse des données de ticket reçues**

```python
@tool
def parse_ticket_data(ticket_json: str) -> str:
    """
    Parse ticket data received from ServiceNow webhook.
    Extracts key information for analysis.
    """
    try:
        ticket = json.loads(ticket_json)

        formatted = {
            "ticket_number": ticket.get("number", "Unknown"),
            "short_description": ticket.get("short_description", ""),
            "description": ticket.get("description", ""),
            "priority": ticket.get("priority", ""),
            "state": ticket.get("state", ""),
            "requester": ticket.get("caller_id", ""),
            "category": ticket.get("category", "")
        }

        return json.dumps(formatted, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to parse: {str(e)}"})
```

**Ce que fait cet outil :**
- Reçoit les données complètes d'un ticket en format JSON
- Extrait et formate les informations clés du ticket
- Gère les erreurs de parsing gracieusement
- Dans l'Article 2, recevra les données directement via webhook ServiceNow

**Architecture webhook (Article 2) :**
```
ServiceNow (nouveau ticket créé)
    ↓ Déclenche Business Rule
    ↓ HTTP POST avec données complètes du ticket
API Gateway (/webhook/servicenow)
    ↓ Invoque
Lambda Function (webhook_handler)
    ↓ Appelle
Agent (parse_ticket_data + analyse + update)
```

**Outil 2 : Recherche dans la base de connaissances**

```python
@tool
def search_knowledge_base(query: str) -> str:
    """Search the knowledge base for solutions related to the query"""
    # Simulated knowledge base - will be replaced with AWS Bedrock Knowledge Base in Article 3
    knowledge_articles = []

    query_lower = query.lower()

    if "vpn" in query_lower:
        knowledge_articles.append({
            "article_id": "KB0001",
            "title": "VPN Connection Timeout Troubleshooting",
            "summary": "Common causes and solutions for VPN connection timeout errors",
            "solution": [
                "1. Check if user's home network allows VPN traffic...",
                "2. Verify VPN client version is up to date",
                # ... autres étapes
            ],
            "category": "Network Access"
        })

    # ... autres articles

    return json.dumps(response, indent=2)
```

**Ce que fait cet outil :**
- Recherche des articles de la base de connaissances pertinents
- Retourne les solutions correspondantes
- Dans cet article, utilise une logique simple basée sur des mots-clés
- Dans l'Article 3, utilisera AWS Bedrock Knowledge Bases avec recherche sémantique

**Outil 3 : Mise à jour de ticket ServiceNow**

```python
@tool
def update_servicenow_ticket(ticket_number: str, resolution_notes: str) -> str:
    """
    Update ServiceNow ticket with resolution notes.
    Makes real API call to ServiceNow (in Article 2).
    """
    try:
        # Simulated update - will be replaced with real ServiceNow API call in Article 2
        result = {
            "success": True,
            "ticket_number": ticket_number,
            "message": "Ticket update prepared",
            "state": "In Progress",
            "work_notes": resolution_notes,
            "note": "This is a simulated update. In Article 2, this will make a real API call to ServiceNow."
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to update: {str(e)}"
        }, indent=2)
```

**Ce que fait cet outil :**
- Prépare une mise à jour de ticket avec notes de résolution
- Simule la mise à jour dans cet article
- Dans l'Article 2, effectuera un vrai appel API REST à ServiceNow
- Retourne un résultat structuré indiquant le succès ou l'échec

#### Initialisation de l'application AgentCore

```python
# Créer l'application AgentCore
app = BedrockAgentCoreApp()

# Créer l'agent avec le modèle Nova Lite
agent = Agent(
    model="eu.amazon.nova-lite-v1:0",
    system_prompt=SYSTEM_PROMPT,
    tools=[
        calculator,
        current_time,
        parse_ticket_data,      # Parse les données de ticket reçues
        search_knowledge_base,
        update_servicenow_ticket  # Met à jour ServiceNow
    ]
)
```

**Explications :**
- `BedrockAgentCoreApp()` : Crée l'application AgentCore
- `Agent()` : Initialise l'agent Strands avec :
  - **model** : Amazon Nova Lite (rapide et économique)
  - **system_prompt** : Le prompt système défini plus haut
  - **tools** : Liste des outils disponibles pour l'agent

#### Point d'entrée de l'application

```python
@app.entrypoint
def invoke(payload):
    """Handler for agent invocation"""
    user_message = payload.get(
        "prompt",
        "No prompt found in input. Please provide a 'prompt' key in the JSON payload."
    )
    response = agent(user_message)
    return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()
```

**Explications :**
- `@app.entrypoint` : Définit la fonction appelée lors d'une invocation
- `payload.get("prompt")` : Extrait le message utilisateur du payload JSON
- `agent(user_message)` : Invoque l'agent avec le message
- `response.message['content'][0]['text']` : Extrait le texte de la réponse

---

## Tests locaux

Avant de déployer sur AWS, testons l'agent localement.

### 1. Lancer l'agent en mode local

```bash
# Depuis le répertoire racine du projet
agentcore launch --local
```

**Ce que fait cette commande :**
- Lance l'agent dans un serveur local
- Écoute sur `http://localhost:8080`
- Permet de tester l'agent sans déploiement AWS
- Utilise vos credentials AWS locaux pour accéder à Bedrock

Vous devriez voir :
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

### 2. Tester avec le CLI AgentCore

Ouvrez un nouveau terminal (gardez le serveur qui tourne) et testez :

**Test 1 : Salutation simple**
```bash
agentcore invoke --local '{"prompt": "Hello! What can you help me with?"}'
```

L'agent devrait vous répondre en expliquant son rôle de support pour ServiceNow.

**Test 2 : Analyse de données de ticket VPN**
```bash
agentcore invoke --local '{"prompt": "Analyze this ticket data: {\"number\": \"INC0001234\", \"short_description\": \"VPN connection timeout\", \"description\": \"User cannot connect to VPN from home\", \"priority\": \"2\", \"state\": \"1\"}"}'
```

L'agent devrait :
1. Appeler `parse_ticket_data()` avec les données JSON du ticket
2. Extraire les informations clés (numéro, description, priorité)
3. Appeler `search_knowledge_base` avec "VPN"
4. Trouver l'article KB0001
5. Proposer une solution basée sur l'article
6. Appeler `update_servicenow_ticket()` pour mettre à jour le ticket

**Test 3 : Recherche générale**
```bash
agentcore invoke --local '{"prompt": "How do I troubleshoot email sync issues on iPhone?"}'
```

L'agent devrait rechercher dans la base de connaissances et retourner l'article KB0003 sur les problèmes de synchronisation email mobile.

### 3. Tester avec curl (optionnel)

Vous pouvez aussi tester directement avec curl :

```bash
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze ticket INC0001235"
  }'
```

### 4. Observer le comportement de l'agent

Quand vous invoquez l'agent, observez comment il :
- **Raisonne** : Planifie les étapes nécessaires
- **Agit** : Appelle les outils appropriés
- **Synthétise** : Combine les informations pour donner une réponse complète

C'est le cycle **Reasoning → Acting → Observing** des agents IA.

---

## Déploiement sur AWS

Maintenant que l'agent fonctionne localement, déployons-le sur AWS avec AgentCore Runtime.

### 1. Configurer l'agent pour le déploiement

Arrêtez le serveur local (Ctrl+C) et exécutez :

```bash
agentcore configure --entrypoint src/agent/agent_level_one_triage.py
```

**Questions posées par le CLI :**

1. **Auto-create IAM execution role?** → Appuyez sur Entrée (Yes)
   - Crée automatiquement un rôle IAM avec les permissions nécessaires

2. **Auto-create ECR repository?** → Appuyez sur Entrée (Yes)
   - Crée un repository Amazon ECR pour stocker l'image Docker

3. **Dependency file detected** → Appuyez sur Entrée (Confirm)
   - Utilise requirements.txt pour installer les dépendances

Cette commande crée un fichier `.bedrock_agentcore.yaml` avec la configuration :

```yaml
default_agent: agent_level_one_triage
agents:
  agent_level_one_triage:
    name: agent_level_one_triage
    entrypoint: src/agent/agent_level_one_triage.py
    platform: linux/arm64
    container_runtime: docker
    aws:
      account: 'VOTRE-ACCOUNT-ID'
      region: eu-central-1
      ecr_auto_create: true
      execution_role_auto_create: true
      network_configuration:
        network_mode: PUBLIC
      observability:
        enabled: true
```

### 2. Activer l'observabilité avec CloudWatch

Pour activer la livraison de traces, configurez Transaction Search dans CloudWatch :

```bash
# Activer CloudWatch Logs pour les traces
aws xray update-trace-segment-destination --destination CloudWatchLogs

# Configurer le taux d'échantillonnage (1% ici)
aws xray update-indexing-rule --name "Default" --rule '{"Probabilistic": {"DesiredSamplingPercentage": 1}}'
```

Vérifiez la configuration :

```bash
aws xray get-trace-segment-destination
aws xray get-indexing-rules
```

### 3. Déployer l'agent

Lancez le déploiement :

```bash
agentcore launch
```

**Ce que fait cette commande :**
1. **Build** : Construit l'image Docker de votre agent
2. **Push** : Pousse l'image vers Amazon ECR
3. **Deploy** : Crée l'infrastructure AgentCore Runtime :
   - Environnement serverless isolé
   - Configuration réseau (mode PUBLIC)
   - Rôles IAM avec permissions Bedrock
   - Endpoints pour l'invocation

Le déploiement prend généralement **2-3 minutes**.

Vous verrez :
```
Building agent...
Pushing to ECR...
Deploying to AgentCore Runtime...
✓ Agent deployed successfully!

Endpoint: https://xxxxxx.execute-api.eu-central-1.amazonaws.com/prod/invoke
```

---

## Invocation de l'agent

Une fois déployé, invoquez l'agent depuis n'importe où.

### 1. Vérifier le statut

```bash
agentcore status
```

Devrait afficher :
```
Agent: agent_level_one_triage
Status: ACTIVE
Endpoint: https://xxxxxx.execute-api.eu-central-1.amazonaws.com/prod/invoke
Region: eu-central-1
```

### 2. Invoquer l'agent déployé

**Sans le flag `--local`, les commandes utilisent l'endpoint AWS :**

```bash
agentcore invoke '{"prompt": "Analyze ticket INC0001234 and provide a resolution"}'
```

L'agent s'exécute maintenant sur AWS AgentCore Runtime !

### 3. Exemple d'utilisation complète

Testons un scénario complet :

```bash
agentcore invoke '{
  "prompt": "Analyze this ticket: {\"number\": \"INC0001236\", \"short_description\": \"Email sync issues on iPhone\", \"description\": \"User cannot sync email on iPhone 14\", \"priority\": \"3\", \"state\": \"1\"}. Find relevant KB articles and update the ticket with the solution."
}'
```

L'agent va :
1. ✅ Parser les données du ticket INC0001236 avec `parse_ticket_data()`
2. ✅ Identifier le problème (email sync sur iPhone)
3. ✅ Rechercher dans la KB avec `search_knowledge_base()` → trouve KB0003
4. ✅ Mettre à jour ServiceNow avec `update_servicenow_ticket()` avec les étapes de résolution
5. ✅ Retourner une réponse professionnelle et structurée

---

## Observabilité

### Consulter les logs

AgentCore Runtime intègre automatiquement avec CloudWatch Logs.

**Via le CLI :**
```bash
# Voir les derniers logs
agentcore logs --tail 50

# Suivre les logs en temps réel
agentcore logs --follow
```

**Via la console AWS :**
1. Ouvrez CloudWatch dans la console AWS
2. Allez dans **Logs > Log groups**
3. Cherchez le log group de votre agent
4. Explorez les logs d'exécution

### Traces X-Ray (si configuré)

Si vous avez activé X-Ray Transaction Search, vous pouvez :
- Visualiser les traces d'exécution
- Voir les appels aux outils
- Analyser les performances
- Déboguer les erreurs

Nous approfondirons l'observabilité dans l'Article 4.

---

## Résumé et bonnes pratiques

### Ce que nous avons accompli 🎉

✅ Créé un agent de support intelligent pour ServiceNow
✅ Défini 3 outils personnalisés :
   - `parse_ticket_data` : Parse les données de tickets reçues
   - `search_knowledge_base` : Recherche dans la KB
   - `update_servicenow_ticket` : Met à jour les tickets
✅ Testé l'agent localement avec `agentcore launch --local`
✅ Déployé l'agent sur AWS avec `agentcore launch`
✅ Invoqué l'agent via le CLI
✅ Configuré l'observabilité de base

### Bonnes pratiques

#### 1. Développement itératif

Toujours suivre ce cycle :
```
Développer localement → Tester localement → Déployer → Tester en prod
```

#### 2. System Prompt

- Soyez précis sur le rôle de l'agent
- Donnez des exemples de comportement attendu
- Itérez sur le prompt basé sur les résultats

#### 3. Outils (Tools)

- Gardez les outils simples et focalisés
- Retournez toujours du JSON structuré
- Incluez une gestion d'erreur robuste

#### 4. Tests

Testez différents scénarios :
- Cas nominaux (ticket existe, KB trouve une solution)
- Cas d'erreur (ticket inexistant, pas de solution)
- Cas edge (requêtes ambiguës, multiples solutions possibles)

---

## Dépannage

### L'agent ne trouve pas le modèle

**Erreur :** `Model eu.amazon.nova-lite-v1:0 not found`

**Solution :**
- Vérifiez que vous avez accès à Amazon Bedrock dans eu-central-1
- Activez le modèle Nova Lite dans la console Bedrock
- Vérifiez les permissions IAM pour invoquer le modèle

### Erreur de permissions IAM

**Erreur :** `AccessDeniedException`

**Solution :**
Le rôle IAM créé automatiquement doit avoir :
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:eu-central-1::foundation-model/amazon.nova-lite-v1:0"
    }
  ]
}
```

### L'agent local ne démarre pas

**Erreur :** `Port 8080 already in use`

**Solution :**
```bash
# Trouver le processus utilisant le port
lsof -i :8080

# Tuer le processus
kill -9 <PID>

# Ou utiliser un autre port
agentcore launch --local --port 8081
```

---

## Prochaines étapes

Dans le **prochain article (Article 2)**, nous allons :

🔜 **Implémenter l'architecture webhook complète** (ServiceNow → API Gateway → Lambda → Agent)
🔜 **Créer un client API ServiceNow** pour les mises à jour en temps réel
🔜 **Déployer l'infrastructure** avec AWS CDK (API Gateway + Lambda + Secrets Manager)
🔜 **Configurer ServiceNow Business Rules** pour déclencher les webhooks
🔜 **Implémenter un flux de tickets de bout en bout** :
   - ServiceNow envoie les données de ticket via webhook
   - Lambda invoque l'agent avec les données
   - Agent analyse et met à jour ServiceNow directement
🔜 **Créer une suite de tests complète** (81 tests, 91% de couverture)

**Branche Git :** `step-02-gateway-servicenow`

---

## Ressources

### Documentation
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Strands Agents Documentation](https://docs.strands.ai/)
- [Amazon Nova Models](https://aws.amazon.com/bedrock/nova/)

### Code source
- [Repository GitHub](https://github.com/votre-username/aws-agentcore-tutorial)
- Branch : `step-01-runtime-deployment`

### Support
- Ouvrez une [issue sur GitHub](https://github.com/votre-username/aws-agentcore-tutorial/issues)
- [ServiceNow Developer Portal](https://developer.servicenow.com/)

---

## Conclusion

Félicitations ! 🎉 Vous avez déployé votre premier agent intelligent avec AWS AgentCore Runtime.

**Récapitulatif :**
- Vous avez compris les concepts d'AgentCore Runtime
- Créé un agent avec 3 outils ServiceNow :
  - `parse_ticket_data` : Parse les données de tickets
  - `search_knowledge_base` : Recherche de solutions
  - `update_servicenow_ticket` : Mise à jour de tickets
- Testé localement puis déployé sur AWS
- Invoqué l'agent en production

**L'approche progressive :**
- **Article 1** (ce tutoriel) : Agent fonctionnel avec parsing de données
- **Article 2** : Architecture webhook complète + API ServiceNow réelle + Infrastructure AWS CDK
- **Articles 3-5** : Fonctionnalités avancées (KB, Observability, Identity)

Cette approche vous permet de valider rapidement le concept avant d'investir dans l'infrastructure complète. L'agent est déjà conçu pour recevoir des données de tickets en entrée, ce qui facilite l'intégration webhook dans l'Article 2.

**Prêt pour la suite ?** → [Article 2 : Gateway et intégration ServiceNow](article-02-gateway.md)

---

**Auteur :** Votre Nom
**Date :** Octobre 2025
**Série :** Agent de Support Backoffice avec AWS AgentCore (1/5)

*Cet article fait partie d'une série de 5 articles sur AWS AgentCore.*
