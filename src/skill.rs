//! Skill discovery: the `skills/` tree is embedded at compile time, and any
//! directory named by `CUSTOM_SKILLS_PATH` is read at startup so a skill can be
//! edited and reloaded by restarting the client rather than rebuilding.

use std::{
    collections::BTreeMap,
    path::{Component, Path, PathBuf},
};

use anyhow::{bail, Context, Result};
use include_dir::{include_dir, Dir, File};
use serde::Deserialize;

pub static EMBEDDED: Dir<'_> = include_dir!("$CARGO_MANIFEST_DIR/skills");

/// Environment variable holding extra skill roots, separated like `PATH`.
pub const SKILL_PATH_VAR: &str = "CUSTOM_SKILLS_PATH";

#[derive(Debug, Deserialize)]
struct Frontmatter {
    name: String,
    description: String,
}

/// Where a skill's files live, and therefore how a resource beside its
/// `SKILL.md` is read back.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Origin {
    /// Compiled in; the path is the skill directory relative to `skills/`.
    Embedded(PathBuf),
    /// Read at startup; the path is the skill directory on disk.
    Disk(PathBuf),
}

#[derive(Clone, Debug)]
pub struct Skill {
    pub name: String,
    pub description: String,
    pub body: String,
    pub origin: Origin,
}

impl Skill {
    /// Reads a file that sits beside this skill's `SKILL.md`.
    ///
    /// The path is relative to the skill directory and may not climb out of
    /// it: a skill serves its own files and nothing else.
    pub fn read_resource(&self, rel: &str) -> Result<String> {
        let rel = sanitize_relative(rel)?;
        match &self.origin {
            Origin::Embedded(root) => EMBEDDED
                .get_file(root.join(&rel))
                .with_context(|| format!("skill {:?} declares no file {rel:?}", self.name))?
                .contents_utf8()
                .map(str::to_owned)
                .with_context(|| format!("{rel:?} in skill {:?} is not UTF-8", self.name)),
            Origin::Disk(root) => {
                let base = root
                    .canonicalize()
                    .with_context(|| format!("skill directory vanished: {}", root.display()))?;
                let full = base
                    .join(&rel)
                    .canonicalize()
                    .with_context(|| format!("skill {:?} has no file {rel:?}", self.name))?;
                if !full.starts_with(&base) {
                    bail!("{rel:?} resolves outside skill {:?}", self.name);
                }
                std::fs::read_to_string(&full)
                    .with_context(|| format!("failed to read {}", full.display()))
            }
        }
    }

    /// Every file beside this skill's `SKILL.md`, as skill-relative paths.
    pub fn resources(&self) -> Vec<String> {
        let mut out = match &self.origin {
            Origin::Embedded(root) => {
                let mut acc = Vec::new();
                if let Some(dir) = EMBEDDED.get_dir(root) {
                    collect_embedded_files(dir, root, &mut acc);
                }
                acc
            }
            Origin::Disk(root) => {
                let mut acc = Vec::new();
                collect_disk_files(root, root, &mut acc);
                acc
            }
        };
        out.retain(|p| !p.eq_ignore_ascii_case("SKILL.md"));
        out.sort();
        out
    }
}

/// Loads embedded skills, then lets each extra root override them by name.
///
/// Later roots win, so `CUSTOM_SKILLS_PATH=/a:/b` with the same skill in both
/// serves `/b`'s copy — the same precedence a shell `PATH` reversed would give,
/// chosen so the last thing you point at is the thing you are editing.
pub fn load_all(extra_roots: &[PathBuf]) -> Result<Vec<Skill>> {
    let mut by_name: BTreeMap<String, Skill> = BTreeMap::new();
    for skill in load_embedded()? {
        insert_unique(&mut by_name, skill)?;
    }
    for root in extra_roots {
        let mut from_root: BTreeMap<String, Skill> = BTreeMap::new();
        for skill in load_from_disk(root)? {
            insert_unique(&mut from_root, skill)?;
        }
        by_name.extend(from_root);
    }
    Ok(by_name.into_values().collect())
}

