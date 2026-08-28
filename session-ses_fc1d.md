# New session - 2026-08-26T12:52:40.451Z

**Session ID:** ses_fc1dec47dffe7a0XLwqxJNEVXj
**Created:** 8/26/2026, 4:52:40 PM
**Updated:** 8/26/2026, 5:08:17 PM

---

## User

Привет. Я хочу построить себе ultimate ИИ агентную систему. Он будет иметь выход ко всем моим соц сетям (ватсап телеграм инстаграм, имейл), будет иметь контроль над моим компьютером, телефоном (если получится), и ноутбуком. К нему будет легко подключать новые tools-ы или коннекторы для внешнего мира. У него будет ОГРОМНАЯ текстовая база данных обо мне. Которую мы для начала вынесем из ОГРОМНЫХ экспортов моих переписок с людьми, моей переписки с ИИшками. Далее он будет сам накапливать данные. Обо мне, о моих проектах, о моей жизни, буквально все обо мне. Эта БД будет огромной, и в такой форме, которая будет очень легко подключаться к ИИ. (скорее всего RAG). В ней в .md файлах все будет хранится (а может и картинки), они будут переплетены, связаны между собой, буквально как центр знаний что люди делают в Obsidian. Агент будет не одной ллм, а системой из многих. Они будут разделены по уровню цена\скорость. Будет одна главная, умная ллмка, потом будут поменьше, побыстрее. А самих агентов (ллм + инструкции + промпт) будет очень много под разные вещи. Будет главный оркестратор, который контролирует всех, будет один который будет "лицом" всей системы, и все эти агенты внутри должны будут уметь общаться между собой. Это наверное большой проект, но этого я хочу добиться. Я начал с простого single агента помощника для сайта elen.az . Он в отличии от моей затеи многопоточный, и работает со многими людьми, а мне нужен чисто для меня. Но я написал этого агента с нуля сам, и многие вещи увидел (не сам, дирижировал ИИ агентов и они писали). Теперь вопрос, как вообще мне начать осуществлять мой проект ? Знаю , должны быть уже готовые проекты, например openclaw, или может еще другие появились. Я с openclaw игрался, но он слишком большой и сложный для меня чтобы кастомизировать его. Твоя задача щас это посмотреть готовые opensource проекты, посмотреть подходят ли они, и вообще понять как мне начать свой проект писать.

---

## Assistant (Plan · Ox Alpha · 57.2s)

_Thinking:_

Let me understand the user's request. Magerram wants to build an "ultimate AI agent system" for personal use:

1. Access to his social networks (WhatsApp, Telegram, Instagram, email)
2. Control over his computer, phone, laptop
3. Easy to plug in new tools/connectors
4. Huge text database about him (from exports of chats with people, chats with AIs)
5. The agent will accumulate data itself - about him, projects, life
6. DB stored in .md files, interconnected like Obsidian knowledge center
7. Multi-agent system: main smart LLM + smaller/faster ones, many agents (LLM + instructions + prompt) for different things
8. Main orchestrator controlling all agents
9. One agent as the "face" of the system
10. Agents should be able to communicate with each other

He already built a single-agent assistant for elen.az website from scratch.

Now he asks:
- Look at ready-made opensource projects (e.g., openclaw) and see if they fit
- Understand how to start writing his own project

This is a research/planning task. I'm in plan mode - READ ONLY. I should:
1. Research existing open-source projects that could fit
2. Present a plan/analysis

Let me think about what I know and what I need to research:

Known projects in this space (as of my knowledge):
- **OpenClaw** (formerly Clawdbot/Moltbot?) - actually "OpenClaw" is a rebranding of "Clawdbot" by Peter Steinberger — a personal AI assistant that runs on your machine, connects to WhatsApp/Telegram/etc. It's quite complex.
- **OpenHands** (formerly OpenDevin) - more coding focused
- **AutoGen** (Microsoft) - multi-agent framework
- **CrewAI** - multi-agent orchestration
- **LangGraph** - graph-based agent orchestration
- **Letta** (formerly MemGPT) - memory-focused agents
- **mem0** - memory layer for LLMs
- **Zep** / Graphiti - temporal knowledge graph memory
- **Khoj** - open-source personal AI, works with Obsidian markdown notes! Very relevant for RAG over markdown
- **Danswer** (now Onyx) - enterprise search/RAG
- **n8n** - workflow automation with AI nodes, has connectors to everything (WhatsApp, Telegram, etc.)
- **Activepieces** - similar to n8n
- **AnythingLLM** - RAG desktop app
- **Open WebUI** - chat UI with RAG
- **Aider/Open Interpreter** - computer control
- **Claude Code / opencode itself** - CLI agents

For the messaging integrations:
- WhatsApp: Baileys (unofficial), whatsapp-web.js, or official Meta Cloud API
- Telegram: Telethon/Pyrogram/GramJS or official Bot API
- Instagram: unofficial libraries are fragile; official API limited
- Email: IMAP/SMTP straightforward

The user's vision maps well onto:
1. Memory/knowledge base: markdown files + Obsidian-style links → RAG. Options: build custom with sqlite-vec/LanceDB/Qdrant + chunking, or use Letta/mem0/Zep.
2. Agent orchestration: LangGraph, AutoGen, CrewAI, or custom router pattern.
3. Connectors: MCP (Model Context Protocol) is now the standard for pluggable tools! This is a key insight - MCP servers for Telegram, email, filesystem, browser control exist. Building the system around MCP gives him easy tool plugging.

Actually, the modern architecture answer here is likely:
- Core orchestrator (custom code or LangGraph)
- Tools via MCP servers
- Memory as local markdown files (Obsidian-compatible vault!) indexed into vector DB
- Messaging channels as adapters feeding into the orchestrator

I should research current state of these projects since my knowledge may be outdated. Today's date is Aug 26, 2026. My training cutoff... I should use webfetch/search to check current state of OpenClaw and alternatives.

Wait, do I have web search tools? I have webfetch. No explicit search tool listed, but webfetch can fetch pages. I can fetch GitHub pages, awesome lists, etc.

Let me plan my research:
1. Fetch OpenClaw GitHub/docs to assess its current state and complexity
2. Look at other projects: Khoj, Letta, mem0, LangGraph, AutoGen, CrewAI
3. Maybe look at an awesome-agents list for 2025/2026 newcomers
4. Check MCP ecosystem status

Then present:
- Analysis of ready-made options vs building own
- Recommended architecture sketch
- Roadmap of how to start (MVP first)

Since Magerram learns by building and found OpenClaw too big/complex to customize, the honest recommendation is probably: build a thin custom core (he already proved he can by building elen.az agent) + use established building blocks (MCP for connectors, vector DB for RAG, maybe LangGraph if needed or plain Python). Use OpenClaw's design as inspiration/reference rather than base.

Also per AGENTS.md: any architectural decision must be discussed and approved before implementation. This is exactly a planning conversation, so that fits perfectly. I'm in plan mode anyway.

Language: respond in Russian since he writes in Russian.

Let me do research now. I'll fetch several sources in parallel:
1. https://github.com/openclaw/openclaw (or whatever the repo is - let me try openclaw.ai docs too)
2. https://github.com/letta-ai/letta
3. https://github.com/mem0ai/mem0
4. Khoj: https://github.com/khoj-ai/khoj
5. LangGraph
6. Maybe an awesome list of autonomous agents

Let me start with parallel fetches. Note webfetch might fail on some; I'll adapt.

Actually let me also check what exists in his working directory - he mentioned elen.az project. Working dir is "Sales agent". Let me look at the directory structure quickly to understand context. That could inform recommendations (language choice — probably TypeScript or Python?).

Plan mode allows read-only exploration. Let me batch:
- read working directory listing
- webfetch OpenClaw
- webfetch mem0
- webfetch khoj

Then follow-ups based on results.

Привет! Отличный проект и правильный инстинкт — сначала исследовать готовое, потом решать. Давай я сделаю разведку: посмотрю текущее состояние готовых проектов и твою кодовую базу, чтобы рекомендации были предметными.

**Tool: read**

**Input:**
```json
{
  "filePath": "C:\\Users\\maliy\\Programming\\Sales agent"
}
```

**Output:**
```
<path>C:\Users\maliy\Programming\Sales agent</path>
<type>directory</type>
<entries>
.env
.env.example
.git/
.gitignore
.private/
data/
knowledge/
prompts/
README.md
requirements.txt
ROADMAP.md
src/
templates/
tests/

(14 entries)
</entries>
```

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://github.com/openclaw/openclaw",
  "format": "markdown"
}
```

**Output:**
```
                                                                                                         GitHub - openclaw/openclaw: Your own personal AI assistant. Any OS. Any Platform. The lobster way. 🦞 · GitHub                                             

