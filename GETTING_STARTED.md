# Getting Started | Démarrage

[🇫🇷 Français](#français) | [🇬🇧 English](#english)

---

## English

### Welcome to the AWS AgentCore Tutorial Series!

This repository contains a complete tutorial series for building an intelligent backoffice support agent using AWS AgentCore.

### 🎯 What You'll Build

An intelligent agent that:
- Receives and analyzes ServiceNow tickets
- Searches a knowledge base for relevant information
- Automatically updates tickets with solutions
- Provides full observability and monitoring
- Implements secure authentication and authorization

### 📚 Tutorial Structure

The tutorial is organized into **5 progressive steps**, each on its own Git branch:

| Step | Topic | Branch | Status |
|------|-------|--------|--------|
| 1 | AWS AgentRuntime Deployment | `step-01-runtime-deployment` | ✅ Available |
| 2 | Gateway & ServiceNow Integration | `step-02-gateway-ticketing` | 🚧 Coming Soon |
| 3 | Knowledge Base Integration | `step-03-knowledge-base` | 🚧 Coming Soon |
| 4 | Observability & Monitoring | `step-04-observability` | 🚧 Coming Soon |
| 5 | Identity & Authorization | `step-05-identity` | 🚧 Coming Soon |

### 🚀 Quick Start

#### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-username/aws-agentcore-tutorial.git
cd aws-agentcore-tutorial

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Navigate to Step 1

```bash
# Using the navigation script
python scripts/navigate.py --step 1

# Or directly with Git
git checkout step-01-runtime-deployment
```

#### 3. Read the Article

- **English**: [docs/en/article-01-runtime.md](docs/en/article-01-runtime.md)
- **Français**: [docs/fr/article-01-runtime.md](docs/fr/article-01-runtime.md)

#### 4. Follow the Tutorial

Each article is a complete, hands-on tutorial that will guide you through:
- Theory and concepts
- Implementation details
- Deployment instructions
- Testing and validation
- Best practices

### 📂 Repository Structure

```
aws-agentcore-tutorial/
├── docs/
│   ├── fr/                    # French articles
│   │   ├── article-01-runtime.md
│   │   ├── article-02-gateway.md
│   │   └── ...
│   └── en/                    # English articles
│       ├── article-01-runtime.md
│       ├── article-02-gateway.md
│       └── ...
├── src/
│   ├── agent/                 # Agent code
│   │   └── my_agent.py
│   ├── tools/                 # Custom tools
│   ├── servicenow/            # ServiceNow integration
│   └── utils/                 # Utilities
├── infrastructure/
│   ├── cdk/                   # AWS CDK infrastructure
│   │   ├── bin/
│   │   ├── lib/
│   │   └── package.json
│   └── provisioning/          # Provisioning scripts
├── scripts/
│   └── navigate.py            # Navigation helper script
├── tests/                     # Tests
├── .bedrock_agentcore.yaml   # AgentCore configuration
├── Dockerfile                 # Container definition
├── requirements.txt           # Python dependencies
└── README.md                  # Main README
```

### 🛠️ Navigation Between Steps

Use the included navigation script to easily switch between tutorial steps:

```bash
# Interactive mode
python scripts/navigate.py

# Direct navigation
python scripts/navigate.py --step 2

# With language preference
python scripts/navigate.py --step 1 --lang fr

# List all steps
python scripts/navigate.py --list
```

### 📖 Available Articles

#### ✅ Article 1: Deploying Your First AWS AgentRuntime

**What you'll learn:**
- AWS AgentCore Runtime fundamentals
- Creating an agent with custom tools
- Deploying to AWS with CDK
- Local and production testing

**Read:** [English](docs/en/article-01-runtime.md) | [Français](docs/fr/article-01-runtime.md)

#### 🚧 Article 2: Gateway Integration for Ticket Management (Coming Soon)

Integration with AWS AgentCore Gateway and ServiceNow

#### 🚧 Article 3: Knowledge Base and Intelligent Analysis (Coming Soon)

Adding semantic search with AWS Bedrock Knowledge Bases

#### 🚧 Article 4: Observability and Monitoring (Coming Soon)

Complete observability with CloudWatch, X-Ray, and metrics

#### 🚧 Article 5: Identity and Authorization (Coming Soon)

Securing your agent with Cognito and IAM

### 🔧 Prerequisites

- **Python 3.9+**
- **Node.js 18+** (for CDK)
- **AWS CLI** (configured)
- **Docker**
- **AWS Account** with Bedrock access

### 💡 Tips

1. **Start with Step 1**: Each step builds on the previous one
2. **Use branches**: Each tutorial step has its own branch with the complete code
3. **Test locally first**: All agents can be tested locally before AWS deployment
4. **Read the articles**: Each article contains detailed explanations and best practices
5. **Check the code**: The repository contains production-ready code examples

### 📞 Support

- 📝 [Open an issue](https://github.com/your-username/aws-agentcore-tutorial/issues)
- 💬 Join our Discord community
- 📧 Contact: your-email@example.com

### 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

---

## Français

### Bienvenue dans la Série de Tutoriels AWS AgentCore !

Ce repository contient une série complète de tutoriels pour construire un agent de support backoffice intelligent utilisant AWS AgentCore.

### 🎯 Ce Que Vous Allez Construire

Un agent intelligent capable de :
- Recevoir et analyser des tickets ServiceNow
- Rechercher des informations dans une base de connaissances
- Mettre à jour automatiquement les tickets avec des solutions
- Fournir une observabilité et un monitoring complets
- Implémenter une authentification et autorisation sécurisées

### 📚 Structure du Tutoriel

Le tutoriel est organisé en **5 étapes progressives**, chacune sur sa propre branche Git :

| Étape | Sujet | Branche | Statut |
|-------|-------|---------|--------|
| 1 | Déploiement AWS AgentRuntime | `step-01-runtime-deployment` | ✅ Disponible |
| 2 | Gateway & Intégration ServiceNow | `step-02-gateway-ticketing` | 🚧 Bientôt |
| 3 | Intégration Base de Connaissances | `step-03-knowledge-base` | 🚧 Bientôt |
| 4 | Observabilité & Monitoring | `step-04-observability` | 🚧 Bientôt |
| 5 | Identité & Autorisation | `step-05-identity` | 🚧 Bientôt |

### 🚀 Démarrage Rapide

#### 1. Cloner et Configurer

```bash
# Cloner le repository
git clone https://github.com/votre-username/aws-agentcore-tutorial.git
cd aws-agentcore-tutorial

# Créer l'environnement virtuel Python
python -m venv .venv
source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

#### 2. Naviguer vers l'Étape 1

```bash
# Utiliser le script de navigation
python scripts/navigate.py --step 1 --lang fr

# Ou directement avec Git
git checkout step-01-runtime-deployment
```

#### 3. Lire l'Article

- **Français**: [docs/fr/article-01-runtime.md](docs/fr/article-01-runtime.md)
- **English**: [docs/en/article-01-runtime.md](docs/en/article-01-runtime.md)

#### 4. Suivre le Tutoriel

Chaque article est un tutoriel complet et pratique qui vous guidera à travers :
- Théorie et concepts
- Détails d'implémentation
- Instructions de déploiement
- Tests et validation
- Bonnes pratiques

### 📂 Structure du Repository

```
aws-agentcore-tutorial/
├── docs/
│   ├── fr/                    # Articles français
│   │   ├── article-01-runtime.md
│   │   ├── article-02-gateway.md
│   │   └── ...
│   └── en/                    # Articles anglais
│       ├── article-01-runtime.md
│       ├── article-02-gateway.md
│       └── ...
├── src/
│   ├── agent/                 # Code de l'agent
│   │   └── my_agent.py
│   ├── tools/                 # Outils personnalisés
│   ├── servicenow/            # Intégration ServiceNow
│   └── utils/                 # Utilitaires
├── infrastructure/
│   ├── cdk/                   # Infrastructure AWS CDK
│   │   ├── bin/
│   │   ├── lib/
│   │   └── package.json
│   └── provisioning/          # Scripts de provisioning
├── scripts/
│   └── navigate.py            # Script d'aide à la navigation
├── tests/                     # Tests
├── .bedrock_agentcore.yaml   # Configuration AgentCore
├── Dockerfile                 # Définition du conteneur
├── requirements.txt           # Dépendances Python
└── README.md                  # README principal
```

### 🛠️ Navigation Entre les Étapes

Utilisez le script de navigation inclus pour basculer facilement entre les étapes :

```bash
# Mode interactif
python scripts/navigate.py

# Navigation directe
python scripts/navigate.py --step 2 --lang fr

# Avec préférence de langue
python scripts/navigate.py --step 1 --lang fr

# Lister toutes les étapes
python scripts/navigate.py --list --lang fr
```

### 📖 Articles Disponibles

#### ✅ Article 1 : Déploiement de votre premier AWS AgentRuntime

**Ce que vous apprendrez :**
- Fondamentaux d'AWS AgentCore Runtime
- Création d'un agent avec des outils personnalisés
- Déploiement sur AWS avec CDK
- Tests locaux et en production

**Lire :** [Français](docs/fr/article-01-runtime.md) | [English](docs/en/article-01-runtime.md)

#### 🚧 Article 2 : Intégration du Gateway pour la gestion des tickets (Bientôt)

Intégration avec AWS AgentCore Gateway et ServiceNow

#### 🚧 Article 3 : Base de Connaissances et Analyse Intelligente (Bientôt)

Ajout de la recherche sémantique avec AWS Bedrock Knowledge Bases

#### 🚧 Article 4 : Observabilité et Monitoring (Bientôt)

Observabilité complète avec CloudWatch, X-Ray et métriques

#### 🚧 Article 5 : Identité et Autorisation (Bientôt)

Sécurisation de votre agent avec Cognito et IAM

### 🔧 Prérequis

- **Python 3.9+**
- **Node.js 18+** (pour CDK)
- **AWS CLI** (configuré)
- **Docker**
- **Compte AWS** avec accès Bedrock

### 💡 Conseils

1. **Commencez par l'Étape 1** : Chaque étape s'appuie sur la précédente
2. **Utilisez les branches** : Chaque étape a sa propre branche avec le code complet
3. **Testez d'abord localement** : Tous les agents peuvent être testés localement avant le déploiement AWS
4. **Lisez les articles** : Chaque article contient des explications détaillées et des bonnes pratiques
5. **Vérifiez le code** : Le repository contient des exemples de code prêts pour la production

### 📞 Support

- 📝 [Ouvrir une issue](https://github.com/votre-username/aws-agentcore-tutorial/issues)
- 💬 Rejoignez notre communauté Discord
- 📧 Contact : votre-email@example.com

### 🤝 Contributions

Les contributions sont bienvenues ! Veuillez lire nos directives de contribution avant de soumettre des PRs.

---

## 📜 License

MIT License - See [LICENSE](LICENSE) file for details.

## 🙏 Remerciements

- AWS Bedrock AgentCore Team
- AWS Community Builders
- ServiceNow Developer Community
- Tous les contributeurs

---

**Ready to start? → [Begin with Article 1](docs/en/article-01-runtime.md) | [Commencez par l'Article 1](docs/fr/article-01-runtime.md)**