fn insert_unique(map: &mut BTreeMap<String, Skill>, skill: Skill) -> Result<()> {
    if let Some(existing) = map.get(&skill.name) {
        bail!(
            "two skills claim the name {:?}: {:?} and {:?}",
            skill.name,
            existing.origin,
            skill.origin
        );
    }
    map.insert(skill.name.clone(), skill);
    Ok(())
}

fn load_embedded() -> Result<Vec<Skill>> {
    let mut out = Vec::new();
    collect_embedded_skills(&EMBEDDED, &mut out)?;
    Ok(out)
}

/// Walks the embedded tree. A directory holding a `SKILL.md` is a skill; one
/// holding only directories is a grouping level. A directory that is neither is
/// an error, because silently skipping it is how a misfiled skill disappears
/// from the tool list while the server still starts.
fn collect_embedded_skills(root: &'static Dir<'static>, out: &mut Vec<Skill>) -> Result<()> {
    for dir in root.dirs() {
        if let Some(file) = find_skill_md(dir) {
            out.push(parse_skill(
                file.contents_utf8()
                    .with_context(|| format!("SKILL.md is not UTF-8: {}", file.path().display()))?,
                Origin::Embedded(dir.path().to_path_buf()),
                &file.path().display().to_string(),
            )?);
            continue;
        }
        let before = out.len();
        collect_embedded_skills(dir, out)?;
        if out.len() == before {
            bail!(
                "{} holds no SKILL.md and no skill directories: a skill placed here \
                 would be served by nothing",
                dir.path().display()
            );
        }
    }
    Ok(())
}

fn load_from_disk(root: &Path) -> Result<Vec<Skill>> {
    if !root.is_dir() {
        bail!("{} in {SKILL_PATH_VAR} is not a directory", root.display());
    }
    let mut out = Vec::new();
    collect_disk_skills(root, &mut out)?;
    Ok(out)
}

fn collect_disk_skills(root: &Path, out: &mut Vec<Skill>) -> Result<()> {
    let mut entries: Vec<PathBuf> = std::fs::read_dir(root)
        .with_context(|| format!("failed to read {}", root.display()))?
        .map(|e| e.map(|e| e.path()))
        .collect::<std::io::Result<_>>()
        .with_context(|| format!("failed to read {}", root.display()))?;
    entries.sort();
    for dir in entries.into_iter().filter(|p| p.is_dir()) {
        let manifest = dir.join("SKILL.md");
        if manifest.is_file() {
            let raw = std::fs::read_to_string(&manifest)
                .with_context(|| format!("failed to read {}", manifest.display()))?;
            out.push(parse_skill(
                &raw,
                Origin::Disk(dir.clone()),
                &manifest.display().to_string(),
            )?);
            continue;
        }
        collect_disk_skills(&dir, out)?;
    }
    Ok(())
}

fn find_skill_md<'a>(dir: &'a Dir<'a>) -> Option<&'a File<'a>> {
    dir.files().find(|f| {
        f.path()
            .file_name()
            .and_then(|s| s.to_str())
            .is_some_and(|s| s.eq_ignore_ascii_case("SKILL.md"))
    })
}

fn parse_skill(raw: &str, origin: Origin, whence: &str) -> Result<Skill> {
    let (fm, body) = split_frontmatter(raw)
        .with_context(|| format!("SKILL.md missing YAML frontmatter: {whence}"))?;
    let meta: Frontmatter = serde_yaml::from_str(fm)
        .with_context(|| format!("failed to parse frontmatter in {whence}"))?;
    validate_name(&meta.name).with_context(|| format!("invalid skill name in {whence}"))?;
    if meta.description.trim().is_empty() {
        bail!("skill {:?} has an empty description in {whence}", meta.name);
    }
    Ok(Skill {
        name: meta.name,
        description: meta.description.trim().to_owned(),
        body: body.trim_start_matches('\n').to_owned(),
        origin,
    })
}

/// Splits `---\n...\n---\n` frontmatter from the body.
pub fn split_frontmatter(src: &str) -> Option<(&str, &str)> {
    let rest = src.strip_prefix("---")?;
    let rest = rest.strip_prefix('\n').unwrap_or(rest);
    let end = rest.find("\n---")?;
    let fm = &rest[..end];
    let after = &rest[end + 4..];
    let body = after.strip_prefix('\n').unwrap_or(after);
    Some((fm, body))
}

