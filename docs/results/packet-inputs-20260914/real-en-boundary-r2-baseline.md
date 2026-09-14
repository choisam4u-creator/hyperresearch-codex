# Question: Compare the two archive routes while preserving their scope and boundary conditions.

## Answer

Neither route is universally superior: Cedar is the applicable route for a signed archive on a pre-approved private hostname, while Maple is limited to public HTTPS sources [S1][S2]. Choose according to source location and approval constraints, not the reported median retrieval times, because the tests used different file-size ranges and Cedar’s measurement excluded prior copying and manual approval [S1][S2]. For an intranet-only archive, Cedar is the viable route if an administrator can approve the hostname before the run [S1] (judgment). For an archive already available through validated public HTTPS, Maple avoids Cedar’s private-host approval condition [S1][S2] (judgment).

| Criterion | Cedar | Maple |
|---|---|---|
| Eligible source | Signed archive on an approved private hostname [S1] | Public HTTPS source only [S2] |
| Required condition | Administrator lists the hostname before the run; otherwise connection is refused [S1] | Source must be publicly published and pass usual validation [S2] |
| Private-network access | Supported only for the approved hostname; arbitrary private-address access is not claimed [S1] | Rejected, so an unpublished intranet archive is inaccessible [S2] |
| Recorded provenance | Original file hash, retrieval timestamp, and audit event for configured source and retrieval action [S1] | Final redirected URL and content hash [S2] |
| Observed timing | 38-second median for eight 80–140 MB archives, after copying to the approved segment [S1] | 31-second median for eight 50–90 MB public archives [S2] |
| End-to-end comparison | Unknown; copy and manual approval time were excluded [S1] | Unknown under conditions matched to Cedar [S1][S2] |
| Reliability, cost, security completeness, throughput | Unknown [S1] | Unknown [S2] |

## Evidence

Cedar reads a signed archive from an approved private hostname only when an administrator has listed that hostname before the run [S1]. If the hostname has not been listed, Cedar refuses the connection, and the guide does not claim access to arbitrary private addresses [S1].

S1 reports that Cedar preserved the original file hash and stored a retrieval timestamp [S1]. Its audit event records use of the approved hostname, the configured source, and the retrieval action, but it does not establish that the archive’s contents are accurate [S1].

Cedar recorded a median retrieval time of 38 seconds across eight archives ranging from 80 to 140 MB [S1]. Measurement began only after each archive had been copied to the approved network segment, excluding that copy and manual approval time, so the result is not an end-to-end time for a new customer [S1].

Maple accepts only public HTTPS sources and intentionally rejects private network addresses [S2]. It therefore cannot retrieve an intranet archive unless the department publishes a public copy that passes the usual validation [S2].

S2 reports that Maple stores the final redirected URL and content hash and observed a 31-second median in its public test set [S2].

The routes cover different source boundaries: Cedar supports a pre-approved private hostname with additional setup, whereas Maple supports public HTTPS sources [S1][S2]. Their timing figures do not constitute a controlled comparison because the archive-size ranges differ and Cedar’s measurement omits preceding work [S1][S2].

## Counter-evidence and limits

The reviewed sources do not disagree about either route’s stated boundary, and neither identifies a universal winner [S1][S2]. Maple’s lower observed median does not prove that it is faster under equivalent conditions because its archives were smaller and the tests were not matched [S1][S2]. The sources provide no controlled end-to-end test using the same archives and conditions [S1][S2]. They also provide no results that support comparing reliability, cost, security completeness, or throughput [S1][S2]. Cedar’s audit event is evidence of the configured source and retrieval action, not evidence that the retrieved content is correct [S1].

## Next actions

1. Confirm whether the authoritative archive must remain private or may be published through validated public HTTPS before selecting a route [S1][S2] (judgment).
2. If the archive must remain private, arrange Cedar hostname approval and include copying plus manual approval in the operational schedule [S1] (judgment).
3. If performance determines the decision, benchmark both routes with the same archives and measure the complete workflow from approval or publication through retrieval [S1][S2] (judgment).

## Sources

- S1 — “replay real-en-boundary S1”: https://fixture.invalid/replay/real-en-boundary/S1
- S2 — “replay real-en-boundary S2”: https://fixture.invalid/replay/real-en-boundary/S2