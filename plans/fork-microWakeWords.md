# Plan: `microWakeWords` Fork Migration

## Status

Completed for this trainer repo. The firmware source is the cleaned fork:

```text
Gabriel-Lewis/microWakeWords
```

The fork uses cleaned root template names:

- `voicePE.yaml`
- `satellite1.yaml`

## Trainer Behavior

- `trainer_server.py` defaults to `FIRMWARE_GITHUB_OWNER=Gabriel-Lewis`, `FIRMWARE_GITHUB_REPO=microWakeWords`, and `FIRMWARE_GITHUB_REF=main`.
- The Firmware tab fetches `voicePE.yaml` and `satellite1.yaml` from the fork at runtime.
- There is no default fallback to the old firmware repo.
- Saved firmware profile values and template content may still be normalized from legacy URLs to the configured firmware repo.
- `watcher.sh` defaults `MW_ISSUE_REPO` to `Gabriel-Lewis/microWakeWords`.

## Verification

```bash
gh repo view Gabriel-Lewis/microWakeWords --json defaultBranchRef,pushedAt
gh api repos/Gabriel-Lewis/microWakeWords/contents/voicePE.yaml --jq .name
gh api repos/Gabriel-Lewis/microWakeWords/contents/satellite1.yaml --jq .name
```

Manual smoke test:

1. Start the server with `./run.sh`.
2. Open the Firmware tab.
3. Confirm both `VoicePE` and `Sat1` load editable fields.
4. Build or preview generated firmware config and confirm package/import URLs point at `Gabriel-Lewis/microWakeWords`.
