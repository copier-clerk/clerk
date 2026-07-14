# Changelog — clerk-mod-cloudformation

All notable changes to this module are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

- - -

## Unreleased

### Added

- Initial module: CloudFormation / SAM overlay with SEED-ONCE `template.yaml` and
  per-env `parameters/<env>.json`, MANAGED `.cfnlintrc.yaml`, and OPT-IN
  `aws cloudformation validate-template` task.