[Skip to content](#start-of-content)     

            

## Navigation Menu

[](/)

[Sign in](/login?return_to=https%3A%2F%2Fgithub.com%2Fopenclaw%2Fopenclaw)

Appearance settings

-   Platform
    
    -   AI CODE CREATION
        
        -   [GitHub CopilotWrite better code with AI](https://github.com/features/copilot)
        -   [GitHub Copilot appDirect agents from issue to merge](https://github.com/features/ai/github-app)
        -   [MCP RegistryIntegrate external tools](https://github.com/mcp)
        
    -   DEVELOPER WORKFLOWS
        
        -   [ActionsAutomate any workflow](https://github.com/features/actions)
        -   [CodespacesInstant dev environments](https://github.com/features/codespaces)
        -   [IssuesPlan and track work](https://github.com/features/issues)
        -   [Code ReviewManage code changes](https://github.com/features/code-review)
        -   [Code QualityEnforce quality at merge](https://github.com/features/code-quality)
        
    -   APPLICATION SECURITY
        
        -   [GitHub Advanced SecurityFind and fix vulnerabilities](https://github.com/security/advanced-security)
        -   [Code securitySecure your code as you build](https://github.com/security/advanced-security/code-security)
        -   [Secret protectionStop leaks before they start](https://github.com/security/advanced-security/secret-protection)
        
    -   EXPLORE
        
        -   [Why GitHub](https://github.com/why-github)
        -   [Documentation](https://docs.github.com)
        -   [Blog](https://github.blog)
        -   [Changelog](https://github.blog/changelog)
        -   [Marketplace](https://github.com/marketplace)
        
    
    [View all features](https://github.com/features)
    
-   Solutions
    
    -   BY COMPANY SIZE
        
        -   [Enterprises](https://github.com/enterprise)
        -   [Small and medium teams](https://github.com/team)
        -   [Startups](https://github.com/enterprise/startups)
        -   [Nonprofits](https://github.com/solutions/industry/nonprofits)
        
    -   BY USE CASE
        
        -   [App Modernization](https://github.com/solutions/use-case/app-modernization)
        -   [DevSecOps](https://github.com/solutions/use-case/devsecops)
        -   [DevOps](https://github.com/solutions/use-case/devops)
        -   [CI/CD](https://github.com/solutions/use-case/ci-cd)
        -   [View all use cases](https://github.com/solutions/use-case)
        
    -   BY INDUSTRY
        
        -   [Healthcare](https://github.com/solutions/industry/healthcare)
        -   [Financial services](https://github.com/solutions/industry/financial-services)
        -   [Manufacturing](https://github.com/solutions/industry/manufacturing)
        -   [Government](https://github.com/solutions/industry/government)
        -   [View all industries](https://github.com/solutions/industry)
        
    
    [View all solutions](https://github.com/solutions)
    
-   Resources
    
    -   EXPLORE BY TOPIC
        
        -   [AI](https://github.com/resources/articles?topic=ai)
        -   [Software Development](https://github.com/resources/articles?topic=software-development)
        -   [DevOps](https://github.com/resources/articles?topic=devops)
        -   [Security](https://github.com/resources/articles?topic=security)
        -   [View all topics](https://github.com/resources/articles)
        
    -   EXPLORE BY TYPE
        
        -   [Customer stories](https://github.com/customer-stories)
        -   [Events & webinars](https://github.com/resources/events)
        -   [Ebooks & reports](https://github.com/resources/whitepapers)
        -   [Business insights](https://github.com/solutions/executive-insights)
        -   [GitHub Skills](https://skills.github.com)
        
    -   SUPPORT & SERVICES
        
        -   [Documentation](https://docs.github.com)
        -   [Customer support](https://support.github.com)
        -   [Community forum](https://github.com/orgs/community/discussions)
        -   [Trust center](https://github.com/trust-center)
        -   [Partners](https://github.com/partners)
        
    
    [View all resources](https://github.com/resources)
    
-   Open Source
    
    -   COMMUNITY
        
        -   [GitHub SponsorsFund open source developers](https://github.com/open-source/sponsors)
        
    -   PROGRAMS
        
        -   [Security Lab](https://securitylab.github.com)
        -   [Maintainer Community](https://maintainers.github.com)
        -   [Accelerator](https://github.com/open-source/accelerator)
        -   [GitHub Stars](https://stars.github.com)
        -   [Archive Program](https://archiveprogram.github.com)
        
    -   REPOSITORIES
        
        -   [Topics](https://github.com/topics)
        -   [Trending](https://github.com/trending)
        -   [Collections](https://github.com/collections)
        
    
-   Enterprise
    
    -   ENTERPRISE SOLUTIONS
        
        -   [Enterprise platformAI-powered developer platform](https://github.com/enterprise)
        
    -   AVAILABLE ADD-ONS
        
        -   [GitHub Advanced SecurityEnterprise-grade security features](https://github.com/security/advanced-security)
        -   [Copilot for BusinessEnterprise-grade AI features](https://github.com/features/copilot/copilot-business)
        -   [Premium SupportEnterprise-grade 24/7 support](https://github.com/enterprise/premium-support)
        
    
-   [Pricing](https://github.com/pricing)

Search/

[Sign in](/login?return_to=https%3A%2F%2Fgithub.com%2Fopenclaw%2Fopenclaw)

[Sign up](/signup?ref_cta=Sign+up&ref_loc=header+logged+out&ref_page=%2F%3Cuser-name%3E%2F%3Crepo-name%3E&source=header-repo&source_repo=openclaw%2Fopenclaw)

Appearance settings

You signed in with another tab or window. Reload to refresh your session. You signed out in another tab or window. Reload to refresh your session. You switched accounts on another tab or window. Reload to refresh your session. Dismiss alert

### Uh oh!

There was an error while loading. Please reload this page.

[openclaw](/openclaw) / **[openclaw](/openclaw/openclaw)** Public

-   ### Uh oh!
    
    There was an error while loading. Please reload this page.
    
-   [Notifications](/login?return_to=%2Fopenclaw%2Fopenclaw) You must be signed in to change notification settings
-   [Fork 81.4k](/login?return_to=%2Fopenclaw%2Fopenclaw)
-   [Star 388k](/login?return_to=%2Fopenclaw%2Fopenclaw)
    

-   [Code](/openclaw/openclaw)
-   [Issues 3.5k](/openclaw/openclaw/issues)
-   [Pull requests 2.2k](/openclaw/openclaw/pulls)
-   [Actions](/openclaw/openclaw/actions)
-   [Projects](/openclaw/openclaw/projects)
-   [Security and quality 647](/openclaw/openclaw/security)
-   [Insights](/openclaw/openclaw/pulse)

Additional navigation options

-   [Code](/openclaw/openclaw)
-   [Issues](/openclaw/openclaw/issues)
-   [Pull requests](/openclaw/openclaw/pulls)
-   [Actions](/openclaw/openclaw/actions)
-   [Projects](/openclaw/openclaw/projects)
-   [Security and quality](/openclaw/openclaw/security)
-   [Insights](/openclaw/openclaw/pulse)

 [](/openclaw/openclaw)

main

[Branches](/openclaw/openclaw/branches)[Tags](/openclaw/openclaw/tags)

[](/openclaw/openclaw/branches)[](/openclaw/openclaw/tags)

Go to file

Code

Open more actions menu

## Latest commit

## History

[82,907 Commits](/openclaw/openclaw/commits/main/)

[](/openclaw/openclaw/commits/main/)82,907 Commits

## Folders and files

Name

Name

Last commit message

Last commit date

[.agents](/openclaw/openclaw/tree/main/.agents ".agents")

[.agents](/openclaw/openclaw/tree/main/.agents ".agents")

[.claude](/openclaw/openclaw/tree/main/.claude ".claude")

[.claude](/openclaw/openclaw/tree/main/.claude ".claude")

[.github](/openclaw/openclaw/tree/main/.github ".github")

[.github](/openclaw/openclaw/tree/main/.github ".github")

[.vscode](/openclaw/openclaw/tree/main/.vscode ".vscode")

[.vscode](/openclaw/openclaw/tree/main/.vscode ".vscode")

[apps](/openclaw/openclaw/tree/main/apps "apps")

[apps](/openclaw/openclaw/tree/main/apps "apps")

[config](/openclaw/openclaw/tree/main/config "config")

[config](/openclaw/openclaw/tree/main/config "config")

[custodian-skills](/openclaw/openclaw/tree/main/custodian-skills "custodian-skills")

[custodian-skills](/openclaw/openclaw/tree/main/custodian-skills "custodian-skills")

[deploy](/openclaw/openclaw/tree/main/deploy "deploy")

[deploy](/openclaw/openclaw/tree/main/deploy "deploy")

[docs](/openclaw/openclaw/tree/main/docs "docs")

[docs](/openclaw/openclaw/tree/main/docs "docs")

[examples/ai-chat](/openclaw/openclaw/tree/main/examples/ai-chat "This path skips through empty directories")

[examples/ai-chat](/openclaw/openclaw/tree/main/examples/ai-chat "This path skips through empty directories")

[extensions](/openclaw/openclaw/tree/main/extensions "extensions")

[extensions](/openclaw/openclaw/tree/main/extensions "extensions")

[git-hooks](/openclaw/openclaw/tree/main/git-hooks "git-hooks")

[git-hooks](/openclaw/openclaw/tree/main/git-hooks "git-hooks")

[packages](/openclaw/openclaw/tree/main/packages "packages")

[packages](/openclaw/openclaw/tree/main/packages "packages")

[patches](/openclaw/openclaw/tree/main/patches "patches")

[patches](/openclaw/openclaw/tree/main/patches "patches")

[qa](/openclaw/openclaw/tree/main/qa "qa")

[qa](/openclaw/openclaw/tree/main/qa "qa")

[scripts](/openclaw/openclaw/tree/main/scripts "scripts")

[scripts](/openclaw/openclaw/tree/main/scripts "scripts")

[security](/openclaw/openclaw/tree/main/security "security")

[security](/openclaw/openclaw/tree/main/security "security")

[skills](/openclaw/openclaw/tree/main/skills "skills")

[skills](/openclaw/openclaw/tree/main/skills "skills")

[src](/openclaw/openclaw/tree/main/src "src")

[src](/openclaw/openclaw/tree/main/src "src")

[test](/openclaw/openclaw/tree/main/test "test")

[test](/openclaw/openclaw/tree/main/test "test")

[ui](/openclaw/openclaw/tree/main/ui "ui")

[ui](/openclaw/openclaw/tree/main/ui "ui")

[.crabbox.yaml](/openclaw/openclaw/blob/main/.crabbox.yaml ".crabbox.yaml")

[.crabbox.yaml](/openclaw/openclaw/blob/main/.crabbox.yaml ".crabbox.yaml")

[.dockerignore](/openclaw/openclaw/blob/main/.dockerignore ".dockerignore")

[.dockerignore](/openclaw/openclaw/blob/main/.dockerignore ".dockerignore")

[.env.example](/openclaw/openclaw/blob/main/.env.example ".env.example")

[.env.example](/openclaw/openclaw/blob/main/.env.example ".env.example")

[.gitattributes](/openclaw/openclaw/blob/main/.gitattributes ".gitattributes")

[.gitattributes](/openclaw/openclaw/blob/main/.gitattributes ".gitattributes")

[.gitignore](/openclaw/openclaw/blob/main/.gitignore ".gitignore")

[.gitignore](/openclaw/openclaw/blob/main/.gitignore ".gitignore")

[.npmrc](/openclaw/openclaw/blob/main/.npmrc ".npmrc")

[.npmrc](/openclaw/openclaw/blob/main/.npmrc ".npmrc")

[.oxfmtrc.jsonc](/openclaw/openclaw/blob/main/.oxfmtrc.jsonc ".oxfmtrc.jsonc")

[.oxfmtrc.jsonc](/openclaw/openclaw/blob/main/.oxfmtrc.jsonc ".oxfmtrc.jsonc")

[.oxlintrc.json](/openclaw/openclaw/blob/main/.oxlintrc.json ".oxlintrc.json")

[.oxlintrc.json](/openclaw/openclaw/blob/main/.oxlintrc.json ".oxlintrc.json")

[.pre-commit-config.yaml](/openclaw/openclaw/blob/main/.pre-commit-config.yaml ".pre-commit-config.yaml")

[.pre-commit-config.yaml](/openclaw/openclaw/blob/main/.pre-commit-config.yaml ".pre-commit-config.yaml")

[.semgrepignore](/openclaw/openclaw/blob/main/.semgrepignore ".semgrepignore")

[.semgrepignore](/openclaw/openclaw/blob/main/.semgrepignore ".semgrepignore")

[AGENTS.md](/openclaw/openclaw/blob/main/AGENTS.md "AGENTS.md")

[AGENTS.md](/openclaw/openclaw/blob/main/AGENTS.md "AGENTS.md")

[CHANGELOG.md](/openclaw/openclaw/blob/main/CHANGELOG.md "CHANGELOG.md")

[CHANGELOG.md](/openclaw/openclaw/blob/main/CHANGELOG.md "CHANGELOG.md")

[CLAUDE.md](/openclaw/openclaw/blob/main/CLAUDE.md "CLAUDE.md")

[CLAUDE.md](/openclaw/openclaw/blob/main/CLAUDE.md "CLAUDE.md")

[CONTRIBUTING.md](/openclaw/openclaw/blob/main/CONTRIBUTING.md "CONTRIBUTING.md")

[CONTRIBUTING.md](/openclaw/openclaw/blob/main/CONTRIBUTING.md "CONTRIBUTING.md")

[Dockerfile](/openclaw/openclaw/blob/main/Dockerfile "Dockerfile")

[Dockerfile](/openclaw/openclaw/blob/main/Dockerfile "Dockerfile")

[LICENSE](/openclaw/openclaw/blob/main/LICENSE "LICENSE")

[LICENSE](/openclaw/openclaw/blob/main/LICENSE "LICENSE")

[README.md](/openclaw/openclaw/blob/main/README.md "README.md")

[README.md](/openclaw/openclaw/blob/main/README.md "README.md")

[SECURITY.md](/openclaw/openclaw/blob/main/SECURITY.md "SECURITY.md")

[SECURITY.md](/openclaw/openclaw/blob/main/SECURITY.md "SECURITY.md")

[THIRD\_PARTY\_NOTICES.md](/openclaw/openclaw/blob/main/THIRD_PARTY_NOTICES.md "THIRD_PARTY_NOTICES.md")

[THIRD\_PARTY\_NOTICES.md](/openclaw/openclaw/blob/main/THIRD_PARTY_NOTICES.md "THIRD_PARTY_NOTICES.md")

[VISION.md](/openclaw/openclaw/blob/main/VISION.md "VISION.md")

[VISION.md](/openclaw/openclaw/blob/main/VISION.md "VISION.md")

[appcast.xml](/openclaw/openclaw/blob/main/appcast.xml "appcast.xml")

[appcast.xml](/openclaw/openclaw/blob/main/appcast.xml "appcast.xml")

[docker-compose.yml](/openclaw/openclaw/blob/main/docker-compose.yml "docker-compose.yml")

[docker-compose.yml](/openclaw/openclaw/blob/main/docker-compose.yml "docker-compose.yml")

[fly.toml](/openclaw/openclaw/blob/main/fly.toml "fly.toml")

[fly.toml](/openclaw/openclaw/blob/main/fly.toml "fly.toml")

[node-version.d.mts](/openclaw/openclaw/blob/main/node-version.d.mts "node-version.d.mts")

[node-version.d.mts](/openclaw/openclaw/blob/main/node-version.d.mts "node-version.d.mts")

[node-version.mjs](/openclaw/openclaw/blob/main/node-version.mjs "node-version.mjs")

[node-version.mjs](/openclaw/openclaw/blob/main/node-version.mjs "node-version.mjs")

[openclaw.mjs](/openclaw/openclaw/blob/main/openclaw.mjs "openclaw.mjs")

[openclaw.mjs](/openclaw/openclaw/blob/main/openclaw.mjs "openclaw.mjs")

[package.json](/openclaw/openclaw/blob/main/package.json "package.json")

[package.json](/openclaw/openclaw/blob/main/package.json "package.json")

[pnpm-lock.yaml](/openclaw/openclaw/blob/main/pnpm-lock.yaml "pnpm-lock.yaml")

[pnpm-lock.yaml](/openclaw/openclaw/blob/main/pnpm-lock.yaml "pnpm-lock.yaml")

[pnpm-workspace.yaml](/openclaw/openclaw/blob/main/pnpm-workspace.yaml "pnpm-workspace.yaml")

[pnpm-workspace.yaml](/openclaw/openclaw/blob/main/pnpm-workspace.yaml "pnpm-workspace.yaml")

[render.yaml](/openclaw/openclaw/blob/main/render.yaml "render.yaml")

[render.yaml](/openclaw/openclaw/blob/main/render.yaml "render.yaml")

[taxonomy.yaml](/openclaw/openclaw/blob/main/taxonomy.yaml "taxonomy.yaml")

[taxonomy.yaml](/openclaw/openclaw/blob/main/taxonomy.yaml "taxonomy.yaml")

[tsconfig.core.json](/openclaw/openclaw/blob/main/tsconfig.core.json "tsconfig.core.json")

[tsconfig.core.json](/openclaw/openclaw/blob/main/tsconfig.core.json "tsconfig.core.json")

[tsconfig.extensions.json](/openclaw/openclaw/blob/main/tsconfig.extensions.json "tsconfig.extensions.json")

[tsconfig.extensions.json](/openclaw/openclaw/blob/main/tsconfig.extensions.json "tsconfig.extensions.json")

[tsconfig.extensions.projects.json](/openclaw/openclaw/blob/main/tsconfig.extensions.projects.json "tsconfig.extensions.projects.json")

[tsconfig.extensions.projects.json](/openclaw/openclaw/blob/main/tsconfig.extensions.projects.json "tsconfig.extensions.projects.json")

[tsconfig.json](/openclaw/openclaw/blob/main/tsconfig.json "tsconfig.json")

[tsconfig.json](/openclaw/openclaw/blob/main/tsconfig.json "tsconfig.json")

[tsconfig.plugin-sdk.dts.json](/openclaw/openclaw/blob/main/tsconfig.plugin-sdk.dts.json "tsconfig.plugin-sdk.dts.json")

[tsconfig.plugin-sdk.dts.json](/openclaw/openclaw/blob/main/tsconfig.plugin-sdk.dts.json "tsconfig.plugin-sdk.dts.json")

[tsconfig.scripts.json](/openclaw/openclaw/blob/main/tsconfig.scripts.json "tsconfig.scripts.json")

[tsconfig.scripts.json](/openclaw/openclaw/blob/main/tsconfig.scripts.json "tsconfig.scripts.json")

[tsconfig.ui.json](/openclaw/openclaw/blob/main/tsconfig.ui.json "tsconfig.ui.json")

[tsconfig.ui.json](/openclaw/openclaw/blob/main/tsconfig.ui.json "tsconfig.ui.json")

[tsdown.ai.config.ts](/openclaw/openclaw/blob/main/tsdown.ai.config.ts "tsdown.ai.config.ts")

[tsdown.ai.config.ts](/openclaw/openclaw/blob/main/tsdown.ai.config.ts "tsdown.ai.config.ts")

[tsdown.config.ts](/openclaw/openclaw/blob/main/tsdown.config.ts "tsdown.config.ts")

[tsdown.config.ts](/openclaw/openclaw/blob/main/tsdown.config.ts "tsdown.config.ts")

[vitest.config.ts](/openclaw/openclaw/blob/main/vitest.config.ts "vitest.config.ts")

[vitest.config.ts](/openclaw/openclaw/blob/main/vitest.config.ts "vitest.config.ts")

View all files

## Repository files navigation

-   [README](#)
-   [Contributing](#)
-   [License](#)
-   [Security](#)

More items

# OpenClaw 🦞 — Your assistant, on your devices, in your chats

[](#openclaw---your-assistant-on-your-devices-in-your-chats)

 ![OpenClaw — EXFOLIATE! EXFOLIATE! Your personal AI assistant, running on your own devices.](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/openclaw-banner-dark.png)

[![CI status](https://camo.githubusercontent.com/f13833506d22ab17e357a456aa6b529c8c93e272cfd4db544334c963d795f62a/68747470733a2f2f696d672e736869656c64732e696f2f6769746875622f616374696f6e732f776f726b666c6f772f7374617475732f6f70656e636c61772f6f70656e636c61772f63692e796d6c3f6272616e63683d6d61696e267374796c653d666c61742d737175617265266c6162656c3d6369)](https://github.com/openclaw/openclaw/actions/workflows/ci.yml) [![npm version](https://camo.githubusercontent.com/05d5966b56a176864edeec1fee8b2e8e4738418723910c89ea5f92bc561b966a/68747470733a2f2f696d672e736869656c64732e696f2f6e706d2f762f6f70656e636c61773f7374796c653d666c61742d737175617265266c6162656c3d6e706d)](https://www.npmjs.com/package/openclaw) [![Node.js version](https://camo.githubusercontent.com/297d602fa7c5b1e8d793d8d73d54e1205d2e3361cd3ada13a43cba61d7765e04/68747470733a2f2f696d672e736869656c64732e696f2f6e6f64652f762f6f70656e636c61773f7374796c653d666c61742d737175617265)](https://nodejs.org) [![License: MIT](https://camo.githubusercontent.com/422db9fd40f5831c765cf6530b6750c081b696bd18d904cf89554df98c676277/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f6c6963656e73652d4d49542d677265656e3f7374796c653d666c61742d737175617265)](/openclaw/openclaw/blob/main/LICENSE) [![Discord](https://camo.githubusercontent.com/4a7cf39d8e7bc01c86a2f81ae413f325b81c2aeeaf56418c18cd9e8020125204/68747470733a2f2f696d672e736869656c64732e696f2f646973636f72642f313435363335303036343036353930343836373f6c6162656c3d646973636f7264266c6f676f3d646973636f7264266c6f676f436f6c6f723d776869746526636f6c6f723d353836354632267374796c653d666c61742d737175617265)](https://discord.gg/clawd)

OpenClaw is a personal AI assistant that runs on your devices and meets you in the channels you already use. It is designed for a single operator and connects models, tools, messaging channels, and optional companion apps through one Gateway.

[Website](https://openclaw.ai) · [Docs](https://docs.openclaw.ai) · [Getting started](https://docs.openclaw.ai/start/getting-started) · [Showcase](https://docs.openclaw.ai/start/showcase) · [FAQ](https://docs.openclaw.ai/help/faq) · [Vision](/openclaw/openclaw/blob/main/VISION.md) · [DeepWiki](https://deepwiki.com/openclaw/openclaw)

## Install

[](#install)

The installer supports macOS, Linux, and Windows. It provisions a supported Node.js runtime when needed.

# macOS / Linux / WSL2
curl -fsSL https://openclaw.ai/install.sh | bash

# Windows PowerShell
iwr \-useb https://openclaw.ai/install.ps1 | iex

Already manage Node.js? Install the published package instead (Node 22.22.3+, 24.15+, or 25.9+):

npm install -g openclaw@latest --allow-scripts=openclaw

That command is for npm 12 or npm 11.16+. On npm 11.15 and earlier, omit `--allow-scripts=openclaw`. See the [installation guide](https://docs.openclaw.ai/install) for the lifecycle script contract, Docker, Nix, and other deployment paths.

## Quick start

[](#quick-start)

On a fresh install, the installer scripts start onboarding automatically. Complete the wizard they open. If you installed the package directly with npm, pnpm, or Bun, run:

openclaw onboard --install-daemon

After onboarding:

openclaw gateway status
openclaw dashboard

Onboarding verifies model access, creates the workspace, and configures the Gateway. The last command opens the Control UI; send a message there to confirm the assistant is working. See the [getting started guide](https://docs.openclaw.ai/start/getting-started) for channel setup and troubleshooting.

## How it fits together

[](#how-it-fits-together)

-   The [Gateway](https://docs.openclaw.ai/gateway) is the local control plane for sessions, tools, events, and channel connections.
-   The [Control UI](https://docs.openclaw.ai/web/control-ui), CLI, and [TUI](https://docs.openclaw.ai/web/tui) connect to the Gateway.
-   [Channels](https://docs.openclaw.ai/channels) bring the assistant to WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, and other messaging services.
-   [Companion apps and nodes](https://docs.openclaw.ai/platforms) add voice, Canvas, camera, screen, and device-local actions on supported platforms.

OpenClaw works with hosted and local [model providers](https://docs.openclaw.ai/concepts/model-providers). Its [tools](https://docs.openclaw.ai/tools), [skills](https://docs.openclaw.ai/tools/skills), and [plugins](https://docs.openclaw.ai/plugins) extend what an assistant can do.

## Security

[](#security)

Treat inbound messages as untrusted input. DM-capable channels pair unknown senders by default; approve a pairing request with `openclaw pairing approve <channel> <code>`.

Tools run on the host for the main session unless you configure sandboxing. Read the [security guide](https://docs.openclaw.ai/gateway/security), [exposure runbook](https://docs.openclaw.ai/gateway/security/exposure-runbook), and [sandboxing guide](https://docs.openclaw.ai/gateway/sandboxing) before connecting other users or exposing the Gateway remotely.

## Documentation

[](#documentation)

Goal

Start here

Configure models and auth

[Models](https://docs.openclaw.ai/concepts/models) · [Model providers](https://docs.openclaw.ai/concepts/model-providers)

Connect a messaging service

[Channels](https://docs.openclaw.ai/channels)

Add tools, skills, and plugins

[Tools](https://docs.openclaw.ai/tools) · [Skills](https://docs.openclaw.ai/tools/skills) · [Plugins](https://docs.openclaw.ai/plugins) · [ClawHub](https://clawhub.ai)

Run apps and device nodes

[Platforms](https://docs.openclaw.ai/platforms) · [Nodes](https://docs.openclaw.ai/nodes)

Use the CLI and chat commands

[CLI reference](https://docs.openclaw.ai/cli) · [Slash commands](https://docs.openclaw.ai/tools/slash-commands)

Configure or operate the Gateway

[Configuration](https://docs.openclaw.ai/gateway/configuration) · [Architecture](https://docs.openclaw.ai/concepts/architecture) · [Updating](https://docs.openclaw.ai/install/updating) · [Release channels](https://docs.openclaw.ai/install/development-channels)

## Development

[](#development)

The repository is a pnpm workspace. Plain `npm install` at the repository root is not supported.

git clone https://github.com/openclaw/openclaw.git
cd openclaw
pnpm install
pnpm build
pnpm ui:build

See [CONTRIBUTING.md](/openclaw/openclaw/blob/main/CONTRIBUTING.md) for the contribution workflow and the [source setup guide](https://docs.openclaw.ai/start/setup) for the development loop.

## Community

[](#community)

OpenClaw is developed in the open by the [OpenClaw Foundation](https://openclaw.org), a non-profit. See [CONTRIBUTING.md](/openclaw/openclaw/blob/main/CONTRIBUTING.md) for maintainers and contribution guidelines; AI-assisted PRs are welcome.

Use the [issue chooser](https://github.com/openclaw/openclaw/issues/new/choose) for bugs and feature requests, ask setup questions in [Discord](https://discord.gg/clawd), and report vulnerabilities through [SECURITY.md](/openclaw/openclaw/blob/main/SECURITY.md). New capabilities usually belong in plugins built on the [plugin SDK](https://docs.openclaw.ai/plugins/building-plugins) and shared through [ClawHub](https://clawhub.ai).

OpenClaw was built for **Molty**, a space lobster AI assistant, by Peter Steinberger and the community. Explore the [project lore](https://docs.openclaw.ai/start/lore), [soul.md](https://soul.md), [Peter's site](https://steipete.me), [Star History](https://www.star-history.com/#openclaw/openclaw&type=date&legend=top-left), and [@openclaw](https://x.com/openclaw).

Special thanks to [Mario Zechner](https://mariozechner.at/) for his support and for [pi](https://github.com/earendil-works/pi), and to Adam Doppelt for the lobster.bot domain.

## Sponsors

[](#sponsors)

[![OpenAI](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/sponsors/openai.svg)](https://github.com/openai)

[![GitHub](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/sponsors/github.svg)](https://github.com/)

[![NVIDIA](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/sponsors/nvidia-dark.svg)](https://www.nvidia.com/)

[![Vercel](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/sponsors/vercel.svg)](https://vercel.com/)

[![Blacksmith](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/sponsors/blacksmith.svg)](https://blacksmith.sh/)

[![Convex](https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/sponsors/convex.svg)](https://www.convex.dev/)

## Contributors

[](#contributors)

Thanks to all clawtributors:


...69730 bytes truncated...

The tool call succeeded but the output was truncated. Full output saved to: C:\Users\maliy\.local\share\opencode\tool-output\tool_03e221835001D2O1bbuk1yMaM3
Use the Task tool to have explore agent process this file with Grep and Read (with offset/limit). Do NOT read the full file yourself - delegate to save context.
```

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://github.com/khoj-ai/khoj",
  "format": "markdown"
}
```

**Output:**
```
                                                                                                         GitHub - khoj-ai/khoj: Your AI second brain. Self-hostable. Get answers from the web or your docs. Build custom agents, schedule automations, do deep research. Turn any online or local LLM into your personal, autonomous AI (gpt, claude, gemini, llama, qwen, mistral). Get started - free. · GitHub                                             

[Skip to content](#start-of-content)     

            

## Navigation Menu

[](/)

[Sign in](/login?return_to=https%3A%2F%2Fgithub.com%2Fkhoj-ai%2Fkhoj)

Appearance settings

-   Platform
    
    -   AI CODE CREATION
        
        -   [GitHub CopilotWrite better code with AI](https://github.com/features/copilot)
        -   [GitHub Copilot appDirect agents from issue to merge](https://github.com/features/ai/github-app)
        -   [MCP RegistryIntegrate external tools](https://github.com/mcp)
        
    -   DEVELOPER WORKFLOWS
        
        -   [ActionsAutomate any workflow](https://github.com/features/actions)
        -   [CodespacesInstant dev environments](https://github.com/features/codespaces)
        -   [IssuesPlan and track work](https://github.com/features/issues)
        -   [Code ReviewManage code changes](https://github.com/features/code-review)
        -   [Code QualityEnforce quality at merge](https://github.com/features/code-quality)
        
    -   APPLICATION SECURITY
        
        -   [GitHub Advanced SecurityFind and fix vulnerabilities](https://github.com/security/advanced-security)
        -   [Code securitySecure your code as you build](https://github.com/security/advanced-security/code-security)
        -   [Secret protectionStop leaks before they start](https://github.com/security/advanced-security/secret-protection)
        
    -   EXPLORE
        
        -   [Why GitHub](https://github.com/why-github)
        -   [Documentation](https://docs.github.com)
        -   [Blog](https://github.blog)
        -   [Changelog](https://github.blog/changelog)
        -   [Marketplace](https://github.com/marketplace)
        
    
    [View all features](https://github.com/features)
    
-   Solutions
    
    -   BY COMPANY SIZE
        
        -   [Enterprises](https://github.com/enterprise)
        -   [Small and medium teams](https://github.com/team)
        -   [Startups](https://github.com/enterprise/startups)
        -   [Nonprofits](https://github.com/solutions/industry/nonprofits)
        
    -   BY USE CASE
        
        -   [App Modernization](https://github.com/solutions/use-case/app-modernization)
        -   [DevSecOps](https://github.com/solutions/use-case/devsecops)
        -   [DevOps](https://github.com/solutions/use-case/devops)
        -   [CI/CD](https://github.com/solutions/use-case/ci-cd)
        -   [View all use cases](https://github.com/solutions/use-case)
        
    -   BY INDUSTRY
        
        -   [Healthcare](https://github.com/solutions/industry/healthcare)
        -   [Financial services](https://github.com/solutions/industry/financial-services)
        -   [Manufacturing](https://github.com/solutions/industry/manufacturing)
        -   [Government](https://github.com/solutions/industry/government)
        -   [View all industries](https://github.com/solutions/industry)
        
    
    [View all solutions](https://github.com/solutions)
    
-   Resources
    
    -   EXPLORE BY TOPIC
        
        -   [AI](https://github.com/resources/articles?topic=ai)
        -   [Software Development](https://github.com/resources/articles?topic=software-development)
        -   [DevOps](https://github.com/resources/articles?topic=devops)
        -   [Security](https://github.com/resources/articles?topic=security)
        -   [View all topics](https://github.com/resources/articles)
        
    -   EXPLORE BY TYPE
        
        -   [Customer stories](https://github.com/customer-stories)
        -   [Events & webinars](https://github.com/resources/events)
        -   [Ebooks & reports](https://github.com/resources/whitepapers)
        -   [Business insights](https://github.com/solutions/executive-insights)
        -   [GitHub Skills](https://skills.github.com)
        
    -   SUPPORT & SERVICES
        
        -   [Documentation](https://docs.github.com)
        -   [Customer support](https://support.github.com)
        -   [Community forum](https://github.com/orgs/community/discussions)
        -   [Trust center](https://github.com/trust-center)
        -   [Partners](https://github.com/partners)
        
    
    [View all resources](https://github.com/resources)
    
-   Open Source
    
    -   COMMUNITY
        
        -   [GitHub SponsorsFund open source developers](https://github.com/open-source/sponsors)
        
    -   PROGRAMS
        
        -   [Security Lab](https://securitylab.github.com)
        -   [Maintainer Community](https://maintainers.github.com)
        -   [Accelerator](https://github.com/open-source/accelerator)
        -   [GitHub Stars](https://stars.github.com)
        -   [Archive Program](https://archiveprogram.github.com)
        
    -   REPOSITORIES
        
        -   [Topics](https://github.com/topics)
        -   [Trending](https://github.com/trending)
        -   [Collections](https://github.com/collections)
        
    
-   Enterprise
    
    -   ENTERPRISE SOLUTIONS
        
        -   [Enterprise platformAI-powered developer platform](https://github.com/enterprise)
        
    -   AVAILABLE ADD-ONS
        
        -   [GitHub Advanced SecurityEnterprise-grade security features](https://github.com/security/advanced-security)
        -   [Copilot for BusinessEnterprise-grade AI features](https://github.com/features/copilot/copilot-business)
        -   [Premium SupportEnterprise-grade 24/7 support](https://github.com/enterprise/premium-support)
        
    
-   [Pricing](https://github.com/pricing)

Search/

[Sign in](/login?return_to=https%3A%2F%2Fgithub.com%2Fkhoj-ai%2Fkhoj)

[Sign up](/signup?ref_cta=Sign+up&ref_loc=header+logged+out&ref_page=%2F%3Cuser-name%3E%2F%3Crepo-name%3E&source=header-repo&source_repo=khoj-ai%2Fkhoj)

Appearance settings

You signed in with another tab or window. Reload to refresh your session. You signed out in another tab or window. Reload to refresh your session. You switched accounts on another tab or window. Reload to refresh your session. Dismiss alert

### Uh oh!

There was an error while loading. Please reload this page.

[khoj-ai](/khoj-ai) / **[khoj](/khoj-ai/khoj)** Public

-   ### Uh oh!
    
    There was an error while loading. Please reload this page.
    
-   [Notifications](/login?return_to=%2Fkhoj-ai%2Fkhoj) You must be signed in to change notification settings
-   [Fork 2.4k](/login?return_to=%2Fkhoj-ai%2Fkhoj)
-   [Star 36.7k](/login?return_to=%2Fkhoj-ai%2Fkhoj)
    

-   [Code](/khoj-ai/khoj)
-   [Issues 101](/khoj-ai/khoj/issues)
-   [Pull requests 41](/khoj-ai/khoj/pulls)
-   [Discussions](/khoj-ai/khoj/discussions)
-   [Actions](/khoj-ai/khoj/actions)
-   [Projects](/khoj-ai/khoj/projects)
-   [Security and quality 6](/khoj-ai/khoj/security)
-   [Insights](/khoj-ai/khoj/pulse)

Additional navigation options

-   [Code](/khoj-ai/khoj)
-   [Issues](/khoj-ai/khoj/issues)
-   [Pull requests](/khoj-ai/khoj/pulls)
-   [Discussions](/khoj-ai/khoj/discussions)
-   [Actions](/khoj-ai/khoj/actions)
-   [Projects](/khoj-ai/khoj/projects)
-   [Security and quality](/khoj-ai/khoj/security)
-   [Insights](/khoj-ai/khoj/pulse)

 [](/khoj-ai/khoj)

master

[Branches](/khoj-ai/khoj/branches)[Tags](/khoj-ai/khoj/tags)

[](/khoj-ai/khoj/branches)[](/khoj-ai/khoj/tags)

Go to file

Code

Open more actions menu

## Latest commit

## History

[5,180 Commits](/khoj-ai/khoj/commits/master/)

[](/khoj-ai/khoj/commits/master/)5,180 Commits

## Folders and files

Name

Name

Last commit message

Last commit date

[.devcontainer](/khoj-ai/khoj/tree/master/.devcontainer ".devcontainer")

[.devcontainer](/khoj-ai/khoj/tree/master/.devcontainer ".devcontainer")

[.github](/khoj-ai/khoj/tree/master/.github ".github")

[.github](/khoj-ai/khoj/tree/master/.github ".github")

[.vscode](/khoj-ai/khoj/tree/master/.vscode ".vscode")

[.vscode](/khoj-ai/khoj/tree/master/.vscode ".vscode")

[documentation](/khoj-ai/khoj/tree/master/documentation "documentation")

[documentation](/khoj-ai/khoj/tree/master/documentation "documentation")

[scripts](/khoj-ai/khoj/tree/master/scripts "scripts")

[scripts](/khoj-ai/khoj/tree/master/scripts "scripts")

[src](/khoj-ai/khoj/tree/master/src "src")

[src](/khoj-ai/khoj/tree/master/src "src")

[tests](/khoj-ai/khoj/tree/master/tests "tests")

[tests](/khoj-ai/khoj/tree/master/tests "tests")

[.dockerignore](/khoj-ai/khoj/blob/master/.dockerignore ".dockerignore")

[.dockerignore](/khoj-ai/khoj/blob/master/.dockerignore ".dockerignore")

[.gitattributes](/khoj-ai/khoj/blob/master/.gitattributes ".gitattributes")

[.gitattributes](/khoj-ai/khoj/blob/master/.gitattributes ".gitattributes")

[.gitignore](/khoj-ai/khoj/blob/master/.gitignore ".gitignore")

[.gitignore](/khoj-ai/khoj/blob/master/.gitignore ".gitignore")

[.pre-commit-config.yaml](/khoj-ai/khoj/blob/master/.pre-commit-config.yaml ".pre-commit-config.yaml")

[.pre-commit-config.yaml](/khoj-ai/khoj/blob/master/.pre-commit-config.yaml ".pre-commit-config.yaml")

[Dockerfile](/khoj-ai/khoj/blob/master/Dockerfile "Dockerfile")

[Dockerfile](/khoj-ai/khoj/blob/master/Dockerfile "Dockerfile")

[LICENSE](/khoj-ai/khoj/blob/master/LICENSE "LICENSE")

[LICENSE](/khoj-ai/khoj/blob/master/LICENSE "LICENSE")

[README.md](/khoj-ai/khoj/blob/master/README.md "README.md")

[README.md](/khoj-ai/khoj/blob/master/README.md "README.md")

[computer.Dockerfile](/khoj-ai/khoj/blob/master/computer.Dockerfile "computer.Dockerfile")

[computer.Dockerfile](/khoj-ai/khoj/blob/master/computer.Dockerfile "computer.Dockerfile")

[docker-compose.yml](/khoj-ai/khoj/blob/master/docker-compose.yml "docker-compose.yml")

[docker-compose.yml](/khoj-ai/khoj/blob/master/docker-compose.yml "docker-compose.yml")

[gunicorn-config.py](/khoj-ai/khoj/blob/master/gunicorn-config.py "gunicorn-config.py")

[gunicorn-config.py](/khoj-ai/khoj/blob/master/gunicorn-config.py "gunicorn-config.py")

[manifest.json](/khoj-ai/khoj/blob/master/manifest.json "manifest.json")

[manifest.json](/khoj-ai/khoj/blob/master/manifest.json "manifest.json")

[prod.Dockerfile](/khoj-ai/khoj/blob/master/prod.Dockerfile "prod.Dockerfile")

[prod.Dockerfile](/khoj-ai/khoj/blob/master/prod.Dockerfile "prod.Dockerfile")

[pyproject.toml](/khoj-ai/khoj/blob/master/pyproject.toml "pyproject.toml")

[pyproject.toml](/khoj-ai/khoj/blob/master/pyproject.toml "pyproject.toml")

[pytest.ini](/khoj-ai/khoj/blob/master/pytest.ini "pytest.ini")

[pytest.ini](/khoj-ai/khoj/blob/master/pytest.ini "pytest.ini")

[uv.lock](/khoj-ai/khoj/blob/master/uv.lock "uv.lock")

[uv.lock](/khoj-ai/khoj/blob/master/uv.lock "uv.lock")

[versions.json](/khoj-ai/khoj/blob/master/versions.json "versions.json")

[versions.json](/khoj-ai/khoj/blob/master/versions.json "versions.json")

View all files

## Repository files navigation

-   [README](#)
-   [AGPL-3.0 license](#)

More items

[![Khoj Logo](https://camo.githubusercontent.com/aceab34fe2adf75b48319e8893632fc4dcdace9cbb4e2910f7d4106f706f6b90/68747470733a2f2f6173736574732e6b686f6a2e6465762f6b686f6a2d6c6f676f2d73696465776179732d31323030783534302e706e67)](https://camo.githubusercontent.com/aceab34fe2adf75b48319e8893632fc4dcdace9cbb4e2910f7d4106f706f6b90/68747470733a2f2f6173736574732e6b686f6a2e6465762f6b686f6a2d6c6f676f2d73696465776179732d31323030783534302e706e67)

[![test](https://github.com/khoj-ai/khoj/actions/workflows/test.yml/badge.svg)](https://github.com/khoj-ai/khoj/actions/workflows/test.yml) [![docker](https://github.com/khoj-ai/khoj/actions/workflows/dockerize.yml/badge.svg)](https://github.com/khoj-ai/khoj/pkgs/container/khoj) [![pypi](https://github.com/khoj-ai/khoj/actions/workflows/pypi.yml/badge.svg)](https://pypi.org/project/khoj/) [![discord](https://camo.githubusercontent.com/48b99f8abc14696133e21bac5b324a8605faec9a628a62aacae9bbe42e3ea8f7/68747470733a2f2f696d672e736869656c64732e696f2f646973636f72642f313131323036353935363634373238343735363f7374796c653d706c6173746963266c6162656c3d646973636f7264)](https://discord.gg/BDgyabRM6e)

**Your AI second brain**

  

[📑 Docs](https://docs.khoj.dev)   •   [🌐 Web](https://khoj.dev)   •   [🔥 App](https://app.khoj.dev)   •   [💬 Discord](https://discord.gg/BDgyabRM6e)   •   [✍🏽 Blog](https://blog.khoj.dev)

[![khoj-ai%2Fkhoj | Trendshift](https://camo.githubusercontent.com/a5ddc160f42d26595a8aef61aba7556a6b734ea872931ed88b35d12220dfc8b4/68747470733a2f2f7472656e6473686966742e696f2f6170692f62616467652f7265706f7369746f726965732f3130333138)](https://trendshift.io/repositories/10318)

---

### 🎁 New

[](#-new)

-   Meet 🌶️ **[Pipali](https://pipali.ai)** - our [open-source](https://github.com/khoj-ai/pipali) AI coworker that runs on your computer.
-   [Read](https://blog.khoj.dev/posts/evaluate-khoj-quality/) about Khoj's excellent performance on modern retrieval and reasoning benchmarks.

---

## Overview

[](#overview)

[Khoj](https://khoj.dev) is a personal AI app to extend your capabilities. It smoothly scales up from an on-device personal AI to a cloud-scale enterprise AI.

-   Chat with any local or online LLM (e.g llama3, qwen, gemma, mistral, gpt, claude, gemini, deepseek).
-   Get answers from the internet and your docs (including image, pdf, markdown, org-mode, word, notion files).
-   Access it from your Browser, Obsidian, Emacs, Desktop, Phone or Whatsapp.
-   Create agents with custom knowledge, persona, chat model and tools to take on any role.
-   Automate away repetitive research. Get personal newsletters and smart notifications delivered to your inbox.
-   Find relevant docs quickly and easily using our advanced semantic search.
-   Generate images, talk out loud, play your messages.
-   Khoj is open-source, self-hostable. Always.
-   Run it privately on [your computer](https://docs.khoj.dev/get-started/setup) or try it on our [cloud app](https://app.khoj.dev).

---

## See it in action

[](#see-it-in-action)

[![demo_chat](https://github.com/khoj-ai/khoj/raw/master/documentation/assets/img/quadratic_equation_khoj_web.gif?raw=true)](https://github.com/khoj-ai/khoj/blob/master/documentation/assets/img/quadratic_equation_khoj_web.gif?raw=true)

Go to [https://app.khoj.dev](https://app.khoj.dev) to see Khoj live.

## Full feature list

[](#full-feature-list)

You can see the full feature list [here](https://docs.khoj.dev/category/features).

## Self-Host

[](#self-host)

To get started with self-hosting Khoj, [read the docs](https://docs.khoj.dev/get-started/setup).

## Enterprise

[](#enterprise)

Khoj is available as a cloud service, on-premises, or as a hybrid solution. To learn more about Khoj Enterprise, [visit our website](https://khoj.dev/teams).

## Frequently Asked Questions (FAQ)

[](#frequently-asked-questions-faq)

Q: Can I use Khoj without self-hosting?

Yes! You can use Khoj right away at [https://app.khoj.dev](https://app.khoj.dev) — no setup required.

Q: What kinds of documents can Khoj read?

Khoj supports a wide variety: PDFs, Markdown, Notion, Word docs, org-mode files, and more.

Q: How can I make my own agent?

Check out [this blog post](https://blog.khoj.dev/posts/create-agents-on-khoj/) for a step-by-step guide to custom agents. For more questions, head over to our [Discord](https://discord.gg/BDgyabRM6e)!

## Contributors

[](#contributors)

Cheers to our awesome contributors! 🎉

[![](https://camo.githubusercontent.com/42abb930ce6af71fa3153418b3115d088e3102ea2781cf91cb7a632c114ca053/68747470733a2f2f636f6e747269622e726f636b732f696d6167653f7265706f3d6b686f6a2d61692f6b686f6a)](https://github.com/khoj-ai/khoj/graphs/contributors)

Made with [contrib.rocks](https://contrib.rocks).

### Interested in Contributing?

[](#interested-in-contributing)

Khoj is open source. It is sustained by the community and we’d love for you to join it! Whether you’re a coder, designer, writer, or enthusiast, there’s a place for you.

Why Contribute?

-   Make an Impact: Help build, test and improve a tool used by thousands to boost productivity.
-   Learn & Grow: Work on cutting-edge AI, LLMs, and semantic search technologies.

You can help us build new features, improve the project documentation, report issues and fix bugs. If you're a developer, please see our [Contributing Guidelines](https://docs.khoj.dev/contributing/development) and check out [good first issues](https://github.com/khoj-ai/khoj/contribute) to work on.

## About

Your AI second brain. Self-hostable. Get answers from the web or your docs. Build custom agents, schedule automations, do deep research. Turn any online or local LLM into your personal, autonomous AI (gpt, claude, gemini, llama, qwen, mistral). Get started - free.

[khoj.dev](https://khoj.dev)

### Topics

[agent](/topics/agent)[ai](/topics/ai)[assistant](/topics/assistant)[chat](/topics/chat)[chatgpt](/topics/chatgpt)[emacs](/topics/emacs)[image-generation](/topics/image-generation)[llama3](/topics/llama3)[llamacpp](/topics/llamacpp)[llm](/topics/llm)[obsidian](/topics/obsidian)[obsidian-md](/topics/obsidian-md)[offline-llm](/topics/offline-llm)[productivity](/topics/productivity)[rag](/topics/rag)[research](/topics/research)[self-hosted](/topics/self-hosted)[semantic-search](/topics/semantic-search)[stt](/topics/stt)[whatsapp-ai](/topics/whatsapp-ai)

### Resources

[Readme](#readme-ov-file)

[AGPL-3.0 license](#AGPL-3.0-1-ov-file)

[Activity](/khoj-ai/khoj/activity)

[Custom properties](/khoj-ai/khoj/custom-properties)

### Stars

**36.7k** stars

### Watchers

**174** watching

### Forks

[**2.4k** forks](/khoj-ai/khoj/forks)

[Report repository](/contact/report-content?content_url=https%3A%2F%2Fgithub.com%2Fkhoj-ai%2Fkhoj&report=khoj-ai+%28user%29)

## Releases

## Sponsor this project

## Packages

## Used by

## Contributors

## Languages

## Footer

[](https://github.com)© 2026 GitHub, Inc.

### Footer navigation

-   [Terms](https://docs.github.com/site-policy/github-terms/github-terms-of-service)
-   [Privacy](https://docs.github.com/site-policy/privacy-policies/github-privacy-statement)
-   [Security](https://github.com/security)
-   [Status](https://www.githubstatus.com/)
-   [Community](https://github.community/)
-   [Docs](https://docs.github.com/)
-   [Contact](https://support.github.com?tags=dotcom-footer)
-   Manage cookies
-   Do not share my personal information

You can’t perform that action at this time.
```

---

## Assistant (Plan · Ox Alpha · 346.7s)

_Thinking:_

Good. I got OpenClaw (388k stars, huge project, pnpm workspace, TypeScript) and Khoj (36.7k stars, Python, RAG over markdown/Obsidian, WhatsApp integration).

Now let me look at his existing Sales agent project to understand what stack he used (Python it seems - requirements.txt). Let me read README and src structure.

Also I should research a few more projects:
- mem0 / Letta for memory
- LangGraph for orchestration
- MCP ecosystem status

Let me do these in parallel:
1. Read README.md of Sales agent
2. Glob src/** to see structure
3. webfetch mem0
4. webfetch letta

Actually let me be economical. The key research questions:
1. Does OpenClaw fit? — It's the closest thing to his vision (personal assistant, messaging channels, device control). But he found it too complex to customize. It's now 388k stars with 82k commits — massive. Customizing = hard. But using it AS-IS might actually work for channels + computer control. The question is memory/knowledge base — OpenClaw has workspace files but not a big RAG system AFAIK.
2. Khoj fits the "second brain" RAG part + Obsidian + WhatsApp.
3. For multi-agent: he could build on top of what exists or use frameworks.

Let me check his existing code structure first, then fetch mem0/letta quickly. Actually, maybe better: delegate deeper research to explore/general agents to save context? The webfetch outputs are heavy. Let me use Task agents for parallel web research while I read local files myself.

Plan:
- Read local README.md + glob src
- Launch one general agent to research: current state (2026) of personal AI agent open-source projects: OpenClaw architecture & extensibility, Khoj, Letta, mem0, Zep/Graphiti, LangGraph vs plain code, MCP ecosystem for Telegram/WhatsApp/email/computer-use connectors, n8n AI agents. Return concise comparison + which pieces are mature building blocks.

Actually two agents in parallel:
- Agent A: personal assistant platforms comparison (OpenClaw, Khoj, Pipali, AnythingLLM, Leon AI?)
- Agent B: memory/RAG + multi-agent orchestration building blocks (mem0, Letta, Graphiti/Zep, LangGraph, CrewAI, AutoGen/AG2, MCP servers for telegram/whatsapp/email/computer use)

That saves my context. Then I synthesize into a plan + questions for Magerram.

Let me also quickly read his project files myself since that's cheap and important for tailoring (Python vs TS).

OpenClaw посмотрел — он стал огромным (388k звёзд, 83k коммитов, монорепо на TypeScript). Теперь посмотрю твой текущий проект и параллельно запущу глубокое исследование по остальным кандидатам и строительным блокам.

**Tool: read**

**Input:**
```json
{
  "filePath": "C:\\Users\\maliy\\Programming\\Sales agent\\README.md"
}
```

**Output:**
```
<path>C:\Users\maliy\Programming\Sales agent\README.md</path>
<type>file</type>
<content>
1: # Sales agent
2: 
3: A small terminal chat bot for the future elen.az sales assistant.
4: 
5: ## First version
6: 
7: - sends messages to Gemini through its REST API;
8: - saves separate conversation histories in a local SQLite database;
9: - reads the API key and model name from `.env`;
10: - keeps the database file out of Git.
11: - stops before it sends an oversized history to Gemini.
12: - reads its instructions and store knowledge from Markdown files.
13: - searches elen.az and filters several relevant product candidates.
14: - reads elen.az product links sent directly by a customer.
15: - permanently blocks a session that sends more than 15 messages in 60 seconds.
16: - can explicitly refer a customer to a human operator.
17: 
18: ## Setup
19: 
20: Create a `.env` file from `.env.example` and add your Gemini API key.
21: 
22: Install the dependency:
23: 
24: ```powershell
25: python -m pip install -r requirements.txt
26: ```
27: 
28: Run the chat:
29: 
30: ```powershell
31: python src/main.py
32: ```
33: 
34: ## Telegram demo
35: 
36: Create a bot by opening [@BotFather](https://t.me/BotFather), send `/newbot`,
37: and follow its instructions. Keep the received token private and add it only to
38: your local `.env` file:
39: 
40: ```text
41: TELEGRAM_BOT_TOKEN=your_real_token
42: ```
43: 
44: Run the Telegram bot while this computer stays online:
45: 
46: ```powershell
47: python src/telegram_bot.py
48: ```
49: 
50: Each Telegram chat uses its own session such as `telegram:123456`. Send
51: `/reset` in Telegram to clear only that chat's saved history. This first demo
52: uses long polling. Up to four different sessions can wait for Gemini at the
53: same time.
54: 
55: Messages from one session stay in order. The bot waits one second before a new
56: request so that short message bursts can be combined. If another message
57: arrives during the first Gemini request, the old result is not saved or sent.
58: The bot rebuilds the request once with both messages. Further messages wait for
59: the next turn. This is still a local demo, not a production deployment.
60: 
61: Type `exit` to stop the program.
62: 
63: Useful terminal commands:
64: 
65: - `/use magerram` switches to the session `terminal:magerram`.
66: - `/sessions` shows sessions created in this run.
67: - `/reset` clears only the current session history.
68: 
69: The part before `:` is the message channel. Later, the website chat can use a
70: key such as `website:<visitor_id>` and WhatsApp can use `whatsapp:<number>`.
71: They stay separate even when the part after `:` is the same.
72: 
73: The database is created automatically as `data/sales_agent.db`. It is local to
74: this computer and is ignored by Git because it can contain customer messages.
75: Spam limits and blocked session IDs are stored in the same database. A blocked
76: session stays blocked after the program restarts and is not cleared by `/reset`.
77: 
78: The project reads simple `KEY=value` lines from `.env` itself. It uses
79: `requests` for the direct HTTP request to Gemini and does not use a Gemini SDK.
80: It uses a conservative character-based estimate and stops when a conversation
81: is longer than roughly 250,000 tokens.
82: 
83: The files in `prompts/` and `knowledge/store.md` are loaded when the program
84: starts. Edit them to change the assistant's behavior, then restart the bot.
85: 
86: When Gemini calls `request_operator`, the customer receives a short referral
87: message. A separate operator summary is printed in the terminal for now. The
88: session remains active, and no operator message is added to customer history.
89: 
90: When a customer asks about a product, the agent works in three short steps:
91: 
92: 1. Gemini decides whether a product search is needed.
93: 2. Search results receive temporary candidate IDs and Gemini keeps up to ten
94:    relevant products.
95: 3. Python loads current product details and Gemini writes the customer answer.
96: 
97: If the customer sends a direct elen.az product link, Python validates and opens
98: the link immediately. The search and candidate-selection steps are skipped.
99: 
100: ## WhatsApp Cloud API
101: 
102: The WhatsApp connector uses Meta's official Cloud API. It is separate from the
103: agent core: the webhook turns an incoming customer message into a session such
104: as `whatsapp:994501234567`, then uses the same history, spam guard, concurrency,
105: and agent code as Telegram.
106: 
107: The connector currently accepts text messages. It validates Meta's
108: `X-Hub-Signature-256` signature, ignores events for other phone numbers, and
109: stores received WhatsApp message IDs in SQLite so webhook retries do not create
110: duplicate customer replies.
111: 
112: Required local settings are listed in `.env.example`. This checkout can also
113: load private Meta credentials from `.private/meta-whatsapp/credentials.env`.
114: That folder is local and must never be committed.
115: 
116: Run the local webhook server:
117: 
118: ```powershell
119: python src/whatsapp_bot.py
120: ```
121: 
122: It listens on `http://127.0.0.1:8000/webhooks/whatsapp`. Meta needs a public
123: HTTPS callback URL, so local development will use an HTTPS tunnel such as
124: Cloudflare Tunnel or ngrok. Router port forwarding is not required. The value entered in Meta's
125: Verify token field must exactly match `WHATSAPP_VERIFY_TOKEN`.
126: 
127: ## Run everything with one command
128: 
129: ```powershell
130: python src/runner.py
131: ```
132: 
133: The runner starts Telegram polling, the WhatsApp webhook server, and the
134: admin dashboard in one process with one shared session coordinator
135: (six parallel workers). All channels write to the same two log files.
136: Stop it with Ctrl+C.
137: 
138: The standalone entry points (`telegram_bot.py`, `whatsapp_bot.py`,
139: `admin_dashboard.py`, `main.py`) keep working for running one channel alone,
140: but do not combine them with the runner for the same channel.
141: 
142: ## Application logs
143: 
144: The project writes two rotating log files.
145: 
146: `data/logs/sales_agent.log` is the operational log. It records startup,
147: queueing, reply timing, delivery, operator requests, blocked sessions, and
148: errors. It does not record message text, access tokens, or API keys.
149: 
150: `data/logs/conversations.log` is the full conversation log. It records the
151: customer message text, the agent's decision steps (product search query,
152: found product titles, selected candidates), the final model reply, operator
153: requests, and manual replies sent from the dashboard. Each line starts with
154: the session ID:
155: 
156: ```text
157: 2026-08-23 21:00:01 | telegram:123456 | USER | Есть Samsung TV?
158: 2026-08-23 21:00:02 | telegram:123456 | DECISION | search query='Samsung TV'
159: 2026-08-23 21:00:02 | telegram:123456 | FOUND | query='Samsung TV' found=30 | Samsung 43" Crystal; LG OLED; … ещё 28
160: 2026-08-23 21:00:03 | telegram:123456 | SELECTED | ids=[3] | Samsung 43" Crystal UHD
161: 2026-08-23 21:00:05 | telegram:123456 | MODEL | Да, в наличии…
162: ```
163: 
164: Both active files are limited to 2 MB. Up to three older files are kept
165: automatically. To watch a log live in PowerShell:
166: 
167: ```powershell
168: Get-Content .\data\logs\sales_agent.log -Wait -Tail 50
169: Get-Content .\data\logs\conversations.log -Wait -Tail 50
170: ```
171: 
172: Do not run `src/runner.py` and a standalone bot for the same channel at the
173: same time: two Telegram pollers would steal updates from each other, and the
174: WhatsApp port 8000 can only be bound by one process.
175: 
176: ## Local chat dashboard
177: 
178: Run the local operator dashboard in a separate PowerShell window:
179: 
180: ```powershell
181: python src/admin_dashboard.py
182: ```
183: 
184: Or use the combined runner, which also serves the dashboard at the same
185: address in the same process (see "Run everything with one command").
186: 
187: Open `http://127.0.0.1:8001`. The page lists the current SQLite sessions,
188: refreshes the selected conversation automatically, and can send a manual reply
189: to WhatsApp or Telegram sessions through the existing channel clients. It binds
190: only to localhost and is not exposed through the WhatsApp Cloudflare tunnel.
191: 
192: The full search result and the temporary selection response are not added to
193: the conversation history or SQLite. The final request contains only the chosen
194: product data. Python checks every candidate ID before it opens a product URL.
195: 
196: Detailed product data stays compact. A product without selectable options has
197: its price and stock at the top level. A configurable product has no top-level
198: price or stock; instead, every radio or dropdown value is returned in
199: `variants` with only its name, price, and stock quantity. Product descriptions
200: are included as plain text, with table rows kept on separate lines.
201: 
202: ## Project layout
203: 
204: - `src/runner.py` runs Telegram, WhatsApp, and the dashboard in one process.
205: - `src/main.py` runs the terminal chat.
206: - `src/telegram_bot.py` receives and sends Telegram messages.
207: - `src/whatsapp_bot.py` connects the shared agent to WhatsApp Cloud API.
208: - `src/whatsapp_client.py` sends text messages through Meta Graph API.
209: - `src/whatsapp_webhook.py` verifies and parses Meta webhook events.
210: - `src/whatsapp_server.py` exposes the small Flask webhook endpoint.
211: - `src/whatsapp_store.py` prevents duplicate webhook processing.
212: - `src/reply_delivery.py` delivers normal replies and operator events to channels.
213: - `src/app_logging.py` configures private rotating application logs.
214: - `src/message_service.py` runs one customer message through the shared agent.
215: - `src/message_guard.py` blocks sessions that exceed the message rate limit.
216: - `src/session_coordinator.py` coordinates parallel sessions and message bursts.
217: - `src/agent.py` coordinates product search, selection, and the final answer.
218: - `src/agent_reply.py` separates the customer reply from an operator request.
219: - `src/chat.py` adds messages to a conversation history.
220: - `src/database.py` saves and loads session histories from SQLite.
221: - `src/prompts.py` builds the system instruction from Markdown files.
222: - `src/config.py` loads local settings from `.env`.
223: - `src/gemini.py` makes the HTTP request to Gemini.
224: - `src/product_search.py` reads product search result pages.
225: - `src/product_parser.py` reads current product details and variants.
226: - `tests/test_chat.py` checks chat history and session isolation with Python's
227:   built-in `unittest` module.

(End of file - total 227 lines)
</content>
```

**Tool: glob**

**Input:**
```json
{
  "pattern": "src/**/*.py"
}
```

**Output:**
```
C:\Users\maliy\Programming\Sales agent\src\database.py
C:\Users\maliy\Programming\Sales agent\src\config.py
C:\Users\maliy\Programming\Sales agent\src\chat.py
C:\Users\maliy\Programming\Sales agent\src\app_logging.py
C:\Users\maliy\Programming\Sales agent\src\agent_reply.py
C:\Users\maliy\Programming\Sales agent\src\agent.py
C:\Users\maliy\Programming\Sales agent\src\admin_dashboard.py
C:\Users\maliy\Programming\Sales agent\src\reply_delivery.py
C:\Users\maliy\Programming\Sales agent\src\prompts.py
C:\Users\maliy\Programming\Sales agent\src\product_search.py
C:\Users\maliy\Programming\Sales agent\src\product_parser.py
C:\Users\maliy\Programming\Sales agent\src\message_service.py
C:\Users\maliy\Programming\Sales agent\src\message_guard.py
C:\Users\maliy\Programming\Sales agent\src\main.py
C:\Users\maliy\Programming\Sales agent\src\gemini.py
C:\Users\maliy\Programming\Sales agent\src\whatsapp_bot.py
C:\Users\maliy\Programming\Sales agent\src\telegram_bot.py
C:\Users\maliy\Programming\Sales agent\src\session_coordinator.py
C:\Users\maliy\Programming\Sales agent\src\runner.py
C:\Users\maliy\Programming\Sales agent\src\whatsapp_server.py
C:\Users\maliy\Programming\Sales agent\src\whatsapp_client.py
C:\Users\maliy\Programming\Sales agent\src\whatsapp_store.py
C:\Users\maliy\Programming\Sales agent\src\whatsapp_webhook.py
```

**Tool: task**

**Input:**
```json
{
  "description": "Research personal AI assistant platforms",
  "prompt": "You are doing WEB RESEARCH ONLY (no code writing). Research the current state (August 2026) of open-source PERSONAL AI ASSISTANT platforms that run locally and connect to the user's own messaging channels. Use webfetch to read GitHub repos, docs sites, and blog posts. Do not guess from memory alone - verify with fetched pages.\n\nResearch these candidates in depth:\n1. OpenClaw (https://github.com/openclaw/openclaw, docs at https://docs.openclaw.ai) - focus on: its architecture (Gateway concept), how extensible it is (plugins/skills/extensions), whether it supports custom multi-agent setups with different LLM tiers (cheap/fast models vs smart models), what its memory/story system is, and how hard it is to customize deeply. Also note license and language (TypeScript).\n2. Khoj (https://github.com/khoj-ai/khoj) - focus on: RAG over Obsidian/markdown vaults, integrations (WhatsApp etc), custom agents feature, extensibility limits. Language/license (AGPL).\n3. Khoj's new project Pipali (https://pipali.ai, https://github.com/khoj-ai/pipali) - what is it, is it relevant as a local personal AI coworker?\n4. Check if there are other notable NEW open-source personal-assistant frameworks in 2025-2026 worth knowing (e.g. search github trending lists, awesome-ai-agents lists like https://github.com/e2b-dev/awesome-ai-agents). Briefly list anything significant besides the three above.\n\nFor each candidate report concisely:\n- What it does well / poorly relative to this vision: single-user personal agent, connects WhatsApp+Telegram+Instagram+email, controls the user's PC/laptop, pluggable tools/connectors, large personal knowledge base of interconnected .md files (Obsidian-style) queried via RAG, multi-agent architecture (orchestrator + face agent + many specialist sub-agents, tiered by model cost/speed).\n- Architecture overview in 3-6 bullets.\n- Extensibility story (how would you add a custom connector/tool/subagent).\n- Verdict: adopt as base / use as reference only / ignore.\n\nReturn a structured markdown report under ~1200 words. Include URLs you verified.",
  "subagent_type": "general"
}
```

**Output:**
```
<task id="ses_fc1dd42c9ffePxLbz9VwckxK9N" state="completed">
<task_result>
All research complete. Report below.

---

# Open-Source Personal AI Assistant Platforms — Research Report (Aug 2026)

Vision benchmark: single-user local agent; WhatsApp+Telegram+Instagram+email; controls user's PC; pluggable connectors; large interconnected .md knowledge base queried via RAG; orchestrator + face agent + tiered specialist sub-agents (cheap vs smart models).

## 1. OpenClaw

**Repo:** https://github.com/openclaw/openclaw · **Docs:** https://docs.openclaw.ai
MIT license, TypeScript/Node 22+, pnpm monorepo. ~388k stars / 82.9k commits — enormous, extremely fast-moving (beta releases within hours; plugin authors must re-test every release). Built by Peter Steinberger + OpenClaw Foundation (non-profit).

**vs. vision:** Strongest match found anywhere for channels, PC control, multi-agent tiering, and md-native memory. Gaps: no native Instagram channel (bundled list: WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Matrix, MS Teams, Google Chat, LINE, IRC, Nostr, Twilio SMS, Zalo, etc.); email appears only as Gmail Pub/Sub *trigger* automation, not a full two-way channel (both verifiable in https://docs.openclaw.ai/llms.txt). Memory is its own workspace md files — indexing a big pre-existing Obsidian vault needs `memory.search.extraPaths` config, not a first-class vault sync.

**Architecture** (https://docs.openclaw.ai/concepts/architecture):
- Single **Gateway** daemon owns all messaging surfaces (one Baileys session per host) + typed WebSocket JSON API (default `127.0.0.1:18789`), TypeBox-schema'd protocol.
- Clients (Control UI, CLI, TUI, macOS app) and **Nodes** (iOS/Android/macOS/headless devices exposing `camera.*`, `screen.record`, `location.get`, computer-use via Peekaboo) connect over WS with device pairing.
- **Agent loop** runs per session; sessions keyed per agent/channel/thread; queue lanes with concurrency caps; SQLite session stores per agent.
- **Multi-agent routing**: N isolated agents in one process, each with own workspace (`SOUL.md`, `AGENTS.md`, `USER.md`), auth profiles, model registry, session DB; deterministic **bindings** route channel/account/peer → agent (https://docs.openclaw.ai/concepts/multi-agent).
- Explicit tiered-model example in docs: WhatsApp → Sonnet-class "everyday" agent, Telegram DM → Opus "deep work" agent (same config file).
- Sandboxing (Docker containers, per-agent tool allow/deny), secrets store, Tailscale/SSH remote access.

**Memory/story system** (https://docs.openclaw.ai/concepts/memory): everything is plain Markdown in the workspace — `MEMORY.md` (curated long-term), `USER.md` (preference directives), `memory/YYYY-MM-DD.md` (daily notes), `DREAMS.md`. A "dreaming" background cron scores and promotes daily notes into MEMORY.md (sleep-time-compute inspired), with human review diary. Retrieval = hybrid vector+keyword (`memory_search`) over indexed notes; engines: built-in SQLite, LanceDB, Honcho plugins. Bonus: bundled **memory-wiki** plugin compiles durable knowledge into an Obsidian-friendly wiki vault with claims/provenance/lint tools.

**Extensibility:** best-in-class. Formal Plugin SDK — channel, provider (model/media/search), tool, hook, CLI-backend plugins — published to **ClawHub** marketplace, installed via `openclaw plugins install clawhub:<name>` (https://docs.openclaw.ai/plugins/building-plugins). Skills are simple instruction folders. Sub-agents: `sessions_spawn`, configurable nesting to depth 5 (orchestrator pattern at depth 2), per-child model/thinking overrides ("cheaper model for sub-agents" is an explicit documented cost pattern), fork/isolated context modes (https://docs.openclaw.ai/tools/subagents).

**Verdict: adopt as base.** Covers ~90% of the vision natively; you'd add Instagram connector as a channel plugin and decide between extending memory-wiki vs. wiring extraPaths to your vault.

## 2. Khoj

**Repo:** https://github.com/khoj-ai/khoj (~36.7k stars) · **Docs:** https://docs.khoj.dev
AGPL-3.0, Python backend (Django-style server + Docker deploy). Positions as self-hostable "AI second brain."

**vs. vision:** Wins decisively on **RAG over personal docs**: ingests PDFs, Markdown, org-mode, Word, Notion; first-class Obsidian/Emacs clients; semantic search ("Second Brain"); works with local or cloud LLMs (llama3, qwen, mistral, gpt, claude…). Has **WhatsApp** access and **custom agents** (persona + custom knowledge + chat model + tools, per README and https://docs.khoj.dev/category/features). Loses on: no Telegram/iMessage/Instagram channel story (web/desktop/Obsidian/WhatsApp only); no PC-control/device layer; agents are UI-configured personas inside one server, not a true orchestrator→specialist hierarchy with per-task model tiers; automations are scheduled queries emailed to you. Extensibility = contribute code; no public plugin/connector SDK comparable to OpenClaw (conclusion from docs structure — features are fixed, contribution is via repo PRs).

**Architecture:**
- Server (Python) with web app, desktop/Obsidian/Emacs clients.
- Ingestion pipeline → embeddings index for search/RAG.
- Chat layer over any OpenAI-compatible/local LLM.
- Agents = named configs (prompt, knowledge, model, tools).
- Automations = cron'd queries delivered via email.
- Code execution (Python) + image generation + voice.

**Verdict: reference only** for RAG-over-md-vault design and doc ingestion UX; wrong shape as the base (AGPL + no device control + flat agent model). Note AGPL matters if you ever distribute derived work.

## 3. Pipali (Khoj team)

**Site:** https://pipali.ai · **Repo:** https://github.com/khoj-ai/pipali (Beta, **Apache-2.0**, desktop app for macOS/Windows/Linux)

A desktop "AI coworker": assign async tasks, produces deliverables (docs, spreadsheets, emails), schedules recurring jobs, teaches workflows as [skills](https://agentskills.io), integrates Jira/Linear/Slack via MCP, runs commands in a local sandbox requiring approval for broad access.

**Key caveat for your vision:** model access goes through the **Pipali Platform (SSO/billing)** — "no API keys" means *their* hosted models, so it is not a fully local/self-hosted LLM setup despite running locally (verified in repo README FAQ). No messaging-channel layer at all. It's a task-executor, not an always-on chat-side assistant. **Relevance: interesting as a reference** for sandboxed local execution and skill teaching; not a base, not yet a coworker substitute for this use case.

## 4. Other notable projects (2025–2026)

The e2b awesome list (https://github.com/e2b-dev/awesome-ai-agents, 29.7k stars) is dominated by older general agent frameworks (AutoGPT, BabyAGI lineage, CrewAI, AutoGen, LangChain agents) — none are single-user, channel-connected personal assistants. Two adjacent items surfaced directly from OpenClaw's own docs/README (so they're real and active in this niche):

- **Hermes** — a personal assistant with `MEMORY.md`/`USER.md` conventions; OpenClaw ships dedicated migration/import paths for it (https://docs.openclaw.ai/install/migrating-hermes) — evidence it was significant enough to build converters for.
- **pi** (https://github.com/earendil-works/pi, Mario Zechner) — minimal coding-agent runtime credited in OpenClaw's README; architecturally interesting, but a harness, not a channel-connected assistant.

Nothing else found matches the three above in maturity for this exact vision.

## Bottom line

| | Channels | PC control | Multi-agent tiers | md/RAG memory | Extensibility | Verdict |
|---|---|---|---|---|---|---|
| **OpenClaw** | ★★★★ (−IG, −email) | ★★★★★ (nodes/computer-use) | ★★★★★ (bindings+subagents+model overrides) | ★★★★ (native md, dreaming; vault wiring needed) | ★★★★★ SDK+marketplace | **Adopt as base** |
| **Khoj** | ★★ (WA, web) | ✗ | ★★ (flat agents) | ★★★★★ (doc RAG) | ★★ (PRs only) | Reference for RAG design |
| **Pipali** | ✗ | sandboxed tasks only | ✗ | ✗ | MCP + skills files | Reference for sandboxing/skills |
</task_result>
</task>
```

**Tool: task**

**Input:**
```json
{
  "description": "Research agent building blocks",
  "prompt": "You are doing WEB RESEARCH ONLY (no code writing). Research the current state (August 2026) of BUILDING BLOCKS someone would use to build their OWN personal multi-agent AI system from scratch. Use webfetch to verify against official docs/GitHub - do not rely on memory alone. Cover three areas:\n\nAREA 1 - Agent MEMORY / knowledge base (the person wants: huge personal knowledge base stored as interconnected .md files like an Obsidian vault, built by ingesting exported chat logs (WhatsApp/Telegram/AI chats), auto-growing over time, queried by agents via RAG):\n- mem0 (https://github.com/mem0ai/mem0) - current features, self-hosting, graph memory option\n- Letta (formerly MemGPT) (https://github.com/letta-ai/letta)\n- Zep / Graphiti (https://github.com/getzep/graphiti) - temporal knowledge graphs\n- Any established pattern for \"markdown files as source of truth + vector index\" (e.g. sqlite-vec, LanceDB, Qdrant; Obsidian-compatible vaults). What's the pragmatic standard approach in 2026?\n\nAREA 2 - Multi-agent ORCHESTRATION frameworks:\n- LangGraph (https://github.com/langchain-ai/langgraph) - is it still the standard? \n- AutoGen/AG2 (https://github.com/ag2ai/ag2 or microsoft/autogen), CrewAI (https://github.com/crewAIInc/crewAI), OpenAI Agents SDK (https://github.com/openai/openai-agents-python), Claude Agent SDK if findable\n- Key question: when is a framework actually needed vs just writing your own router/orchestrator loop calling LLM APIs directly (~500 lines of code)? Find any credible recent opinion pieces/benchmarks on this.\n\nAREA 3 - Tool CONNECTIVITY standard:\n- Model Context Protocol (MCP) (https://modelcontextprotocol.io) - confirm current status, whether it became the de-facto standard for connecting tools to agents, and availability of ready-made MCP servers for: filesystem access/computer control, email (IMAP/Gmail), Telegram, WhatsApp, browser automation, phone/Android control (e.g. via ADB or Termux). Check https://github.com/modelcontextprotocol/servers and the MCP registry (https://github.com/mcp or registry.modelcontextprotocol.io).\n- How agents consume MCP servers programmatically (client libraries in Python/TypeScript).\n\nReturn a structured markdown report under ~1400 words with concrete verified facts, versions/stars where notable, and URLs. End with a short \"pragmatic 2026 stack recommendation\" section for someone who already built a working single-agent chatbot in Python and wants full control and easy pluggability.",
  "subagent_type": "general"
}
```

**Output:**
```
<task id="ses_fc1dd01c8ffeF1JjVrFwhlRK2Z" state="completed">
<task_result>
# Building Blocks for a Personal Multi-Agent AI System — State of Play, August 2026

*All facts below were verified live against the linked repos/docs/registries on Aug 26, 2026.*

---

## Area 1 — Agent Memory / Knowledge Base

### mem0 — https://github.com/mem0ai/mem0
- **64.1k stars**, Apache-2.0, YC S24; Python (`pip install mem0ai`) + TS SDKs + CLI.
- **Major April 2026 algorithm rewrite** ("v3"): ADD-only extraction (memories accumulate, nothing overwritten), entity linking, multi-signal retrieval (semantic + BM25 + entity matching fused), temporal reasoning. Benchmarks: LoCoMo **92.5** (+21 pts), LongMemEval **94.4**, new BEAM (1M/10M token) benchmarks published at ~1s p50 latency. Evaluation framework open-sourced at `mem0ai/memory-benchmarks`. Caveat stated in README: headline scores come from the managed platform; OSS SDK is "directionally similar."
- **Graph memory changed**: the old open-source option of plugging in Neo4j/Memgraph/Kuzu via `enable_graph` is **gone**. Per docs.mem0.ai/open-source/features/graph-memory, graph memory is now a **native platform feature** (entity co-occurrence graph, all plans, zero config); it boosts retrieval ranking but doesn't expose typed relations or a `relations` field anymore.
- **Self-hosting**: official Docker server (`cd server && make bootstrap`), auth on by default, dashboard included. Three tiers: library → self-hosted server → cloud.
- Fit: great "memory layer" (facts extracted from conversations), not a document store. Your raw chat logs stay yours; mem0 stores distilled memories.

### Letta (fka MemGPT) — https://github.com/letta-ai/letta
- **24.4k stars**, Apache-2.0. **Big structural change**: this repo is now just a landing page. Active source lives in [`letta-ai/letta-code`](https://github.com/letta-ai/letta-code) — an npm-distributed agent harness/TUI/app-server (`npm install -g @letta-ai/letta-code`). The old self-hostable Python V1 server is on the `archive` branch, explicitly unsupported ("should not be used in production").
- Now positioned as a Claude Code-style agent product with desktop/web apps and channels (Slack, Telegram, Discord). If your goal was "self-host MemGPT server as my memory backend," that path effectively closed in 2026.

### Zep / Graphiti — https://github.com/getzep/graphiti
- **30.3k stars**, Apache-2.0. Graphiti = open-source engine for **temporal context graphs**: facts carry validity windows (invalidated, never deleted), every fact traces back to raw "episodes," bi-temporal queries ("what was true then"), hybrid retrieval (semantic + BM25 + graph traversal). Paper: arXiv:2501.13956.
- Backends: Neo4j 5.26, FalkorDB, Amazon Neptune (**Kuzu deprecated** — upstream unmaintained). Ships an **MCP server** (`mcp_server/`) so Claude/Cursor/your agents can use the graph as memory directly, plus a FastAPI REST service.
- Zep = the commercial managed version (proprietary engine, sub-200ms retrieval, dashboards). Graphiti = DIY core; you operate the DB yourself.

### Markdown-as-source-of-truth + vector index
The pattern you describe (.md vault as canonical data, vector index derived from it) is alive and is arguably *the* pragmatic personal-RAG architecture in 2026 — because MCP made "the files are the database" trivially consumable:
- **sqlite-vec** (https://github.com/asg017/sqlite-vec, **8.0k stars**, Mozilla-sponsored): pure-C SQLite extension, vec0 virtual tables, runs anywhere incl. WASM; pre-v1. Ideal single-file local index over a vault.
- Alternatives: LanceDB (embedded, columnar) or Qdrant (if you want a real server). All three are standard choices; none is "the winner."
- Reference implementation of the idea exists inside MCP itself: the official **Memory reference server** (`@modelcontextprotocol/server-memory`) is literally "knowledge-graph-based persistent memory." Filesystem access goes through `@modelcontextprotocol/server-filesystem` with allowlisted dirs.
- No single dominant "Obsidian-RAG framework" exists; the common shape is: ingest script (chat exports → normalized .md notes with frontmatter) → chunk+embed into sqlite-vec/LanceDB → agents read .md via filesystem MCP + query index via a thin tool/MCP wrapper. Obsidian stays fully usable since it's plain markdown.

---

## Area 2 — Multi-Agent Orchestration

| Framework | Stars | Status (verified) |
|---|---|---|
| **LangGraph** ([repo](https://github.com/langchain-ai/langgraph)) | 40.5k | Still the low-level standard. MIT. Durable execution, interrupts/HITL, short+long-term memory. Higher-level **Deep Agents** package now sits on top. Used by Klarna, Replit, Elastic. |
| **CrewAI** ([repo](https://github.com/crewAIInc/crewAI)) | 57.6k | Crews (role-based autonomy) + Flows (event-driven control). New JSON-first project scaffold. MCP/A2A support. Commercial AMP control plane around OSS core. |
| **OpenAI Agents SDK** ([repo](https://github.com/openai/openai-agents-python)) | 29k | Lightweight, **provider-agnostic** (100+ LLMs via any-llm/LiteLLM), handoffs, guardrails, sessions, tracing, sandbox agents, realtime voice agents, native MCP support. |
| **AG2** ([repo](https://github.com/ag2ai/ag2)) | 4.9k | v1.0 is a full async rewrite ("AgentOS"); classic AutoGen API moved to `ag2ai/ag2-classic`, still maintained. Network hub/channels replace GroupChat. |
| **Claude Agent SDK** ([docs](https://docs.claude.com/en/api/agent-sdk/overview)) | n/a | Confirmed current: Python + TS libs exposing the exact Claude Code loop — built-in tools, hooks, subagents, sessions, permissions, skills/plugins, MCP. |

### Framework vs hand-rolled loop (~500 lines)
Two credible anchors, both still live and widely cited:

- **Anthropic, "Building Effective Agents"** (Dec 2024, updated note pointing to their newer Managed Agents post): "the most successful implementations use simple, composable patterns rather than complex frameworks"; frameworks "create extra layers of abstraction that can obscure prompts and responses"; recommendation: **start by using LLM APIs directly**, add complexity only when measured outcomes improve. An agent is "typically just LLMs using tools based on environmental feedback in a loop."
- **Cognition (Devin), "Don't Build Multi-Agents"** (June 2025): parallel multi-agent architectures are fragile because context can't be shared thoroughly; principles: share full agent traces; actions carry implicit decisions. Default to a **single-threaded linear agent** with context compression; spawn subagents only for well-scoped Q&A that keeps noise out of the main history.

Emerging consensus in 2026: you don't need a framework until you need (a) durable/resumable long-running state, (b) human-in-the-loop interrupts mid-run, or (c) heavy fan-out parallelism with state checkpoints. A router + tool loop + per-domain specialists called as functions genuinely fits in a few hundred lines. Notably, even Microsoft's own Playwright MCP README now observes coding agents shifting toward CLI+skills over MCP/tool-schemas for token efficiency — the trend is toward less orchestration machinery, not more.

---

## Area 3 — Tool Connectivity: MCP

**Status: confirmed de-facto standard.**
- Official docs (https://modelcontextprotocol.io): "open-source standard for connecting AI applications to external systems… like USB-C for AI applications." Docs currently versioned `2026-07-28`.
- Broad client support listed officially: Claude, **ChatGPT**, VS Code/Copilot, Cursor, Gemini CLI, Goose, etc.
- **Official registry is live**: https://registry.modelcontextprotocol.io (API-queriable; schema versions 2025-09-29 → 2025-12-11; listings actively updated days before today's date).
- Reference servers repo (https://github.com/modelcontextprotocol/servers): **89.9k stars**. Maintained set: Filesystem, Git, Fetch, Memory, Sequential Thinking, Time, Everything. Many originals (Puppeteer, Slack, Postgres, GitHub…) archived and moved to vendor/community maintenance.
- **Official SDKs in 10 languages** (TS, Python, Go, Java, Kotlin, C#, Ruby, Rust, Swift, PHP). Programmatic consumption: embed an MCP client (e.g., `modelcontextprotocol/python-sdk`), or use frameworks with built-in MCP clients — OpenAI Agents SDK and Claude Agent SDK both accept MCP servers natively; transports: stdio (local subprocess) and streamable-http (remote).

**Ready-made servers verified via registry searches (counts = active registry results):**
- **Filesystem/computer**: official `server-filesystem`; computer-use via Anthropic's reference demo; Playwright MCP ([microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp), **36.5k stars**) for browser automation via accessibility tree — plus a companion Playwright CLI+skills mode.
- **Email/Gmail**: 16 registered Gmail servers (e.g., `gmail-mcp` npm v2.4.0 by domdomegg; PulseMCP's OAuth2 + Workspace service-account server). Generic IMAP servers exist in community lists (awesome-mcp-servers) — less standardized.
- **Telegram**: 17 servers, including serious personal-account (MTProto/userbot) options: `@overpod/mcp-telegram` v1.41.5 (GramJS), TDLib-based `telegram-mcp-tdlib` (110 tools, read-only default, tool profiles), dual-mode Bot-API+MTProto `better-telegram-mcp`.
- **WhatsApp**: 21 servers. Personal account via whatsapp-web.js QR pairing (`mario-andreschak/mcp-whatsapp-web` v1.1.0, headless Chrome session); Meta Cloud API variants (`@codespar/mcp-whatsapp-cloud`, nakulben); Green API gateway. Note: personal-account ones ride unofficial web protocols — ban risk exists; Business/Cloud API ones are official but need a WABA.
- **Android/phone**: 13 results. ADB-based device control (`@us-all/android-mcp` v1.14.4 — screenshots/UI automation/logcat, read-only by default, shell opt-in), `ghost-in-the-droid/android-agent` (62 tools, Android+iPhone), plus Google's own remote **Android Management API MCP endpoint** for enterprise MDM. Termux-specific: nothing first-class found in registry; ADB-from-desktop is the established route.

---

## Pragmatic 2026 Stack Recommendation
(for someone with a working single-agent Python chatbot who wants full control)

1. **Orchestrator: write your own loop.** You already have one agent calling LLM APIs; extend it: a small router (LLM classifies intent → dispatch to specialist function/agent), each specialist = same tool-loop you already wrote. Add MCP client support via `modelcontextprotocol/python-sdk` so any MCP server plugs in as tools — that's your pluggability layer instead of a framework. Adopt LangGraph only when you need durable resumable runs or mid-run HITL interrupts.
2. **Memory: markdown vault + sqlite-vec.** Ingest WhatsApp/Telegram/AI-chat exports into dated .md notes (frontmatter: source, people, date) in an Obsidian-compatible folder — files remain the source of truth, greppable and portable forever. Chunk → embed → `vec0` tables in one SQLite file; rebuild incrementally. Give agents two tools: `read_note`/`write_note` (filesystem) and `semantic_search`. Skip graph DBs initially; if entity/temporal questions start hurting, bolt on **Graphiti** (FalkorDB backend is the lightest ops) rather than restructuring.
3. **Connectivity: MCP everywhere.** Filesystem (official), Playwright (browser), Telegram MTProto userbot server, Gmail MCP, ADB Android server — all exist, all register through one client. Wrap anything custom as a tiny MCP server so every future agent reuses it.
4. **Multi-agent scope: follow Cognition's advice** — keep one main thread with shared context; run "subagents" only as context-isolated research calls. Parallel autonomous crews add fragility without payoff for a personal system.

Net effect: ~500–800 lines of your own glue + SQLite file + markdown vault + off-the-shelf MCP servers ≈ everything a framework bundle would give you, minus lock-in.
</task_result>
</task>
```

---

## Assistant (Plan · Ox Alpha · 439.2s)

_Thinking:_

Excellent research results. Now I have a comprehensive picture. Let me synthesize for Magerram.

Key facts:
1. **OpenClaw** — actually matches his vision remarkably well NOW (it evolved a lot since he played with it, presumably): channels (WhatsApp/Telegram/Signal/iMessage etc., no Instagram natively), PC control via nodes, multi-agent routing with per-agent model tiers (documented pattern: WhatsApp → cheap Sonnet-class agent, Telegram → Opus deep-work), markdown memory system with "dreaming" cron, plugin SDK + ClawHub marketplace, subagents with cheaper models documented. MIT license.
   - BUT: it's enormous and fast-moving; he already found it too complex to customize. Gaps: Instagram channel missing natively, email is only a Gmail trigger not full two-way channel.
   
2. **Khoj** — great RAG over md vaults but wrong shape: AGPL, flat agents, no device control, limited channels. Reference only.

3. **Pipali** — not relevant as base.

4. Building blocks research:
   - Memory: md vault + sqlite-vec is the pragmatic standard. mem0 = memory layer (distilled facts) — optional later. Graphiti if temporal/entity questions matter. Letta self-host path closed.
   - Orchestration: consensus = write your own loop (~500-800 lines); frameworks only when durable execution/HITL/fan-out needed. Anthropic's "Building Effective Agents" + Cognition's "Don't Build Multi-Agents" support this.
   - MCP = de-facto standard, official registry live, SDKs in Python/TS, ready-made servers: filesystem, Playwright browser, Telegram MTProto userbot (17 servers), WhatsApp (21 servers, unofficial web protocol ban risk / Cloud API official), Gmail (16), Android ADB control (13).

His existing project: pure Python, no framework, direct Gemini REST calls via requests, SQLite sessions, markdown prompts/knowledge, multi-channel (Telegram polling, WhatsApp Cloud API webhook), runner with shared session coordinator. This is EXACTLY the architecture style the research recommends! He unknowingly built the right foundation: channels → session coordinator → agent loop → tools. 

So the honest recommendation:

**Option A: OpenClaw as base** — covers 90% of the vision out of the box. But: TypeScript monorepo of 83k commits, fast-moving; customizing deeply means swimming upstream; his stated pain was exactly that. However, using it *unmodified* as infrastructure + adding plugins (Instagram channel, email) is viable. The risk: he doesn't own the core logic, learning value lower, and complexity when things break inside it.

**Option B: Build own core on the pattern he already knows** (recommended given his goals — learning, full control, personal system):
- Core: Python orchestrator loop (evolve his elen.az patterns)
- Channels as adapters feeding one inbox (he has telegram_bot.py + whatsapp_bot.py patterns already)
- Tools via MCP client (python-sdk) — pluggability solved by an ecosystem, not by his code
- Memory: Obsidian-compatible vault of .md files (source of truth) + sqlite-vec index; ingestion pipeline from chat exports
- Agents: config-driven (md/json files: name, model tier, prompt, allowed tools) — many agents without code changes
- Model tiers: router picks model per task

Trade-offs to present honestly. Also mention hybrid: run OpenClaw alongside to steal ideas / use as reference implementation.

Per my instructions: architectural decision must be discussed and approved before implementation. This IS the discussion. I should present the analysis, give my recommendation with reasoning, ask key questions:

1. Language preference: stay Python? (his stack) vs TS (OpenClaw ecosystem)?
2. OpenClaw unmodified as infra vs own core?
3. Where will this run 24/7? (his Windows PC? a server/VPS? laptop?) — affects design (always-on daemon).
4. WhatsApp on personal account: unofficial (ban risk) vs Cloud API (official, needs WABA)?

Actually I shouldn't overload with questions. The main architectural fork is A vs B. Let me present a clear comparison + recommended roadmap skeleton, then ask the decisive questions.

Format: Russian, concise but this deserves detail since it's a planning/research deliverable. He asked "как вообще мне начать" — so end with concrete first steps for the recommended path.

Let me structure:

1. Что я выяснил (короткая сводка по кандидатам)
2. Главная находка: твой elen.az проект — уже правильная архитектура в миниатюре
3. Развилка: OpenClaw как база vs свой каркас (+ гибрид)
4. Моя рекомендация с обоснованием
5. Целевая архитектура (схема текстом)
6. Дорожная карта MVP → полная система (этапы)
7. Вопросы для решения перед стартом

Keep it reasonably tight. Use tables where helpful.

Исследование готово. Вот что я выяснил и что рекомендую.

## Главные выводы из разведки

**OpenClaw** (388k звёзд, MIT, TypeScript-монорепо на 83k коммитов) с тех пор как ты его смотрел сильно эволюционировал и теперь покрывает ~90% твоего зрения «из коробки»: каналы (WhatsApp, Telegram, Signal, iMessage...), контроль компьютеров через Nodes, мультиагентность с разными моделями по уровням (это прямо задокументированный паттерн), память в .md файлах с фоновым «dreaming»-кроном, Plugin SDK + магазин ClawHub. Но: он гигантский и очень быстрый (бета-релизы каждые несколько часов), нет нативного Instagram, email только как триггер, а не полноценный двусторонний канал. Твоя боль «слишком большой чтобы кастомизировать» — объективна: глубокая кастомизация там означает плавание против течения мегапроекта.

**Khoj** — лучший открытый RAG над Obsidian-хранилищами, но неверная форма: плоские агенты без оркестратора, нет контроля устройств, каналов мало, лицензия AGPL. Только как источник идей.

**Важный факт про индустрию:** MCP (Model Context Protocol) стал де-факто стандартом подключения инструментов — есть официальный реестр и готовые серверы почти под всё твоё: файловая система, браузер (Playwright MCP), Telegram через личный аккаунт (MTProto), WhatsApp, Gmail/IMAP, Android через ADB. Это решает твоё требование «легко подключать новые коннекторы» — экосистема уже есть, тебе нужен только MCP-клиент в своём коде.

И второй важный факт: консенсус 2025–2026 (Anthropic «Building Effective Agents», Cognition «Don't Build Multi-Agents») — **фреймворки мультиагентности чаще вредны, чем полезны**: router + tool-loop + специалисты-агенты честно помещаются в ~500–800 строк своего кода.

## Ключевое наблюдение

Я посмотрел твой Sales agent: `runner.py` с общим session coordinator'ом, каналы как отдельные адаптеры (`telegram_bot`, `whatsapp_webhook`), агентный цикл на прямых REST-вызовах, промпты и знания в .md, SQLite для состояний. **Ты уже неосознанно построил миниатюру именно той архитектуры, которую индустрия считает правильной.** Личный агент — это тот же проект, но: одна сессия (ты), больше каналов, инструменты через MCP, и вместо поиска товаров — память о тебе.

## Развилка

| | Вариант A: OpenClaw как база | Вариант B: свой каркас |
|---|---|---|
| Скорость до результата | Быстро (90% из коробки) | Медленнее, но инкрементально |
| Контроль и понимание | Низкий, чужой монорепо | Полный, ты знаешь каждую строку |
| Instagram/email | Плагины писать самому | Коннекторы писать самому (но у тебя уже есть паттерн WhatsApp-коннектора) |
| Обучение | Минимальное | Максимальное |
| Риск | Зависимость от чужого темпа релизов | Твои баги — твои |

**Моя рекомендация: вариант B**, потому что твоя цель — система «для себя» на годы + ты учишься строя, + твой стек (Python, без фреймворков) совпадает с проверенным подходом. Гибрид: держать OpenClaw установленным как референс (подглядывать решения), но не зависеть от него. mem0/Graphiti и LangGraph — сознательно не берём сейчас: это опциональные апгрейды позже, если упрёмся.

## Целевая архитектура (вариант B)

```
Каналы (адаптеры):        Telegram │ WhatsApp │ Email │ Instagram │ CLI/веб
                                    ↓ единый inbox (очередь сообщений)
Оркестратор («лицо»):     главный цикл LLM, дешёвая модель решает маршрут,
                          умная модель подключается для сложных задач
Инструменты:              MCP-клиент ← [filesystem, playwright, gmail,
                          telegram-mtp, android-adb, ...любой свой сервер]
Память:                   Obsidian-совместимое хранилище .md (источник правды)
                          + индекс sqlite-vec (RAG) + ingestion из экспортов чатов
Агенты:                   конфиги (.md/.json: имя, модель, промпт, инструменты),
                          а не код — новые агенты без изменения ядра
```

Дорожная карта: 
1. **MVP-ядро** — вынести цикл агента из elen.az в личного агента: один канал (Telegram), один инструмент (filesystem), память = папка .md. 
2. **Ingestion** — скрипт: экспорты переписок → нормализованные .md заметки с frontmatter → индексация в sqlite-vec → инструмент `semantic_search`. 
3. **MCP-клиент** — подключение готовых серверов как инструментов. 
4. **Мультиагентность** — конфиги агентов + маршрутизация, субагенты для изолированных задач. 
5. **Новые каналы** — email, потом Instagram (самый хрупкий). Телефон — последним, через ADB.

Прежде чем оформлять детальный план — три вопроса, которые реально влияют на дизайн:

**Tool: question**

**Input:**
```json
{
  "questions": [
    {
      "header": "База системы",
      "options": [
        {
          "description": "Полный контроль, обучение, твой стек Python. Дольше до полной функциональности, но каждый шаг твой.",
          "label": "Свой каркас (Рекомендую)"
        },
        {
          "description": "Быстрый результат из коробки, но жизнь внутри чужого мегапроекта и его темпа релизов.",
          "label": "OpenClaw как база"
        },
        {
          "description": "Свой каркас, но установленный OpenClaw как образец для решений.",
          "label": "Гибрид"
        }
      ],
      "question": "Принимаешь ли ты развилку: строим свой каркас (вариант B), а OpenClaw используем только как референс?"
    },
    {
      "header": "Хостинг",
      "options": [
        {
          "description": "Просто начать, но спящий режим/перезагрузки будут рвать работу агента.",
          "label": "Мой ПК (Windows)"
        },
        {
          "description": "Always-on с первого дня, доступ извне решён. Но дороже и дальше от 'контроль моего железа'.",
          "label": "VPS/сервер"
        },
        {
          "description": "Начать на ПК, спроектировав ядро так, чтобы переезд на сервер был заменой конфига.",
          "label": "ПК сейчас → VPS позже"
        }
      ],
      "question": "Где система будет жить 24/7? Это влияет на дизайн (демон, туннели, доступ извне)."
    },
    {
      "header": "WhatsApp",
      "options": [
        {
          "description": "Meta Cloud API — официально, стабильно, но это отдельный бизнес-номер, не твой личный чат.",
          "label": "Cloud API (как в elen.az)"
        },
        {
          "description": "Через whatsapp-web.js/MCP — работает с личным аккаунтом, но неофициально: теоретический риск бана.",
          "label": "Личный аккаунт"
        },
        {
          "description": "Личный аккаунт как эксперимент, Cloud API как надёжный канал.",
          "label": "Оба"
        }
      ],
      "question": "WhatsApp: какой путь для ЛИЧНОГО аккаунта? Это важно из-за риска бана."
    }
  ]
}
```

**Output:**
```
User has answered your questions: "Принимаешь ли ты развилку: строим свой каркас (вариант B), а OpenClaw используем только как референс?"="Свой каркас (Рекомендую)", "Где система будет жить 24/7? Это влияет на дизайн (демон, туннели, доступ извне)."="ПК сейчас → VPS позже", "WhatsApp: какой путь для ЛИЧНОГО аккаунта? Это важно из-за риска бана."="Да, личный аккаунт. В этом и весь смысл. Да, я проходил через всю боль открытия АПИ, и даже блокировали один раз левый номер, когда попытался левый headless browser parser использовать. Но если прямо основательно подумать, написать чистый , аккуратный код, который будет имитировать пользователя, в реальном браузере, интеракции делать как реальный человек, то риска бана наверное не будет.". You can now continue with the user's answers in mind.
```

---

## Assistant (Plan · Ox Alpha · 93.7s)

_Thinking:_

Magerram's answers:
1. Свой каркас (вариант B) — confirmed
2. ПК сейчас → VPS позже — design core so migration = config change
3. WhatsApp personal account — he wants the real thing. He says: if you write clean, careful code imitating a user in a real browser with human-like interactions, ban risk probably won't materialize.

On #3 I should give honest engineering assessment: whatsapp-web.js/Baileys ride the WhatsApp Web protocol. The risk isn't primarily about "looking human" in browser interactions — WhatsApp detects unofficial clients at protocol level (Baileys doesn't even use a browser, it implements the WebSocket multidevice protocol). Detection signals: new device registrations, message volume patterns, automation speed, reports from contacts. Since it's HIS OWN number receiving/sending his own messages mostly to himself/known contacts, risk is lower (no spam reports). Practical mitigations: keep it read-heavy, avoid mass messaging, link as a "linked device" like WhatsApp Web does. This is acceptable risk for personal use — many people run it. I'll note it honestly but not preach.

Now I need to produce the final plan. Plan mode: comprehensive yet concise plan for implementation. No code writing. The deliverable: detailed architecture + phased roadmap + first concrete step.

Let me think about the actual design carefully.

## Project structure

New project folder, e.g. `C:\Users\maliy\Programming\Personal agent` or similar. Separate repo from Sales agent. Reuse patterns/code from Sales agent (copy-adapt, not import — different lifecycle).

### Core principles
1. Markdown vault = source of truth (Obsidian-compatible)
2. sqlite-vec index = derived cache (rebuildable)
3. Channels = adapters → unified inbox queue
4. Orchestrator = main loop; face agent; specialists = configs
5. Tools via MCP client + a few native tools initially
6. Config-driven agents
7. PC-first, VPS-migration-friendly: no absolute paths, .env config, single long-running process (or few), stateless-ish core with SQLite state

### Components

**1. Core (`core/`)**
- `loop.py` — main event loop: pulls events from inbox queue, routes to session handler
- `agent.py` — generic tool-loop agent (LLM call → tool calls → results → repeat), model-agnostic provider layer (Gemini now, OpenAI-compatible later)
- `router.py` — cheap model decides: answer directly / delegate to specialist agent / use memory search etc.
- `providers.py` — LLM API adapters with model tiers config (fast/smart)
- `sessions.py` — session store (SQLite) — he has this pattern already

**2. Memory (`vault/` + `memory/`)**
- `vault/` — Obsidian-compatible folder: `people/`, `projects/`, `daily/YYYY-MM-DD.md`, `topics/`, `raw/` (ingested exports)
- Ingestion scripts (`scripts/ingest_*.py`): WhatsApp/TG exports → normalized md with frontmatter
- Indexer: chunk → embed (embedding API or local) → sqlite-vec vec0 table
- Tools exposed to agent: `search_memory(query)`, `read_note(path)`, `write_note(path)` — write enables auto-accumulation ("сам накапливать данные")

**3. Channels (`channels/`)**
- `base.py` — Channel interface: start(), poll/receive → inbox; send(session, text)
- `telegram.py` — port of his telegram_bot pattern
- `whatsapp_personal.py` — whatsapp-web.js via Node sidecar OR MCP server; needs a persistent browser session
- later: email IMAP/SMTP, instagram DM (via browser automation), CLI/web UI

**4. Tools/MCP (`tools/`)**
- `mcp_client.py` — connect to configured MCP servers (stdio), list tools, expose them to agent loop
- native tools first (filesystem within workspace, memory tools) then MCP servers

**5. Agents (`agents/*.md` or yaml)**
- frontmatter: name, model tier, tools allowed, description; body = system prompt
- face agent, researcher, summarizer, ingestion assistant...

**6. Runner**
- one process on Windows: channels polling + inbox worker; logs like Sales agent; `.env` config; designed so moving to VPS = same code, Linux systemd instead of Windows startup task

### Phases (MVP-first)

Phase 0: skeleton + decisions recorded (MEMORY.md)
Phase 1: Core loop + Telegram channel + filesystem/memory tools + vault skeleton. Milestone: chat from Telegram that can read/write notes about him.
Phase 2: Ingestion pipeline from existing chat exports + sqlite-vec RAG + semantic_search tool. Milestone: ask questions about old conversations.
Phase 3: Model tiers + router + agent configs + subagent spawn. 
Phase 4: MCP client integration; add Playwright/browser, Gmail.
Phase 5: WhatsApp personal channel.
Phase 6: Computer control, Android ADB, more channels; VPS migration when stable.

Also security notes: secrets in .env, vault contains very private data — keep out of git, backups, encryption at rest consideration later; pairing/approval gates for dangerous tools (computer control).

Naming: suggest "jarvis-like" name? Let him decide. Suggest folder `Personal Agent`.

I should present this plan and get approval before any implementation. Also note what happens with Sales agent — untouched, separate repo.

One more honest point re WhatsApp: the realistic risk factors and mitigation (own number, low volume, linked-device protocol e.g. Baileys/whatsapp-web.js, avoid bulk automation). Fine.

Keep response structured but not bloated. Russian language.

Отлично, все три решения зафиксированы. По WhatsApp — короткое честное замечание, потом план.

**Про «имитировать человека в браузере»:** риск бана определяется не столько «человечностью» кликов, сколько тем, что неофициальные клиенты видны на уровне протокола (Baileys/whatsapp-web.js подключаются как «linked device» по протоколу WhatsApp Web — Meta это знает). Реальные факторы риска: массовая рассылка, жалобы контактов, новые девайсы с лавиной сообщений. Для личного номера, который переписывается с тобой и знакомыми в обычном объёме — риск низкий, люди так живут годами. Принимаем: **личный аккаунт, аккуратный темп, без массовых действий**.

---

# План: Personal Agent System (вариант B)

## Архитектура

```
┌─ Каналы (адаптеры) ──────────────────────────────────────────┐
│ Telegram │ WhatsApp (личный) │ CLI/веб │ Email │ Instagram   │
└──────────────┬───────────────────────────────────────────────┘
               ↓  единая очередь входящих (SQLite inbox)
┌─ Ядро ───────────────────────────────────────────────────────┐
│ Router (дешёвая модель): ответить самому / вызвать агента    │
│ Face-агент («лицо», главный диалог)                          │
│ Специалисты = конфиги (.md: модель+промпт+инструменты)       │
│ Provider-слой: уровни моделей fast / mid / smart             │
└──────┬───────────────────────────────┬───────────────────────┘
       ↓ инструменты                   ↓
┌─ Инструменты ─┐          ┌─ Память ──────────────────────────┐
│ нативные      │          │ vault/ — Obsidian-хранилище .md   │
│ MCP-клиент ←──┼──────────│ (источник правды, ты видишь всё)  │
│ filesystem,   │          │ sqlite-vec индекс (перестроимый)  │
│ playwright,   │          │ ingestion: экспорты чатов → .md   │
│ gmail, adb... │          │ инструменты: search/read/write    │
└───────────────┘          └───────────────────────────────────┘
```

Ключевые принципы:
- **Файлы — источник правды**, векторный индекс — кэш, который можно пересобрать. Хранилище открывается в Obsidian как обычное хранилище.
- **Агенты — это данные, а не код**: новый агент = новый .md файл с frontmatter (модель, инструменты, промпт).
- **Плагинность через MCP**: свой коннектор = маленький MCP-сервер на любом языке; экосистема готовых серверов уже есть (реестр проверен: Telegram MTProto ×17, WhatsApp ×21, Gmail ×16, Android ADB ×13, Playwright 36.5k звёзд).
- **ПК→VPS**: никаких абсолютных путей, всё в .env, один долгоживущий процесс, состояние в SQLite/.md. Переезд = тот же код под systemd.
- Sales agent остаётся нетронутым отдельным репо; оттуда переносим паттерны (session coordinator, каналы, логирование), копируя и адаптируя, а не линкуя.

## Структура проекта

```
PersonalAgent/
├── src/
│   ├── runner.py            # один процесс: каналы + воркер inbox
│   ├── core/                # loop, router, agent (tool-loop), providers
│   ├── channels/            # base.py, telegram.py, cli.py, ...
│   ├── tools/               # mcp_client.py, память (search/read/write_note)
│   └── memory/              # indexer.py (sqlite-vec), embedder
├── scripts/                 # ingest_whatsapp.py, ingest_telegram.py, ...
├── agents/                  # face.md, researcher.md, ... (конфиги-агенты)
├── vault/                   # people/, projects/, daily/, topics/, raw/
├── data/                    # agent.db (сессии+inbox+векторный индекс)
├── tests/
└── MEMORY.md                # выученные фиксы и квирки окружения
```

## Этапы (каждый заканчивается работающим артефактом)

| # | Что | Результат |
|---|---|---|
| 1 | Скелет: core loop (перенос паттерна из elen.az) + CLI-канал + Gemini provider | Агент в терминале, читает/пишет vault |
| 2 | Telegram-канал (порт твоего telegram_bot.py) + inbox очередь | Живой чат с телефона |
| 3 | Ingestion экспортов переписок → .md + индексация sqlite-vec + `search_memory` | «Что я обсуждал с X про Y?» работает |
| 4 | Router + уровни моделей + конфиги-агенты (face + первый специалист) | Мультиагентность без изменения ядра |
| 5 | MCP-клиент + первые серверы (filesystem, playwright, gmail) | Подключение инструмента = строка конфига |
| 6 | WhatsApp личный (whatsapp-web.js sidecar или MTProto-MCP) | Основной канал |
| 7 | Контроль ПК, Android через ADB; затем email/Instagram; переезд на VPS | Полное покрытие зрения |

Этапы 4–7 можно менять местами по приоритету. Безопасность с первого дня: секреты только в .env, vault вне Git (+ бэкапы), опасные инструменты (контроль ПК) — только через явное подтверждение.

## Вопрос перед стартом

Осталось одно решение, влияющее на этап 1: **новый проект создаём рядом как отдельный репозиторий** (рекомендую: `Programming\personal-agent`)? Если да — следующим шагом я оформлю детальный план этапа 1 (какие модули, какие интерфейсы, что переносим из Sales agent) на твоё подтверждение, и начнём.

---

