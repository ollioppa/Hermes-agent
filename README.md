# Hermes-agent

Six practical projects by Roland Chotika, developed with AI assistance and published together as sanitized, independently usable exports. This is a project collection, **not the Hermes Agent framework and not an official Nous Research distribution**.

## Choose a project

- **[market-data-collector](market-data-collector/README.md)** — Python market-data collection, calculations, Google Sheets persistence and structured snapshots. Includes a credential-free synthetic example using the real calculation and snapshot code.
- **[Opportunity Radar](opportunity-radar/README.md)** — equity/ETF research workflow with deterministic Python state management, canonical research prompts and supporting methods. Start with its [agent instructions](opportunity-radar/AGENTS.md) when using an AI harness.
- **[Documentation Guide](documentation-guide/README.md)** — a reusable documentation method with a neutral worked example. Open `documentation-guide/START-HERE.html` locally for its HTML entry point.

- **[Project Discovery](project-discovery/README.md)** — clarify an uncertain question and save an evidence-based answer or implementation handoff.
- **[Decision Council](decision-council/README.md)** — review designs and decisions through seven independent agent roles with human fact review.
- **[Delivery Workflow](delivery-workflow/README.md)** — coordinate real implementation, verification and documented handover without replacing the host agent.

The three workflow projects can be used in sequence: **Discovery → Council → Delivery**, or independently. Each requires the capabilities described in its README; private run artifacts must stay outside this repository.

## Read and explore

Each project README links to its user guide and self-contained source walkthrough. Download/open `walkthrough.html` in a browser: GitHub's file view shows the HTML source rather than running the interactive page. The atlas preserves the shared renderer's German navigation labels; project explanations and guides are English.

The walkthroughs explain the published source snapshot, not a recorded live execution. Their maps distinguish code calls, saved-artifact handoffs, human decisions and work performed by the agent host. Use the user guide to begin; use the walkthrough for technical depth.

For the development workflow, start with **Discovery** when the question is unclear, use **Council** when a consequential choice needs independent challenge, and use **Delivery** for authorized implementation and verification. These are human-guided handoffs, not an automatic pipeline; a Council recommendation does not authorize a deployment.

## Get started

```sh
git clone https://github.com/ollioppa/Hermes-agent.git
cd Hermes-agent
```

Choose one project and follow its README **from that project's directory**. There is no shared Python environment or global installer. Do not run live-provider or write commands before configuring your own accounts and understanding their effects.

Radar needs an intelligent agent/harness with suitable research and execution tools. Hermes, Claude Code, Codex or OpenClaw can be used as integration environments; compatibility with every harness is not claimed or independently tested. No private installation, scheduler or account is included. The agent should read the project instructions, identify its available tools and configure the workflow rather than invent missing evidence or bypass human decisions.

## What was verified

- **market-data-collector:** clean Python 3.14.5 installation on macOS; 255 tests passed; real offline consumer ran twice with identical output; import and network/write isolation checked.
- **Opportunity Radar:** clean Python 3.13 installation; 132 tests passed, including another run at the final export location; offline smoke/demo exercised real persistence and reader paths. Canonical prompts and selected research references are included.
- **Documentation Guide:** method preservation reviewed; example commands executed; local links and packaged entry files checked.

- **Workflow projects:** local nominal checks saved a Discovery report, completed the Council coordinator using explicitly synthetic role responses, and completed a real small text change with Delivery verification. These checks do not prove live model execution or universal host compatibility.

These are scoped checks, not a guarantee of investment performance, live-provider availability, mail delivery, or a newly executed end-to-end LLM research run. Synthetic examples are not market observations. Historical macro inputs intentionally omitted from market-data-collector must be supplied lawfully for its optional full macro workflow. See each project's limitations.

## Export boundary

This repository starts with new Git history. Private operational repositories, their histories, personal databases, credentials, account configuration and internal review logs are not included. Component references to a local review candidate or pending publication describe the preparation stage; publication of these exports was subsequently authorized together. They do not imply that private originals or live automations have been published.

## License

Each project includes an **MIT LICENSE**. Third-party notices, dependency licenses and market-data rights remain separate; see the component provenance/rights documents. Code licensing does not grant redistribution rights to provider data.
