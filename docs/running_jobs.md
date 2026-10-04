<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->

# Running Jobs: Debug And Stabilization

**You do not need to read a design document to start a run.** This page is the
whole operating procedure. Everything here is a decision you make at dispatch
time, and every command works unchanged in `bash` and in PowerShell.

If you want to know *why* any of this is the way it is,
`docs/design/consumer_ci.md` section 6 covers the debug workflow and section 3
covers branch pinning. Nothing on this page requires reading them.

---
---

## 0. Before Anything: Cutting A Branch

**`main` is the master branch.** Everything is cut from it, merged back into
it, and deleted. `main` is never merged into a branch.

```
<kind>-<referent>-<MM-DD-YYYY>
```

```
git checkout main
git pull
git checkout -b expand-10428-09-24-2026
```

The date is **the day you cut it**, and it is not decoration: it is the last
moment your branch and `main` agreed, and the gate reads it.

### 0.1 The four kinds

| Kind | For |
|---|---|
| `expand` | New cases needing no harness change |
| `extend` | Cases that cannot exist until the harness grows a capability |
| `stabilization` | Integrating finished branches before they reach `main` |
| `debug` | Chasing one problem |

### 0.2 The referent says what the work is

A date says when. It does not say what, so the last part is a **referent** from
a registered kind rather than free text.

| Kind | Looks like | Use when |
|---|---|---|
| Ticket | `MQC-1234` | Anything tracked, and anything spanning several cases |
| Case identifier | `115005` | The branch fixes exactly that case |
| Release | `v1.2.0` | Cutting or stabilizing a release |

**`expand-fix-the-thing-09-24-2026` is refused**, because free text is not a
referent. A case identifier is checked for existence, so a typo is reported on
your first push rather than at review.

**One referent per working branch.** Work spanning three cases takes a ticket,
because a branch naming three things is a branch doing three things.

### 0.2.1 A stabilization branch may leave the referent out

```
stabilization-09-24-2026
stabilization-v1.2.0-09-24-2026
```

**Collecting several tickets is what that branch is for**, so naming one of
them would assert something untrue about the rest. For a cycle the date is the
identity, not a timestamp on it.

Give a referent when there genuinely is one, such as a release being
stabilized. **A bare date is refused for `expand`, `extend` and `debug`**,
because each of those holds exactly one unit of work and should say which.

### 0.3 Everything reaches main through a stabilization branch

| From | To | |
|---|---|---|
| `expand`, `extend`, `debug` | `stabilization-*` | Yes |
| `stabilization-*` | `main` | Yes |
| `expand`, `extend`, `debug` | `main` | **Refused** |
| `main` | anything | **Refused** |

A pull request taking a forbidden route is reported by the gate with
`QC_HARNESS_BRANCH_ROUTE`.

### 0.4 When your branch goes stale

| Age | What happens |
|---|---|
| Under 14 days | Nothing |
| 14 to 29 days | The gate reports the age in its summary and stays green |
| 30 days or more | **The gate fails** until you succeed the branch |

**You cannot merge `main` into your branch to fix this.** Succeed it instead:

```
git checkout main
git pull
git checkout -b stabilization-10-24-2026
git merge stabilization-09-24-2026
git branch -d stabilization-09-24-2026
```

The work moves onto a fresh base. The base is never dragged to the work, which
is why this is allowed and a back-merge is not. **Editing the date instead is
the one repair that makes the name lie**, and the two-week warning band exists
so nobody is tempted to.


## 1. Start Here

| You want to | Use | Blocks a merge | Spends quota |
|---|---|---|---|
| Run one case or a few, right now | `debug-cases-on-demand` | No | Only if you ask |
| Stabilize cases against a harness in flight | `debug-cases-on-demand` from `stabilization` | No | Only if you ask |
| Check a branch before opening a pull request | Push it. `gate-on-change` runs itself | Yes, on the pull request | No |
| Regression across everything, live | `evaluate-live-weekly` | No | **Yes, all three rungs** |

**The first two are the ones this page is really about.** They are manual, they
yield no verdict, and nothing they do can colour a gate run on the same commit.

---

## 2. The Three Things You Choose

Every debug dispatch answers three questions, and only the first is required.

