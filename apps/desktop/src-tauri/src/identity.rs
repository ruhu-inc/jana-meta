//! The app's own identity on the device (SPEC §17 Identity, JM-D7, JM-D19).
//!
//! Builds before this one shared Jana's bundle identifier `app.jana.desktop` and its key folder `jana`, so on a
//! computer that also runs Jana the two apps shared one data folder and one keychain service. This build is
//! `app.jana-meta.desktop` (tauri.conf.json), so its keychain service follows, and its key folder is `jana-meta`.
//!
//! The first start under the new names adopts what an earlier build left under the former ones, by copying, never by
//! moving: Jana's own install may still use them, so the former folder and keychain items are left as they were.
//!
//! - The core's data (`core/` in the data folder: profiles, packs, models) is copied to a staging folder beside its
//!   new place, compared byte for byte with the original, and only then renamed into place, so the new folder either
//!   holds the whole verified copy or none of it. An interrupted copy leaves only the staging folder, which the next
//!   start removes and makes again. Nothing is adopted once the new folder holds core data of its own, so a later
//!   start never mixes the two apps' data. The shell's pid file stays behind: its processes are the other app's.
//! - The device secrets (`jana.device-db` and the others the core keeps) are copied with that data: a
//!   marker beside the adopted data says the keys are still to come, and the next key store opened copies them into
//!   the new store, when it holds none yet, reference by reference, then removes the marker. So a later start never
//!   brings Jana's keys back into a store the core has emptied.

use crate::data_home::{copy_tree, same_tree};
use crate::keychain::KeyStore;
use std::fs::{self, File};
use std::io;
use std::path::{Path, PathBuf};

/// The bundle identifier builds before this one used (Jana's own).
pub const FORMER_IDENTIFIER: &str = "app.jana.desktop";
/// The folder, in the user's configuration folder, that holds the key fallback folder (SEC-17).
pub const KEYS_PARENT: &str = "jana-meta";
/// The one builds before this one used (Jana's own).
pub const FORMER_KEYS_PARENT: &str = "jana";
/// The part of the data folder that is adopted: the core's data.
const CORE: &str = "core";
const STAGING: &str = "core.jana-adopting";
/// Written beside the adopted data until the device keys have been adopted too.
const KEYS_PENDING: &str = ".jana-keys-to-adopt";

/// The data folder builds before this one used, beside `local` (the same parent, the former identifier's name).
pub fn former_data(local: &Path) -> PathBuf {
    local.with_file_name(FORMER_IDENTIFIER)
}

/// Copy the core's data from `former` into `local` when `local` has none yet (module docs); whether it did.
pub fn adopt_data(former: &Path, local: &Path) -> io::Result<bool> {
    let target = local.join(CORE);
    let staged = local.join(STAGING);
    if fs::symlink_metadata(&target).is_ok() {
        return Ok(false);
    }
    let source = former.join(CORE);
    if !source.is_dir() {
        return Ok(false);
    }
    if staged.exists() {
        fs::remove_dir_all(&staged)?; // an interrupted copy: the original is untouched
    }
    fs::create_dir_all(local)?;
    let copied = copy_tree(&source, &staged).and_then(|()| same_tree(&source, &staged));
    if !matches!(copied, Ok(true)) {
        let _ = fs::remove_dir_all(&staged);
        return Err(copied.err().unwrap_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "the copy did not verify")
        }));
    }
    File::create(local.join(KEYS_PENDING))?.sync_all()?;
    fs::rename(&staged, &target)?;
    Ok(true)
}

/// Whether the data adopted from the former folder still waits for its device keys.
pub fn keys_pending(local: &Path) -> bool {
    local.join(KEYS_PENDING).exists()
}

