# Question: Compare the two archive routes while preserving their scope and boundary conditions.

## Answer

Cedar is applicable to a signed archive on an approved private hostname after an administrator lists that hostname before the run; it is not a general-purpose route to arbitrary private addresses. [S1] Maple is applicable only when the archive is available through a valid public HTTPS source, because it intentionally rejects private network addresses. [S2] The reported retrieval medians—38 seconds for Cedar and 31 seconds for Maple—do not establish that Maple is faster because the tests used different file-size ranges and Cedar’s measurement excluded prerequisite work. [S1][S2] Choose by source accessibility and required controls before considering the timing figures: use Cedar only for a signed archive on an approved private hostname and Maple for an eligible public HTTPS source. [S1][S2] (judgment)

| Criterion | Cedar | Maple |
|---|---|---|
| Eligible source | Signed archive on a pre-approved private hostname [S1] | Public HTTPS source passing usual validation [S2] |
| Boundary condition | Administrator must list the hostname before the run; unlisted connections are refused [S1] | Private network addresses are intentionally rejected [S2] |
| Recorded provenance | Original file hash, retrieval timestamp, and audit event for the configured source and action [S1] | Final post-redirect URL and content hash [S2] |
| Observed timing | 38-second median for eight 80–140 MB archives, after copying to the approved segment [S1] | 31-second median for eight 50–90 MB archives [S2] |
| End-to-end or matched comparison | No; prior copying and manual approval are excluded [S1] | Unknown; the tested files are not matched to Cedar’s range [S2] |
| Key exception | Does not claim access to arbitrary private addresses [S1] | Cannot retrieve an intranet archive without a public copy [S2] |

## Evidence

Cedar reads a signed archive from an approved private hostname only after an administrator has listed that hostname, and it refuses the connection otherwise. [S1] Its guide does not claim access to arbitrary private addresses. [S1]

In the tested environment, Cedar preserved the original file hash and stored a retrieval timestamp. [S1] It also recorded an audit event when an approved hostname was used, but that event documented the configured source and retrieval action rather than proving that the archive’s content was accurate. [S1]

Cedar’s 38-second median covered eight archives between 80 and 140 MB after each archive had already been copied to the approved network segment. [S1] The figure excluded both the prior copy and manual approval time, so it was not an end-to-end measurement for a new customer. [S1]

Maple accepts only public HTTPS sources and deliberately rejects private network addresses to reduce the chance of reaching an internal service by mistake. [S2] A department whose required intranet archive lacks a public copy therefore cannot use Maple and must instead provide a public HTTPS source that passes the usual validation. [S2]

For provenance, Maple stores the final URL reached after redirects and a content hash. [S2]

Maple’s public test set contained eight archives between 50 and 90 MB and produced a median retrieval time of 31 seconds. [S2]

The routes therefore cover different source boundaries: Cedar supports an approved private source subject to advance setup, whereas Maple supports public HTTPS sources. [S1][S2] Their timing results are operational observations rather than a controlled performance comparison because the file-size ranges differ and Cedar’s measurement has explicit exclusions. [S1][S2]

## Counter-evidence and limits

The supplied claims identify no directly disagreeing source. (no source) Maple’s guide explicitly says that neither route is a universal winner and cautions that the two timing figures are not a controlled comparison. [S2] No matched-file-set, end-to-end benchmark was available, so relative speed, total onboarding time, and performance under identical conditions could not be verified. (no source) The notes also do not establish which route is preferable beyond the distinction between an approved private hostname and a valid public HTTPS source. (no source) Cedar’s audit event records the configured source and retrieval action, not that the retrieved content was correct. [S1]

## Next actions

1. Classify the department’s archive location as an approved private hostname or a valid public HTTPS source before selecting a route. [S1][S2] (judgment)
2. If Cedar is considered, confirm that an administrator can approve and list the exact hostname before execution. [S1] (judgment)
3. If Maple is considered, verify that a public copy exists and passes normal HTTPS validation. [S2] (judgment)
4. If speed affects the decision, run a matched-file-set end-to-end test that includes Cedar’s copying and approval work. (no source) (judgment)

## Sources

- S1 — “replay real-en-boundary S1” — https://fixture.invalid/replay/real-en-boundary/S1
- S2 — “replay real-en-boundary S2” — https://fixture.invalid/replay/real-en-boundary/S2