# Question: Compare the two archive routes while preserving their scope and boundary conditions.

## Answer

Neither route is universally superior: Cedar is suitable for a signed archive on an approved private hostname, while Maple requires a public HTTPS source and rejects private addresses.[S1][S2] Cedar fits an intranet-source requirement only for a signed archive on an approved private hostname that an administrator has listed.[S1] The reported medians—38 seconds for Cedar and 31 seconds for Maple—do not establish that Maple is faster because the archive sizes and measured workflow boundaries differ.[S1][S2] The primary decision criterion should be source accessibility and the required network boundary, with timing treated as secondary until a controlled end-to-end test is available.[S1][S2] (judgment)

| Route | Eligible source and conditions | Explicit exceptions or exclusions | Records produced | Reported timing |
|---|---|---|---|---|
| Cedar | Signed archive on an approved private hostname; an administrator must list the hostname before the run.[S1] | It is not claimed to reach arbitrary private addresses; the reported time excludes the prior network-segment copy and manual approval.[S1] | Original file hash, retrieval timestamp, and an audit event for the configured source and retrieval action.[S1] | Median 38 seconds for eight 80–140 MB archives already copied to the approved segment.[S1] |
| Maple | Public HTTPS source that passes the usual validation.[S2] | Private network addresses and an unpublished intranet archive are out of scope.[S2] | Final URL after redirects and a content hash; audit-event behavior is unknown from the supplied note.[S2] | Median 31 seconds for eight 50–90 MB archives in a public test set.[S2] |

## Evidence

Cedar reads a signed archive from an approved private hostname, but the hostname must be listed by an administrator before execution begins.[S1] If that prerequisite is not satisfied, Cedar refuses the connection.[S1]

In the tested environment, Cedar preserved the archive’s original file hash and stored a retrieval timestamp.[S1] This observed behavior does not broaden its network scope, because the guide makes no claim that Cedar can access arbitrary private addresses.[S1]

Cedar’s median retrieval time was 38 seconds across eight archives ranging from 80 to 140 MB.[S1] Measurement began only after each archive had been copied to the approved network segment, and it excluded both that prior copy and manual approval time.[S1] The figure is consequently not an end-to-end duration for a new customer.[S1]

Cedar records an audit event when an approved hostname is used.[S1] That event records the configured source and retrieval action, rather than proving that the archive’s contents are accurate.[S1] A valid event therefore neither detects nor corrects an archive that is itself wrong.[S1]

Maple accepts only public HTTPS sources and intentionally rejects private network addresses to reduce accidental access to internal services.[S2] A department whose required archive exists only on an intranet cannot retrieve it through Maple unless it publishes a public copy that passes the usual validation.[S2]

Maple recorded a median retrieval time of 31 seconds for eight public-test archives between 50 and 90 MB.[S2] Those archive sizes differ from Cedar’s 80–140 MB range, preventing a size-matched comparison.[S1][S2]

Maple stores the final URL reached after redirects and a content hash.[S2] The supplied Maple note does not describe a retrieval timestamp or an audit event equivalent to Cedar’s, so their availability cannot be established from this evidence.[S1][S2]

The guides provide no universal winner because Cedar and Maple address different source boundaries and impose different eligibility conditions.[S1][S2] Their median timings are operational observations from different file sets, not results from a controlled comparative benchmark.[S1][S2]

## Counter-evidence and limits

No supplied source directly disputes the other route’s documented scope; instead, the evidence emphasizes that the routes serve different network conditions.[S1][S2] Maple’s lower reported median is potential counter-evidence to Cedar on raw retrieval time, but it cannot demonstrate superior performance because the files, locations, and measurement boundaries were not matched.[S1][S2] Neither note supplies an end-to-end test using identical archives, network conditions, approval steps, and timing boundaries.[S1][S2] Both supplied notes identify the same fixture.invalid domain, so the report lacks evidence from an independently represented domain.[S1][S2] Operational behavior outside the described tests, including failure rates and performance at other archive sizes, could not be verified.[S1][S2]

## Next actions

1. Classify the required archive as approved-private or public-HTTPS before selecting a route.[S1][S2] (judgment)
2. If both routes can be made eligible, benchmark them with the same archives, network conditions, validation steps, and end-to-end start and stop points.[S1][S2] (judgment)
3. Separately verify archive correctness, because Cedar’s audit event records source and retrieval activity but does not prove that the archive content is accurate.[S1] (judgment)

## Sources

- [S1] “replay real-en-boundary S1” — https://fixture.invalid/replay/real-en-boundary/S1
- [S2] “replay real-en-boundary S2” — https://fixture.invalid/replay/real-en-boundary/S2