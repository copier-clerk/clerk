# Changelog

## [0.4.2](https://github.com/bailiff-io/bailiff/compare/v0.4.1...v0.4.2) (2026-07-20)


### Bug Fixes

* fail with install guidance when a module's required tool is missing ([#52](https://github.com/bailiff-io/bailiff/issues/52)) ([adcf599](https://github.com/bailiff-io/bailiff/commit/adcf5994cecdf604790dfb9144713ebee54ec60a))
* **release:** uv sync --frozen so a lockfile drift never dirties the cog-bump tree ([#54](https://github.com/bailiff-io/bailiff/issues/54)) ([cb114f2](https://github.com/bailiff-io/bailiff/commit/cb114f2d2376f2a6078ef6f7aa86400d751297a0))

## [0.4.1](https://github.com/bailiff-io/bailiff/compare/v0.4.0...v0.4.1) (2026-07-20)


### Bug Fixes

* init under symlinked path works on reproduce/update; wire agent projections ([#50](https://github.com/bailiff-io/bailiff/issues/50)) ([c842735](https://github.com/bailiff-io/bailiff/commit/c842735f23da37f9076f9ba51f8c54fcdcfd6e32))

## [0.4.0](https://github.com/bailiff-io/bailiff/compare/v0.3.1...v0.4.0) (2026-07-20)


### Features

* agent-projected capabilities (cross-format hooks, agentic editorconfig) ([#47](https://github.com/bailiff-io/bailiff/issues/47)) ([453464e](https://github.com/bailiff-io/bailiff/commit/453464eb516023c8d18ab44cd16d71c9f2e544d9))

## [0.3.1](https://github.com/bailiff-io/bailiff/compare/v0.3.0...v0.3.1) (2026-07-18)


### Bug Fixes

* owner/repo template shorthand resolves, and init works under symlinked dest ([#46](https://github.com/bailiff-io/bailiff/issues/46)) ([7ba5156](https://github.com/bailiff-io/bailiff/commit/7ba515654158a0ee2adae2772c2c5139d0f8bd1f))
* tree is clean after multi-layer init (initial commit is engine-owned) ([#44](https://github.com/bailiff-io/bailiff/issues/44)) ([b9e309d](https://github.com/bailiff-io/bailiff/commit/b9e309df9c90ea45977e98f8ecbfcc4ff21b37cc))

## [0.3.0](https://github.com/bailiff-io/bailiff/compare/v0.2.0...v0.3.0) (2026-07-17)


### Features

* **014 agentic:** wire _external_data.base for project_name; migrate edge model ([9281a3c](https://github.com/bailiff-io/bailiff/commit/9281a3c376f53abe7e34c427307aed4360cde59d))
* **014 mkdocs:** mise conf.d drop-in, _external_data facts, depends_on edge (T027/T035/T037) ([318aac7](https://github.com/bailiff-io/bailiff/commit/318aac79b48f60a28ea20f91da92aafbfa21a2a8))
* **014 n-base:** T019/T031/T048/T052 + T018/T047 tests for bailiff-mod-base ([a2e5b31](https://github.com/bailiff-io/bailiff/commit/a2e5b31c06e6261a031a5e7f28e7c58ede7ee077))
* **014 rust:** fragment model — mise conf.d, pre-commit.d, gitignore.d; _external_data aliases ([6c6ba7d](https://github.com/bailiff-io/bailiff/commit/6c6ba7ddd44599347e63206ebf588db0ea61895a))
* **014/api:** migrate bailiff-mod-api to fragment/fact model (T026/T035/T037/T039/T045) ([ef0bad4](https://github.com/bailiff-io/bailiff/commit/ef0bad464cdd09238be5ee9ea31987fe74ee3ee8))
* **014/apm:** _external_data.base facts, depends_on, .gitignore.d fragment ([84f747f](https://github.com/bailiff-io/bailiff/commit/84f747ff0907616bc3ef86015fb8e02e53225872))
* **014/cdk:** migrate to _external_data alias + depends_on/phase model ([59cd582](https://github.com/bailiff-io/bailiff/commit/59cd5824cd4c2766845bce62dcbffadbd63377a7))
* **014/justfile:** migrate edge/phase model, add mise conf.d fragment ([cc5123f](https://github.com/bailiff-io/bailiff/commit/cc5123f1161b1403ca219645e7df583295aeff6d))
* **014/n-precommit-lefthook:** strip lefthook from bailiff-mod-precommit ([d86267e](https://github.com/bailiff-io/bailiff/commit/d86267ec1916bd8948d6c1e3657731c89e6255c3))
* **014/n-ts:** migrate bailiff-mod-ts to private-by-default + fragment model ([d16eb47](https://github.com/bailiff-io/bailiff/commit/d16eb47e8c6dd3e700d8070f24391e01e785a55d))
* **014/T040:** wire editorconfig ts_linter via _external_data.ts ([ecd6bae](https://github.com/bailiff-io/bailiff/commit/ecd6bae6f47ce8d197f3a15ee3d6785bfce7aeaa))
* **014/terraform:** migrate to fragment/merge model + _external_data facts ([7cb3bf6](https://github.com/bailiff-io/bailiff/commit/7cb3bf60fb2e3ca8791c86a030e2d389a84c6d38))
* **014:** T032/T044/T043 — precommit fragment/merge model ([e1f75cb](https://github.com/bailiff-io/bailiff/commit/e1f75cb7e9763e3df5140a6d0ff41544f49025d5))
* add release-please for engine versioning (PyPI package lifecycle) ([edec2d7](https://github.com/bailiff-io/bailiff/commit/edec2d7f0fd51f8a3cf311d599d6516f708d41b5))
* **ci-github:** wire _external_data facts, migrate to depends_on/phase (014 T038/T041) ([b8d3091](https://github.com/bailiff-io/bailiff/commit/b8d3091267250f24c25825dd497e433467275f63))
* **ci-gitlab:** wire _external_data aliases for base+moon facts (spec 014 T035/T038/T041) ([57db781](https://github.com/bailiff-io/bailiff/commit/57db7812ac416a27b4ddffc01ba20c425285c469))
* **cocogitto:** migrate to spec-014 fragment/facts model (T024/T035/T036/T041/T045/T049) ([f381738](https://github.com/bailiff-io/bailiff/commit/f381738ab9cd4fe70d46e5d086723fefb77d8636))
* **devcontainer:** migrate to bare mise install, _external_data facts, depends_on edge (spec 014 T029/T035) ([6f66925](https://github.com/bailiff-io/bailiff/commit/6f66925c690956d5a8bd2a1d31cb35fffbcc1d3a))
* **go:** migrate bailiff-mod-go to 014 fragment/fact model (T022/T035/T039/T045/T049) ([4f814d4](https://github.com/bailiff-io/bailiff/commit/4f814d4839e25c7a6694424859e9d63ee03e01b7))
* **moon:** migrate to _external_data facts + conf.d mise fragment (spec 014) ([f1d3ebe](https://github.com/bailiff-io/bailiff/commit/f1d3ebe13da04e514fb26e321f58f38f9969a3b5))
* **package-add:** migrate to _external_data for layout + js_pkg_manager (spec 014) ([1cd20e1](https://github.com/bailiff-io/bailiff/commit/1cd20e1dac971e4d1735668ef1ca6b5440b59114))
* **python:** migrate to private-by-default threading (spec 014) ([f81e8e3](https://github.com/bailiff-io/bailiff/commit/f81e8e36191d9a21e8b4d3ef9f98235c8983f05e))
* **quality:** migrate to depends_on/phase, add gitignore.d fragment (T049) ([aa8dec9](https://github.com/bailiff-io/bailiff/commit/aa8dec93c6f54dce9dea39ad05c931541475fd10))
* **readme:** migrate to _external_data model (spec 014 T035/T037) ([5c363d0](https://github.com/bailiff-io/bailiff/commit/5c363d09f0906e9915bc2322851a60f15eefba74))
* **stack-adr:** migrate to _external_data + depends_on (spec 014) ([12debff](https://github.com/bailiff-io/bailiff/commit/12debff2d2990b10789098c2202d270cb34b01f9))


### Bug Fixes

* **014 agentic:** correct README — ordering is via _external_data edge, not depends_on ([b2045ab](https://github.com/bailiff-io/bailiff/commit/b2045abe09c0804fe5bee39fba86ed5b35a2f0cb))
* **014 engine:** move post-task exec to discovery, schema marker on init(), remove subprocess from runner ([5af9c00](https://github.com/bailiff-io/bailiff/commit/5af9c00272a193aeb8694da3e016c4e29423f7a5))
* **014 engine:** single-edge collapse, post-task trust+failure, alias ordering, append-only schema marker ([9cbb70a](https://github.com/bailiff-io/bailiff/commit/9cbb70ac9af79b79ba8ad07503f9129482dfa62a))
* **014 rust:** drop precommit _external_data alias; clippy fragment unconditional (R13) ([ed6cfa4](https://github.com/bailiff-io/bailiff/commit/ed6cfa4151aa598d539679af4ffe7670ff558bbb))
* **014/api:** apply R13 — remove hook_manager/precommit dependency, unconditional fragment ([d12082a](https://github.com/bailiff-io/bailiff/commit/d12082a203a40bc412dd959b4205bd762004043c))
* **014/T040:** revert editorconfig ts_linter to agent-fed --data (standalone contract) ([115a846](https://github.com/bailiff-io/bailiff/commit/115a846181bdc08f05fde3316e9f0f7c78150f1d))
* **014/terraform:** drop precommit alias + render fragment unconditionally (R13) ([d189f79](https://github.com/bailiff-io/bailiff/commit/d189f791a962809e71cccac548ae53fe5d0e4b3e))
* **bailiff-mod-ts:** wrap pre-commit fragment in top-level repos: mapping ([a991e2e](https://github.com/bailiff-io/bailiff/commit/a991e2eed4e353d99eb088ec26b8bb082982cbf2))
* **bundler:** reject non-dict fragments with a clear error ([6d3665d](https://github.com/bailiff-io/bailiff/commit/6d3665d83d79b849eff4f10a4ba76570ecd56a23))
* **ci-github:** drop moon from _external_data, make monorepo_tool agent-fed ([a864b7e](https://github.com/bailiff-io/bailiff/commit/a864b7e87f1f15b4395799760c9b5e2aca1b3051))
* **ci-github:** ruff E501 line-too-long in test ([60b8165](https://github.com/bailiff-io/bailiff/commit/60b8165f37abe3f477540ddcc1f68974966bd10e))
* **ci-gitlab:** revert moon to agent-fed --data (R13 GENERALIZED) ([bef5eab](https://github.com/bailiff-io/bailiff/commit/bef5eabfee322bde46a6a471b567682b00203a05))
* **cocogitto:** revert moon to agent-fed --data per R13 GENERALIZED ([eb919e7](https://github.com/bailiff-io/bailiff/commit/eb919e7de1abe3b31295657f9079cd58674624e6))
* **go:** drop hook_manager coupling; pre-commit fragment unconditional (R13) ([6748a85](https://github.com/bailiff-io/bailiff/commit/6748a857cbdd1880fc9b8e9bc6aebaaa49e5d8a6))
* make release fan-out rerun-safe (tolerate existing tags) ([39edb22](https://github.com/bailiff-io/bailiff/commit/39edb227929d1496eed7d47e31822d64aedbb3e1))
* namespace colliding 'framework' question across three modules ([9a22b6c](https://github.com/bailiff-io/bailiff/commit/9a22b6cf0057b1bb072d3d7526ba830be48ab24b))
* namespace colliding 'framework' question across three modules ([1f996ad](https://github.com/bailiff-io/bailiff/commit/1f996ad06917550a3a7f8ebc5f0d021717baec53))
* **package-add:** make js_pkg_manager agent-fed, remove ts hard dep ([ca420d9](https://github.com/bailiff-io/bailiff/commit/ca420d956642ee2188138ee73b748287f6035448))
* **python:** wrap pre-commit fragment under top-level repos: key ([385ac4b](https://github.com/bailiff-io/bailiff/commit/385ac4bdc5dd795da5a869ceb467f933ddd089fe))
* **release:** fan out every new module version, not just empty mirrors ([#43](https://github.com/bailiff-io/bailiff/issues/43)) ([25b0e4b](https://github.com/bailiff-io/bailiff/commit/25b0e4bd44d9bf93b0dd19546efc6e65c9f12b6d))
* **runner:** restore FR-013 collision scan for _external_data consumers ([a53a335](https://github.com/bailiff-io/bailiff/commit/a53a3355e88d611f16b5f0029122e53a6da5866f))
* **terraform:** default pre_commit_terraform_rev to v1.108.0 ([9e6b07f](https://github.com/bailiff-io/bailiff/commit/9e6b07f0deca7d49f2807663657b5d3cf481024e))
* **terraform:** precommit fragment must be repos-mapping, not bare list ([1eaa342](https://github.com/bailiff-io/bailiff/commit/1eaa342d2bb9ae904f12d759ef95f707c92939cf))
* **test:** correct package-add SEC-001 guard stub regex (7 failing guard tests) ([c128a16](https://github.com/bailiff-io/bailiff/commit/c128a1660fd1ee050e3d868388150aba3f433151))
* **test:** correct stale comment on js_pkg_manager answers assertion ([d9d75ca](https://github.com/bailiff-io/bailiff/commit/d9d75cabeae564d78e6df27469c983f6934dcffa))
* **test:** update stale docstring — monorepo_packages is agent-fed not moon answers ([761ca4f](https://github.com/bailiff-io/bailiff/commit/761ca4f811d658ea77cc74182ca86a4d7245c007))
* version fallback for CI + detect unfanned tags regardless of commit distance ([e36d373](https://github.com/bailiff-io/bailiff/commit/e36d373e5910979975f386ed497f5f5cf89b6e47))
