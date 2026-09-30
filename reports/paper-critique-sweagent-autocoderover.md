# Paper Critique: SWE-agent and AutoCodeRover

**Papers:**
- Yang et al., *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*, NeurIPS '24
- Zhang et al., *AutoCodeRover: Autonomous Program Improvement*, ISSTA '24

Both papers tackle the same problem: given a real GitHub issue and its repository, produce a patch that makes the hidden tests pass (SWE-bench). They reach opposite conclusions about **what the LLM should be given**:
- SWE-agent gives it a carefully designed *interactive environment*.
- AutoCodeRover gives it *program-analysis tools* inside a fixed two-phase workflow.

To ground this critique, I also ran the current open-source release of each tool on a small bug. I used a local 1.5B-parameter model (Qwen2.5-Coder, 4-bit) instead of GPT-4, so those runs can't say anything about the papers' success rates. They do show which parts of each design are robust and which depend on the model. I note these observations where they are relevant.

---

## 1. What I liked

**The problem is the right one.** Before SWE-bench, "LLMs for code" mostly meant writing one function from a docstring (HumanEval). Both papers take on the task developers actually do: read a vague bug report, find the relevant code in a large repo, and change it without breaking anything. That shift is why this line of work matters.

**SWE-agent's central idea is new and, I think, correct.** The LM is a *new kind of user* and deserves its own interface, an **Agent-Computer Interface (ACI)**, in the same way HCI designs interfaces for humans. The design principles are concrete and testable:
- Actions should be simple and compact: `open`, `goto`, `scroll`, `search_file`, `edit start:end`.
- Feedback should be concise and informative: a 100-line window with line numbers, and "no output" messages instead of silence.
- **Guardrails** should stop errors from spreading: the edit command runs a linter and *rejects* syntactically invalid edits.
- Context should be managed: old observations collapse to one line.

The ablations are the most convincing part of the paper. Holding the model fixed, changing the interface alone moves the resolve rate by several points. For example, the linting guardrail and the windowed file viewer each matter, and the plain shell baseline does far worse. That turns "prompt engineering" into something closer to interface *engineering*. The most interesting point is that **interface design for LMs is not the same as for humans**: a longer window is not better, and search that returns *too many* results hurts.

In my run, the edit guardrail worked exactly as described even with no LLM involved. An invalid edit produced an `E999 SyntaxError`, the edit was rejected, and the file was restored byte for byte.

**AutoCodeRover's central idea is equally strong, and cheaper.** Treat the repository as a **program, not a pile of text files**. Instead of `grep` and scrolling, the LLM calls AST-aware APIs: `search_class`, `search_method_in_class`, `search_code_in_file`, and so on. It gathers context in stratified rounds, then writes a patch. When tests exist, it adds **spectrum-based fault localization (SBFL)**, a classic APR technique, as an extra signal. This brings decades of software engineering research (fault localization, program structure) into the LLM era instead of rediscovering it. It also reports solving a comparable or higher share of SWE-bench Lite (about 19%) at a reported cost of about $0.43 per issue.

My test repository included two classes that both have a method named `split` (`Batcher.split` and `TextFormatter.split`). `search_method_in_class("split", "Batcher")` found exactly the right one. That's the case where plain `grep` misleads an agent.

**Is it going to work, who wants it, and when?** For well-specified bugs in well-tested Python repos, yes. It already partly works: descendants of both systems power commercial coding agents, and SWE-bench scores have risen far past these papers' numbers since. The people who want it are maintainers with long issue backlogs and companies with large internal codebases and CI. The missing pieces are trustworthy verification, integration with real issue trackers and CI, and cost control. For narrow bug classes it's here now; for "assign any ticket to an agent" it's still a few years off.

**Most controversial points.**
1. SWE-agent argues that the *interface*, not the model, is the main lever. AutoCodeRover argues that *program analysis and workflow structure* are the lever, and that a free-form agent loop is wasteful. They can't both be the main factor. The field has since mixed the two.
2. AutoCodeRover compares itself favourably with SWE-agent partly on cost and on "correct vs. plausible" patches. Those comparisons use different models, budgets and evaluation settings, so they are debatable.

---

## 2. What I disliked

**Both papers are evaluated almost entirely on SWE-bench, which has known validity problems.** SWE-bench issues come from popular public Python repos that the models may have seen in pre-training, and some "resolved" tasks pass weak tests with incorrect patches. AutoCodeRover deserves credit for at least manually inspecting whether its patches are *semantically* correct, not just test-passing, but it is still one benchmark and one language. Neither paper evaluates on private or post-cutoff repositories.

