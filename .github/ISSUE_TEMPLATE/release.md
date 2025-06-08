---
name: Release
about: Prepare for a release
labels: maintenance
---

- [ ] merge all outstanding PRs
  - [ ] list of prs
- [ ] ensure the versions have been bumped (check with `pixi run pr`)
- [ ] ensure `CHANGELOG.md` is up-to-date
- [ ] validate on [ReadTheDocs][rtd]
- [ ] wait for a successful build of [`main`][main]
  - [ ] URL of build
- [ ] download the `dist` archive and unpack somewhere (maybe a fresh `dist`)
- [ ] create a new release through the GitHub UI
  - [ ] paste in the relevant `CHANGELOG.md` entries
  - [ ] upload the artifacts
- [ ] actually upload to [`pypi.org`][pypi]

  ```bash
  cd dist
  twine upload *.tar.gz *.whl
  ```

- [ ] postmortem
  - [ ] handle `conda-forge` [feedstock] tasks
    - [ ] conda-forge PR URL
  - [ ] make a postmortem PR
    - [ ] postmortem PR URL
    - [ ] bump to next version
    - [ ] start `CHANGELOG.md` _unreleased_ section
    - [ ] rebuild `pixi.lock`
    - [ ] update release procedures with lessons learned
    - [ ] `pixi run pr`

[feedstock]:
  https://github.com/conda-forge/jupyterlite-pyodide-lock-feedstock/issues/new?template=2-bot-commands.yml&title=@conda-forge-admin+please+update+version
[main]:
  https://github.com/deathbeds/jupyterlite-pyodide-lock/actions?query=branch%3Amain+event%3Apush
[pypi]: https://pypi.org/project/jupyterlite-pyodide-lock/#history
[rtd]: https://jupyterlite-pyodide-lock.rtfd.org/en/latest