/// A skill name becomes an MCP tool name, so it is held to the character set
/// every client accepts.
fn validate_name(name: &str) -> Result<()> {
    if name.is_empty() || name.len() > 64 {
        bail!("skill name must be 1-64 characters, got {}", name.len());
    }
    if !name
        .chars()
        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-' || c == '_')
    {
        bail!("skill name {name:?} must use only [a-z0-9_-]");
    }
    Ok(())
}

fn sanitize_relative(rel: &str) -> Result<PathBuf> {
    let path = Path::new(rel);
    if rel.is_empty() {
        bail!("path is empty");
    }
    for component in path.components() {
        match component {
            Component::Normal(_) => {}
            _ => bail!("path {rel:?} must be relative and may not contain `..`"),
        }
    }
    Ok(path.to_path_buf())
}

fn collect_embedded_files(dir: &Dir<'_>, base: &Path, out: &mut Vec<String>) {
    for file in dir.files() {
        if let Ok(rel) = file.path().strip_prefix(base) {
            out.push(rel.display().to_string());
        }
    }
    for sub in dir.dirs() {
        collect_embedded_files(sub, base, out);
    }
}

fn collect_disk_files(dir: &Path, base: &Path, out: &mut Vec<String>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_disk_files(&path, base, out);
        } else if let Ok(rel) = path.strip_prefix(base) {
            out.push(rel.display().to_string());
        }
    }
}