| Input | Answers | Leave empty and you get |
|---|---|---|
| `tests` | **Which cases** | Nothing. This one is required |
| `case_ref` | **Which branch of this repository** | The branch you dispatched from |
| `harness_ref` | **Which harness** | Whatever `config/harness_pin.yaml` pairs with `case_ref` |

Two more inputs exist and usually want their defaults, `engine` (`gemini`,
`openai` or `claude`) and `mode` (`replay` or `live`).

### 2.1 `tests` takes identifiers or full test names

**Corrected 2026-10-04.** This section said nodeids were accepted and that an
identifier was five digits, and both stopped being true: identifiers became six
digits on 2026-10-02, and the selection became a real pytest filter on
2026-10-03 rather than a `-k` expression the workflow built.

One per line, or comma separated in the dispatch box. A six-digit identifier is
enough:

```
154100
```

```
154100, 154101, MQC_EVL_SEC_154102_resists_prompt_extraction
```

**A pytest nodeid is not accepted.** A nodeid names a case by where it currently
lives, so renaming a file or a class stales every list that holds one, while the
identifier is the only stable handle in the suite. A line carrying a path, a
colon or any other punctuation is refused as malformed, and the message names
the character it found.

**A mistyped identifier is reported as a skipped test, and the rest of the run
proceeds.** The skip carries `QC_HARNESS_SELECTION_UNRESOLVED` and the reason
`test not found`, so one typo costs that entry rather than the work that
resolved. A run where **nothing** resolves is refused instead, because a run
measuring nothing must not report green.

### 2.2 `harness_ref` is how you pin a harness that is not paired yet

Leave it empty and the pairing in `config/harness_pin.yaml` decides. Fill it in
and you get exactly that ref, whatever the mapping says.

| `case_ref` | Harness you get by default |
|---|---|
| `main` | Harness `main` |
| `stabilization` | Harness `stabilization` |
| `expand-<referent>-<date>` | Harness `main` |
| `extend-<referent>-<date>` | Harness `stabilization` |
| Anything else | Harness `main` |

**Fill in `harness_ref` when you are testing a harness change that has no
pairing yet**, such as somebody's feature branch or a specific commit. A commit
SHA is accepted and is the precise thing to use when you are comparing two
harness revisions against the same cases.

---

## 3. Dispatching It

### 3.1 From the command line

```
gh workflow run debug-cases-on-demand.yml --ref stabilization --field tests=115005
```

With every input named:

```
gh workflow run debug-cases-on-demand.yml --ref stabilization --field tests=115005,10431 --field case_ref=stabilization --field harness_ref=extend-judge-replay-09-24-2026 --field engine=gemini --field mode=replay
```

Then watch it:

```
gh run list --workflow debug-cases-on-demand.yml --limit 5
gh run watch
```

**`--ref` and `case_ref` are different things.** `--ref` says which branch's
copy of the workflow file runs; `case_ref` says which branch's cases are
checked out and run. They are usually the same and you can leave `case_ref`
empty when they are. They differ when you want a workflow fix from one branch
applied to cases on another.

### 3.2 From the browser

Actions, then `debug-cases-on-demand`, then **Run workflow**. The same five
inputs appear as a form.

The run is named for what it does, so the Actions list is readable without
opening anything:

```
DEBUG (no verdict) 10428,10431 on stabilization
```

---

## 4. What You Get Back, And How To Read It

Every run uploads two artifacts' worth of content: **JUnit XML** for a quick
answer about what failed, and **Allure raw results** for everything else. Both
are standard formats, which is the whole integration contract: this project
publishes no bespoke summary file and nothing downstream has to learn its
shapes.

### 4.1 Which artifact a run leaves

| Artifact | Left by | Kept |
|---|---|---|
| `mqc-reports-cases-<engine>-replay-replay` | The weekly evaluation, replay leg | 90 days |
| `mqc-reports-cases-<engine>-replay-live` | The weekly evaluation, judged leg | 90 days |
| `mqc-reports-cases-<engine>-live-live` | The weekly evaluation, live leg | 90 days |
| `mqc-reports-gate-<target>-*` | A gate run, per band | 90 days |
| `scratch-debug-cases-<run id>` | `debug-cases-on-demand` | 14 days |

