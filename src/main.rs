//! `check-skills` — refuses a skills tree that Claude Code would load wrongly
//! without saying so.
//!
//! ```sh
//! cargo run --quiet -- [skills-dir]     # defaults to ./skills
//! ```
//!
//! Exits 0 and prints the skill count and the total description size when every
//! skill passes; otherwise prints the first problem and exits 1. The rules are
//! on [`skill::load`]. The plugin root, whose `plugin.json` may list extra skill
//! directories, is taken to be the parent of the skills directory.

use std::{path::PathBuf, process::ExitCode};

mod skill;

fn main() -> ExitCode {
    let root = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("skills"));
    let plugin_root = match root.parent() {
        Some(p) if !p.as_os_str().is_empty() => p.to_path_buf(),
        _ => PathBuf::from("."),
    };
    let checked =
        skill::listed_skill_dirs(&plugin_root).and_then(|listed| skill::load(&root, &listed));
    match checked {
        Ok(skills) => {
            let chars: usize = skills.iter().map(|s| s.description.chars().count()).sum();
            println!(
                "ok: {} skills, {chars} description characters in the listing",
                skills.len()
            );
            ExitCode::SUCCESS
        }
        Err(err) => {
            eprintln!("error: {err:#}");
            ExitCode::FAILURE
        }
    }
}
