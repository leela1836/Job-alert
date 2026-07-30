"""Which skills does the market keep asking for that your resume does not mention?

Restricted to postings you could realistically get - matching role family,
reachable location, sane seniority - so the output reflects the jobs you are
actually competing for rather than the whole internet.
"""

from __future__ import annotations

import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor

from matching import has_term, load_preferences, rank_jobs
from models import DATA_DIR, JOBS_PATH, PROFILE_PATH, Job, load_json, save_json
from sources import fetch_greenhouse_description

GAP_REPORT_PATH = DATA_DIR / "gap_report.json"

# Canonical skill -> spellings seen in postings.
SKILLS: dict[str, list[str]] = {
    # Languages
    "Python": ["python"], "Java": ["java"], "TypeScript": ["typescript", "ts"],
    "JavaScript": ["javascript", "js"], "Go": ["golang", "go lang"], "Rust": ["rust"],
    "C++": ["c++"], "C#": ["c#"], "Scala": ["scala"], "Kotlin": ["kotlin"], "Ruby": ["ruby"],
    "SQL": ["sql"], "Bash/Shell": ["bash", "shell scripting"],
    # Web / backend
    "React": ["react", "reactjs", "react.js"], "Node.js": ["node.js", "nodejs", "node"],
    "Express": ["express", "express.js"], "Next.js": ["next.js", "nextjs"],
    "Django": ["django"], "Flask": ["flask"], "FastAPI": ["fastapi", "fast api"],
    "Spring Boot": ["spring boot", "springboot", "spring"],
    "GraphQL": ["graphql"], "gRPC": ["grpc"], "REST APIs": ["rest api", "rest apis", "restful"],
    "Microservices": ["microservices", "microservice"],
    # Data
    "PostgreSQL": ["postgresql", "postgres"], "MySQL": ["mysql"], "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"], "Elasticsearch": ["elasticsearch", "elastic search"],
    "Kafka": ["kafka"], "Spark": ["spark", "pyspark"], "Airflow": ["airflow"],
    "dbt": ["dbt"], "Snowflake": ["snowflake"], "BigQuery": ["bigquery"],
    "Data pipelines": ["data pipeline", "data pipelines", "etl", "elt"],
    "Pandas": ["pandas"], "NumPy": ["numpy"],
    # AI / ML
    "Machine Learning": ["machine learning", "ml"], "Deep Learning": ["deep learning"],
    "PyTorch": ["pytorch"], "TensorFlow": ["tensorflow"], "scikit-learn": ["scikit-learn", "sklearn"],
    "LLMs": ["llm", "llms", "large language model", "large language models"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "Vector databases": ["vector database", "vector db", "pinecone", "weaviate", "qdrant", "chroma"],
    "LangChain": ["langchain"], "LlamaIndex": ["llamaindex", "llama index"],
    "Prompt engineering": ["prompt engineering", "prompting"],
    "AI agents": ["ai agent", "ai agents", "agentic", "multi-agent", "agent framework"],
    "MLOps": ["mlops", "ml ops"], "Model deployment": ["model deployment", "model serving", "inference"],
    "NLP": ["nlp", "natural language processing"], "Computer Vision": ["computer vision", "opencv", "yolo"],
    "Fine-tuning": ["fine-tuning", "fine tuning", "finetuning"],
    "Hugging Face": ["hugging face", "huggingface", "transformers"],
    "Model evaluation": ["model evaluation", "evals", "benchmarking"],
    # Cloud / DevOps
    "AWS": ["aws", "amazon web services"], "Azure": ["azure"], "GCP": ["gcp", "google cloud"],
    "Docker": ["docker", "containerization"], "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"], "CI/CD": ["ci/cd", "cicd", "continuous integration"],
    "GitHub Actions": ["github actions"], "Jenkins": ["jenkins"],
    "Linux": ["linux", "unix"], "Observability": ["observability", "monitoring", "datadog", "grafana"],
    "Serverless": ["serverless", "lambda"],
    # Testing
    "Selenium": ["selenium"], "Appium": ["appium"], "Playwright": ["playwright"],
    "Cypress": ["cypress"], "TestNG": ["testng"], "JUnit": ["junit"], "pytest": ["pytest"],
    "Cucumber/BDD": ["cucumber", "bdd", "behaviour driven", "behavior driven"],
    "Rest Assured": ["rest assured", "restassured"], "JMeter": ["jmeter"],
    "Performance testing": ["performance testing", "load testing"],
    "Test automation": ["test automation", "automation framework", "automated testing"],
    "API testing": ["api testing"], "Mobile testing": ["mobile testing", "android testing", "ios testing"],
    # Practice
    "Agile/Scrum": ["agile", "scrum"], "System design": ["system design", "distributed systems"],
    "Data structures": ["data structures", "algorithms"], "OOP": ["oop", "object oriented", "object-oriented"],
    "Git": ["git", "version control"], "Postman": ["postman"],
}


