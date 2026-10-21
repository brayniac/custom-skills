//! Loading and checking the `skills/` tree that the plugin serves.
//!
//! Claude Code loads a `SKILL.md` whose frontmatter does not parse with empty
//! metadata instead of refusing it, and `claude plugin validate` does not look
//! inside skills, so a misfiled or malformed skill drops out of the listing with
//! no error anywhere. [`load`] refuses every such case, so the check that runs
//! in CI fails where Claude Code would stay quiet.
//!
//! Claude Code loads a plugin's skills from `skills/<name>/SKILL.md` and, for
//! each path `plugin.json` lists under `skills`, from `<path>/SKILL.md` or
//! `<path>/<name>/SKILL.md`. A skill at any other depth is not loaded. Observed
//! on Claude Code 2.1.306.

use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
};

use anyhow::{bail, Context, Result};
use serde::Deserialize;

/// Claude Code's cap on one skill's `description` in the skill listing.
pub const MAX_DESCRIPTION_CHARS: usize = 1536;

/// The variable Claude Code substitutes with a skill's own directory when it
/// loads the skill's body.
const SKILL_DIR_VAR: &str = "${CLAUDE_SKILL_DIR}/";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Frontmatter {
    name: String,
    description: String,
}

#[derive(Clone, Debug)]
pub struct Skill {
    pub name: String,
    pub description: String,
    pub body: String,
    pub dir: PathBuf,
}

/// Loads every skill under `root` and checks the whole tree.
///
/// A directory holding a `SKILL.md` is a skill; one holding only directories is
/// a grouping level. `listed` holds the paths `plugin.json` names, from
/// [`listed_skill_dirs`]. Fails on a skill whose directory is not in `listed`
/// and whose parent is neither `root` nor in `listed`, on a listed path outside
/// `root`, on a directory that is neither a skill nor a group, on frontmatter
/// that is not valid YAML with exactly `name` and `description`, on a `name` that
/// differs from its directory or uses characters outside `[a-z0-9_-]`, on an
/// empty or over-long description, on two skills with one name, and on a
/// `${CLAUDE_SKILL_DIR}` path that names no file inside `root`.
pub fn load(root: &Path, listed: &[PathBuf]) -> Result<Vec<Skill>> {
    if !root.is_dir() {
        bail!("{} is not a directory", root.display());
    }
    let mut skills = Vec::new();
    collect(root, &mut skills)?;
    if skills.is_empty() {
        bail!("{} holds no skills", root.display());
    }
    check_listed(root, listed, &skills)?;
    let mut by_name: BTreeMap<String, Skill> = BTreeMap::new();
    for skill in skills {
        if let Some(existing) = by_name.get(&skill.name) {
            bail!(
                "two skills claim the name {:?}: {} and {}",
                skill.name,
                existing.dir.display(),
                skill.dir.display()
            );
        }
        by_name.insert(skill.name.clone(), skill);
    }
    let root = root
        .canonicalize()
        .with_context(|| format!("failed to resolve {}", root.display()))?;
    for skill in by_name.values() {
        check_skill_dir_paths(&root, skill)?;
    }
    Ok(by_name.into_values().collect())
}

/// The skill directories a plugin's `plugin.json` adds through its `skills`
/// field (a path or a list of paths, relative to the plugin root), resolved.
/// A plugin with no manifest, or a manifest with no `skills`, adds none.
pub fn listed_skill_dirs(plugin_root: &Path) -> Result<Vec<PathBuf>> {
    let manifest = plugin_root.join(".claude-plugin/plugin.json");
    if !manifest.is_file() {
        return Ok(Vec::new());
    }
    let raw = std::fs::read_to_string(&manifest)
        .with_context(|| format!("failed to read {}", manifest.display()))?;
    let json: serde_json::Value = serde_json::from_str(&raw)
        .with_context(|| format!("{} is not valid JSON", manifest.display()))?;
    let paths: Vec<&str> = match json.get("skills") {
        None => Vec::new(),
        Some(serde_json::Value::String(path)) => vec![path],
        Some(serde_json::Value::Array(paths)) => paths
            .iter()
            .map(|p| p.as_str().context("`skills` entries must be strings"))
            .collect::<Result<_>>()?,
        Some(_) => bail!(
            "`skills` in {} must be a string or a list",
            manifest.display()
        ),
    };
    paths
        .into_iter()
        .map(|path| {
            plugin_root.join(path).canonicalize().with_context(|| {
                format!(
                    "`skills` in {} lists {path}, which does not exist",
                    manifest.display()
                )
            })
        })
        .collect()
}

