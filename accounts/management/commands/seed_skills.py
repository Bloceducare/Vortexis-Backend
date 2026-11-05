from django.core.management.base import BaseCommand
from accounts.models import Skill


SKILLS_LIST = [
    # Programming Languages
    "Python",
    "JavaScript",
    "TypeScript",
    "Solidity",
    "Rust",
    "Go",
    "C++",
    "Java",
    "Kotlin",
    "Swift",
    "PHP",
    "SQL",
    
    # AI & Data
    "Artificial Intelligence",
    "Machine Learning",
    "Deep Learning",
    "Data Science",
    "Data Engineering",
    "Computer Vision",
    "Natural Language Processing",
    "Prompt Engineering",
    "Large Language Models (LLMs)",
    
    # Design & Product
    "Product Design",
    "UI/UX Design",
    "Graphic Design",
    "Product Management",
    "Project Management",
    "User Research",
    "Wireframing & Prototyping",
    
    # Web & App Development
    "Frontend Development",
    "Backend Development",
    "Fullstack Development",
    "Mobile App Development",
    "React",
    "Next.js",
    "Vue.js",
    "Node.js",
    "Django",
    "FastAPI",
    "Flutter",
    "React Native",
    "GraphQL",
    "RESTful APIs",
    
    # Web3 & Blockchain
    "Web3 Development",
    "Blockchain Architecture",
    "Smart Contracts",
    "DeFi Development",
    "NFTs & Tokens",
    "Zero Knowledge Proofs (ZKP)",
    
    # DevOps, Cloud & Security
    "DevOps",
    "Cloud Computing",
    "Docker & Containers",
    "Kubernetes",
    "Cybersecurity",
    "Smart Contract Auditing",
    
    # Quality & Documentation
    "QA & Software Testing",
    "Technical Writing",
    "System Architecture",
]


class Command(BaseCommand):
    help = "Seed initial skills into the accounts_skill table"

    def handle(self, *args, **kwargs):
        created_count = 0
        existing_count = 0

        for skill_name in SKILLS_LIST:
            # Check length constraint
            clean_name = skill_name.strip()[:50]
            skill, created = Skill.objects.get_or_create(name=clean_name)
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created skill: {clean_name}"))
            else:
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nFinished seeding skills! Created: {created_count}, Already existed: {existing_count}, Total: {len(SKILLS_LIST)}"
            )
        )

