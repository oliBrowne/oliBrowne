# Tool Experience Report: AutoGen and MetaGPT

**Papers:** Wu et al., *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation*; Hong et al., *MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework* (ICLR '24)
**Tools used:** AutoGen AgentChat 0.7.5 and MetaGPT 0.8.2
**Date of experiments:** 30 September 2026

> **How I ran this.** I used an AI coding assistant to drive the terminal on my Windows machine. It installed the tools, wrote the harnesses and ran them. I kept every command, prompt, raw model response, generated file and test log, and this report is based on those records. No model responses were mocked, and no generated code was edited by hand before testing.

---

## 1. Your Experience Using the Tool

### Setup common to both tools

I had no paid API key. Both papers used GPT-4, but I ran a local model instead: **Qwen2.5-Coder-1.5B-Instruct** (4-bit Q4_K_M GGUF), served by **llama.cpp** as an OpenAI-compatible endpoint on `127.0.0.1`. It ran CPU-only on a Ryzen 7 5800X with 32 GB of RAM, 6 threads and an 8K context. This model is far smaller and weaker than the GPT-4-class models in the papers, so this report is not a reproduction of the papers' numbers. What it *does* test is how much of each framework's value comes from the framework and how much comes from the model behind it.

A smoke test already showed the gap. I asked for "only Python code, no markdown", and the model returned a fenced Markdown block anyway, taking about 14 seconds. Both frameworks later had to deal with this kind of instruction drift.

### The task

I gave both tools the same kind of small but tricky task: `merge_intervals`. The contract has four traps that commonly trip people up:
- Do not mutate the input.
- Do not alias the input's inner lists in the output.
- A contained interval must not shrink its enclosing interval.
- Reversed intervals (`start > end`) must raise `ValueError`.

I wrote independent unit tests *before* any model call and recorded their hashes, so the model could not shape the tests.

### AutoGen

**Install.** Installation was easy. `autogen-agentchat` and `autogen-ext[openai]` installed 28 packages in about 6 seconds once the sandbox allowed network access (the first attempt failed only because of my restricted proxy). The main surprise is that **the AutoGen in the paper no longer exists in that form.** The paper describes `ConversableAgent`, `AssistantAgent`/`UserProxyAgent` pairs and auto-reply hooks. Version 0.7.x is a rewritten, async, layered API (`autogen-core` / `autogen-agentchat` / `autogen-ext`) with `AssistantAgent`, team classes such as `RoundRobinGroupChat`, and pluggable code executors. The concepts carry over, but the paper's code snippets don't.

**Pointing it at a local model.** This worked through the OpenAI client with a `base_url`. The OpenAI client still refuses to start without *some* API key ("Missing credentials"), so I had to pass a placeholder string.

**Friction.**
- `LocalCommandLineCodeExecutor` failed inside my Windows sandbox with `WinError 5` (access denied) when creating subprocess pipes. Run outside the sandbox, it executed `print(sum([1,2,3]))` correctly.
- My own logging code assumed `CommandLineCodeResult` was a Pydantic model, but it is a dataclass. That one was my bug, not AutoGen's.

**What I built.** I used a `RoundRobinGroupChat` with three participants:
1. a **coder** `AssistantAgent` (LLM),
2. a **reviewer** `AssistantAgent` (LLM, told not to write code),
3. a custom **verifier** agent with no LLM, which ran my 11 tests on the coder's latest function through AutoGen's local executor and posted the results into the chat.

The run was capped at 9 turns (3 cycles), with temperature 0.

**What happened** (76.8 s, 6 LLM calls, about 9.3K prompt tokens):

| | Tests passing | Failing tests |
|---|---|---|
| Original buggy code | 8 / 11 | mutation, reversed-interval `ValueError`, nested shrink |
| Coder attempt 1 | 8 / 11 | mutation, `ValueError`, **aliasing (new)** |
| Coder attempt 2 | 8 / 11 | same |
| Coder attempt 3 (identical to 2) | 8 / 11 | same |

The coder fixed the nested-interval bug with `max(...)`. It also introduced a new aliasing bug by seeding the output with `merged = [intervals[0]]`, which is the input's own inner list. It never stopped calling `intervals.sort()` in place and never added validation.

After the verifier posted failing tests, the coder blamed "intervals that share an endpoint". That test was actually passing. It then produced the same code twice.

The **reviewer approved all three versions**, each time saying the code "does not mutate the input… It also raises ValueError". Neither claim was true. The only participant in the conversation that told the truth was the one with no LLM.

AutoGen behaved as described. The conversation loop, turn-taking, termination and executor all worked. The *agents* did not.

### MetaGPT

**Install.** Installation was very hard. It took eight install attempts, and six of them failed:
- The README requires Python `>=3.9,<3.12`. My default was 3.13, so I installed an isolated 3.11.16.
- A plain `install metagpt` made the resolver reject `lancedb==0.4.0`, because that exact pin no longer has a downloadable distribution on PyPI. The resolver then **silently backtracked to MetaGPT 0.1**, which failed while building pandas 1.4.1 from source (`No module named 'pkg_resources'`).
- Pinning `metagpt==0.8.2` was simply unsatisfiable.
- With the lancedb pin overridden, `volcengine-python-sdk` 1.0.x failed to build from source because Windows could not create its extremely long generated file paths.

The version that finally worked used two explicit overrides (`lancedb 0.14.0`, `volcengine-python-sdk 4.0.12`) and installed 218 packages. The dependency checker still flags both overrides as incompatible. I never tested the cloud and vector-store features those packages back.

**Configuration.** Configuration lives in `~/.metagpt/config2.yaml`. I didn't want to write into my home directory, so the harness pointed `metagpt.const.CONFIG_ROOT` at a local folder before importing the config. Plugging in the local endpoint was otherwise simple (`api_type: openai`, `base_url`, a placeholder key).

**What I built.** I did **not** run MetaGPT's built-in "software company" pipeline (Product Manager → Architect → Project Manager → Engineer → QA). Instead, following the official *MultiAgent 101* tutorial, I built a two-role `Team`:
- an `Implementer` with a `WriteModule` action that `_watch`es `UserRequirement`,
- a `Reviewer` with a `ReviewModule` action that `_watch`es `WriteModule`.

This does exercise MetaGPT's real Role/Action/publish-subscribe routing. It does *not* exercise the SOP documents (PRD, system design, API spec) that are the paper's main contribution, so my conclusions about the full pipeline are limited.

**What happened.** The team ran in 4.65 s: 2 LLM calls, the writer taking 3.4 s and the reviewer 1.1 s. The whole process took about 12 s, roughly 6 s of which was importing MetaGPT. The task asked for **tuples**. The generated code:
- sorted the input in place (`intervals.sort(...)`),
- appended the input's own tuples to the output,
- tried `merged[-1][1] = ...` on a tuple.

It passed **3 of 10** tests: 2 assertion failures (no `ValueError` for reversed intervals) and 5 `TypeError: 'tuple' object does not support item assignment` errors. A separate probe confirmed the input was mutated. The Reviewer's entire output was **`PASS`**.

---

## 2. Strengths

**AutoGen**
- **Mixing LLM and non-LLM participants in one conversation works well.** Because the verifier was just another agent in the group chat, I could put a deterministic, trustworthy participant directly inside the loop. This was the most useful design choice I saw, and it's what the paper means by "conversation programming". In my run it was also the *only* part that produced correct information.
- **The local model was easy to swap in.** One `OpenAIChatCompletionClient(base_url=...)` call was enough, and all agents ran on a local model with no code changes.
- **Observability is good.** Every message has a source, type and timestamp, token usage is reported per agent, and the stop reason ("Maximum number of turns 9 reached") is explicit. That made it easy to write the failure analysis above.
- **Setup was light.** It installed in seconds with a small dependency tree.

**MetaGPT**
- **The role/action/watch model is clear and declarative.** "The Reviewer watches `WriteModule`" is a one-line way to express a workflow. Routing is driven by message *type*, not hard-coded turn order, which is exactly the paper's publish-subscribe message pool. It worked right away once installed.
- **Latency was low.** It needed only as many calls as there were roles, with no conversational back-and-forth, so the team ran in under 5 s against AutoGen's 77 s. For a pipeline with fixed stages, that structure saves tokens and time.
- **The team-level budget is built in.** `team.invest(...)` and cost tracking are part of the framework. That's a sensible choice for pipelines that can grow expensive.
- **It ships a lot.** Tool schemas for data science (encoders, scalers, feature selection), web scraping and more come bundled, so the framework is much broader than the paper.

---

## 3. Weaknesses

**Shared by both: an LLM "reviewer" is not verification.** Both papers present role specialisation (coder/reviewer, engineer/QA) as a source of quality. In both of my runs the reviewer confidently approved broken code. With AutoGen it did so three times in a row, even with failing test output directly above it in the conversation. The only thing that caught the bugs was executed tests. MetaGPT's paper actually agrees with this: its ablation credits *executable feedback* for a meaningful part of the gain. But nothing in either framework's defaults stops you from building a review loop that has no execution in it.

**AutoGen**
- **The API has changed a lot since the paper**, so the paper is now more of a concept document than documentation. Tutorials written for 0.2 don't run on 0.7.
- **Repair loops don't break out of repetition.** The coder produced the same wrong function twice after a clear test failure, and the framework has no built-in way to notice that. "Conversation" does not by itself give you error correction.
- **Running code on Windows depends on the platform.** The local executor needs subprocess pipes, which my sandbox blocked. The recommended alternative is a Docker executor, which is heavier.
- **A failed run can still exit with code 0.** My harness exited 0 while logging `status: fail`. That was my fault, but the framework makes it easy to confuse "the conversation finished" with "the task succeeded".

**MetaGPT**
- **The packaging is fragile.** Exact pins (`lancedb==0.4.0`), a Python ceiling below 3.12, and heavy optional cloud SDKs in the core install made it effectively uninstallable without manual overrides. The resolver quietly falling back to version 0.1 is especially bad, because a less careful user would end up with a completely different tool without noticing.
- **The install is huge for what I used.** It pulled in 218 packages to run two prompts.
- **No execution happens by default in a custom team.** Nothing ran the generated code, so `PASS` went unchallenged. The paper's executable-feedback loop belongs to its Engineer role, not to the Team abstraction.
- **It's built for large-context models.** The SOP pipeline passes long structured documents between roles. With an 8K-context, 1.5B model I scoped down to two roles. The framework offers no "lite" mode for small or local models.

---

## 4. Potential for Practical Impact

**How it could change practice.** Both tools turn *LLM workflows into software artifacts*: versionable, testable and composable. AutoGen's biggest practical contribution is the idea of mixing humans, tools and LLMs as equal conversation participants. You can see it in how today's agent frameworks let a test runner, a human approver or a linter take a turn. MetaGPT's contribution is the argument that **structured intermediate artifacts** (PRDs, interface specs) reduce the hallucination cascade you get from free-form chat. That idea now shows up in spec-driven coding assistants.

**Who benefits.**
- *AutoGen:* researchers and platform teams prototyping new multi-agent patterns, and teams that need human-in-the-loop approval steps (data analysis, ops runbooks).
- *MetaGPT:* startups and solo developers who want a scaffolded greenfield prototype, such as a CLI game or a CRUD app, from a one-line requirement. Also educators who want to *show* students what a PRD and design document look like.

**Barriers to adoption.**
1. **Trust.** My runs show why. A reviewer agent that approves broken code is worse than no reviewer, because it creates false confidence. Organisations will need deterministic gates (tests, type checkers, static analysis) inside the loop, and those gates do the real quality work.
2. **Cost and scale.** Multi-agent chat multiplies tokens. AutoGen used about 9K prompt tokens on a 10-line function. With frontier models at real scale, per-task cost and latency grow quickly.
3. **Maintainability.** AutoGen's rewrite and MetaGPT's dependency rot mean an agent pipeline built today may not install in a year. That's a real risk for any company building on them.
4. **Policy and security.** Both tools run LLM-generated code, and on Windows that ran into sandboxing immediately. Enterprises will want containerised executors and audit trails by default.
5. **Model dependence.** Both frameworks assume a GPT-4-class model. Teams that must run locally for privacy won't get the published behaviour.

---

## 5. Reflection and Recommendations

**What I learned by using the tools, not just reading the papers.**
- **The framework is the easy part; verification is the hard part.** Both frameworks did exactly what they promised: messages were routed, roles acted, the conversation ended cleanly. Every *quality* failure came from the agents. The papers' results mix the two together, because a GPT-4 reviewer is much more reliable than a 1.5B one. Using the tools separated "the orchestration works" from "the orchestration makes the output correct", and the second claim depends heavily on the model.
- **Adding more agents can make things worse.** In AutoGen, adding a reviewer added an extra, confident, *wrong* voice to the conversation. It never corrected anything. One coder with a test runner would likely have done just as well, faster and cheaper.
- **Running the same task side by side showed the structural difference clearly.** AutoGen's loop did 6 calls in 77 s and could, in principle, recover. MetaGPT's pipeline did 2 calls in 5 s and had no recovery path at all. Neither paper frames this trade-off as directly as running them together did.
- **Reproducibility of the tools themselves is a research problem.** A two-year-old ICLR artifact couldn't be installed without overrides. The papers don't mention this, but anyone trying to build on them runs into it immediately.

**One recommendation each.**
- **AutoGen:** add a **built-in "stagnation guard"** for repair loops. It would detect when an agent re-emits semantically identical code after a failure, then either stop, escalate to a human, or inject the diff between the failing and expected behaviour. My coder wasted a third of the run repeating itself.
- **MetaGPT:** make **executable verification a default step of every code-producing Team**, not only of the built-in Engineer role, and **fix the packaging**. Move cloud and vector SDKs into optional extras and replace exact pins with ranges, so a fresh `install metagpt` gets the current version and cannot quietly fall back to version 0.1.

---

### Evidence summary

| | AutoGen 0.7.5 | MetaGPT 0.8.2 |
|---|---|---|
| Install attempts / failures | 2 / 1 (network only) | 8 / 6 |
| Packages installed | 28 | 218 (+2 overrides) |
| Python | 3.13 | 3.11 (requires < 3.12) |
| Roles | coder, reviewer, non-LLM verifier | Implementer, Reviewer |
| LLM calls / wall time | 6 / 76.8 s | 2 / 4.65 s (team) |
| Final tests passing | 8 / 11 (unchanged from baseline) | 3 / 10 |
| Reviewer verdict | "correct" ×3 (wrong) | `PASS` (wrong) |
| Task outcome | Fail | Fail |
