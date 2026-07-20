# Changelog — bailiff-mod-cloudformation

All notable changes to this module are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

- - -
## bailiff-mod-cloudformation-v0.1.1 - 2026-07-20
#### Bug Fixes
- fail with install guidance when a module's required tool is missing (#52) - (adcf599) - Sjors Robroek
#### Documentation
- reframe reproduce invariant from byte-identical to config-consistent - (498315f) - Sjors Robroek
- reframe reproduce invariant from byte-identical to config-consistent - (c1d7faf) - Sjors Robroek

- - -

## bailiff-mod-cloudformation-v0.1.0 - 2026-07-15
#### Features
- rename project clerk → bailiff (PyPI: bailiff, org: bailiff-io) - (52ac605) - Sjors Robroek

- - -

## bailiff-mod-cloudformation-v0.1.0 - 2026-07-15
#### Features
- (**011**) implement bailiff-mod-cloudformation (T022) - (c8bbcfc) - Sjors Robroek
#### Bug Fixes
- (**011**) E2E campaign fixes -- cdk nag-splice bug, drop version pin, IaC exclusion tags - (ce28f28) - Sjors Robroek

- - -


## Unreleased

### Added

- Initial module: CloudFormation / SAM overlay with SEED-ONCE `template.yaml` and
  per-env `parameters/<env>.json`, MANAGED `.cfnlintrc.yaml`, and OPT-IN
  `aws cloudformation validate-template` task.
