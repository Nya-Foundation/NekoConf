# Security Considerations in NekoConf

NekoConf provides several features to help you secure your configuration management, especially when using the web server or remote access.

## API Key Authentication

- The web server can be protected with an API key.
- Pass the API key as an `Authorization: Bearer <key>` header or as a cookie (`nekoconf_api_key`).
- Without an API key, anyone can access and modify your configuration.

### Enabling API Key

```bash
nekoconf server --api-key mysecretkey
```

Or in code:

```python
server = NekoConfOrchestrator(config, api_key="mysecretkey")
```

## Best Practices

- **Always set an API key in production.**
- Use strong, randomly generated API keys.
- Rotate API keys regularly.
- Restrict network access to the server (firewall, VPN, etc.).
- Use HTTPS (behind a reverse proxy) for all remote access.
- Limit access to `/api/config` endpoints as needed.
- Use `--read-only` mode for monitoring or audit-only deployments.

## Deployment Tips

- Run the server behind a reverse proxy (nginx, Caddy, etc.) for SSL termination.
- Use environment variables for secrets and API keys (never hardcode in code or config files).
- Monitor access logs for unauthorized attempts.

[!WARNING]
Never expose the NekoConf server to the public internet without authentication and proper network controls.

[!NOTE]
The `/health` and documentation endpoints are unauthenticated for diagnostics. Do not expose them in sensitive environments.
