//! Check-in notifications (SPEC §19.5.5, JM-D24): the shell shows one when the webview asks with a check-in's id and
//! kind (`notify_checkin`), and nothing else crosses. The body is the kind's fixed template, never the check-in's own
//! words, so no learner text reaches the notification centre. Each notification is tagged with a number derived from
//! the commitment id; a click on one the shell showed is kept until the webview takes it (`take_checkin_click`) and
//! opens Home, and a lock or profile switch withdraws every tag shown (`cancel_checkins`).
//!
//! The notification plugin is driven from here only: the webview is granted the app's own commands, never a plugin
//! permission (SEC-11).

use std::collections::BTreeMap;
use std::sync::{Mutex, MutexGuard, PoisonError};

/// The kinds of check-in, in the contract's order (`Commitment.kind`).
pub const KINDS: [&str; 5] = [
    "event_checkin",
    "deadline_check",
    "open_loop",
    "due_reviews",
    "pack_ready",
];

/// The notification body of a kind: plain, short and the same for every check-in of the kind. The catalogue holds the
/// same words under `home.checkin.notify.<kind>` (checked below), so the copy is reviewed with the app's.
pub fn body(kind: &str) -> Option<&'static str> {
    match kind {
        "event_checkin" => Some("Your tutor would like to hear how it went."),
        "deadline_check" => Some("Your tutor has a question about something due today."),
        "open_loop" => Some("Your tutor has a question about something you left open."),
        "due_reviews" => Some("You have review cards due today."),
        "pack_ready" => Some("A research pack you asked for is ready."),
        _ => None,
    }
}

/// `^cmt_[0-9A-HJKMNP-TV-Z]{26}$`, the contract's commitment id.
pub fn valid_id(id: &str) -> bool {
    id.len() == 30
        && id.starts_with("cmt_")
        && id[4..]
            .bytes()
            .all(|b| b.is_ascii_digit() || (b.is_ascii_uppercase() && !b"ILOU".contains(&b)))
}

/// The notification's tag: a stable, positive number from the commitment id (FNV-1a), since the OS identifies a
/// notification by an integer.
pub fn tag(id: &str) -> i32 {
    let mut hash: u32 = 0x811c_9dc5;
    for byte in id.bytes() {
        hash ^= u32::from(byte);
        hash = hash.wrapping_mul(0x0100_0193);
    }
    i32::try_from(hash & 0x7fff_ffff).unwrap_or(0)
}

#[derive(Default)]
struct State {
    shown: BTreeMap<i32, String>,
    clicked: Option<String>,
}

/// The check-in notifications this run showed, by tag, and the last one clicked.
#[derive(Default)]
pub struct Shown(Mutex<State>);

impl Shown {
    fn state(&self) -> MutexGuard<'_, State> {
        self.0.lock().unwrap_or_else(PoisonError::into_inner)
    }

    /// Remember a notification about to be shown; returns its tag.
    pub fn record(&self, commitment_id: &str) -> i32 {
        let tag = tag(commitment_id);
        self.state().shown.insert(tag, commitment_id.to_string());
        tag
    }

    /// A click on a notification: true (and kept for the webview) only for one this run showed and has not withdrawn.
    pub fn click(&self, tag: i32) -> bool {
        let mut state = self.state();
        let Some(id) = state.shown.get(&tag).cloned() else {
            return false;
        };
        state.clicked = Some(id);
        true
    }

    /// The commitment whose notification was clicked since the last call, once.
    pub fn take_click(&self) -> Option<String> {
        self.state().clicked.take()
    }

    /// Forget every notification shown and any click not yet taken; returns their tags, to withdraw them.
    pub fn clear(&self) -> Vec<i32> {
        let mut state = self.state();
        state.clicked = None;
        std::mem::take(&mut state.shown).into_keys().collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const ID: &str = "cmt_01HZY0000000000000000000AB";

    #[test]
    fn every_kind_has_a_fixed_body_and_the_catalogue_holds_the_same_words() {
        let catalogue: serde_json::Value =
            serde_json::from_str(include_str!("../../../../packages/i18n/locales/en.json"))
                .unwrap();
        for kind in KINDS {
            let text = body(kind).unwrap();
            assert!(text.len() <= 80 && !text.contains('{'), "{kind}");
            assert_eq!(
                catalogue[format!("home.checkin.notify.{kind}")].as_str(),
                Some(text),
                "{kind}"
            );
        }
        assert_eq!(body("Saturday's mock paper"), None);
        assert_eq!(body(""), None);
    }

    #[test]
    fn only_a_contract_commitment_id_is_taken() {
        assert!(valid_id(ID));
        for bad in [
            "",
            "cmt_",
            "cmt_01HZY0000000000000000000A",
            "cmt_01HZY0000000000000000000AI",
            "cmt_01hzy0000000000000000000ab",
            "mem_01HZY0000000000000000000AB",
            "cmt_01HZY0000000000000000000A\u{e9}",
        ] {
            assert!(!valid_id(bad), "{bad}");
        }
    }

    #[test]
    fn tags_are_stable_and_positive() {
        assert_eq!(tag(ID), tag(ID));
        assert!(tag(ID) >= 0);
        assert_ne!(tag(ID), tag("cmt_01HZY0000000000000000000AC"));
    }

    #[test]
    fn a_click_counts_only_for_a_shown_notification_and_is_taken_once() {
        let shown = Shown::default();
        assert!(!shown.click(tag(ID)));
        let tag = shown.record(ID);
        assert!(shown.click(tag));
        assert_eq!(shown.take_click().as_deref(), Some(ID));
        assert_eq!(shown.take_click(), None);
        // A lock or profile switch withdraws what was shown: a later click opens nothing.
        assert!(shown.click(tag));
        assert_eq!(shown.clear(), vec![tag]);
        assert_eq!(shown.take_click(), None);
        assert!(!shown.click(tag));
        assert!(shown.clear().is_empty());
    }
}
