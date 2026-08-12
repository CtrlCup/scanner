# CHANGELOG

<!-- version list -->

## v0.4.1 (2026-08-12)

### Bug Fixes

- Toggle switch handle jumps to wrong position on initial state set
  ([`ae8137a`](https://github.com/CtrlCup/scanner/commit/ae8137a458682d450d015c436015a81144bef52a))


## v0.4.0 (2026-08-12)

### Features

- Ship Windows build as a real single .exe, label release assets
  ([`d221369`](https://github.com/CtrlCup/scanner/commit/d2213697f5f6126cca7d612659a9ab80c53ebbce))


## v0.3.2 (2026-08-12)

### Bug Fixes

- Attach built packages to GitHub Releases automatically
  ([`7763271`](https://github.com/CtrlCup/scanner/commit/7763271747160bd318a6ffde0333d73e32db3d47))


## v0.3.1 (2026-08-12)

### Bug Fixes

- Make build_linux.sh work without a local .venv (CI runners)
  ([`ee34b0a`](https://github.com/CtrlCup/scanner/commit/ee34b0a497793e9779315f7f169ee7030cd955b7))


## v0.3.0 (2026-08-12)

### Features

- Add packaging for .exe, .AppImage, .deb, .rpm and .tar.gz
  ([`7b32f41`](https://github.com/CtrlCup/scanner/commit/7b32f415c36e3b2a7bd5073764465f26bcac58ec))

### Testing

- Skip real-tesseract orientation test when osd.traineddata is missing
  ([`c47e920`](https://github.com/CtrlCup/scanner/commit/c47e920411e3465d0399d9e85b33034efb2cdcc8))


## v0.2.0 (2026-08-12)

### Continuous Integration

- Install Qt runtime libraries for headless PySide6 tests
  ([`a86ac66`](https://github.com/CtrlCup/scanner/commit/a86ac665866d70806733357da18cd96a2d4dbd12))

- Pass GH_TOKEN to semantic-release so it can publish GitHub releases
  ([`034ec9c`](https://github.com/CtrlCup/scanner/commit/034ec9c0a86df213b1d04bd9bfbe9393da7f2dfe))

### Features

- Add auto-rotate and optional handwriting recognition
  ([`85e6d1d`](https://github.com/CtrlCup/scanner/commit/85e6d1d79f14323787b659896f0a32174d765b49))


## v0.1.0 (2026-08-11)

### Bug Fixes

- Correct semantic-release config (allow_zero_version, build_command type)
  ([`6f0d8ee`](https://github.com/CtrlCup/scanner/commit/6f0d8ee7694a615ee12a210b0a8c1849953339cb))

### Features

- Add domain model, scanner backends, PDF writer and OCR pipeline
  ([`887f4aa`](https://github.com/CtrlCup/scanner/commit/887f4aa1b7a0d9a31238741f600f22b4ce841f56))

- Implement complete Scanner UI matching the Figma design
  ([`c380250`](https://github.com/CtrlCup/scanner/commit/c380250b805667cec7083cda52cc3d9b2b9f2be0))


## v0.0.1 (initial release)

- Projekt-Grundgerüst
