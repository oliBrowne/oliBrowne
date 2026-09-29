# Maintaining this profile

This is the source for the GitHub profile at [github.com/oliBrowne](https://github.com/oliBrowne). GitHub displays the root `README.md` when it is committed to the public `oliBrowne/oliBrowne` repository.

## What to edit

| File | Purpose |
| --- | --- |
| `profile.json` | Name, bio, interests, and other text used in the generated artwork. |
| `assets/source-avatar.png` | Source photo used to make the ASCII portrait. |
| `scripts/profile_art.py` | Portrait and info-card design, colors, and animation. |
| `README.md` | Layout, accessible text, and project links. |
| `scripts/contributions.py` | Contribution data fetch and calendar rendering. |
| `.github/workflows/update-profile.yml` | Daily contribution refresh. |

After changing the bio, update the README's plain-text bio and image alt text too.

In `profile.json`, edit `name`, `title`, `school`, and `location` for the introduction; `stack`, `interests`, `offline`, and `project` for the detail rows. `portrait_source` points to the local source image. Keep `username` set to `oliBrowne` for this profile. If you reuse the template for another account, also change the username in the workflow and the README links.

## Regenerate the portrait and info card

From the repository root, with Python 3.13:

```sh
python -m pip install -r scripts/requirements-portrait.txt
python scripts/profile_art.py
```

This writes `assets/portrait.svg` and `assets/info-card.svg`. Commit the source changes and regenerated SVGs together. GitHub renders the committed files; it does not run the portrait generator when someone visits the profile.

## Refresh the contribution calendar

The daily workflow runs at **06:17 UTC**. You can also run it from **Actions → Refresh profile contributions → Run workflow**. Scheduled runs can start later than their configured time.

The contribution script uses Python's standard library to read the public calendar from GitHub. The workflow uses the repository's automatic `GITHUB_TOKEN` to commit updates; no personal access token or additional secret is needed. It runs the contribution tests, fetches the latest calendar, and commits only changed output files. A failed refresh leaves the last committed calendar available.

To run the checks and refresh locally:

```sh
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/contributions.py --username oliBrowne
```

The generated files are `data/contributions.json` and `assets/contrib-heatmap.svg`. Commit both together after a successful refresh.

The workflow runs automatically when its own configuration or the contribution script/tests change on `main`. Ordinary artwork and README commits do not trigger a contribution refresh.

## Check the published result

1. Open [the profile repository](https://github.com/oliBrowne/oliBrowne) and confirm the README images render.
2. Open [the profile page](https://github.com/oliBrowne) and check the side-by-side cards and calendar.
3. In **Actions**, check the latest **Refresh profile contributions** run. The YAML alone does not confirm that a run has succeeded.

If a repository rule prevents the automation from pushing to `main`, the refresh job will report a push error. Update the repository rule or use a pull-request workflow for generated updates.

## Design reference

The layout was inspired by [Build an animated GitHub profile README](https://www.avivashishta.com/blog/build-animated-github-profile-readme) by Avi Vashishta. The profile uses generated SVG artwork and a daily contribution refresh.
