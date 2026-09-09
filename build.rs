//! `include_dir!` expands to one `include_bytes!` per file, so Cargo already
//! rebuilds when a tracked skill file changes. It does not notice a *new* file,
//! which would silently leave a freshly added skill out of the binary. Watching
//! the tree closes that gap.
fn main() {
    println!("cargo:rerun-if-changed=skills");
    println!("cargo:rerun-if-env-changed=CUSTOM_SKILLS_PATH");
}
