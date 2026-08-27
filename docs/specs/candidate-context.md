# Candidate context + HH resume linkage (R1.5) + ResumeVersion meta (R2.1.1)

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
- R2.1.1: `resume_content` metadata on candidate-context (no CV body). Full body:
  `GET /api/v1/resume-versions/{id}` — see [`resume-version.md`](resume-version.md)

## Identifier-only linkage (R1.5)

R1.5 stores **linkage only**:

`CandidateProfile` / `ProfileVersion` ↔ HH `external_resume_id` (+ optional cached `title`)

Resume **content** is R2.1.1+ (`ResumeVersion`). Linkage alone is **not** scoring-ready.

## Non-scope

Full SearchProfile, HH content extraction (R2.1.2), Web sync UX (R2.1.5), scoring.
