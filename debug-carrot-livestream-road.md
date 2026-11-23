# Debug session: carrot-livestream-road

- PROJECT_ROOT: `/data/openpilot`
- DEBUG_EVIDENCE_DIR: `/tmp/trae-debug-openpilot-carrot-livestream-road`
- Evidence log: `/tmp/trae-debug-openpilot-carrot-livestream-road/trae-debug-log-carrot-livestream-road.ndjson`
- Environment file: `/tmp/trae-debug-openpilot-carrot-livestream-road/carrot-livestream-road.env`

## Scope

Determine why the device-side `encoderd --carrot-vision-road` process does not produce usable `livestreamRoadEncodeData`, without changing business logic before runtime evidence is collected.

## Hypotheses

- H1: `CarrotVisionActive=false` gates the on-demand encoder.
- H2: The parameter is active, but camera/VIPC input frames are absent.
- H3: Frames are encoded but publication/service wiring is incorrect.
- H4: Encoded messages exist; HTTP 500 is caused by WebRTC negotiation/first-packet handling.
- H5: Device runtime binary/source differs from the workstation source.

## Evidence status

- progress_status: root cause confirmed for missing encoded messages
- conclusion: H1 CONFIRMED; H2 and H3 rejected for the tested path; H4 INCONCLUSIVE because curl cannot complete ICE

## Runtime evidence

- Device parameter API: `CarrotVisionActive=False`; backing file absent before activation.
- Device `roadEncodeData`: 90 messages / 3 seconds, proving camerad/VIPC input is flowing.
- Device `livestreamRoadEncodeData`: 0 messages / 3 seconds while inactive.
- Reversible runtime experiment: setting `CarrotVisionActive=True` produced 150 encoded road messages / 5 seconds.
- Reverting `CarrotVisionActive=False` returned publication to 0 messages / 3 seconds.
- Therefore the encoder binary, input path, V4L encoder, and service publication path all work when the session gate is active.

## Hypothesis table

| Hypothesis | Evidence | Status |
|---|---|---|
| H1: inactive parameter gates encoder | false => 0; true => 150/5s; false again => 0 | CONFIRMED |
| H2: camera/VIPC input absent | roadEncodeData 90/3s; true gate produces output | REJECTED |
| H3: publication/service wiring broken | true gate publishes correct service | REJECTED |
| H4: HTTP 500 is independent WebRTC failure | not yet re-tested with active source | INCONCLUSIVE |
| H5: device binary/source mismatch causes no publication | runtime gate behavior matches source and output works when active | REJECTED for missing-message symptom |
