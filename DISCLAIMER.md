# Disclaimer

This repository contains a **personal portfolio project** by Mustafa Kaan
Taplamacıoğlu, built to explore video processing and pose-based activity
detection end to end.

## Status

This is a **prototype**, not production software. It demonstrates an end-to-end
fullstack architecture (FastAPI + React + ML inference pipeline) and is intended
for portfolio and educational purposes only.

## Compliance posture

This prototype is **not compliant** with the GDPR, CCPA/CPRA, KVKK, the NY SHIELD
Act, or Illinois BIPA in its current state. It is a privacy-aware engineering
exercise, not a production-ready compliance-attested product.

A candid compliance self-assessment and a sequenced production-remediation
roadmap are provided in:

- [LegalandOtherCompliances.md](./LegalandOtherCompliances.md) — full gap
  analysis, biometric-data classification analysis, comparison to industry
  privacy commitments, and remediation roadmap.
- [ComplianceSprintPlan.md](./ComplianceSprintPlan.md) — sprint-level execution
  plan derived from the roadmap, suitable for import into Jira / Linear.

## Trademarks

All trademarks, service marks, trade names, and logos are the property of their
respective owners. This project is **not affiliated with, endorsed by, or
sponsored by** any third-party company or organization.

## Data

The runtime `backend/storage/` directory (uploads, clips, generated incident
files, SQLite database) is **gitignored** and contains only data the operator
chooses to upload locally. Nothing from it is committed.

The repository does, however, contain the following media and model artifacts:

- **`backend/demo_videos/` — 7 sample MP4 clips (committed).** These are
  third-party video clips collected from public sources on the internet for
  demonstration purposes. They depict real people and were **not** produced by
  the author. The author does not hold the copyright to them, has no release
  from the individuals appearing in them, and makes no representation about
  their licensing status. The filenames describe the scenario each clip is used
  to demonstrate; they are **not** assertions of fact about the conduct of any
  person appearing in the footage.

  These clips are included solely so that a first run of the application has
  something to display. They are **not** covered by this project's MIT license.
  If you are a rights holder or a person appearing in one of these clips and
  would like it removed, please open an issue and it will be taken down.

- **ML training artifacts** in `backend/ml/training/` are written against the
  publicly available DCSASS dataset (CC BY 4.0), which is not redistributed
  here.

- **Pre-trained model weights** in `backend/ml/models/` are the author's own
  training output, except for `pose_landmarker_lite.task`, which is Google's
  MediaPipe pose model redistributed under its own license. Weights contain
  learned parameters, not personal data. See [NOTICE](./NOTICE).

## License

The source code in this repository is released under the **MIT License**.
See [LICENSE](./LICENSE) for the full text.

The MIT License covers only the source code authored by the copyright holder.
It does not grant any rights to third-party trademarks, third-party logos,
third-party datasets, third-party model weights, or the third-party video clips
in `backend/demo_videos/`.

## Contact

For questions about this project, or to request removal of any content, please
open an issue on the GitHub repository.
