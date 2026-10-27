# Gateway configuration

`meta-dev.toml` is the local development configuration for Jana on Meta: Muse Spark for reasoning and vision,
SAM 3.1 for segmentation, Muse Voice Transcribe for speech to text and Kokoro-82M (run by the gateway) for the
spoken voice. It holds no key. Put the Meta Model API key in the login keychain (service `jana-meta.cloud-gateway`,
account `meta_api_key`) or in the gateway-only `META_API_KEY` environment variable; `cloud_gateway/custody.py`
describes every source the gateway reads.

The spending limits under `[quotas]` cap the event's Meta credit; the ledger in `storage_dir` keeps every reservation
across restarts, so never delete it to reset a limit.
