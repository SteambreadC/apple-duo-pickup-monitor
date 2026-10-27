# Apple Duo Pickup Monitor Implementation Plan

**Goal:** Deliver a tested, configurable read-only pickup monitor and GitHub Actions deployment.
**Architecture:** Standard-library Apple client, strict parser, persistent event/delivery state, isolated notification adapters and GitHub state storage.
**Tech stack:** Python 3.12+, unittest, Ubuntu GitHub Actions.
**Spec:** design.md. User requested direct implementation in this chat; proceed without a separate design approval round.

## Tasks
- [ ] Write parser/state tests first: exact SKU/title/store, shipping ignored, Date/Age freshness, missing store unknown, two explicit misses rearm, unknown does not rearm, delivery failures retry by channel.
- [ ] Implement monitor.py to pass tests. Interface: `parse_payload(payload, checked_at)`, `validate_freshness(headers, now)`, `process(state, observations, channels, now)`.
- [ ] Write transport tests for 429/541, provider errors, and local HTTP/SMTP end-to-end; implement notify.py and network client.
- [ ] Implement GitHub REST branch state persistence with fail-closed load/save and workflow concurrency; add scheduled run and labelled notification-test dispatch.
- [ ] Run complete test suite, fresh official dry run, SKU verification, and document observed API evidence. Package outputs and publish only after visibility choice.

## Review focus
Cached/old responses; wrong model/capacity/color/store; unknown between misses; partial notification failures; persistence loss or conflicts. Each must have a test or a documented platform limitation.