**"% resolved" hides the variance.** Results are reported for single runs at temperature 0 with a single model. With about 300 tasks in SWE-bench Lite, a 1–2 point difference is only a handful of issues. Confidence intervals and repeated runs are missing.

**The comparisons aren't controlled.** SWE-agent's main results use GPT-4 Turbo with a per-issue budget. AutoCodeRover uses GPT-4 with its own retry policy. Their headline numbers (about 18% and about 19% on Lite) are then compared across papers with different models, prompts and budgets. The *methods* are never compared on the same model.

**SWE-agent's ACI is tuned for one model family, and the paper under-sells how fragile it is.** The interface depends on the LM emitting *exactly one* well-formed command per turn. The authors acknowledge the prompts were iterated on GPT-4. My run shows what happens without a strong model:
- All three responses from my local model were a multi-command script with comments.
- It opened the wrong path (`fixture/stats.py` when the working directory was already `/fixture`).
- It invented an edit range `12:18` for an 8-line file.
- The command parser then **dropped the entire body of the heredoc edit**. The command that actually ran lost everything between `edit 12:18` and `end_of_edit`. It hung for 30 seconds three times until the agent stopped itself.

So the ACI's benefits only appear once the model can use the interface correctly. That's a real limit on the paper's claim that "the interface is what matters".

**AutoCodeRover's workflow is rigid, and its tools depend on the platform.** The fixed "search, then patch" pipeline assumes the issue gives enough clues to guide the search. The paper doesn't really handle issues where the bug is far from anything named in the text. In my run, the AST search APIs mostly worked, but I also found two problems:
- `search_method("split")` reported **4 matches for 2 definitions**.
- `search_code` crashed on Windows because it uses Unix-only `signal.SIGALRM`.

These are engineering issues, not flaws in the idea. But the paper presents the tools as a reliable foundation, and the whole approach depends on their precision.

**The artifacts don't match the papers any more.** Both repositories have moved on significantly:
- SWE-agent 1.x now runs through a separate SWE-ReX runtime. My failed run ended with a version-mismatch crash (`RemoteDeployment.is_alive() got an unexpected keyword argument 'timeout'`).
- AutoCodeRover's current main branch has a reproducer-generation stage that isn't in the ISSTA paper. When run on a local issue, it stopped with `NotImplementedError: PlainTask.execute_reproducer`, and **still exited with code 0** and printed a cost estimate. For papers that are largely about systems, it's a problem that the artifact reviewers evaluated is hard to recover.

**How the test oracle is used could be clearer.** AutoCodeRover uses SBFL "when tests are available", and SWE-agent lets the agent write and run reproduction scripts. SWE-bench *has* tests, but the fail-to-pass tests are hidden. It takes careful reading to be sure no hidden-test information leaks into localization. The papers should state this boundary more plainly.

---

## 3. Future directions for this research

**The authors' own directions:**
- SWE-agent: extend ACIs to other domains (web, data science), learn interfaces automatically, and give agents better navigation and editing tools.
- AutoCodeRover: stronger fault localization, test generation and reproduction (since added in later versions), and broader languages and benchmarks.

**Ideas I came up with while reading and using the tools:**

1. **Combine the two: an ACI whose navigation actions are AutoCodeRover's AST queries.** SWE-agent showed that *how* information is shown matters; AutoCodeRover showed that *what* is retrieved should be structural. An interface with `open_method Batcher.split`, `callers_of X` and `tests_covering Y`, together with SWE-agent's guardrails and windowing, could get the benefits of both. Many later systems move in this direction, but a controlled ablation (same model, both interfaces) is still worth doing.

2. **Make the interface adapt to model capability.** My small model couldn't follow "one command per turn". Rather than requiring a strong model, the ACI could *enforce* its own contract: use constrained decoding or JSON function-calling, and reject or split multi-command responses with a helpful error. That would be a guardrail for the *action format*, the same way the linter is a guardrail for code. It could make these agents usable with small local models, which matters for privacy-sensitive companies.

3. **Apply the idea to other problems.** Could the same approach cover **security vulnerability repair** (using taint-analysis APIs), **dependency upgrades and API migrations** (with a "find all call sites of deprecated API" action), or **flaky-test diagnosis**? AutoCodeRover's structure-aware search in particular seems well suited to large refactorings.

4. **Solve the same problem differently.** Agentless-style pipelines (localize, repair, validate, with no agent loop) later showed that much of the gain doesn't need agent autonomy at all. A fair study of *how much autonomy is actually needed* for each class of issue would be valuable.