/// Parses `CUSTOM_SKILLS_PATH` into roots, dropping empty segments.
pub fn roots_from_env() -> Vec<PathBuf> {
    match std::env::var_os(SKILL_PATH_VAR) {
        Some(value) => std::env::split_paths(&value)
            .filter(|p| !p.as_os_str().is_empty())
            .collect(),
        None => Vec::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn write_skill(root: &Path, name: &str, description: &str, body: &str) -> PathBuf {
        let dir = root.join(name);
        fs::create_dir_all(&dir).unwrap();
        fs::write(
            dir.join("SKILL.md"),
            format!("---\nname: {name}\ndescription: {description}\n---\n\n{body}\n"),
        )
        .unwrap();
        dir
    }

    #[test]
    fn embedded_skills_load() {
        let skills = load_all(&[]).expect("embedded skills load");
        assert!(skills.iter().any(|s| s.name == "skill-authoring"));
        assert!(skills
            .iter()
            .all(|s| matches!(s.origin, Origin::Embedded(_))));
    }

    #[test]
    fn a_disk_root_adds_skills() {
        let tmp = TempDir::new().unwrap();
        write_skill(tmp.path(), "from-disk", "A disk skill.", "Do the thing.");
        let skills = load_all(&[tmp.path().to_path_buf()]).unwrap();
        let found = skills.iter().find(|s| s.name == "from-disk").unwrap();
        assert_eq!(found.body, "Do the thing.\n");
        assert!(matches!(found.origin, Origin::Disk(_)));
    }

    #[test]
    fn a_disk_root_overrides_an_embedded_skill_of_the_same_name() {
        let tmp = TempDir::new().unwrap();
        write_skill(tmp.path(), "skill-authoring", "Overridden.", "Local body.");
        let skills = load_all(&[tmp.path().to_path_buf()]).unwrap();
        let found = skills.iter().find(|s| s.name == "skill-authoring").unwrap();
        assert_eq!(found.description, "Overridden.");
        assert_eq!(
            skills
                .iter()
                .filter(|s| s.name == "skill-authoring")
                .count(),
            1
        );
    }

    #[test]
    fn the_last_root_wins() {
        let first = TempDir::new().unwrap();
        let second = TempDir::new().unwrap();
        write_skill(first.path(), "shared", "First.", "one");
        write_skill(second.path(), "shared", "Second.", "two");
        let skills = load_all(&[first.path().to_path_buf(), second.path().to_path_buf()]).unwrap();
        let found = skills.iter().find(|s| s.name == "shared").unwrap();
        assert_eq!(found.description, "Second.");
    }

    #[test]
    fn two_skills_with_one_name_in_the_same_root_is_an_error() {
        let tmp = TempDir::new().unwrap();
        write_skill(tmp.path(), "dup-a", "A.", "a");
        // Same frontmatter name, different directory.
        let dir = tmp.path().join("dup-b");
        fs::create_dir_all(&dir).unwrap();
        fs::write(
            dir.join("SKILL.md"),
            "---\nname: dup-a\ndescription: B.\n---\nb\n",
        )
        .unwrap();
        let err = load_all(&[tmp.path().to_path_buf()]).unwrap_err();
        assert!(err.to_string().contains("dup-a"), "{err:#}");
    }

    #[test]
    fn nested_directories_group_skills() {
        let tmp = TempDir::new().unwrap();
        write_skill(&tmp.path().join("cluster"), "nested", "Nested.", "body");
        let skills = load_all(&[tmp.path().to_path_buf()]).unwrap();
        assert!(skills.iter().any(|s| s.name == "nested"));
    }

    #[test]
    fn a_bad_name_is_rejected_at_load() {
        let tmp = TempDir::new().unwrap();
        let dir = tmp.path().join("bad");
        fs::create_dir_all(&dir).unwrap();
        fs::write(
            dir.join("SKILL.md"),
            "---\nname: Not Valid\ndescription: x\n---\nbody\n",
        )
        .unwrap();
        let err = load_all(&[tmp.path().to_path_buf()]).unwrap_err();
        assert!(format!("{err:#}").contains("[a-z0-9_-]"), "{err:#}");
    }

    #[test]
    fn missing_frontmatter_is_rejected_at_load() {
        let tmp = TempDir::new().unwrap();
        let dir = tmp.path().join("bare");
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join("SKILL.md"), "just a body\n").unwrap();
        let err = load_all(&[tmp.path().to_path_buf()]).unwrap_err();
        assert!(format!("{err:#}").contains("frontmatter"), "{err:#}");
    }

    #[test]
    fn an_empty_description_is_rejected_at_load() {
        let tmp = TempDir::new().unwrap();
        let dir = tmp.path().join("blank");
        fs::create_dir_all(&dir).unwrap();
        fs::write(
            dir.join("SKILL.md"),
            "---\nname: blank\ndescription: \"  \"\n---\nbody\n",
        )
        .unwrap();
        let err = load_all(&[tmp.path().to_path_buf()]).unwrap_err();
        assert!(format!("{err:#}").contains("description"), "{err:#}");
    }

    #[test]
    fn resources_exclude_the_manifest_and_read_back() {
        let tmp = TempDir::new().unwrap();
        let dir = write_skill(tmp.path(), "with-refs", "Has refs.", "body");
        fs::create_dir_all(dir.join("references")).unwrap();
        fs::write(dir.join("references/table.md"), "contents").unwrap();
        let skills = load_all(&[tmp.path().to_path_buf()]).unwrap();
        let skill = skills.iter().find(|s| s.name == "with-refs").unwrap();
        assert_eq!(skill.resources(), vec!["references/table.md".to_string()]);
        assert_eq!(
            skill.read_resource("references/table.md").unwrap(),
            "contents"
        );
    }

    #[test]
    fn a_resource_path_cannot_climb_out_of_its_skill() {
        let tmp = TempDir::new().unwrap();
        write_skill(tmp.path(), "boxed", "Boxed in.", "body");
        fs::write(tmp.path().join("secret.txt"), "nope").unwrap();
        let skills = load_all(&[tmp.path().to_path_buf()]).unwrap();
        let skill = skills.iter().find(|s| s.name == "boxed").unwrap();
        for attempt in ["../secret.txt", "/etc/hosts", ""] {
            assert!(skill.read_resource(attempt).is_err(), "allowed {attempt:?}");
        }
    }

    #[test]
    fn a_root_that_is_not_a_directory_is_an_error() {
        let tmp = TempDir::new().unwrap();
        let file = tmp.path().join("not-a-dir");
        fs::write(&file, "x").unwrap();
        assert!(load_all(&[file]).is_err());
    }

    #[test]
    fn embedded_resources_are_reachable() {
        let skills = load_all(&[]).unwrap();
        let skill = skills.iter().find(|s| s.name == "skill-authoring").unwrap();
        assert!(skill
            .resources()
            .contains(&"references/frontmatter.md".to_string()));
        assert!(skill
            .read_resource("references/frontmatter.md")
            .unwrap()
            .contains("Frontmatter contract"));
    }
}
