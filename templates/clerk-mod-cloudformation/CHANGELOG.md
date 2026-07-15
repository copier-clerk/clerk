# Changelog — clerk-mod-cloudformation

All notable changes to this module are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

- - -
## clerk-mod-cloudformation-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement clerk-mod-cloudformation (T022) - (c8bbcfc) - Sjors Robroek
#### Bug Fixes
- (**011**) E2E campaign fixes -- cdk nag-splice bug, drop version pin, IaC exclusion tags - (ce28f28) - Sjors Robroek

- - -


## Unreleased

### Added

- Initial module: CloudFormation / SAM overlay with SEED-ONCE `template.yaml` and
  per-env `parameters/<env>.json`, MANAGED `.cfnlintrc.yaml`, and OPT-IN
  `aws cloudformation validate-template` task.
