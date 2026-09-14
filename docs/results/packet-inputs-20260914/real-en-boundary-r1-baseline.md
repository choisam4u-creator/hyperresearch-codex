# Question: Compare the two archive routes while preserving their scope and boundary conditions.

## Answer

There is no universal winner: Cedar is designed for signed archives on pre-approved private hostnames, whereas Maple is designed for public HTTPS sources and rejects private addresses. [S1][S2]
Cedar is the applicable route when an archive must remain on an approved private network, provided an administrator lists the hostname before retrieval. [S1]
Maple is the applicable route when a validated public HTTPS copy exists, including when a department can publish a suitable public copy of an intranet archive. [S2]
The observed 31-second Maple median must not be treated as evidence that Maple is faster than Cedar’s 38-second median because the tests used different file-size ranges and source conditions. [S1][S2]

| Decision criterion | Cedar | Maple |
|---|---|---|
| Source boundary | Approved private hostname only; arbitrary private addresses are not supported. [S1] | Public HTTPS only; private network addresses are intentionally rejected. [S2] |
| Preconditions | Signed archive, hostname listed by an administrator before the run, and archive already copied to the approved segment. [S1] | Public copy available and passing usual validation. [S2] |
| Recorded provenance | Original file hash, retrieval timestamp, and audit event for the configured source and retrieval action. [S1] | Final URL after redirects and content hash; timestamp or equivalent audit event is unknown. [S2] |
| Observed retrieval time | 38-second median for eight archives of 80–140 MB, excluding prior copying and manual approval. [S1] | 31-second median for eight public archives of 50–90 MB. [S2] |
| Important exception | Refuses a hostname that was not approved before the run. [S1] | Cannot retrieve an intranet archive unless a public copy has been published. [S2] |

Choose primarily by network-access boundary and required provenance, not by the unmatched timing medians. [S1][S2] (judgment)

## Evidence

Cedar reads a signed archive from an approved private hostname only after an administrator has listed that hostname, and it refuses the connection when this prerequisite is unmet. [S1]

In the tested environment, Cedar preserved the original file hash, stored a retrieval timestamp, and recorded an audit event when an approved hostname was used. [S1] The event documents the configured source and retrieval action but does not establish that the archive’s content is accurate or correct an erroneous archive. [S1]

Cedar’s reported median retrieval time was 38 seconds across eight archives ranging from 80 to 140 MB. [S1] Measurement began only after each archive had been copied into the approved network segment, so the figure excludes that copy and manual approval time. [S1]

Maple accepts only public HTTPS sources and intentionally rejects private network addresses to reduce the chance of inadvertently reaching an internal service. [S2] Consequently, it cannot retrieve an intranet archive unless the department publishes a public copy that passes the usual validation. [S2]

For provenance, Maple stores the final URL reached after redirects and a content hash. [S2]

Maple recorded a median retrieval time of 31 seconds in a public test set of eight archives ranging from 50 to 90 MB. [S2]

The routes therefore cover different source conditions: Cedar adds administrative setup for an approved private source, while Maple serves public HTTPS sources. [S1][S2] Their timing results are operational observations rather than a controlled, like-for-like performance comparison. [S1][S2]

## Counter-evidence and limits

The supplied sources do not disagree about either route’s stated boundary, and neither claims a universal winner. [S1][S2] Cedar’s end-to-end time for a new customer cannot be verified because its measurement omits copying the archive into the approved segment and obtaining manual approval. [S1] Relative performance also cannot be established because Cedar tested larger files on an approved network segment while Maple tested smaller files from public sources. [S1][S2] Maple’s notes do not specify a retrieval timestamp, a Cedar-like audit event, or behavior for a public source that later becomes unavailable, so those details remain unknown. [S2] Cedar’s successful audit event proves that the configured source was used and the retrieval action occurred, not that the archived content was substantively accurate. [S1]

## Next actions

- Classify the required archive location as approved-private or public-HTTPS before selecting a route. [S1][S2] (judgment)
- For Cedar, include hostname approval, archive copying, and manual approval in an end-to-end timing test. [S1] (judgment)
- If performance will affect the decision, benchmark both routes with matched archive sizes and comparable source conditions. [S1][S2] (judgment)
- Confirm whether Maple’s recorded final URL and hash satisfy the organization’s audit requirements before adopting it. [S2] (judgment)

## Sources

- S1 — *replay real-en-boundary S1* — https://fixture.invalid/replay/real-en-boundary/S1
- S2 — *replay real-en-boundary S2* — https://fixture.invalid/replay/real-en-boundary/S2