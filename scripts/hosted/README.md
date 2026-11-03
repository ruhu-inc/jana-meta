# The hosted demo

One Compute Engine VM, in Belgium (`europe-west1-b`) by default, runs the browser app for judges: one gateway, one front door and one core per private link. See
`scripts/jana_tools/hosted.py`. Offline tutoring with Muse Glimmer stays a desktop feature.

Only the gateway reads the Meta key: systemd hands it over as a credential file, and no key goes in this repository,
the image or the instance metadata. Private links are shown once on the machine that deploys, and the VM holds only
their SHA-256.

## Deploy

```bash
scripts/hosted/deploy.sh PROJECT_ID
```

The first run stops and asks you to add the key to Secret Manager with the command it prints. Run it again afterwards.
Add `--domain demo.example.com` to use your own name, once its DNS points at the printed address. Without it the demo
uses `<address>.sslip.io`.

## Sign-in

Besides the private links, people can sign in with email and password. Sign-up needs the invite code in the links file,
so a stranger who finds the address can neither use the app nor spend the Meta credit. Each account gets one of 10 member
places. There is no email delivery, so a forgotten password is reset on the VM, with the new one on stdin:

```bash
sudo -u jana /opt/jana/app/.venv/bin/python -m jana_tools.hosted reset-password --config /etc/jana/hosted.toml someone@example.com
```

For Google sign-in, create a Web OAuth client with the redirect URI `https://HOST/auth/google/callback`, put its secret in
Secret Manager as `jana-google-client-secret` readable by the `jana-demo` service account, then deploy with
`--google-client-id` and reboot the VM. Google sign-up still needs the invite code.

## After deploying

```bash
gcloud compute ssh jana-demo --project PROJECT_ID --zone europe-west1-b --command 'sudo journalctl -u jana-front -n 50'
```

Delete everything after judging, including the learners' data:

```bash
scripts/hosted/teardown.sh PROJECT_ID
```
