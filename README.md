# AWS AgentCore Tutorial Series | Série de Tutoriels AWS AgentCore

[🇫🇷 Français](#français) | [🇬🇧 English](#english)

---

## Français

### 📚 Série de Tutoriels : Agent de Support Backoffice avec AWS AgentCore

Bienvenue dans cette série de tutoriels complète qui vous guidera dans la création d'un agent de support backoffice intelligent utilisant AWS AgentCore. L'agent recevra des tickets depuis ServiceNow, les analysera, recherchera dans une base de connaissances et mettra automatiquement à jour les tickets.

### 🎯 Objectif de la Série

Construire un système d'agent intelligent capable de :
- ✅ Recevoir et analyser des tickets ServiceNow
- ✅ Rechercher des informations dans une base de connaissances
- ✅ Mettre à jour automatiquement les tickets
- ✅ Monitorer et observer les performances
- ✅ Gérer l'authentification et les autorisations

### 📖 Articles de la Série

#### Article 1 : Déploiement de votre premier AWS AgentRuntime
**Branch:** `step-01-runtime-deployment`

Déployez votre premier agent intelligent avec AWS AgentCore Runtime.

**Ce que vous apprendrez :**
- Configuration de l'environnement AWS AgentCore
- Création d'un agent de base avec des outils personnalisés
- Déploiement sur AWS avec CDK
- Tests locaux et en production

**📄 Lire l'article :** [docs/fr/article-01-runtime.md](docs/fr/article-01-runtime.md)

```bash
git checkout step-01-runtime-deployment
```

---

#### Article 2 : Intégration du Gateway pour la gestion des tickets
**Branch:** `step-02-gateway-ticketing`

Intégrez AWS AgentCore Gateway pour recevoir et traiter les tickets ServiceNow.

**Ce que vous apprendrez :**
- Configuration d'AWS AgentCore Gateway
- Intégration avec ServiceNow
- Gestion du flux de tickets
- Webhooks et événements

**📄 Lire l'article :** [docs/fr/article-02-gateway.md](docs/fr/article-02-gateway.md)

```bash
git checkout step-02-gateway-ticketing
```

---

#### Article 3 : Base de Connaissances et Analyse Intelligente
**Branch:** `step-03-knowledge-base`

Ajoutez une base de connaissances pour des réponses contextuelles et intelligentes.

**Ce que vous apprendrez :**
- Intégration AWS Bedrock Knowledge Bases
- Recherche sémantique (RAG)
- Analyse automatique des tickets
- Génération de réponses contextuelles

**📄 Lire l'article :** [docs/fr/article-03-knowledge.md](docs/fr/article-03-knowledge.md)

```bash
git checkout step-03-knowledge-base
```

---

#### Article 4 : Observabilité et Monitoring
**Branch:** `step-04-observability`

Implémentez une observabilité complète pour votre agent.

**Ce que vous apprendrez :**
- Configuration CloudWatch Logs et Metrics
- Traces AWS X-Ray
- Dashboards de monitoring
- Alertes et alarmes

**📄 Lire l'article :** [docs/fr/article-04-observability.md](docs/fr/article-04-observability.md)

```bash
git checkout step-04-observability
```

---

#### Article 5 : Identité et Autorisation
**Branch:** `step-05-identity`

Sécurisez votre agent avec authentification et autorisation.

**Ce que vous apprendrez :**
- AWS Cognito pour l'authentification
- Contrôle d'accès basé sur les rôles (RBAC)
- Gestion des permissions IAM
- Sécurisation des endpoints

**📄 Lire l'article :** [docs/fr/article-05-identity.md](docs/fr/article-05-identity.md)

```bash
git checkout step-05-identity
```

---

### 🚀 Démarrage Rapide

1. **Clonez le repository**
   ```bash
   git clone https://github.com/votre-username/aws-agentcore-tutorial.git
   cd aws-agentcore-tutorial
   ```

2. **Installez les dépendances**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Naviguez vers l'étape souhaitée**
   ```bash
   # Utilisez le script de navigation
   python scripts/navigate.py --step 1

   # Ou utilisez git directement
   git checkout step-01-runtime-deployment
   ```

### 📁 Structure du Projet

```
aws-agentcore-tutorial/
├── docs/
│   ├── fr/              # Articles en français
│   └── en/              # Articles en anglais
├── infrastructure/
│   ├── cdk/             # Infrastructure AWS CDK
│   └── provisioning/    # Scripts de provisioning
├── src/
│   ├── agent/           # Code de l'agent
│   ├── tools/           # Outils personnalisés
│   ├── servicenow/      # Intégration ServiceNow
│   └── utils/           # Utilitaires
├── tests/               # Tests unitaires et d'intégration
└── scripts/             # Scripts utilitaires
```

### 🛠️ Prérequis

- Python 3.9+
- AWS CLI configuré
- Node.js 18+ (pour CDK)
- Compte AWS
- Compte ServiceNow (pour les articles 2+)

### 📞 Support et Contributions

Des questions ? Ouvrez une issue sur GitHub !

Contributions bienvenues via Pull Requests.

---

## English

### 📚 Tutorial Series: Backoffice Support Agent with AWS AgentCore

Welcome to this comprehensive tutorial series that will guide you in creating an intelligent backoffice support agent using AWS AgentCore. The agent will receive tickets from ServiceNow, analyze them, search a knowledge base, and automatically update tickets.

### 🎯 Series Goal

Build an intelligent agent system capable of:
- ✅ Receiving and analyzing ServiceNow tickets
- ✅ Searching information in a knowledge base
- ✅ Automatically updating tickets
- ✅ Monitoring and observing performance
- ✅ Managing authentication and authorization

### 📖 Series Articles

#### Article 1: Deploying Your First AWS AgentRuntime
**Branch:** `step-01-runtime-deployment`

Deploy your first intelligent agent with AWS AgentCore Runtime.

**What you'll learn:**
- AWS AgentCore environment setup
- Creating a basic agent with custom tools
- Deploying on AWS with CDK
- Local and production testing

**📄 Read the article:** [docs/en/article-01-runtime.md](docs/en/article-01-runtime.md)

```bash
git checkout step-01-runtime-deployment
```

---

#### Article 2: Gateway Integration for Ticket Management
**Branch:** `step-02-gateway-ticketing`

Integrate AWS AgentCore Gateway to receive and process ServiceNow tickets.

**What you'll learn:**
- AWS AgentCore Gateway configuration
- ServiceNow integration
- Ticket flow management
- Webhooks and events

**📄 Read the article:** [docs/en/article-02-gateway.md](docs/en/article-02-gateway.md)

```bash
git checkout step-02-gateway-ticketing
```

---

#### Article 3: Knowledge Base and Intelligent Analysis
**Branch:** `step-03-knowledge-base`

Add a knowledge base for contextual and intelligent responses.

**What you'll learn:**
- AWS Bedrock Knowledge Bases integration
- Semantic search (RAG)
- Automatic ticket analysis
- Contextual response generation

**📄 Read the article:** [docs/en/article-03-knowledge.md](docs/en/article-03-knowledge.md)

```bash
git checkout step-03-knowledge-base
```

---

#### Article 4: Observability and Monitoring
**Branch:** `step-04-observability`

Implement complete observability for your agent.

**What you'll learn:**
- CloudWatch Logs and Metrics configuration
- AWS X-Ray traces
- Monitoring dashboards
- Alerts and alarms

**📄 Read the article:** [docs/en/article-04-observability.md](docs/en/article-04-observability.md)

```bash
git checkout step-04-observability
```

---

#### Article 5: Identity and Authorization
**Branch:** `step-05-identity`

Secure your agent with authentication and authorization.

**What you'll learn:**
- AWS Cognito for authentication
- Role-based access control (RBAC)
- IAM permissions management
- Endpoint security

**📄 Read the article:** [docs/en/article-05-identity.md](docs/en/article-05-identity.md)

```bash
git checkout step-05-identity
```

---

### 🚀 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/aws-agentcore-tutorial.git
   cd aws-agentcore-tutorial
   ```

2. **Install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Navigate to desired step**
   ```bash
   # Use the navigation script
   python scripts/navigate.py --step 1

   # Or use git directly
   git checkout step-01-runtime-deployment
   ```

### 📁 Project Structure

```
aws-agentcore-tutorial/
├── docs/
│   ├── fr/              # French articles
│   └── en/              # English articles
├── infrastructure/
│   ├── cdk/             # AWS CDK infrastructure
│   └── provisioning/    # Provisioning scripts
├── src/
│   ├── agent/           # Agent code
│   ├── tools/           # Custom tools
│   ├── servicenow/      # ServiceNow integration
│   └── utils/           # Utilities
├── tests/               # Unit and integration tests
└── scripts/             # Utility scripts
```

### 🛠️ Prerequisites

- Python 3.9+
- Configured AWS CLI
- Node.js 18+ (for CDK)
- AWS Account
- ServiceNow Account (for articles 2+)

### 📞 Support and Contributions

Questions? Open an issue on GitHub!

Contributions welcome via Pull Requests.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- AWS Bedrock AgentCore Team
- AWS Community Builders
- ServiceNow Developer Community
