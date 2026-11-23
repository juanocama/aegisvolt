# AegisVolt CI Failure Repair Report

**Audit date:** 2026-11-22

## 1. Scope

This report diagnoses and repairs the two failing Pull Request checks observed
on PR #3 and PR #4:

- `Continuous integration / Backend tests and syntax`
- `Continuous integration / Frontend lint, tests, and build`

The inspection and local repairs used:

- `.github/workflows/ci.yml`
- The exact GitHub Actions job logs for run `45078197332`
- Backend dependency and test configuration
- Frontend package metadata and lockfile

No branch protection, review requirement, PR, AWS resource, Terraform remote
state, commit, push, merge, or permanent branch was changed.

## 2. Backend check diagnosis

### Workflow and job

- Workflow: `.github/workflows/ci.yml`
- Job: `Backend tests and syntax`
- Failing step: `python -m pytest -q`
- Affected PRs: PR #3 and PR #4

### First real error

The exact GitHub Actions failure was:

```text
FAILED tests/test_services.py::test_charge_replay_and_refund_replay_are_atomic
fastapi.exceptions.HTTPException:
503: Refund outcome is uncertain; retry the same refund
```

The failure was preceded by a Moto
`TransactionCanceledException` with conditional cancellation reasons:

```text
TransactionCanceledException
ConditionalCheckFailed
ConditionalCheckFailed
```

The test then reported:

```text
1 failed, 19 passed, 368 warnings
```

### Root cause

The concurrent refund replay test issued two refunds for the same charge.
One request can observe an uncertain transaction outcome while the replaying
request is completing.

The test did not retry the documented HTTP 503 recovery contract.

A subsequent local full-suite run also exposed a second, real race condition:
the losing replay path could return before the wallet and charge state were
recovered consistently. Strengthening the test to retry 503 alone was therefore
not sufficient; the refund transaction needed an additional wallet balance
condition.

This is a code-and-test consistency issue, not a dependency or syntax failure.

## 3. Backend repair

### Production service fix

Updated `services/billing-wallet/app.py` so refund processing reads the current
wallet balance and requires the wallet balance to equal the observed value in
the DynamoDB transaction condition.

The wallet update now requires:

```text
attribute_exists(id) AND balance = :expected
```

This prevents a replayed refund with stale balance state from applying another
credit to the wallet. Existing charge-status and refund-record conditions
remain enforced in the same transaction.

### Test fix

Updated `tests/test_services.py` so the concurrent replay caller retries HTTP
503 outcomes up to 50 attempts.

The retry remains limited to the documented uncertain-refund response:

- HTTP 503: retry
- Any other HTTP error: fail
- Exhausted retry budget: fail with an assertion

This preserves the real service contract and does not weaken the replay or
atomicity assertions.

## 4. Frontend check diagnosis

### Workflow and job

- Workflow: `.github/workflows/ci.yml`
- Job: `Frontend lint, tests, and build`
- Failing step: `npm ci`
- Affected PRs: PR #3 and PR #4

### Exact error

```text
npm ci can only install packages when your package.json and
package-lock.json or npm-shrinkwrap.json are in sync.

Missing: @emnapi/core@2.0.0-beta.2 from lock file
Missing: @emnapi/runtime@2.0.0-beta.2 from lock file
```

The CI runner used:

- Node `24.15.0`
- npm `11.12.1`
- Ubuntu `26.04`

### Root cause

The frontend `package-lock.json` did not contain entries required by the
resolved optional dependency graph. It was not fully synchronized with the
package metadata under npm 11.12.1.

This is a lockfile/dependency-graph configuration issue.

## 5. Frontend repair

Updated `frontend/package-lock.json` using npm 11.12.1.

The regenerated lock now contains:

- `node_modules/@emnapi/core@2.0.0-beta.2`
- `node_modules/@emnapi/runtime@2.0.0-beta.2`
- Their resolved URLs and integrity hashes

No application dependency or package script was removed or changed.

## 6. Files modified

Modified on `feature/phase-2-terraform-readiness`:

- `services/billing-wallet/app.py`
- `tests/test_services.py`
- `frontend/package-lock.json`

No commit or push was created.

## 7. Local validation

### Backend

```powershell
python -m compileall -q common gateway services tests
python -m pytest -q
```

Result:

```text
20 passed, 379 warnings
```

Replay stress test:

```powershell
python -m pytest -q -p no:cacheprovider `
  tests/test_services.py::test_charge_replay_and_refund_replay_are_atomic
```

Repeated in 20 separate pytest processes:

```text
failed=0
```

### Frontend

```powershell
Set-Location C:\Users\iamju\Desktop\patrones\aegisvolt\frontend
npx --yes npm@11.12.1 install --package-lock-only
npx --yes npm@11.12.1 ci
npm run lint
npm test
npm run build
```

Results:

- npm 11.12.1 clean install: passed
- lint: passed
- tests: 2 test files and 3 tests passed
- build: passed

The local Node is `24.13.0`, not the exact CI `24.15.0`. The exact CI npm
version `11.12.1` was reproduced through `npx`; the clean install passed. The
remaining engine warnings concern `jsdom` requiring Node `24.15.0` or newer
within the local 24.x line, but lint/tests/build completed successfully.

### Terraform

```powershell
Set-Location C:\Users\iamju\Desktop\patrones\aegisvolt\infra
terraform fmt -check -recursive
terraform validate -no-color
```

Result:

```text
Success! The configuration is valid.
```

## 8. PR incorporation

PR #4 already contains the larger feature baseline and the Phase 2 commit, so
its source branch is the appropriate branch for the local repair.

The following changes must be committed and pushed to the relevant source branch
for GitHub to run the corrected CI:

- `services/billing-wallet/app.py`
- `tests/test_services.py`
- `frontend/package-lock.json`

These are shared CI/application fixes and must not be duplicated into unrelated
Phase 2 files.

Before updating PR #3, determine whether PR #3 should also receive the three
shared repair files or whether PR #3 should be closed after PR #4 is merged and
rebased through the official promotion sequence. Do not merge or rebase without
explicit approval.

Current local status: repairs exist only as uncommitted changes on
`feature/phase-2-terraform-readiness`.

## 9. Remaining blockers

- The repaired files have not been committed or pushed.
- PR #3 and PR #4 have not received another CI run.
- PR #3 and PR #4 still require an independent approving review.
- GitHub CI may still reveal environment-specific failures after the lockfile
  correction.
- Branch protection, review requirements, and merge policy remain unchanged.
- AWS and Terraform remote operations were not performed.

## 10. Commands for review

```powershell
Set-Location C:\Users\iamju\Desktop\patrones\aegisvolt
git status --short --branch
git diff --stat
git diff --check
git diff -- services/billing-wallet/app.py tests/test_services.py
git diff -- frontend/package-lock.json
```

Do not commit, push, merge, close, or modify branch protection until the
repaired changes are separately approved for the relevant PR source branch.