5. **Run bigger and harder evaluations:**
   - Repositories created after the model's training cutoff (to control for contamination).
   - Languages other than Python (Java would suit AutoCodeRover's roots in program analysis).
   - Repeated runs with confidence intervals.
   - Measuring *semantic* correctness against developer patches, not only test pass rates.
   - A **cost-normalized** comparison: success per dollar and per minute on the same model.

6. **Put humans in the loop.** Neither paper measures whether developers *accept* these patches, or how long reviewing an agent's patch takes compared with writing it. A user study with maintainers would tell us whether 19% resolution saves real time.

---

## 4. Open questions

1. **How much of SWE-agent's gain is the ACI, and how much is GPT-4 having learned shell and editor conventions?** Would the ACI ablations look the same with an open-weights model, or with one fine-tuned on the ACI? My run suggests the ACI's benefit depends heavily on the model, but that's one data point.
2. **Is the "LM as a user" analogy literally true?** Human interface design uses user studies, cognitive-load models and error taxonomies. What is the equivalent for an LM? Could interfaces be *optimized automatically* against a benchmark, or would that just overfit SWE-bench?
3. **How good is AutoCodeRover's search really?** When localization fails, is it because the search APIs returned the wrong thing, or because the LLM asked the wrong questions? The paper reports overall localization accuracy but separates these causes only partly. The duplicate matches I saw make me wonder how often imprecise tool output misleads the model.
4. **What counts as a *correct* fix?** Both papers use test passing as the oracle. If a patch passes the tests but differs in meaning from the developer's patch, is it wrong or just different? How should overfitting to weak tests be handled?
5. **How do these systems fail on issues with no clear location**, such as performance bugs, concurrency bugs, or configuration and build issues?
6. **How safe is it to let an agent run arbitrary shell commands?** SWE-agent executes model-generated commands in a container. My setup needed a bubblewrap sandbox inside WSL to feel safe. What is the right isolation model for deployment inside a company?
7. **Are SWE-bench-style "issue → patch" tasks representative of real maintenance?** Many real issues are feature requests, duplicates, or need a design discussion before any code is written.

---

## 5. Most important for class discussion

1. **Interface vs. analysis vs. model: where does the improvement really come from?** I'd like to discuss the two papers side by side. SWE-agent says "better interface", AutoCodeRover says "better program analysis + workflow", and the uncomfortable third option is "better model". What experiment would separate these three cleanly?
2. **Benchmark validity.** How much should we trust SWE-bench numbers given contamination, weak tests and single-run reporting? What should the minimum evaluation standard be for agent papers?
3. **Robustness and reproducibility of agent artifacts.** In my hands-on runs, *neither* tool produced a patch. The causes were a mix of the weak model and fragility in the frameworks: a parser that dropped an edit body, a runtime version mismatch, an unimplemented task mode, and exit code 0 on failure. What responsibility do SE researchers have to keep agent systems runnable, and how should reviewers evaluate artifacts that depend on a moving API?
4. **Autonomy vs. structure.** Is a free-roaming agent (SWE-agent) or a fixed, analysis-driven pipeline (AutoCodeRover) the better foundation for production tools? I'd like the professor's view on where industry is heading.
5. **The developer's role.** If agents resolve 20–50% of well-specified issues, does the maintainer's job shift from writing fixes to *specifying and verifying* them? What skills should SE education emphasize in response?

---

## 6. Summary

Both papers show that **LLMs get much better at repository-level bug fixing when they are given the right tools instead of just a bigger prompt.**

- **SWE-agent's lesson:** the *interface* between the model and the computer is a first-class design problem. Compact actions, concise feedback, guardrails and context management make a measurable difference with the model held fixed.
- **AutoCodeRover's lesson:** decades of program-analysis research (AST-level code search, spectrum-based fault localization) still matter. They make LLM repair cheaper and more targeted than treating code as plain text.

My main takeaway is that **these designs amplify a capable model but don't replace one.** Both are evaluated narrowly (one benchmark, one language, single runs, GPT-4) and their artifacts have drifted since publication. Used with a small local model, neither tool fixed an easy bug. Some of the failures were the model's. Others were the tools': an edit body lost by the command parser, a runtime version mismatch, an unimplemented task mode, and a success exit code on failure.

The lasting contribution is the principle: **design the agent's environment as carefully as you would design a tool for a human developer, and ground it in real program structure.** The numbers will keep changing; that principle is likely to hold.
