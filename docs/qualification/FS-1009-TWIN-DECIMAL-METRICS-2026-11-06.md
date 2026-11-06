# FS.1009 — Twin Decimal metrics candidate

**Status: candidate-build procedure committed; host execution and endpoint qualification pending.**

## Background

FS.1004–FS.1008 isolated the Twin /metrics HTTP 503 to the filesystem observation exporter. The active query selects the latest explicitly real observation for CI-FS-LAB-12M / fs_used_percent; PostgreSQL returns Decimal("92"). The runtime implementation rejected it because it accepted only exact int and float types.

Evidence:
- FS.1004: Twin database is healthy; /metrics returns 503 invalid_observation_value.
- FS.1005: exception originates in twin.fs_observations.fs_lab_metrics.
- FS.1007: five real observations exist for the exact node/metric pair; 35 other listed observations are synthetic.
- FS.1008: exact active-filter row is Decimal, value 92, timestamp present; metrics call still fails.

## Candidate change

scripts/fs/FS.1009.sh performs a narrow, reproducible candidate build:

1. Reads the current image name and image ID for aiops2-rebuild-twin.
2. Copies /app/twin/fs_observations.py out of that container without modifying it.
3. Adds _validated_fs_percent, accepting int, float, and Decimal, explicitly rejecting bool, and rejecting non-finite or out-of-range values.
4. Converts the validated value to float only for Prometheus exposition and threshold comparison. The database row and timestamp are not changed.
5. Builds aiops2-twin:fs1009-decimal-metrics-candidate-20261106 from the exact current Twin image.
6. Runs pure validation-contract tests inside the candidate image.

The patch deliberately fails closed if the runtime source no longer matches the exact guard and exposition statements observed in FS.1005/FS.1008. It does not use a fuzzy replacement.

## Contract cases

Expected accepted inputs:
- Decimal("92"), Decimal("0"), Decimal("100")
- integer and float values within the inclusive 0–100 range

Expected rejected inputs:
- True and False
- Decimal/float NaN and positive/negative Infinity
- values below 0 or above 100
- strings and None

## Execution and qualification

On SRV-DEB-05:

    REPO=/home/aiops/aiops2-v2-delivery
    git -C "$REPO" fetch origin fix/fs-1009-twin-decimal-metrics
    git -C "$REPO" show origin/fix/fs-1009-twin-decimal-metrics:scripts/fs/FS.1009.sh > /tmp/FS.1009.sh
    bash -n /tmp/FS.1009.sh && bash /tmp/FS.1009.sh

The script must report FS1009_CONTRACT_RESULT=PASS and BASE_CONTAINER_IMAGE_UNCHANGED=YES.

## Explicit qualification limits

A successful script run proves source patching, Python compilation, image construction, and the pure numeric contract only. It does not prove the /metrics endpoint returns HTTP 200, that Prometheus marks Twin UP, or that the alert state is correct. Those require a separately authorized isolated runtime test against the candidate image.

No Twin service is started or replaced. No production restart, database write, HTTP write, business workflow, or live remediation is performed. Do not promote this image until endpoint media type, metric values, observation timestamp, Prometheus target health, and rollback are independently qualified.