/// The plugin root for a skills directory: the parent of its resolved path,
/// so `.` run from inside `skills/` and `skills/group/..` both find the
/// manifest beside `skills/`. A path that does not resolve is used as given,
/// and [`load`] reports it.
pub fn plugin_root(skills: &Path) -> PathBuf {
    let resolved = skills
        .canonicalize()
        .unwrap_or_else(|_| skills.to_path_buf());
    match resolved.parent() {
        Some(p) if !p.as_os_str().is_empty() => p.to_path_buf(),
        _ => PathBuf::from("."),
    }
}

fn check_listed(root: &Path, listed: &[PathBuf], skills: &[Skill]) -> Result<()> {
    let root = root
        .canonicalize()
        .with_context(|| format!("failed to resolve {}", root.display()))?;
    // `collect` walks only `root`, so a skill under a listed path elsewhere
    // would load in Claude Code without being checked.
    if let Some(outside) = listed.iter().find(|p| !p.starts_with(&root)) {
        bail!(
            "plugin.json lists {} under `skills`, which is outside {}; check-skills \
             checks only skills under {}",
            outside.display(),
            root.display(),
            root.display()
        );
    }
    for skill in skills {
        let dir = skill
            .dir
            .canonicalize()
            .with_context(|| format!("failed to resolve {}", skill.dir.display()))?;
        if listed.contains(&dir) {
            continue;
        }
        let parent = dir.parent().unwrap_or(&dir).to_path_buf();
        if parent != root && !listed.contains(&parent) {
            bail!(
                "skill {:?} is in {}, which plugin.json does not list under `skills`; \
                 Claude Code loads only {}/<name>, a listed directory, and <listed>/<name>",
                skill.name,
                parent.display(),
                root.display()
            );
        }
    }
    Ok(())
}

fn collect(dir: &Path, out: &mut Vec<Skill>) -> Result<()> {
    let mut entries: Vec<PathBuf> = std::fs::read_dir(dir)
        .with_context(|| format!("failed to read {}", dir.display()))?
        .map(|e| e.map(|e| e.path()))
        .collect::<std::io::Result<_>>()
        .with_context(|| format!("failed to read {}", dir.display()))?;
    entries.sort();
    for sub in entries.into_iter().filter(|p| p.is_dir()) {
        let manifest = sub.join("SKILL.md");
        if manifest.is_file() {
            let raw = std::fs::read_to_string(&manifest)
                .with_context(|| format!("failed to read {}", manifest.display()))?;
            out.push(
                parse_skill(&raw, &sub).with_context(|| format!("in {}", manifest.display()))?,
            );
            continue;
        }
        let before = out.len();
        collect(&sub, out)?;
        if out.len() == before {
            bail!(
                "{} holds no SKILL.md and no skill directories: a skill placed here \
                 would be loaded by nothing",
                sub.display()
            );
        }
    }
    Ok(())
}