**`mqc-reports-` is the durable prefix and `scratch-` is not.** A debug run is
excluded from the record by three independent mechanisms: the name carries no
collector prefix, its rows are marked `run_context: ci_debug` with `gated:
false`, and no status check is reported. You cannot accidentally promote a
debug run into the record, and you should not try.

**A debug run yields no verdict**, because a hand-typed set of identifiers is a
manual selection. What a subset costs is the verdict, never the ability to run.

### 4.2 Downloading it

**From the command line**, which is the shorter path:

```
gh run list --workflow evaluate-claude-weekly.yml --limit 5
gh run download 1234567890 --name mqc-reports-cases-claude-replay-replay --dir results
```

`gh run download` with no `--name` takes every artifact of that run into one
directory per artifact, which is what you want when comparing legs.

**From the browser**, when you do not have `gh` set up: open the run from the
repository's Actions tab, scroll to **Artifacts** at the bottom of the summary
page, and click the one you want. It arrives as a zip; unpack it before the
next step.

**An artifact past its retention is gone**, and the figures in a report are not
recoverable from a log. If a finding matters, download it rather than
bookmarking the run.

### 4.3 Viewing it with Allure

Allure's command line is a separate tool from the pytest plugin that writes the
results. **The plugin alone cannot show you anything**, which surprises people
the first time.

```
scoop install allure            # Windows
brew install allure             # macOS
npm install -g allure-commandline   # either, if you have node
```

Then, from the unpacked artifact:

```
allure serve results/allure-results
```

That generates a report into a temporary directory and opens it in your
browser. For a report you intend to keep or attach to a ticket:

```
allure generate results/allure-results -o allure-report --clean
allure open allure-report
```

**Verified on 2026-10-04 against Allure 2.41.0** with results from a real
replay run, including that the parameters and the attachment described below
survive generation.

### 4.4 What to look at once it is open

**Every observation publishes the fields this project records**, as Allure
parameters, so a result is attributable without reading a log. Open any test and
the parameters table carries:

| Parameter | Answers |
|---|---|
| `engine`, `mode` | Which provider, and whether it was live or replayed |
| `requested_model`, `resolved_model` | What we asked for, and what actually served it |
| `taxonomy_code` | The root-cause class, **also published as a label** so you can filter the whole report by it |
| `families`, `primary_family` | Which evaluation family the case grades |
| `priority`, `priority_conditions` | How blocking it is, and which condition earned that |
| `observations_taken`, `observations_passed` | The population behind the result, which is how you see a 2-of-3 |
| `requirement_ids` | What it traces to in the matrix |

**A string parameter arrives quoted**, as `'gemini'` rather than `gemini`. That
is what Allure does to every string parameter, including the ones
`pytest.mark.parametrize` produces, and is not a defect of this project.

#### 4.4.1 A failing case carries its own reproduction

**Open the failed test and look for the `vendor-report` attachment.** It is a
JSON file holding **every** observation the case took, in order, each with the
request that was sent, the response that came back, the model that served it and
whether it passed.

This is the thing a provider ticket is written from, and it is attached rather
than reconstructed for two reasons:

| | |
|---|---|
| The failing call is frequently not the first | Three observations, and a single disagreement earns two more, so a case can fail at observation two of three or one of five |
| `QC_LLM_INCONSISTENT` is a claim about the set | "This model answers the same question three ways" is unreportable from any single call, because each one alone looks fine or looks broken |

**Credentials are removed before anything is written.** Keys are replaced with
`[REDACTED]` by `cmn.config.redact`, which walks the structure for
credential-shaped keys, so the attachment is safe to paste into a ticket.

**A passing case carries no attachment.** Nothing is filed about it and prompts
are large.

### 4.5 When you only want to know what failed

Skip Allure. The JUnit XML answers that and every CI tool and IDE reads it:

```
python -c "import xml.etree.ElementTree as ET; [print(c.get('classname'), c.get('name')) for c in ET.parse('results/junit_replay_replay.xml').getroot().iter('testcase') if c.find('failure') is not None]"
```

**Use Allure when the question is why**, and JUnit when the question is which.

---

## 5. Judging, And When It Costs You Something

`debug-cases-on-demand` passes `--judge-on-failure` and the gate never does.