/// After the data was adopted into `local`: copy every secret the `former` store holds (none when it cannot be opened)
/// into `store` when `store` holds none yet (module docs), then mark the adoption finished; how many were copied.
pub fn adopt_keys(local: &Path, store: &KeyStore, former: Option<&KeyStore>) -> io::Result<usize> {
    if !keys_pending(local) {
        return Ok(0);
    }
    let copied = match former {
        Some(former) if store.entries().is_empty() => former
            .entries()
            .iter()
            .filter(|entry| store.put(&entry.r#ref, &entry.value))
            .count(),
        _ => 0,
    };
    fs::remove_file(local.join(KEYS_PENDING))?;
    Ok(copied)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::control::Redacted;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn scratch(name: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "jana-identity-{name}-{}-{nanos}",
            std::process::id()
        ));
        fs::create_dir_all(&root).unwrap();
        root
    }

    /// A former data folder as an earlier build left it: the core's data and the shell's pid file.
    fn former_folder(root: &Path) -> PathBuf {
        let former = root.join(FORMER_IDENTIFIER);
        fs::create_dir_all(former.join("core/profiles/p1")).unwrap();
        fs::write(
            former.join("core/profiles/p1/learner.db"),
            b"synthetic learner rows",
        )
        .unwrap();
        fs::write(former.join("shell-pids.json"), b"[123]").unwrap();
        former
    }

    #[test]
    fn identity_former_data_is_copied_once_and_left_in_place() {
        let root = scratch("adopt");
        let former = former_folder(&root);
        let local = root.join("app.jana-meta.desktop");
        assert_eq!(former_data(&local), former);
        assert!(adopt_data(&former, &local).unwrap());
        assert_eq!(
            fs::read(local.join("core/profiles/p1/learner.db")).unwrap(),
            b"synthetic learner rows"
        );
        assert!(
            !local.join("shell-pids.json").exists(),
            "the other app's processes"
        );
        assert!(!local.join(STAGING).exists() && keys_pending(&local));
        assert!(
            same_tree(&former.join("core"), &local.join("core")).unwrap(),
            "the former data stays whole"
        );
        assert_eq!(fs::read(former.join("shell-pids.json")).unwrap(), b"[123]");
        // A later start keeps its own data, whatever the former folder holds by then.
        fs::write(local.join("core/profiles/p1/learner.db"), b"newer rows").unwrap();
        fs::write(former.join("core/profiles/p1/learner.db"), b"jana's rows").unwrap();
        assert!(!adopt_data(&former, &local).unwrap());
        assert_eq!(
            fs::read(local.join("core/profiles/p1/learner.db")).unwrap(),
            b"newer rows"
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn identity_interrupted_copy_is_made_again() {
        let root = scratch("interrupted");
        let former = former_folder(&root);
        let local = root.join("app.jana-meta.desktop");
        fs::create_dir_all(local.join(STAGING).join("profiles")).unwrap();
        fs::write(local.join(STAGING).join("profiles/half"), b"half").unwrap();
        assert!(adopt_data(&former, &local).unwrap());
        assert!(!local.join("core/profiles/half").exists() && !local.join(STAGING).exists());
        assert!(same_tree(&former.join("core"), &local.join("core")).unwrap());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn identity_nothing_to_adopt() {
        let root = scratch("fresh");
        let local = root.join("app.jana-meta.desktop");
        assert!(!adopt_data(&root.join(FORMER_IDENTIFIER), &local).unwrap());
        assert!(!local.exists(), "a fresh install creates nothing here");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn identity_keys_follow_the_adopted_data_once() {
        let root = scratch("keys");
        let former_dir = former_folder(&root);
        let local = root.join("app.jana-meta.desktop");
        let former = KeyStore::memory();
        assert!(former.put("jana.device-db", &Redacted::new("ZGJfa2V5")));
        assert!(former.put(
            "jana.service-credential.id",
            &Redacted::new("ZGNyX2V4YW1wbGU")
        ));
        let store = KeyStore::memory();
        // Without adopted data nothing is copied: a fresh install starts with its own keys.
        assert_eq!(adopt_keys(&local, &store, Some(&former)).unwrap(), 0);
        assert!(store.entries().is_empty());
        assert!(adopt_data(&former_dir, &local).unwrap());
        assert_eq!(adopt_keys(&local, &store, Some(&former)).unwrap(), 2);
        let held: Vec<(String, String)> = store
            .entries()
            .into_iter()
            .map(|e| (e.r#ref, e.value.reveal().to_string()))
            .collect();
        assert_eq!(
            held,
            [
                ("jana.device-db".to_string(), "ZGJfa2V5".to_string()),
                (
                    "jana.service-credential.id".to_string(),
                    "ZGNyX2V4YW1wbGU".to_string()
                )
            ]
        );
        assert_eq!(former.entries().len(), 2, "the former store keeps its keys");
        assert!(!keys_pending(&local));
        // A store the core has emptied since stays empty.
        assert!(store.delete("jana.device-db") && store.delete("jana.service-credential.id"));
        assert_eq!(adopt_keys(&local, &store, Some(&former)).unwrap(), 0);
        assert!(store.entries().is_empty());
        fs::remove_dir_all(root).unwrap();
    }
}
