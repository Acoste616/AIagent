# GitHub Auth Required

Date: 2026-06-06

Local project repo is prepared at:

```text
github-AIagent
```

Remote:

```text
https://github.com/Acoste616/AIagent.git
```

Current blocker:

- Mac: no GitHub SSH key with access.
- Codex GitHub connector: token expired.
- Windows GitHub CLI: token invalid.

Fix on Windows Desktop:

```powershell
gh auth login -h github.com
```

Fix in Codex:

- re-authenticate the GitHub connector/plugin.

After auth is fixed:

```bash
cd github-AIagent
git push -u origin main
```

