//! The app's own identity on the device (SPEC §17 Identity, JM-D7, JM-D19).
//!
//! The bundle identifier is `app.jana-meta.desktop` (tauri.conf.json), so the keychain service follows it; the key
//! fallback folder is `jana-meta`, and the core's key references start `jana-meta.` (`$defs/KeyRef`).

/// The folder, in the user's configuration folder, that holds the key fallback folder (SEC-17).
pub const KEYS_PARENT: &str = "jana-meta";