fn parse_skill(raw: &str, dir: &Path) -> Result<Skill> {
    let (fm, body) = split_frontmatter(raw).context("missing YAML frontmatter")?;
    let meta: Frontmatter = serde_yaml::from_str(fm)
        .context("frontmatter must be valid YAML holding exactly `name` and `description`")?;
    validate_name(&meta.name)?;
    let dir_name = dir.file_name().and_then(|n| n.to_str()).unwrap_or_default();
    if meta.name != dir_name {
        bail!(
            "name {:?} differs from its directory {dir_name:?}; Claude Code falls back \
             to the directory name, so the two must agree",
            meta.name
        );
    }
    let description = meta.description.trim();
    if description.is_empty() {
        bail!("skill {:?} has an empty description", meta.name);
    }
    let chars = description.chars().count();
    if chars > MAX_DESCRIPTION_CHARS {
        bail!(
            "skill {:?} has a {chars}-character description; Claude Code truncates \
             past {MAX_DESCRIPTION_CHARS}",
            meta.name
        );
    }
    Ok(Skill {
        name: meta.name,
        description: description.to_owned(),
        body: body.trim_start_matches('\n').to_owned(),
        dir: dir.to_path_buf(),
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

/// Every path a body names through `${CLAUDE_SKILL_DIR}`.
pub fn skill_dir_paths(body: &str) -> Vec<&str> {
    body.match_indices(SKILL_DIR_VAR)
        .map(|(at, _)| {
            let rest = &body[at + SKILL_DIR_VAR.len()..];
            let end = rest
                .find(|c: char| c.is_whitespace() || "`'\");,".contains(c))
                .unwrap_or(rest.len());
            rest[..end].trim_end_matches(['.', ':'])
        })
        .collect()
}

fn check_skill_dir_paths(root: &Path, skill: &Skill) -> Result<()> {
    // `<file>` and `<other>` in instructions about paths are placeholders.
    for rel in skill_dir_paths(&skill.body)
        .into_iter()
        .filter(|rel| !rel.contains('<'))
    {
        let full = skill.dir.join(rel).canonicalize().with_context(|| {
            format!(
                "skill {:?} names ${{CLAUDE_SKILL_DIR}}/{rel}, which does not exist",
                skill.name
            )
        })?;
        if !full.starts_with(root) {
            bail!(
                "skill {:?} names ${{CLAUDE_SKILL_DIR}}/{rel}, which is outside {}",
                skill.name,
                root.display()
            );
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn write_skill(root: &Path, dir: &str, frontmatter: &str, body: &str) -> PathBuf {
        let path = root.join(dir);
        fs::create_dir_all(&path).unwrap();
        fs::write(
            path.join("SKILL.md"),
            format!("---\n{frontmatter}\n---\n\n{body}\n"),
        )
        .unwrap();
        path
    }

    fn ok_skill(root: &Path, name: &str, body: &str) -> PathBuf {
        write_skill(
            root,
            name,
            &format!("name: {name}\ndescription: Does a thing."),
            body,
        )
    }

    fn load_err(root: &Path) -> String {
        format!("{:#}", load(root, &[]).unwrap_err())
    }

    #[test]
    fn the_repository_skills_load() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("skills");
        let listed = listed_skill_dirs(&plugin_root(&root)).unwrap();
        let skills = load(&root, &listed).expect("skills/ passes the check");
        assert!(skills.iter().any(|s| s.name == "skill-authoring"));
    }

    #[test]
    fn a_valid_tree_loads_with_bodies() {
        let tmp = TempDir::new().unwrap();
        ok_skill(tmp.path(), "one", "Do the thing.");
        let skills = load(tmp.path(), &[]).unwrap();
        assert_eq!(skills.len(), 1);
        assert_eq!(skills[0].body, "Do the thing.\n");
    }

    #[test]
    fn a_listed_group_directory_loads_its_skills() {
        let tmp = TempDir::new().unwrap();
        ok_skill(&tmp.path().join("cluster"), "nested", "body");
        let listed = vec![tmp.path().join("cluster").canonicalize().unwrap()];
        let skills = load(tmp.path(), &listed).unwrap();
        assert!(skills.iter().any(|s| s.name == "nested"));
    }

    #[test]
    fn a_listed_skill_directory_loads() {
        let tmp = TempDir::new().unwrap();
        ok_skill(&tmp.path().join("cluster"), "direct", "body");
        let listed = vec![tmp.path().join("cluster/direct").canonicalize().unwrap()];
        load(tmp.path(), &listed).unwrap();
    }

    #[test]
    fn a_skill_two_levels_under_a_listed_group_is_an_error() {
        let tmp = TempDir::new().unwrap();
        ok_skill(&tmp.path().join("cluster/sub"), "deep", "body");
        let listed = vec![tmp.path().join("cluster").canonicalize().unwrap()];
        let err = format!("{:#}", load(tmp.path(), &listed).unwrap_err());
        assert!(err.contains("does not list under `skills`"));
    }

    #[test]
    fn a_listed_path_outside_the_root_is_an_error() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path().join("skills");
        ok_skill(&root, "flat", "body");
        ok_skill(&tmp.path().join("other"), "elsewhere", "body");
        let listed = vec![tmp.path().join("other").canonicalize().unwrap()];
        let err = format!("{:#}", load(&root, &listed).unwrap_err());
        assert!(err.contains("outside"));
    }

    #[test]
    fn plugin_root_is_the_parent_of_the_resolved_skills_dir() {
        let tmp = TempDir::new().unwrap();
        let plugin = tmp.path().canonicalize().unwrap();
        fs::create_dir_all(plugin.join("skills/group")).unwrap();
        assert_eq!(plugin_root(&plugin.join("skills")), plugin);
        assert_eq!(plugin_root(&plugin.join("skills/")), plugin);
        assert_eq!(plugin_root(&plugin.join("skills/.")), plugin);
        assert_eq!(plugin_root(&plugin.join("skills/group/..")), plugin);
        assert_eq!(plugin_root(Path::new("does-not-exist")), PathBuf::from("."));
    }

    #[test]
    fn a_group_listed_in_the_manifest_passes_from_any_skills_path() {
        let tmp = TempDir::new().unwrap();
        let plugin = tmp.path().canonicalize().unwrap();
        fs::create_dir_all(plugin.join(".claude-plugin")).unwrap();
        fs::write(
            plugin.join(".claude-plugin/plugin.json"),
            r#"{"name":"p","skills":["./skills/group"]}"#,
        )
        .unwrap();
        ok_skill(&plugin.join("skills"), "flat", "body");
        ok_skill(&plugin.join("skills/group"), "nested", "body");
        for skills in [plugin.join("skills"), plugin.join("skills/group/..")] {
            let listed = listed_skill_dirs(&plugin_root(&skills)).unwrap();
            assert_eq!(load(&skills, &listed).unwrap().len(), 2);
        }
    }

    #[test]
    fn a_skill_in_an_unlisted_group_is_an_error() {
        let tmp = TempDir::new().unwrap();
        ok_skill(tmp.path(), "flat", "body");
        ok_skill(&tmp.path().join("cluster"), "nested", "body");
        assert!(load_err(tmp.path()).contains("does not list under `skills`"));
    }

    #[test]
    fn listed_skill_dirs_reads_a_path_or_a_list() {
        let tmp = TempDir::new().unwrap();
        fs::create_dir_all(tmp.path().join(".claude-plugin")).unwrap();
        fs::create_dir_all(tmp.path().join("skills/a")).unwrap();
        fs::create_dir_all(tmp.path().join("skills/b")).unwrap();
        let manifest = tmp.path().join(".claude-plugin/plugin.json");
        assert!(listed_skill_dirs(tmp.path()).unwrap().is_empty());
        fs::write(&manifest, r#"{"name":"p"}"#).unwrap();
        assert!(listed_skill_dirs(tmp.path()).unwrap().is_empty());
        fs::write(&manifest, r#"{"name":"p","skills":"./skills/a"}"#).unwrap();
        assert_eq!(listed_skill_dirs(tmp.path()).unwrap().len(), 1);
        fs::write(
            &manifest,
            r#"{"name":"p","skills":["./skills/a","./skills/b"]}"#,
        )
        .unwrap();
        assert_eq!(listed_skill_dirs(tmp.path()).unwrap().len(), 2);
        fs::write(&manifest, r#"{"name":"p","skills":["./skills/gone"]}"#).unwrap();
        assert!(listed_skill_dirs(tmp.path()).is_err());
    }

    #[test]
    fn two_skills_with_one_name_in_different_groups_is_an_error() {
        let tmp = TempDir::new().unwrap();
        ok_skill(&tmp.path().join("a"), "dup", "a");
        ok_skill(&tmp.path().join("b"), "dup", "b");
        assert!(load_err(tmp.path()).contains("dup"));
    }

    #[test]
    fn frontmatter_that_is_not_yaml_is_an_error() {
        let tmp = TempDir::new().unwrap();
        write_skill(
            tmp.path(),
            "colon",
            "name: colon\ndescription: runs: twice: here",
            "b",
        );
        assert!(load_err(tmp.path()).contains("must be valid YAML"));
    }

    #[test]
    fn an_unknown_frontmatter_key_is_an_error() {
        let tmp = TempDir::new().unwrap();
        write_skill(
            tmp.path(),
            "extra",
            "name: extra\ndescription: x\nwhen-to-use: y",
            "b",
        );
        assert!(load_err(tmp.path()).contains("must be valid YAML"));
    }

    #[test]
    fn missing_frontmatter_is_an_error() {
        let tmp = TempDir::new().unwrap();
        fs::create_dir_all(tmp.path().join("bare")).unwrap();
        fs::write(tmp.path().join("bare/SKILL.md"), "just a body\n").unwrap();
        assert!(load_err(tmp.path()).contains("frontmatter"));
    }

    #[test]
    fn a_bad_name_is_an_error() {
        let tmp = TempDir::new().unwrap();
        write_skill(tmp.path(), "bad", "name: Not Valid\ndescription: x", "b");
        assert!(load_err(tmp.path()).contains("[a-z0-9_-]"));
    }

    #[test]
    fn a_name_that_differs_from_its_directory_is_an_error() {
        let tmp = TempDir::new().unwrap();
        write_skill(tmp.path(), "dir-name", "name: other\ndescription: x", "b");
        assert!(load_err(tmp.path()).contains("differs from its directory"));
    }

    #[test]
    fn an_empty_description_is_an_error() {
        let tmp = TempDir::new().unwrap();
        write_skill(tmp.path(), "blank", "name: blank\ndescription: \"  \"", "b");
        assert!(load_err(tmp.path()).contains("empty description"));
    }

    #[test]
    fn a_description_over_the_cap_is_an_error() {
        let tmp = TempDir::new().unwrap();
        let long = "x".repeat(MAX_DESCRIPTION_CHARS + 1);
        write_skill(
            tmp.path(),
            "long",
            &format!("name: long\ndescription: {long}"),
            "b",
        );
        assert!(load_err(tmp.path()).contains("1537-character"));
    }

    #[test]
    fn a_directory_with_no_skill_is_an_error() {
        let tmp = TempDir::new().unwrap();
        ok_skill(tmp.path(), "real", "b");
        fs::create_dir_all(tmp.path().join("misfiled/empty")).unwrap();
        assert!(load_err(tmp.path()).contains("holds no SKILL.md"));
    }

    #[test]
    fn a_root_that_is_not_a_directory_is_an_error() {
        let tmp = TempDir::new().unwrap();
        let file = tmp.path().join("not-a-dir");
        fs::write(&file, "x").unwrap();
        assert!(load(&file, &[]).is_err());
    }

    #[test]
    fn a_skill_dir_path_to_an_existing_file_passes() {
        let tmp = TempDir::new().unwrap();
        let dir = ok_skill(
            tmp.path(),
            "refs",
            "Read `${CLAUDE_SKILL_DIR}/references/table.md`.\n\
             Run `bash ${CLAUDE_SKILL_DIR}/references/run.sh --flag`.",
        );
        fs::create_dir_all(dir.join("references")).unwrap();
        fs::write(dir.join("references/table.md"), "t").unwrap();
        fs::write(dir.join("references/run.sh"), "s").unwrap();
        load(tmp.path(), &[]).unwrap();
    }

    #[test]
    fn a_skill_dir_path_to_a_missing_file_is_an_error() {
        let tmp = TempDir::new().unwrap();
        ok_skill(
            tmp.path(),
            "refs",
            "Read `${CLAUDE_SKILL_DIR}/references/gone.md`.",
        );
        assert!(load_err(tmp.path()).contains("references/gone.md"));
    }

    #[test]
    fn a_placeholder_skill_dir_path_is_not_checked() {
        let tmp = TempDir::new().unwrap();
        ok_skill(
            tmp.path(),
            "docs",
            "Name each file as `${CLAUDE_SKILL_DIR}/references/<file>`.",
        );
        load(tmp.path(), &[]).unwrap();
    }

    #[test]
    fn a_skill_dir_path_into_a_sibling_skill_passes() {
        let tmp = TempDir::new().unwrap();
        let other = ok_skill(tmp.path(), "other", "b");
        fs::create_dir_all(other.join("references")).unwrap();
        fs::write(other.join("references/x.md"), "x").unwrap();
        ok_skill(
            tmp.path(),
            "user",
            "See `${CLAUDE_SKILL_DIR}/../other/references/x.md`.",
        );
        load(tmp.path(), &[]).unwrap();
    }

    #[test]
    fn a_skill_dir_path_outside_the_root_is_an_error() {
        let tmp = TempDir::new().unwrap();
        let root = tmp.path().join("skills");
        fs::create_dir_all(&root).unwrap();
        fs::write(tmp.path().join("secret.txt"), "x").unwrap();
        ok_skill(
            &root,
            "escape",
            "Read `${CLAUDE_SKILL_DIR}/../../secret.txt`.",
        );
        assert!(load_err(&root).contains("outside"));
    }

    #[test]
    fn skill_dir_paths_stop_at_delimiters() {
        let body = "`${CLAUDE_SKILL_DIR}/a.md`, H=${CLAUDE_SKILL_DIR}/b.py; \
                    run ${CLAUDE_SKILL_DIR}/c.sh --x (${CLAUDE_SKILL_DIR}/d.md).";
        assert_eq!(skill_dir_paths(body), vec!["a.md", "b.py", "c.sh", "d.md"]);
    }
}