def detect(text: str) -> set[str]:
    lowered = text.lower()
    return {name for name, aliases in SKILLS.items() if any(has_term(lowered, a) for a in aliases)}


def enrich_greenhouse(results: list) -> int:
    """Greenhouse's list endpoint omits descriptions; pull them for the shortlist only."""
    pending = [r.job for r in results if r.job.ats == "greenhouse" and len(r.job.description or "") <= 200]
    if not pending:
        return 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        for job, description in zip(pending, executor.map(fetch_greenhouse_description, pending)):
            if description:
                job.description = description
    return sum(1 for job in pending if len(job.description or "") > 200)


def main() -> None:
    parser = argparse.ArgumentParser(description="Find in-demand skills missing from your resume")
    parser.add_argument("--threshold", type=int, default=50, help="only analyse jobs scoring at least this")
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--top", type=int, default=18, help="how many gaps to show")
    args = parser.parse_args()

    profile = load_json(PROFILE_PATH, None) or load_preferences()
    raw = load_json(JOBS_PATH, [])
    jobs = [Job(**item) for item in raw] if isinstance(raw, list) else []

    results = rank_jobs(jobs, profile, threshold=args.threshold, floor=args.threshold, limit=args.limit)
    if not results:
        print("No jobs above the threshold. Run scripts/fetch_jobs.py first.")
        return

    enriched = enrich_greenhouse(results)
    usable = [r for r in results if len(r.job.description or "") > 200]

    have = detect(" ".join(profile.get("detected_skills", [])) + " " + " ".join(profile.get("skills", [])))

    demand: dict[str, list] = {}
    for result in usable:
        for skill in detect(result.job.description):
            demand.setdefault(skill, []).append(result)

    total = len(usable)
    ranked = sorted(demand.items(), key=lambda kv: -len(kv[1]))
    gaps = [(s, rs) for s, rs in ranked if s not in have]
    strengths = [(s, rs) for s, rs in ranked if s in have]

    print(f"Analysed {total} reachable postings scoring {args.threshold}+")
    if enriched:
        print(f"(fetched full descriptions for {enriched} Greenhouse postings)")
    print()
    print(f"{'MISSING FROM YOUR RESUME':<26}{'JOBS':>6}{'SHARE':>8}   EXAMPLE EMPLOYERS")
    print("-" * 92)
    for skill, rs in gaps[: args.top]:
        share = 100 * len(rs) / total
        companies = sorted({r.job.company for r in rs})[:3]
        print(f"{skill:<26}{len(rs):>6}{share:>7.0f}%   {', '.join(companies)}")

    print()
    print(f"{'ALREADY ON YOUR RESUME':<26}{'JOBS':>6}{'SHARE':>8}")
    print("-" * 44)
    for skill, rs in strengths[:10]:
        print(f"{skill:<26}{len(rs):>6}{100 * len(rs) / total:>7.0f}%")

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "postings_analysed": total,
        "threshold": args.threshold,
        "gaps": [
            {
                "skill": s,
                "count": len(rs),
                "share": round(100 * len(rs) / total, 1),
                "companies": sorted({r.job.company for r in rs})[:6],
            }
            for s, rs in gaps[:25]
        ],
        "strengths": [
            {"skill": s, "count": len(rs), "share": round(100 * len(rs) / total, 1)}
            for s, rs in strengths[:15]
        ],
    }
    save_json(GAP_REPORT_PATH, payload)
    # Keep the enriched descriptions so the next run does not refetch them.
    save_json(JOBS_PATH, [job.to_dict() for job in jobs])
    print(f"\nSaved to {GAP_REPORT_PATH.name}")


if __name__ == "__main__":
    main()
