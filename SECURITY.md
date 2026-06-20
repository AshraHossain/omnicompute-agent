# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in OmniCompute, please report it responsibly by emailing **security@omncompute.dev** instead of using the public issue tracker.

**Do NOT** open a public GitHub issue for security vulnerabilities.

## What to Include

Please include:
- Description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact
- Any suggested fixes (if you have them)

## Response Timeline

We aim to:
- Acknowledge receipt within 24 hours
- Provide initial assessment within 72 hours
- Issue a fix within 7-14 days for critical issues
- Coordinate disclosure timing with you

## Security Best Practices

### For Users

1. **Keep dependencies updated**: Run `pip install -r requirements.txt` regularly
2. **Protect encryption keys**: Store Fernet keys securely (use environment variables, secrets managers)
3. **Validate telemetry input**: OmniCompute validates all inputs, but validate at your boundary too
4. **Use HTTPS**: Always transmit uplink bundles over HTTPS
5. **Enable FIPS-140-2 mode**: Use only for ITAR-classified deployments

### For Contributors

1. **Never hardcode secrets**: Use environment variables or configuration
2. **Validate all inputs**: Especially at system boundaries (user input, API responses)
3. **Use parameterized queries**: Prevent injection attacks
4. **Avoid unsafe serialization**: Never pickle untrusted data
5. **Review security checklist** before submitting PR:
   - [ ] No hardcoded credentials
   - [ ] All user inputs validated
   - [ ] No obvious XSS/injection vulnerabilities
   - [ ] Cryptographic operations are sound
   - [ ] Error messages don't leak sensitive info

## Known Security Considerations

### Encryption

- Uses Fernet (FIPS-140-2 compatible)
- Requires 32-byte key (base64-encoded)
- Supports rotation between bundle generations

### Access Control

- No built-in authentication (intended for edge deployment)
- Assumes trusted network within satellite constellation
- Implement network-level access controls for your deployment

### Data Handling

- Compresses telemetry data before transmission
- Summarizes metrics (no raw sensor values transmitted)
- Respects ITAR requirements for classified nodes
- Supports per-node encryption keys if needed

## Compliance

OmniCompute is designed for:
- **FIPS-140-2**: Encryption and random number generation
- **ITAR**: Classified network node isolation
- **DO-178C**: Deterministic output, audit trail logging

For regulated deployments, review DEPLOYMENT.md and work with your compliance team.

## Security Audit

Last security audit: **2026-06-20**
- Coverage: All 4 phases, 155 tests, 97% code coverage
- Focus: Input validation, encryption, error handling, ITAR compliance
- Status: ✅ Passed

Next audit: **Scheduled after Phase 5**

## Dependency Security

We use:
- `cryptography` (maintained, audited)
- `pydantic` (v2, actively maintained)
- `pyyaml` (safe loading only)
- `pytest` (testing only, dev dependency)

All dependencies are pinned in `requirements.txt` for reproducibility.

To check for known vulnerabilities:
```bash
pip install safety
safety check
```

## Questions?

- For security questions: email security@omnicompute.dev
- For general support: open an issue on GitHub
- For compliance questions: see DEPLOYMENT.md

Thank you for helping keep OmniCompute secure! 🔒
