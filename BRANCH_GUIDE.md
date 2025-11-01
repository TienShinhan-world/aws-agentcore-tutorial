# Branch Navigation Guide | Guide de Navigation des Branches

[🇫🇷 Français](#français) | [🇬🇧 English](#english)

---

## English

### Tutorial Branch Structure

This repository uses **Git branches** to organize the tutorial steps. Each step builds upon the previous one, creating a progressive learning experience.

### Available Branches

| Branch | Step | Description | Status |
|--------|------|-------------|--------|
| `main` | - | Latest complete version (currently Step 2) | ✅ Active |
| `step-01-runtime-deployment` | 1 | Basic AgentCore deployment with simulated services | ✅ Complete |
| `step-02-gateway-servicenow` | 2 | Full webhook + ServiceNow integration | ✅ Complete |
| `step-03-knowledge-base` | 3 | Knowledge base with RAG | 🚧 Coming Soon |
| `step-04-observability` | 4 | Full observability stack | 🚧 Coming Soon |
| `step-05-identity` | 5 | Authentication & authorization | 🚧 Coming Soon |

### Key Differences Between Steps

#### Step 1 vs Step 2

**Step 1** (`step-01-runtime-deployment`):
- ✅ Simplified agent for learning AgentCore basics
- ✅ **Simulated** ServiceNow updates (no real API calls)
- ✅ Hardcoded knowledge base (keyword matching)
- ✅ Basic Dockerfile
- ✅ 4 Python dependencies
- ✅ No webhook infrastructure
- ✅ Perfect for: Learning AgentCore fundamentals

**Step 2** (`step-02-gateway-servicenow`):
- ✅ Full webhook architecture (API Gateway + Lambda)
- ✅ **Real** ServiceNow API integration
- ✅ ServiceNow client with error handling
- ✅ Infrastructure as Code (AWS CDK)
- ✅ 5 Python dependencies (adds `requests`)
- ✅ Complete webhook handler
- ✅ Perfect for: Production-ready integration

### How to Navigate

#### Using the Navigation Script (Recommended)

```bash
# Interactive mode - shows all steps and lets you choose
python scripts/navigate.py

# Direct navigation to Step 1
python scripts/navigate.py --step 1

# Direct navigation to Step 2
python scripts/navigate.py --step 2

# List all available steps
python scripts/navigate.py --list
```

#### Using Git Directly

```bash
# Switch to Step 1
git checkout step-01-runtime-deployment

# Switch to Step 2
git checkout step-02-gateway-servicenow

# Return to main branch
git checkout main
```

### What's on Each Branch

#### `step-01-runtime-deployment`

**Files unique to or different from Step 2:**
- `src/agent/my_agent.py` - Simplified (no ServiceNow imports)
- `requirements.txt` - 4 dependencies only
- `Dockerfile` - Simplified CMD
- `README_STEP01.md` - Step 1 specific guide

**What's NOT included:**
- No `src/servicenow/` directory
- No `infrastructure/cdk/` for webhooks
- No `scripts/test_webhook.sh`

#### `step-02-gateway-servicenow`

**All Step 1 files PLUS:**
- `src/servicenow/client.py` - Real ServiceNow API client
- `src/servicenow/config.py` - Configuration management
- `src/servicenow/webhook_handler.py` - Lambda handler
- `infrastructure/cdk/` - Complete CDK stack
- `scripts/test_webhook.sh` - Webhook testing
- `README_STEP02.md` - Step 2 specific guide
- Updated `src/agent/my_agent.py` with real API integration

#### `main`

The `main` branch always contains the **latest complete version**. Currently, this is equivalent to `step-02-gateway-servicenow`.

### Recommended Learning Path

1. **Start with Step 1** (`step-01-runtime-deployment`)
   - Learn AgentCore fundamentals
   - Deploy your first agent
   - Test locally and on AWS
   - Understand the agent pattern

2. **Progress to Step 2** (`step-02-gateway-servicenow`)
   - Add real API integration
   - Deploy webhook infrastructure
   - Configure ServiceNow Business Rules
   - Test end-to-end flow

3. **Continue with upcoming steps** (when available)
   - Step 3: Advanced knowledge base with RAG
   - Step 4: Production observability
   - Step 5: Enterprise authentication

### Branch Merging Strategy

**Important:** Do NOT merge step branches into each other. Each step branch is standalone and represents a complete, working tutorial at that level.

- `step-01` → Standalone (simplified version)
- `step-02` → Standalone (full version, built from step-01 concepts)
- `main` → Tracks the latest complete step

### Testing Each Step

#### Step 1 Testing

```bash
git checkout step-01-runtime-deployment
source .venv/bin/activate
pip install -r requirements.txt

# Test locally
agentcore launch --local
agentcore invoke --local '{"prompt": "Hello!"}'
```

#### Step 2 Testing

```bash
git checkout step-02-gateway-servicenow
source .venv/bin/activate
pip install -r requirements.txt

# Configure ServiceNow credentials
aws secretsmanager create-secret --name servicenow/credentials --secret-string '...'

# Deploy infrastructure
cd infrastructure/cdk
npm install
npm run cdk deploy

# Test webhook
../scripts/test_webhook.sh --url YOUR_WEBHOOK_URL
```

### File Comparison

To see what changed between steps:

```bash
# Compare Step 1 to Step 2
git diff step-01-runtime-deployment..step-02-gateway-servicenow

# Compare specific file
git diff step-01-runtime-deployment..step-02-gateway-servicenow -- src/agent/my_agent.py

# List files that differ
git diff --name-only step-01-runtime-deployment..step-02-gateway-servicenow
```

### Getting Help

If you're lost or unsure which branch to use:

1. **New to AgentCore?** → Start with `step-01-runtime-deployment`
2. **Want production integration?** → Use `step-02-gateway-servicenow`
3. **Want latest code?** → Use `main`

---

## Français

### Structure des Branches du Tutoriel

Ce repository utilise des **branches Git** pour organiser les étapes du tutoriel. Chaque étape s'appuie sur la précédente, créant une expérience d'apprentissage progressive.

### Branches Disponibles

| Branche | Étape | Description | Statut |
|---------|-------|-------------|--------|
| `main` | - | Version complète la plus récente (actuellement Étape 2) | ✅ Active |
| `step-01-runtime-deployment` | 1 | Déploiement AgentCore de base avec services simulés | ✅ Complète |
| `step-02-gateway-servicenow` | 2 | Intégration complète webhook + ServiceNow | ✅ Complète |
| `step-03-knowledge-base` | 3 | Base de connaissances avec RAG | 🚧 Bientôt |
| `step-04-observability` | 4 | Stack d'observabilité complète | 🚧 Bientôt |
| `step-05-identity` | 5 | Authentification & autorisation | 🚧 Bientôt |

### Différences Clés Entre les Étapes

#### Étape 1 vs Étape 2

**Étape 1** (`step-01-runtime-deployment`):
- ✅ Agent simplifié pour apprendre les bases d'AgentCore
- ✅ Mises à jour ServiceNow **simulées** (pas d'appels API réels)
- ✅ Base de connaissances hardcodée (correspondance par mots-clés)
- ✅ Dockerfile basique
- ✅ 4 dépendances Python
- ✅ Pas d'infrastructure webhook
- ✅ Parfait pour : Apprendre les fondamentaux d'AgentCore

**Étape 2** (`step-02-gateway-servicenow`):
- ✅ Architecture webhook complète (API Gateway + Lambda)
- ✅ Intégration API ServiceNow **réelle**
- ✅ Client ServiceNow avec gestion d'erreurs
- ✅ Infrastructure as Code (AWS CDK)
- ✅ 5 dépendances Python (ajoute `requests`)
- ✅ Gestionnaire webhook complet
- ✅ Parfait pour : Intégration prête pour la production

### Comment Naviguer

#### Utiliser le Script de Navigation (Recommandé)

```bash
# Mode interactif - affiche toutes les étapes et vous laisse choisir
python scripts/navigate.py

# Navigation directe vers l'Étape 1
python scripts/navigate.py --step 1 --lang fr

# Navigation directe vers l'Étape 2
python scripts/navigate.py --step 2 --lang fr

# Lister toutes les étapes disponibles
python scripts/navigate.py --list --lang fr
```

#### Utiliser Git Directement

```bash
# Basculer vers l'Étape 1
git checkout step-01-runtime-deployment

# Basculer vers l'Étape 2
git checkout step-02-gateway-servicenow

# Retourner sur la branche main
git checkout main
```

### Contenu de Chaque Branche

#### `step-01-runtime-deployment`

**Fichiers uniques ou différents de l'Étape 2 :**
- `src/agent/my_agent.py` - Simplifié (pas d'imports ServiceNow)
- `requirements.txt` - 4 dépendances seulement
- `Dockerfile` - CMD simplifié
- `README_STEP01.md` - Guide spécifique à l'Étape 1

**Ce qui N'est PAS inclus :**
- Pas de répertoire `src/servicenow/`
- Pas de `infrastructure/cdk/` pour les webhooks
- Pas de `scripts/test_webhook.sh`

#### `step-02-gateway-servicenow`

**Tous les fichiers de l'Étape 1 PLUS :**
- `src/servicenow/client.py` - Client API ServiceNow réel
- `src/servicenow/config.py` - Gestion de configuration
- `src/servicenow/webhook_handler.py` - Gestionnaire Lambda
- `infrastructure/cdk/` - Stack CDK complète
- `scripts/test_webhook.sh` - Tests webhook
- `README_STEP02.md` - Guide spécifique à l'Étape 2
- `src/agent/my_agent.py` mis à jour avec intégration API réelle

#### `main`

La branche `main` contient toujours la **dernière version complète**. Actuellement, c'est équivalent à `step-02-gateway-servicenow`.

### Parcours d'Apprentissage Recommandé

1. **Commencez par l'Étape 1** (`step-01-runtime-deployment`)
   - Apprenez les fondamentaux d'AgentCore
   - Déployez votre premier agent
   - Testez localement et sur AWS
   - Comprenez le pattern agent

2. **Progressez vers l'Étape 2** (`step-02-gateway-servicenow`)
   - Ajoutez l'intégration API réelle
   - Déployez l'infrastructure webhook
   - Configurez les Business Rules ServiceNow
   - Testez le flux de bout en bout

3. **Continuez avec les étapes à venir** (quand disponibles)
   - Étape 3 : Base de connaissances avancée avec RAG
   - Étape 4 : Observabilité pour la production
   - Étape 5 : Authentification d'entreprise

### Stratégie de Fusion des Branches

**Important :** Ne fusionnez PAS les branches step entre elles. Chaque branche step est autonome et représente un tutoriel complet et fonctionnel à ce niveau.

- `step-01` → Autonome (version simplifiée)
- `step-02` → Autonome (version complète, basée sur les concepts de step-01)
- `main` → Suit la dernière étape complète

### Tester Chaque Étape

#### Test de l'Étape 1

```bash
git checkout step-01-runtime-deployment
source .venv/bin/activate
pip install -r requirements.txt

# Test local
agentcore launch --local
agentcore invoke --local '{"prompt": "Bonjour!"}'
```

#### Test de l'Étape 2

```bash
git checkout step-02-gateway-servicenow
source .venv/bin/activate
pip install -r requirements.txt

# Configurer les credentials ServiceNow
aws secretsmanager create-secret --name servicenow/credentials --secret-string '...'

# Déployer l'infrastructure
cd infrastructure/cdk
npm install
npm run cdk deploy

# Tester le webhook
../scripts/test_webhook.sh --url VOTRE_URL_WEBHOOK
```

### Comparaison de Fichiers

Pour voir ce qui a changé entre les étapes :

```bash
# Comparer l'Étape 1 à l'Étape 2
git diff step-01-runtime-deployment..step-02-gateway-servicenow

# Comparer un fichier spécifique
git diff step-01-runtime-deployment..step-02-gateway-servicenow -- src/agent/my_agent.py

# Lister les fichiers qui diffèrent
git diff --name-only step-01-runtime-deployment..step-02-gateway-servicenow
```

### Obtenir de l'Aide

Si vous êtes perdu ou incertain de quelle branche utiliser :

1. **Nouveau sur AgentCore ?** → Commencez par `step-01-runtime-deployment`
2. **Voulez une intégration production ?** → Utilisez `step-02-gateway-servicenow`
3. **Voulez le code le plus récent ?** → Utilisez `main`

---

**Questions?** Open an issue on GitHub | Ouvrez une issue sur GitHub
