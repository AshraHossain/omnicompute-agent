# GitHub Setup Guide

**Complete instructions for GitHub features and community setup**

---

## Table of Contents

1. [GitHub Discussions](#github-discussions)
2. [Project Board](#project-board)
3. [Contributing Badge](#contributing-badge)
4. [Branch Protection](#branch-protection)
5. [Automated Releases](#automated-releases)

---

## GitHub Discussions

### Enable Discussions

1. Go to repository **Settings** → **Features**
2. Check **Discussions** checkbox
3. Click **Save**

### Configure Discussion Categories

1. Go to **Discussions** tab
2. Click **Settings** (gear icon)
3. Add these categories:

#### Category 1: Questions & Answers
- **Title**: Questions & Answers
- **Description**: Ask questions, get help, share knowledge
- **Emoji**: ❓
- **Template**: `.github/DISCUSSION_TEMPLATE/questions.md`

#### Category 2: Ideas & Features
- **Title**: Ideas & Features
- **Description**: Suggest new features or enhancements
- **Emoji**: 💡
- **Template**: `.github/DISCUSSION_TEMPLATE/ideas.md`

#### Category 3: Show & Tell
- **Title**: Show & Tell
- **Description**: Share your OmniCompute deployments and success stories
- **Emoji**: 🚀
- **Template**: `.github/DISCUSSION_TEMPLATE/showandtell.md`

#### Category 4: Announcements (Announcement only)
- **Title**: Announcements
- **Description**: Important updates and releases
- **Emoji**: 📢
- **Announcement only**: YES

### Link Discussions in README

Add this section to README.md:

```markdown
## 💬 Community

Have questions? Want to share your deployment? Join the discussion:

- **[Questions & Answers](https://github.com/AshraHossain/omnicompute-agent/discussions/categories/q-a)** — Ask for help
- **[Ideas & Features](https://github.com/AshraHossain/omnicompute-agent/discussions/categories/ideas--features)** — Suggest improvements
- **[Show & Tell](https://github.com/AshraHossain/omnicompute-agent/discussions/categories/show--tell)** — Share your work

Or email: ashrafuzzmanhossain@gmail.com
```

---

## Project Board

### Create Project Board

1. Click **Projects** tab
2. Click **New project**
3. Name: `v1.0 Roadmap`
4. Template: **Table**
5. Click **Create project**

### Add Columns

1. **Backlog** (default)
2. **Ready** (approved, waiting to start)
3. **In Progress** (actively being worked on)
4. **Review** (PR open, awaiting review)
5. **Done** (merged/completed)

### Add Issues to Board

1. Create issue for each roadmap item
2. Add to project board
3. Move through columns as work progresses

### Example Issues for Roadmap

```
Phase 5: Multi-Orbit Coordination
  ├─ Implement Raft consensus protocol
  ├─ Add peer-to-peer baseline sync
  ├─ Implement distributed decision-making
  └─ 80+ tests for consensus

Phase 6: Adaptive Learning
  ├─ Sliding-window baseline updates
  ├─ Playbook effectiveness metrics
  ├─ Automatic threshold adjustment
  └─ 40+ tests for learning
```

---

## Contributing Badge

### Add All-Contributors Bot

1. Go to [All-Contributors](https://allcontributors.org/)
2. Click **Generate your contributors file**
3. Connect your GitHub repository
4. Add `.all-contributorsrc` config (see below)

### Create `.all-contributorsrc`

```json
{
  "projectName": "omnicompute-agent",
  "projectOwner": "AshraHossain",
  "repoType": "github",
  "repoHost": "https://github.com",
  "files": [
    "README.md"
  ],
  "imageSize": 100,
  "commit": false,
  "contributors": [
    {
      "login": "AshraHossain",
      "name": "Ashraf Hossain",
      "avatar_url": "https://avatars.githubusercontent.com/u/...",
      "profile": "https://github.com/AshraHossain",
      "contributions": [
        "code",
        "doc",
        "ideas",
        "maintenance"
      ]
    }
  ],
  "contributorsPerLine": 7,
  "skipCi": true,
  "repoLink": "https://github.com/AshraHossain/omnicompute-agent"
}
```

### Add Badge to README

Add this below the project title in README.md:

```markdown
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-1-orange.svg)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->
```

### Recognize Contributors

When someone contributes:

1. Comment: `@all-contributors please add @username for code,doc`
2. Bot will create a PR with updated contributors list
3. Merge the PR

---

## Branch Protection

### Protect Main Branch

1. Go to **Settings** → **Branches**
2. Click **Add rule**
3. Branch name pattern: `master`
4. Enable:
   - **Require a pull request before merging**
   - **Require status checks to pass**
   - **Require branches to be up to date**
   - **Require code reviews**: 1 reviewer

### Recommended Status Checks

Add these required checks:
- `build` (GitHub Actions tests)
- `coverage` (80%+ required)
- `type-check` (mypy)
- `lint` (flake8)

---

## Automated Releases

### Enable Auto-Release

1. Create `release.yml` in `.github/workflows/`

```yaml
name: Create Release on Tag
on:
  push:
    tags:
      - "v*"

jobs:
  create-release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Get release notes
        id: notes
        run: |
          NOTES=$(sed -n "/^## ${{ github.ref_name }}/,/^## /p" CHANGELOG.md | head -n -1)
          echo "NOTES<<EOF" >> $GITHUB_OUTPUT
          echo "$NOTES" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
      
      - name: Create Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref_name }}
          release_name: Release ${{ github.ref_name }}
          body: ${{ steps.notes.outputs.NOTES }}
          draft: false
          prerelease: false
```

2. When you create a tag, release is auto-created:
```bash
git tag v1.1.0
git push origin v1.1.0
```

---

## Community Health

### Enable Code Scanning

1. Go to **Security** → **Code scanning**
2. Click **Set up code scanning**
3. Choose **GitHub Advanced Security** (free for public repos)
4. Enable for:
   - Python security issues
   - Secret detection
   - Dependency scanning

### Enable Dependabot

1. Go to **Settings** → **Security & analysis**
2. Enable:
   - **Dependabot alerts**
   - **Dependabot security updates**
   - **Dependabot version updates** (optional)

### Add Community Profile

1. Go to **Insights** → **Community**
2. Complete checklist:
   - ✅ Description
   - ✅ README
   - ✅ Code of Conduct
   - ✅ Contributing guidelines
   - ✅ License
   - ✅ Issue templates
   - ✅ PR template

---

## GitHub Actions Setup

### Enable Actions

1. Go to **Actions** tab
2. Select **Workflow permissions**: **Read repository contents**
3. Review auto-created workflows from `.github/workflows/`

### Current Workflows

- **tests.yml** — Run tests on every push/PR
- **coverage.yml** — Report coverage to Codecov
- **security.yml** — CodeQL security scanning

---

## Suggested GitHub Labels

Create these labels for consistent issue tracking:

| Label | Color | Description |
|-------|-------|-------------|
| `bug` | Red (#d73a49) | Something is broken |
| `enhancement` | Blue (#0366d6) | New feature or improvement |
| `documentation` | Green (#0e8a16) | Docs update |
| `good first issue` | Purple (#7057ff) | Good for newcomers |
| `help wanted` | Orange (#ffa500) | Need community help |
| `critical` | Dark red (#b60205) | Blocks other work |
| `phase-5` | Light blue (#a2eeef) | Phase 5 work |
| `phase-6` | Light blue (#1f6feb) | Phase 6 work |

---

## Milestones

Create these milestones for planning:

- **v1.0.0** (closed)
- **v1.1.0** (open) — Bug fixes & minor enhancements
- **v2.0.0** (planning) — Phase 5+

---

## Checklist

- [ ] Discussions enabled with 4 categories
- [ ] Project board created with 5 columns
- [ ] Contributing badge configured
- [ ] Main branch protected
- [ ] Auto-releases enabled
- [ ] Community profile complete
- [ ] Code scanning enabled
- [ ] Dependabot enabled
- [ ] Labels created
- [ ] Milestones created
- [ ] README updated with links

---

**Version**: 1.0.0 | **Last Updated**: 2026-06-20
