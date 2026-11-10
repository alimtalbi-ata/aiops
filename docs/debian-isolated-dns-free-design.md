# Isolated Debian deployment: DNS policy (corrected)

**Authoritative scope clarification:** Docker embedded DNS and service-name resolution **between applications on this server are allowed**. Only DNS resolution to resolvers **outside the server** is prohibited.

## Allowed
- Compose service names such as `aiops2-postgres`, `aiops2-core`, `aiops2-temporal` and the Docker embedded resolver (typically `127.0.0.11`) for local inter-container discovery.
- Internal service-to-service traffic on dedicated Docker networks.

## Prohibited
- DNS queries forwarded to resolvers beyond the server, whether from containers or the host during the isolated workflow.
- Internet-dependent image pulls, remote package downloads or other network dependencies during installation and qualification.

## Acceptance criteria
1. Verify the full 18-service network graph, especially n8n → PostgreSQL and simulator → core, without requiring static IPv4 addresses.
2. Verify all six published ports bind only to host loopback; preserve internal network segmentation.
3. Audit host Docker daemon DNS configuration and upstream resolver behavior. **An internal Docker DNS query can be forwarded upstream on cache misses**: do not assume `127.0.0.11` alone guarantees no external DNS.
4. Use a controlled isolated test environment to observe outbound DNS traffic on UDP/TCP 53 (and review encrypted DNS / proxy routes where applicable). Confirm that only locally resolvable service names are needed.
5. Validate no external egress, image pulls or builds during deployment, and all image identities preloaded. Keep security P0 #535, independent review, backup/restore rehearsal and explicit authorization as release gates.
6. Do not access Debian `10.79.94.202` until release gates pass.

## Historical note
Earlier documents incorrectly interpreted the requirement as forbidding Docker internal DNS and mandating static IPs. That interpretation was withdrawn on user clarification. The standalone static network-plan validator, if retained, is **optional and not a deployment prerequisite**.

**Status: RELEASE HOLD for outstanding qualification and security gates, not for use of Docker internal DNS.**
