# Delivery Workflow method guidance

This read-only seed belongs to the distributed skill. Personal improvements live in the user's
separate `lessons.yaml`. Neither location stores case findings or project knowledge.

- Read the actual source and trace the reported behavior before changing it.
- A passed manifest audit permits execution; it does not mean the task is finished.
- Record evidence during each phase. Keep a failed or unavailable check visible.
- Explain the observed result, its practical effect and what remains unverified.
- Preserve user state and unrelated work. Validate the path that actually consumes a change.
- Reuse relevant confirmed method improvements with their context and limitations.
- Diagnose an unexpected result against current requirements. Fix valid checks; remove obsolete
  ones together with their hooks. Preserve the finding in the existing task, not another rule tier.
- Reuse sufficient build checks. Ship the product without its tests, fixtures or test dependencies.
