# Release Governance

## Rules

- All changes must go through Pull Request review
- main branch must stay deployable
- No direct hotfix push to main
- CI should pass before merge
- Secrets must never be committed

## Release Flow

1. Feature branch
2. PR review
3. CI validation
4. Merge to main
5. Tag release if needed
