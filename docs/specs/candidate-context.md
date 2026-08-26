# Candidate context + HH resume linkage (R1.5)

## User Story

```text
Как оператор,
Я хочу связать активное HH resume с локальным CandidateProfile / ProfileVersion,
Чтобы R2 мог опираться на локальный candidate context.
```

## Implemented

- Core tables: `candidate_profiles`, `profile_versions`, `active_hh_resume_links`
- HTTP: `GET /api/v1/candidate-context`, `PUT /api/v1/candidate-context/hh-resume-link`
- Fresh install returns empty context (no automatic legacy data)
- Select creates profile + `r1-default` version + `source=hh` link (`status=active`)
- Clear marks `status=cleared` without deleting profile/version history
- Not Person / Application.resume_version / SearchProfile

## Non-scope

Full SearchProfile, resume content ingestion, scoring input wiring, R1.6 recovery.