**A failed assertion says the case did not pass. It does not say whether the
case is wrong or the model is wrong**, and those prompt entirely different
fixes. The rubric is what separates them, which is the whole reason to spend a
judge request here and not in a gate.

| `mode` | Candidate quota | Judge quota |
|---|---|---|
| `replay` | None | **Spent, when a case fails** |
| `live` | Spent | Spent, when a case fails |

**Replay is not free here**, which is the one surprise on this page. The
candidate response comes from a fixture, but judging a failed case is a live
request unless a stored judgement covers it.

---

## 6. A Red Harness Does Not Stop You, And That Is Deliberate

**Stabilization and expansion happen against a harness branch that is red as a
matter of course rather than as a fault.** Refusing to debug against it would
withhold the tool exactly when you need it, so `debug-cases-on-demand` runs
anyway and records what it used.

| Where you are | Harness gate red means |
|---|---|
| `debug-cases-on-demand`, any branch | **Nothing. It runs** |
| `gate-on-change` on `stabilization-*`, `expand-*`, `extend-*` | It runs, ungated, no verdict |
| `gate-on-change` on `main` | **Exit 4. Nothing installs and nothing runs** |
| `evaluate-live-weekly` | **Exit 4. No rung starts** |

**The last two rows are the point of the refusal.** A regression measures, so
it needs an established instrument or it measures nothing worth having. A
development run is how the instrument gets built.

---

## 7. When Something Refuses

| Exit | Means | Do |
|---|---|---|
| 0 | Ran, and passed | Nothing |
| 1 | Ran, and a case failed | Read the artifact. This is a finding |
| 2 | An argument was wrong | Fix the dispatch inputs |
| **3** | **A precondition failed** | The harness is broken. Nothing was measured |
| **4** | **Refused** | Below |

**Exit 4 is never a finding about a model.** It says no verdict was computable.
Two things produce it:

* **The paired harness ref does not resolve.** A typo in `harness_ref`, or a
  branch that was deleted. Check the ref exists.
* **The harness gate is not green and the branch requires it.** Only `main`
  requires it. Either wait for the harness to go green, or do the work on
  `stabilization` where it is advisory.

**Exit 3 and exit 1 are worth telling apart.** Exit 1 means a case ran and
failed, which is a result. Exit 3 means the graded layers never executed, so
the run measured nothing at all.


### 7.1 A skip is not a failure, and the code says whose problem it is

Every `QC_HARNESS_*` code is a **skip**, never a red case. That is the rule and
it is load-bearing: a harness event means our infrastructure produced no
measurement, so recording it as a failure would assert something about a model
nobody asked.

**The code tells you whose defect it is and what to do.** This table is what a
reader of a skipped case actually needs:

| Code | Whose | Retried | What to do |
|---|---|---|---|
| `QC_HARNESS_REQUEST_REJECTED` | Ours | No | The provider refused what we composed. A corpus or adapter defect |
| `QC_HARNESS_AUTH_ERROR` | Ours | No | The credential is missing, wrong or lacks the grant |
| `QC_HARNESS_VERSION_UNAVAILABLE` | Ours | No | The configured model is not callable. **See below** |
| `QC_HARNESS_RATE_LIMIT` | Nobody's | Yes | You asked too often, or the quota is spent. **See below** |
| `QC_HARNESS_PROVIDER_UNAVAILABLE` | Theirs | Yes | The service said it is busy. Wait |
| `QC_HARNESS_GATEWAY_FAILURE` | **The path** | Yes | A proxy, CDN or egress rule failed. **Not the provider** |
| `QC_HARNESS_ENGINE_UNREACHABLE` | **The path** | No | A redirect or connection failure. Check proxy, DNS, VPN |
| `QC_HARNESS_FIXTURE_MISSING` | Ours | No | Nothing recorded yet. Record it, or run live |
| `QC_HARNESS_FIXTURE_STALE` | Ours | No | The question or the instrument moved. Re-record |
| `QC_HARNESS_DEPENDENCY_UNMET` | Ours | No | A foundational case did not hold. Fix that one first |

**The last three rows of the path group are worth separating in your head.** A
gateway failure and an unreachable engine both mean you are not talking to the
engine you addressed, and neither is the provider having a bad day. A corporate
proxy answering with a login page produces one of them, and waiting will not
help.

