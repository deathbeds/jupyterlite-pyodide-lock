---
name: Release
about: Prepare for a release
labels: maintenance
---

- [ ] merge all outstanding PRs
- [ ] ensure the versions have been bumped (check with `pixi r pr`)
- [ ] ensure `CHANGELOG.md` is up-to-date
- [ ] validate on [ReadTheDocs][rtd]
- [ ] wait for a successful build of [`main`][main]
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
  - [ ] make a postmortem PR
    - [ ] bump to next version
    - [ ] start `CHANGELOG.md` unreleased section
    - [ ] rebuild `pixi.lock`
    - [ ] update release procedures with lessons learned

[feedstock]:
  https://github.com/conda-forge/jupyterlite-pyodide-lock-feedstock/issues/new?template=2-bot-commands.yml&title=@conda-forge-admin+please+update+version
[main]:
  https://github.com/deathbeds/jupyterlite-pyodide-lock/actions?query=branch%3Amain+event%3Apush
[pypi]: https://pypi.org/project/jupyterlite-pyodide-lock/#history
[rtd]: https://jupyterlite-pyodide-lock.readthedocs.io/en/latest
