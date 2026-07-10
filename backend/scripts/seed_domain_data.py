"""Seed the domain registry (Hospital/Ward/Room/Bed/Patient/Nurse/Robot,
roadmap item 4) with the same single hospital / one ward / two rooms+beds /
two patients / one nurse / one robot the rest of the codebase already
hard-codes (backend.core.config.PATIENTS, workflow_service.DEFAULT_ROBOT_ID).

Dev/demo tool only, same convention as seed_demo_data.py -- never imported
or run automatically; run explicitly:

    python -m backend.scripts.seed_domain_data

Idempotent: running it again after the tables are already populated is a
no-op (see domain_service.seed_default_domain_data's docstring) rather than
raising a primary-key collision.
"""
from backend.services import domain_service


def main() -> None:
    result = domain_service.seed_default_domain_data()
    if result["seeded"]:
        print(f"Seeded {result['hospitals']} hospital(s), {result['patients']} patient(s).")
    else:
        print(
            f"Already seeded -- {result['hospitals']} hospital(s), "
            f"{result['patients']} patient(s) found. No changes made."
        )


if __name__ == "__main__":
    main()