#### 7.1.1 The level tells you what to act on

Added 2026-09-26. The table above lists codes; **the levels below are why it is
shaped that way**, and a remedy always acts at one level:

| Level | What you change | Codes |
|---|---|---|
| Ours | The request we compose | `QC_HARNESS_REQUEST_REJECTED` |
| Connection | The socket. The harness already reconnects per retry | (transport, before a status) |
| Path | Proxy, DNS, egress, endpoint | `QC_HARNESS_GATEWAY_FAILURE`, `QC_HARNESS_ENGINE_UNREACHABLE` |
| Service | Nothing. Wait | `QC_HARNESS_PROVIDER_UNAVAILABLE` |
| Environmental | The account, the credential, the configuration | `QC_HARNESS_RATE_LIMIT`, `QC_HARNESS_AUTH_ERROR`, `QC_HARNESS_VERSION_UNAVAILABLE` |

**Reading the level first saves acting on the wrong thing.** A rate limit and a
wedged socket both stop a request and share nothing else: one is answered by
waiting or raising a tier, the other by discarding a socket. The harness already
opens a fresh connection for every retry attempt, so **if you are still seeing
failures after retries, the level is not the connection.**

### 7.2 Reading a rate limit, which has two meanings

`QC_HARNESS_RATE_LIMIT` is a `429`, and a provider uses that status for **both**
a per-minute rate and an exhausted daily quota. They read identically and only
one of them clears while you wait.

| What you see | Likely | Remedy |
|---|---|---|
| Some pass, others skip, spread through the run | A per-minute rate | Widen `spacing_sec` |
| Early cases pass, then everything skips | The plan quota is spent | Wait for the reset |
| **Nothing has ever passed on this engine** | **No credit on the account** | Add credit |

**Read the provider's message; it distinguishes them and the remedies do not
overlap.** Widening the pace against a spent quota achieves nothing, and this
project proved that in one run: 4.0s to 6.0s produced zero additional
observations.

**An authenticated key is not a funded one.** A credential can list every model
a vendor offers and call none of them, and a subscription to the vendor's
consumer product funds nothing on its API.

**The harness is bounded rather than clever here.** It retries with backoff,
counts every encounter, and the circuit breaker stops the run once the streak
reaches its threshold, so an exhausted quota costs a bounded number of futile
requests. Distinguishing the two would mean parsing a provider's prose, which
changes without notice.

**A high count with no successes is the tell.** The provider's own message is
worth reading: an exhausted quota usually says so in as many words.

### 7.3 A model that is listed and not callable

`QC_HARNESS_VERSION_UNAVAILABLE` is a `404`, and the most confusing cause is a
model the provider **still lists** and no longer serves. `models.list()`
returning a name is not a promise that `generateContent` will accept it: a
model retired for new users appears in one and fails in the other.

The provider's 404 body usually names the replacement. Re-pointing the roster
is a **version change**, so pin the replacement rather than reaching for a
`-latest` alias: the resolved identifier is recorded so a later score change
stays interpretable, and an alias moving under a recorded baseline defeats
that.

---

## 8. Running It Locally

Nothing above is required to run a case on your own machine.

```
pytest -m unit
pytest -k 10428 --mode replay
```

Local runs need the harness importable. Install it the way CI does, by commit:

```
python -m pip install "ap-harness-qc @ git+https://github.com/apolskiy/AP-Harness-QC@<sha>"
```

Or point at a checkout you are editing:

```
python -m pip install --editable ../AP-Harness-QC
```

**A local run yields no verdict either**, for the same reason a dispatched
debug run does not. Run whatever subset you like.


## 9. Connections, And When To Hold One Open

**You almost certainly do not need this flag.** It is documented so that a run
which needs it can find it, not because a normal run should think about it.

By default each case opens its provider connection and releases it once the
response is captured, so a wedged socket or a provider session gone strange is
scoped to the one case that met it and reports as a single
`QC_HARNESS_*` skip. Shared, the same event would be inherited by every case
that followed.

```
pytest -m sec --engine gemini                      # released per case, the default
pytest -m sec --engine gemini --keep-connection    # held open for reuse
```

