# CHANGELOG

<!-- version list -->

## v0.8.0 (2026-08-13)

### Features

- Rebuild UI to match provided design mockup pixel-for-pixel
  ([`d72435a`](https://github.com/CtrlCup/scanner/commit/d72435ab31e0ce640380ad2acf75780687ede000))


## v0.7.1 (2026-08-12)

### Bug Fixes

- Prevent hard crash from destroying a still-running QThread
  ([`a1d6ff8`](https://github.com/CtrlCup/scanner/commit/a1d6ff8f22dd2bff46c02aec00462063dd7b87e7))


## v0.7.0 (2026-08-12)

### Features

- Add update check against GitHub Releases (MVP, closes #2)
  ([`db9f6ec`](https://github.com/CtrlCup/scanner/commit/db9f6ec018e95c25468e8139ae797e25ef59ff6e))


## v0.6.1 (2026-08-12)

### Bug Fixes

- Mitigate Windows SmartScreen false-positive risk, document workaround
  ([`4fba800`](https://github.com/CtrlCup/scanner/commit/4fba8001a43e09468ccd3ca8f84881e79a9bee55))


## v0.6.0 (2026-08-12)

### Features

- Move settings into an embedded page instead of a separate window (closes #4)
  ([`b77eb40`](https://github.com/CtrlCup/scanner/commit/b77eb4084067c68fba7bfa3f651fa216944c5c03))


## v0.5.1 (2026-08-12)

### Bug Fixes

- Set app icon for taskbar/titlebar (closes #5)
  ([`367c80d`](https://github.com/CtrlCup/scanner/commit/367c80d525737bbd4f97355ed7eb4ccb84027857))


## v0.5.0 (2026-08-12)

### Documentation

- Add README with feature overview, download table and screenshots
  ([`3269638`](https://github.com/CtrlCup/scanner/commit/3269638778bd0dd4485a5525ba82e54fb533fed5))

### Features

- Add a real Windows installer (Inno Setup) alongside the portable exe
  ([`9442417`](https://github.com/CtrlCup/scanner/commit/9442417914f93ffb4dd275efded1e5355899f271))


## v0.4.2 (2026-08-12)

### Bug Fixes

- Remove emoji from release asset labels (GitHub rejects 4-byte UTF-8)
  ([`8eafc8e`](https://github.com/CtrlCup/scanner/commit/8eafc8ee8acbd5fe8298e3c789d7edc8288d7a23))


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
