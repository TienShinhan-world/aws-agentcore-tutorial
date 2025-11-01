#!/usr/bin/env python3
"""
Navigation script for AWS AgentCore Tutorial Series
Script de navigation pour la série de tutoriels AWS AgentCore
"""
import argparse
import subprocess
import sys
from pathlib import Path

STEPS = {
    1: {
        "branch": "step-01-runtime-deployment",
        "title_fr": "Déploiement de votre premier AWS AgentRuntime",
        "title_en": "Deploying Your First AWS AgentRuntime",
        "article_fr": "docs/fr/article-01-runtime.md",
        "article_en": "docs/en/article-01-runtime.md",
    },
    2: {
        "branch": "step-02-gateway-ticketing",
        "title_fr": "Intégration du Gateway pour la gestion des tickets",
        "title_en": "Gateway Integration for Ticket Management",
        "article_fr": "docs/fr/article-02-gateway.md",
        "article_en": "docs/en/article-02-gateway.md",
    },
    3: {
        "branch": "step-03-knowledge-base",
        "title_fr": "Base de Connaissances et Analyse Intelligente",
        "title_en": "Knowledge Base and Intelligent Analysis",
        "article_fr": "docs/fr/article-03-knowledge.md",
        "article_en": "docs/en/article-03-knowledge.md",
    },
    4: {
        "branch": "step-04-observability",
        "title_fr": "Observabilité et Monitoring",
        "title_en": "Observability and Monitoring",
        "article_fr": "docs/fr/article-04-observability.md",
        "article_en": "docs/en/article-04-observability.md",
    },
    5: {
        "branch": "step-05-identity",
        "title_fr": "Identité et Autorisation",
        "title_en": "Identity and Authorization",
        "article_fr": "docs/fr/article-05-identity.md",
        "article_en": "docs/en/article-05-identity.md",
    },
}


def run_command(cmd):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e.stderr}")
        return None


def get_current_branch():
    """Get the current git branch."""
    return run_command("git branch --show-current")


def list_steps(lang="en"):
    """List all available steps."""
    print("\n" + "=" * 70)
    if lang == "fr":
        print("📚 Série de Tutoriels AWS AgentCore - Étapes Disponibles")
    else:
        print("📚 AWS AgentCore Tutorial Series - Available Steps")
    print("=" * 70 + "\n")

    for step_num, step_info in STEPS.items():
        title = step_info[f"title_{lang}"]
        branch = step_info["branch"]
        print(f"Step {step_num}: {title}")
        print(f"  Branch: {branch}")
        print()


def navigate_to_step(step_num, lang="en"):
    """Navigate to a specific step."""
    if step_num not in STEPS:
        print(f"❌ Error: Step {step_num} does not exist.")
        print(f"Available steps: 1-{len(STEPS)}")
        return False

    step_info = STEPS[step_num]
    branch = step_info["branch"]
    title = step_info[f"title_{lang}"]
    article = step_info[f"article_{lang}"]

    print(f"\n🚀 Navigating to Step {step_num}: {title}")
    print(f"📍 Branch: {branch}\n")

    # Check for uncommitted changes
    status = run_command("git status --porcelain")
    if status:
        print("⚠️  Warning: You have uncommitted changes.")
        response = input("Do you want to stash them? (y/n): ")
        if response.lower() == "y":
            run_command("git stash")
            print("✅ Changes stashed successfully.")
        else:
            print("❌ Aborting. Please commit or stash your changes first.")
            return False

    # Checkout the branch
    result = run_command(f"git checkout {branch}")
    if result is None:
        print(f"❌ Failed to checkout branch: {branch}")
        print(f"Creating new branch from main...")
        run_command(f"git checkout -b {branch} main")

    print(f"\n✅ Successfully navigated to Step {step_num}!")
    print(f"\n📖 Article: {article}")
    print(f"\n💡 To read the article, run:")
    print(f"   cat {article}")
    print(f"\n🔙 To return to main, run:")
    print(f"   git checkout main")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Navigate through AWS AgentCore Tutorial Series steps"
    )
    parser.add_argument(
        "--step",
        type=int,
        help=f"Step number to navigate to (1-{len(STEPS)})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available steps",
    )
    parser.add_argument(
        "--lang",
        choices=["fr", "en"],
        default="en",
        help="Language for messages (fr/en)",
    )

    args = parser.parse_args()

    # Check if we're in a git repository
    if not Path(".git").exists():
        print("❌ Error: Not in a git repository.")
        print("Please run this script from the repository root.")
        sys.exit(1)

    if args.list:
        list_steps(args.lang)
    elif args.step:
        navigate_to_step(args.step, args.lang)
    else:
        # Interactive mode
        list_steps(args.lang)
        try:
            step_num = int(input(f"\nEnter step number (1-{len(STEPS)}): "))
            navigate_to_step(step_num, args.lang)
        except ValueError:
            print("❌ Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")


if __name__ == "__main__":
    main()
