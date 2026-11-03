# 多人協作規範

## 分支策略：GitHub Flow

| 分支 | 用途 | 來源 | 合併到 |
|---|---|---|---|
| `main` | 永遠可部署；合併後自動部署到 Cloud Run | — | — |
| `feature/<簡述>` | 新功能 | `main` | `main`（PR） |
| `fix/<簡述>` | 一般錯誤修正 | `main` | `main`（PR） |
| `hotfix/<簡述>` | 線上緊急修正，優先審核 | `main` | `main`（PR） |
| `docs/<簡述>` | 文件更新 | `main` | `main`（PR） |

### 為什麼選 GitHub Flow 而不是 Git Flow？

- 本服務採用「合併即部署」的持續交付模式，不需要 `develop` 與 `release` 分支來管理排程發佈。
- 分支較少，流程簡單，適合小型團隊與微服務。
- 若未來需要同時維護多個發佈版本（例如需要經過正式驗收的金融系統），可以改用 Git Flow，或加上 `release/*` 分支。

## Commit 訊息：Conventional Commits

```
<type>(<scope>): <簡短描述>

feat(convert): support inverse rate in response
fix(rate-client): treat AttributeError as malformed upstream data
test(api): add stale cache scenario
docs(readme): add architecture diagram
ci: add terraform validate job
```

常用的 type：`feat`、`fix`、`test`、`docs`、`refactor`、`ci`、`chore`

## Pull Request 檢查清單

- [ ] 標題遵循 Conventional Commits 格式
- [ ] 說明「做了什麼」與「為什麼」
- [ ] 新功能附有測試，`pytest` 全數通過
- [ ] `ruff check` 與 `ruff format --check` 通過
- [ ] 若修改 API，已確認 `/docs` 文件正確
- [ ] 若修改 Terraform，已附上 `terraform plan` 結果

## main 分支保護設定（GitHub → Settings → Branches）

- Require a pull request before merging（至少 1 個 approval）
- Require status checks to pass：`Lint & Test`、`Terraform Validate`、`Docker Build Check`
- Require branches to be up to date before merging
- Do not allow bypassing the above settings
