//! `custom-skills-mcp` — a single self-contained Model Context Protocol server
//! that exposes a library of agent skills as MCP tools over stdio.
//!
//! Each `skills/<name>/SKILL.md` becomes one tool: calling it returns the
//! skill's instructions for the agent to follow. Nothing is copied into the
//! calling project and nothing is written. Two read-only tools round it out —
//! `skill_catalog` lists what is available, `skill_resource` returns a file
//! that sits beside a skill's `SKILL.md`.
//!
//! The `skills/` tree is embedded at compile time, so the binary needs no
//! sidecar directory. Set `CUSTOM_SKILLS_PATH` to load additional skill roots
//! from disk at startup, which is the shorter loop while writing one.

use std::{path::PathBuf, sync::Arc};

use anyhow::{bail, Context, Result};
use rmcp::{
    model::{
        CallToolRequestParams, CallToolResponse, CallToolResult, ContentBlock, Implementation,
        InitializeResult, ListToolsResult, PaginatedRequestParams, ProtocolVersion,
        ServerCapabilities, Tool, ToolAnnotations,
    },
    service::RequestContext,
    transport::stdio,
    ErrorData as McpError, RoleServer, ServerHandler, ServiceExt,
};
use serde_json::{json, Value};

mod skill;

use skill::{Origin, Skill};

const CATALOG_TOOL: &str = "skill_catalog";
const RESOURCE_TOOL: &str = "skill_resource";

fn empty_schema() -> Arc<serde_json::Map<String, Value>> {
    obj_schema(json!({
        "type": "object",
        "properties": {},
        "additionalProperties": false
    }))
}

fn obj_schema(v: Value) -> Arc<serde_json::Map<String, Value>> {
    match v {
        Value::Object(map) => Arc::new(map),
        _ => unreachable!("literal is an object"),
    }
}

/// The Rust-backed tools, as opposed to the instructional skills. Both are
/// read-only: this server never writes.
fn builtin_tools() -> Vec<Tool> {
    vec![
        Tool::new(
            CATALOG_TOOL,
            "List every available skill with its description and the files it carries. \
             Read-only; returns metadata only, never skill bodies.",
            empty_schema(),
        )
        .with_annotations(ToolAnnotations::new().read_only(true)),
        Tool::new(
            RESOURCE_TOOL,
            "Read a file that sits beside a skill's SKILL.md, by skill name and \
             skill-relative path. Read-only; never reads arbitrary filesystem paths.",
            obj_schema(json!({
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "description": "Skill name, as listed by skill_catalog"},
                    "path": {"type": "string", "description": "Path relative to the skill directory"}
                },
                "required": ["skill", "path"],
                "additionalProperties": false
            })),
        )
        .with_annotations(ToolAnnotations::new().read_only(true)),
    ]
}

#[derive(Clone)]
struct SkillsServer {
    skills: Arc<Vec<Skill>>,
}

impl SkillsServer {
    fn new(skills: Vec<Skill>) -> Result<Self> {
        for skill in &skills {
            if skill.name == CATALOG_TOOL || skill.name == RESOURCE_TOOL {
                bail!(
                    "skill name {:?} collides with a built-in tool of the same name",
                    skill.name
                );
            }
        }
        Ok(Self {
            skills: Arc::new(skills),
        })
    }

    fn find(&self, name: &str) -> Option<&Skill> {
        self.skills.iter().find(|s| s.name == name)
    }

    fn listed_tools(&self) -> Vec<Tool> {
        let empty = empty_schema();
        let mut tools: Vec<Tool> = self
            .skills
            .iter()
            .map(|s| {
                Tool::new(s.name.clone(), s.description.clone(), empty.clone())
                    .with_annotations(ToolAnnotations::new().read_only(true))
            })
            .collect();
        tools.extend(builtin_tools());
        tools.sort_by(|a, b| a.name.cmp(&b.name));
        tools
    }

