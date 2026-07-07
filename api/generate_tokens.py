"""Mints one demo JWT per role so reviewers can exercise every RBAC path.

Usage:
    python -m api.generate_tokens
"""
from api.auth import Role, create_token

if __name__ == "__main__":
    tokens = {
        "corporate_admin (sees everything)": create_token(Role.CORPORATE_ADMIN),
        "regional_director (Pacific Northwest = OR communities C001-C005)": create_token(
            Role.REGIONAL_DIRECTOR, region="Pacific Northwest"
        ),
        "community_executive_director (C001 only)": create_token(
            Role.COMMUNITY_EXECUTIVE_DIRECTOR, community_id="C001"
        ),
    }
    for label, token in tokens.items():
        print(f"\n{label}:\n{token}")
