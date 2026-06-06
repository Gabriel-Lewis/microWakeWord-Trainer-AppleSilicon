# Migration: Remove TaterTotterson Runtime Dependencies

## Status

Runtime dependencies now target maintained upstreams or Gabriel-Lewis forks:

| Dependency | Target |
|---|---|
| `piper-sample-generator` model assets | `rhasspy/piper-sample-generator` release `v2.0.0` |
| `micro-wake-word` training library | `Gabriel-Lewis/micro-wake-word` |
| Firmware YAML templates | `Gabriel-Lewis/microWakeWords` |
| `watcher.sh` issue repo | `Gabriel-Lewis/microWakeWords` |

The cleaned `Gabriel-Lewis/microWakeWords` repo uses these canonical template names:

- `voicePE.yaml`
- `satellite1.yaml`

The older `voicePE-TaterTimer.yaml` and `satellite1-TaterTimer.yaml` paths are not required by this trainer.

## Implemented Changes

- `trainer_server.py` defaults firmware fetches to `Gabriel-Lewis/microWakeWords` on `main`.
- The Firmware tab fetches `voicePE.yaml` and `satellite1.yaml` directly from the cleaned fork.
- There is no default runtime fallback to the old firmware repo; users can still override the firmware source with `FIRMWARE_GITHUB_OWNER`, `FIRMWARE_GITHUB_REPO`, and `FIRMWARE_GITHUB_REF`.
- `train_microwakeword_macos.sh` clones `Gabriel-Lewis/micro-wake-word` and repoints existing local clones whose origin still references the old fork.
- Piper model downloads use `rhasspy/piper-sample-generator` release assets.
- `watcher.sh` defaults `MW_ISSUE_REPO` to `Gabriel-Lewis/microWakeWords`.

## Verification

```bash
gh repo view Gabriel-Lewis/micro-wake-word --json defaultBranchRef,pushedAt
gh repo view Gabriel-Lewis/microWakeWords --json defaultBranchRef,pushedAt
gh api repos/Gabriel-Lewis/microWakeWords/contents/voicePE.yaml --jq .name
gh api repos/Gabriel-Lewis/microWakeWords/contents/satellite1.yaml --jq .name
```

Expected firmware template URLs:

```text
https://raw.githubusercontent.com/Gabriel-Lewis/microWakeWords/main/voicePE.yaml
https://raw.githubusercontent.com/Gabriel-Lewis/microWakeWords/main/satellite1.yaml
```

Smoke tests:

- Start the server with `./run.sh`, open the Firmware tab, and confirm both template forms load.
- Build firmware config for each template and confirm generated package/import URLs point to `Gabriel-Lewis/microWakeWords`.
- Run enough of `./train_microwakeword_macos.sh "hey_computer"` to confirm `deps/micro-wake-word` is cloned or repointed to `Gabriel-Lewis/micro-wake-word`.

## Notes

Historical credits in documentation may still mention TaterTotterson. Runtime fetches should not depend on TaterTotterson repositories.
