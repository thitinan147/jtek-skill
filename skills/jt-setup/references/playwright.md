# Web app verify

`gate.py detect` prints `VERIFY_CMD` when the repo has a UI (a page framework, a page file, or `index.html`). `gate.py playwright` prints the minimal `playwright.config.ts`. Show both and wait. After the human confirms, run `gate.py playwright --root . --write`.

- `<VERIFY_CMD>` is `npx playwright test`. `<BROWSER_TOOL>` is `playwright`.
- The config sets `updateSnapshots` to `none` and `toHaveScreenshot`. It does not pass `--update-snapshots`. A baseline change is a separate step a human reviews. This task does not accept new snapshots.
- `--write` creates `playwright.config.ts` only when that file is absent. `playwright-config: present` means stop. Do not overwrite a config the repo already has.
- `feature-map: create-verification-skill` means pstack `/create-verification-skill` is installed. Invoke it and use its feature map for the screens the tests cover. Do not invent routes the map does not list.
- `feature-map: none` means that skill is not installed. Keep the minimal config. Do not invent a route list.
- Official docs: https://playwright.dev/docs/getting-started-cli and https://playwright.dev/agent-cli/skills and https://playwright.dev/docs/test-snapshots