    fn route_tool(
        &self,
        name: &str,
        arguments: Option<serde_json::Map<String, Value>>,
    ) -> CallToolResult {
        match name {
            CATALOG_TOOL => match arguments {
                Some(args) if !args.is_empty() => {
                    tool_err(format!("{CATALOG_TOOL} does not accept arguments"))
                }
                _ => self.handle_catalog(),
            },
            RESOURCE_TOOL => self.handle_resource(arguments),
            name => match self.find(name) {
                Some(skill) => tool_ok(skill.body.clone()),
                None => tool_err(format!("unknown tool: {name}")),
            },
        }
    }

    fn handle_catalog(&self) -> CallToolResult {
        let items: Vec<Value> = self
            .skills
            .iter()
            .map(|skill| {
                json!({
                    "name": skill.name,
                    "description": skill.description,
                    "source": match &skill.origin {
                        Origin::Embedded(_) => "embedded",
                        Origin::Disk(_) => "disk",
                    },
                    "resources": skill.resources(),
                })
            })
            .collect();
        let payload = json!({ "count": items.len(), "skills": items });
        match serde_json::to_string_pretty(&payload) {
            Ok(text) => tool_ok(text),
            Err(err) => tool_err(format!("failed to render catalog: {err}")),
        }
    }

    fn handle_resource(&self, arguments: Option<serde_json::Map<String, Value>>) -> CallToolResult {
        let args = arguments.unwrap_or_default();
        let (Some(name), Some(path)) = (
            args.get("skill").and_then(Value::as_str),
            args.get("path").and_then(Value::as_str),
        ) else {
            return tool_err(format!(
                "{RESOURCE_TOOL} requires `skill` and `path` strings"
            ));
        };
        let Some(skill) = self.find(name) else {
            return tool_err(format!("unknown skill: {name}"));
        };
        match skill.read_resource(path) {
            Ok(text) => tool_ok(text),
            Err(err) => tool_err(format!("{err:#}")),
        }
    }
}

impl ServerHandler for SkillsServer {
    fn get_info(&self) -> InitializeResult {
        InitializeResult::new(ServerCapabilities::builder().enable_tools().build())
            .with_protocol_version(ProtocolVersion::LATEST)
            .with_server_info(
                Implementation::new(env!("CARGO_PKG_NAME"), env!("CARGO_PKG_VERSION"))
                    .with_description(env!("CARGO_PKG_DESCRIPTION")),
            )
            .with_instructions(
                "This server exposes a library of skills. Every tool other than \
                 skill_catalog and skill_resource is a skill: calling it returns \
                 instructions to follow, and changes nothing. skill_catalog lists the \
                 available skills and the files each carries; skill_resource returns one \
                 of those files. Start with skill_catalog when you do not know which \
                 skill fits.",
            )
    }

    async fn list_tools(
        &self,
        _request: Option<PaginatedRequestParams>,
        _context: RequestContext<RoleServer>,
    ) -> Result<ListToolsResult, McpError> {
        Ok(ListToolsResult::with_all_items(self.listed_tools()))
    }

    async fn call_tool(
        &self,
        request: CallToolRequestParams,
        _context: RequestContext<RoleServer>,
    ) -> Result<CallToolResponse, McpError> {
        Ok(self
            .route_tool(request.name.as_ref(), request.arguments)
            .into())
    }
}

fn tool_ok(text: String) -> CallToolResult {
    CallToolResult::success(vec![ContentBlock::text(text)])
}

fn tool_err(msg: String) -> CallToolResult {
    CallToolResult::error(vec![ContentBlock::text(msg)])
}

fn load_configured_skills() -> Result<Vec<Skill>> {
    let roots: Vec<PathBuf> = skill::roots_from_env();
    skill::load_all(&roots).context("failed to load skills")
}