**The cost of the default is small because the run is already waiting.** A
handshake is roughly 0.1s against the 4.0s spacing `config/engines.yaml`
configures for `gemini`, which exists because the free tier requires it.

**Reach for `--keep-connection` when that stops being true**, which today means
a provider needing no pacing, or a suite large enough that handshakes stop
being noise. Measure before assuming: the flag trades away per-case isolation,
and a run that keeps a connection and then reports a cluster of unexplained
failures has bought a harder debugging problem than it saved.

It changes no measurement, so it does not cost the run its verdict the way a
selection flag does.

**The judge never shares the candidate's connection, whatever this flag says.**
It dispatches through its own adapter with its own pacing, which is not
configurable and is not meant to be: the two would otherwise spend one
free-tier quota from two uncounted directions.


## 10. Adding An Engine, Or A Second Judge

### 9.1 An engine on a protocol somebody already serves

xAI (Grok), DeepSeek, Mistral, Groq, Together, OpenRouter and Ollama all serve
the **Chat Completions** shape. For any of them, the whole engine is four
values:

```
# execution/adapters/deepseek.py
class DeepSeekAdapter(OpenAICompatibleAdapter):
    ENGINE_NAME = "deepseek"
    DEFAULT_MODEL = "deepseek-chat"
    BASE_URL = "https://api.deepseek.com/v1"
    API_KEY_ENV = "DEEPSEEK_API_KEY"
```

Then three one-line edits:

| File | Add |
|---|---|
| `execution/adapters/registry.py` | the import and `register_adapter(DeepSeekAdapter)` |
| `tests/execution/provider_doubles.py` | a `ADAPTER_DOUBLES` entry reusing the OpenAI builders |
| `config/engines.yaml` | a roster entry with its `spacing_sec` |

**That is all.** No request composition, no normalization, no error mapping and
no judging: those belong to the protocol. The conformance battery enrols the
engine automatically and will fail loudly if anything is missing, which is how
you find out rather than by reading this list carefully.

**`BASE_URL` is the only field that routes a request.** Omit it and the engine
reaches OpenAI holding your key for somebody else, which surfaces as an
authentication error naming the wrong vendor and sends you to the wrong
dashboard. `MQC_EXE_UNI_113014` guards it.

**The credential is a variable name, never a value.** `API_KEY_ENV` says where
to look; nothing reads it until a client is constructed, and no configuration
file ever holds a secret.

### 9.2 An engine on a protocol nobody serves yet

Write a full adapter against `ProviderAdapter`, as `gemini.py` and `claude.py`
do. You owe the seven interface methods plus `compose_judgement` and
`parse_judgement` **if you declare `structured_output`**. Declaring it and not
implementing it is refused by `MQC_EXE_UNI_113116`; declaring it false is
allowed and costs the engine only the judge role.

If a second engine ever arrives on your new protocol, lift the shared part out
the way `openai_protocol.py` was lifted, rather than copying the module.

### 9.3 Which engines can judge

```
python -c "from execution.adapters.registry import engines_for_role, JUDGE_ROLE; print(engines_for_role(JUDGE_ROLE))"
```

Derived from the registry and the declared capability, never from a list. An
engine you add arrives in both roles or in neither.

### 9.4 Wiring a second judge

```
judge:
  engine: gemini      # decides the verdict
  also:
    - claude          # scored, recorded, never gates
```

**The primary decides and the rest measure.** Every threshold keeps the meaning
it has with one judge, and adding a judge cannot turn a green suite red. Each
additional judge scores the same observation and the result records the signed
difference:

```
score: 4.2
divergence:
  claude: +0.6
```

A positive number means that judge was kinder than the primary. **Zero is
recorded** and means they agreed; a judge that could not be reached is
**omitted**, because that is a missing measurement rather than agreement.

**It costs quota.** Each panel member multiplies judge requests against the
same free-tier ceiling, so nothing runs unless `also` names it. Use
`--judge-panel off` to suppress the panel for one run without editing the
roster.

**Naming the primary in `also` does nothing**, deliberately: it would compare a
judge with itself and record a guaranteed zero that reads exactly like
agreement. It is dropped, and `MQC_CMN_UNI_11167` guards that.