#[tokio::main(flavor = "multi_thread", worker_threads = 2)]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("warn")),
        )
        .with_writer(std::io::stderr)
        .with_ansi(false)
        .init();

    let skills = load_configured_skills()?;
    tracing::info!(count = skills.len(), "loaded skills");

    let service = SkillsServer::new(skills)?
        .serve(stdio())
        .await
        .context("failed to start MCP stdio service")?;
    service.waiting().await.context("MCP service error")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn server() -> SkillsServer {
        SkillsServer::new(skill::load_all(&[]).expect("embedded skills load"))
            .expect("no name collisions")
    }

    #[test]
    fn embedded_skills_load_and_are_listed_as_tools() {
        let server = server();
        assert!(!server.skills.is_empty(), "expected at least one skill");
        let names: Vec<String> = server
            .listed_tools()
            .iter()
            .map(|t| t.name.to_string())
            .collect();
        assert!(names.iter().any(|n| n == CATALOG_TOOL));
        assert!(names.iter().any(|n| n == RESOURCE_TOOL));
        for skill in server.skills.iter() {
            assert!(names.contains(&skill.name), "missing tool {}", skill.name);
        }
    }

    #[test]
    fn tools_are_sorted_and_unique() {
        let tools = server().listed_tools();
        let names: Vec<String> = tools.iter().map(|t| t.name.to_string()).collect();
        let mut sorted = names.clone();
        sorted.sort();
        sorted.dedup();
        assert_eq!(names, sorted, "tool names must be sorted and unique");
    }

    #[test]
    fn calling_a_skill_returns_its_body() {
        let server = server();
        let name = server.skills[0].name.clone();
        let result = server.route_tool(&name, None);
        assert_ne!(result.is_error, Some(true));
        let ContentBlock::Text(text) = &result.content[0] else {
            panic!("expected text content");
        };
        assert_eq!(text.text, server.skills[0].body);
        assert!(
            !text.text.starts_with("---"),
            "frontmatter must be stripped"
        );
    }

    #[test]
    fn unknown_tool_is_an_error_result_not_a_protocol_error() {
        let result = server().route_tool("no-such-skill", None);
        assert_eq!(result.is_error, Some(true));
    }

    #[test]
    fn catalog_lists_every_skill() {
        let server = server();
        let result = server.route_tool(CATALOG_TOOL, None);
        let ContentBlock::Text(text) = &result.content[0] else {
            panic!("expected text content");
        };
        let parsed: Value = serde_json::from_str(&text.text).expect("catalog is JSON");
        assert_eq!(
            parsed["count"].as_u64().unwrap() as usize,
            server.skills.len()
        );
    }

    #[test]
    fn catalog_rejects_arguments() {
        let mut args = serde_json::Map::new();
        args.insert("nope".into(), json!(1));
        let result = server().route_tool(CATALOG_TOOL, Some(args));
        assert_eq!(result.is_error, Some(true));
    }

    #[test]
    fn resource_reads_declared_files_and_refuses_traversal() {
        let server = server();
        let skill = server
            .skills
            .iter()
            .find(|s| !s.resources().is_empty())
            .expect("at least one skill ships a resource file");
        let path = skill.resources()[0].clone();

        let mut args = serde_json::Map::new();
        args.insert("skill".into(), json!(skill.name));
        args.insert("path".into(), json!(path));
        let ok = server.route_tool(RESOURCE_TOOL, Some(args));
        assert_ne!(ok.is_error, Some(true));

        let mut escape = serde_json::Map::new();
        escape.insert("skill".into(), json!(skill.name));
        escape.insert("path".into(), json!("../../Cargo.toml"));
        let denied = server.route_tool(RESOURCE_TOOL, Some(escape));
        assert_eq!(denied.is_error, Some(true));
    }

    #[test]
    fn frontmatter_split_handles_a_minimal_document() {
        let (fm, body) = skill::split_frontmatter("---\nname: a\n---\nbody\n").unwrap();
        assert_eq!(fm, "name: a");
        assert_eq!(body, "body\n");
    }
}
