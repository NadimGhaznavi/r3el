# Round-robin optimization

The optimizer visits hidden size, sequence length, batch size, learning rate,
and gamma in schema order, followed by `epsilon_pair` and `reward_pair`, then
wraps to hidden size. Each conversation may change only its assigned single or pair. Before asking the LLM, Ax3l stores the parameter
order and current index as a `round_robin_checkpoint` event in its database.
Restarting during thinking or validation retries resumes that parameter. An
accepted proposal advances the next turn once, even if the MCP reply was lost;
existing startup recovery finishes its simulation and comparison first.
Golden and seed changes preserve position. A changed schema parameter order
requires resetting experiment events before resuming. There is no upgrade path
for old five-entry checkpoints. A fresh experiment starts at hidden size.

Before opening an LLM conversation, Ax3l checks finite schema domains (currently
hidden size, sequence length, batch size, and the 49 reward pairs). If every legal
choice already has a run with the current seed and all other settings unchanged,
it records `parameter_space_exhausted` and advances to the next step. Runs in any
status count as existing choices, matching duplicate-proposal validation. Earlier
seeds and different settings do not exhaust the current domain. Skips survive
restarts and count as completed steps; continuous domains are not skipped.

Seed rotation occurs after `DSnakeLab.SEED_STAGNANT_ROUNDS` (9) complete
round-robin cycles without a new high score. Each cycle includes all seven
entries and counts only once each step has been compared or skipped as exhausted.
A new golden configuration resets the count; a cycle containing an improvement
does not count as stagnant. Rotation increments the seed and reruns the golden
configuration to establish a fresh score baseline. The count survives restarts.

## MCP tools

The SnakeLab MCP entry point is `python -m ax3l.app.snakelab.tools` and uses
stdio. Register domain tool functions in `tools/server.py` with `@mcp.tool()`.
It exposes `submit_single_value(value)` through `SubmitSingleValue`.
Ax3l starts a dedicated MCP session for each conversation, binding its parameter
through `AX3L_CONVERSATION_PARAMETER`. The LLM supplies only a JSON integer or number.
The tool description identifies the assigned parameter and includes its schema rules.
FirstContactSingle and ComparisonSingle include the assigned parameter’s schema description
before requesting a value. Other conversation prompts show its golden value, high score,
and comparable history. MCP rejects strings and booleans as numeric values.
Parameter existence, permitted ranges, duplicates, and submission decisions
belong to Ax3l, not the MCP tool.

`scripts/install-services.sh` generates the installation's `mcp.json` and adds
`--mcp-servers-config` to all three production model commands. It installs the
project requirements in `<app>/.venv`, used by both Ax3l and the MCP child process.
Installation needs Python's venv/pip support and package-index access for this step.
DEV/QA retain their existing health-only LLM stubs.

For a checkout, generate the same configuration with:

```sh
python3 scripts/generate-mcp-config.py --app /opt/dev/ax3l > tmp/mcp.json
```

This unbound configuration supports discovery only. Submission requires an
Ax3l-assigned `AX3L_CONVERSATION_PARAMETER` in the MCP process environment.
The optimization loop configures its own bound MCP sessions automatically.
Pass that file to a llama-server build supporting `--mcp-servers-config`.
llama-server discovers the tool names through MCP. The tool forwards requests
over ZeroMQ using the project-wide `ax3l/zmq/ZMQMsg.py` and `ZMQClient.py`:

```json
{
  "protocol_version": 1,
  "sender": "mcp-snakelab",
  "target": "snakelab",
  "method": "submit_single_value",
  "payload": {"parameter": "learning_rate", "value": 0.003}
}
```

The default endpoint is `DAx3l.ZMQ_ENDPOINT` (`tcp://127.0.0.1:61970`), separate
from Ax3l's HTTP health port. Override it with `AX3L_ZMQ_ENDPOINT` in the MCP
process environment, including through the `env` entry in `mcp.json`.
Ax3l replies with the same envelope shape and an application result in `payload`;
the tool returns that payload as JSON text without changing acceptance or rejection.
`DZMQ.TIMEOUT_SECONDS` bounds send and receive waits. Transport failures propagate
as tool errors; calls are never retried automatically because a timed-out request
may already have been processed. No database or Snake Lab submission occurs in
the tool.

Ax3l starts `ZMQServer` alongside its HTTP health server and keeps it available
while the LLM request runs. Domain dispatch lives in `server/ToolHandler.py`;
SnakeLab validation and submission live in `SubmitSingleValueHandler.py`.
The installer assigns endpoint ports 61968 (DEV), 61969 (QA), and 61970 (PROD)
to both the listener and the generated MCP config. `--zmq-endpoint` overrides
the listener endpoint for manual runs.

The handler verifies the exact payload fields, finite numeric values, parameter
name, and JSON-schema constraints before building a candidate from the golden
configuration. It changes only the selected parameter. A legal but unchanged
configuration is rejected; `SnakeLab.is_config_unique(config)` then checks all
stored runs through `SnakeLabDb`, regardless of status or project version.
Equality compares all 26 numeric columns in `configurations`, including seed,
while ignoring object key order and equivalent numeric representations.

Illegal values return `status: rejected`, `code: invalid_value`, and an
`InvalidValue` prompt. Duplicates return `code: duplicate_config` and a
`NoDupes` prompt. These prompt messages travel back in the MCP result;
the handler does not start a separate LLM conversation. Accepted candidates
return `status: ok` and their submitted `run_id`, with proposal and submission
events logged. Golden selection is unchanged. The listener handles requests
serially; external writers to SnakeLab are outside that serialization boundary.

The single-parameter search space is `hidden_size`, `sequence_length`, `batch_size`,
`learning_rate`, and `gamma`. Each conversation chooses a value for its assigned parameter.
Reward distance values and epsilon initial/decay are tuned in their own pair
entries. Seed and schema-fixed settings cannot be proposed. Comparison histories hold all other settings equal
to the current golden configuration for each parameter.

## Conversation snippets

### Pair MCP tool

`submit_pair_values(value_1, value_2)` forwards a joint proposal to Ax3l.
Bind `AX3L_CONVERSATION_PARAMETER` to `epsilon_pair` or `reward_pair`:

| Assignment | value_1 | value_2 |
| --- | --- | --- |
| epsilon_pair | epsilon.initial | epsilon.decay |
| reward_pair | game.rewards.closer_to_food | game.rewards.further_from_food |

The bound tool description includes these mappings and their schema rules.
The LLM supplies only the two numeric values; the MCP server supplies the pair
identity. Strings and booleans are rejected. Range, integer constraints for
rewards, duplicate checks, and simulation submission belong to Ax3l.
The forwarded ZMQ method is `submit_pair_values`, with payload
`{"pair": "epsilon_pair", "value_1": 0.96, "value_2": 0.97}`.
Replies pass through unchanged and transport errors are not retried.
Unbound sessions permit discovery but reject submissions; single assignments
reject pair submissions and pair assignments reject single submissions.
`SnakeLabTools` discovers and calls the tool for its assigned single or pair.
Ax3l dispatches this method to `SubmitPairValuesHandler`. It validates both
values before reading the golden configuration, changes only the assigned pair
in a copy, validates the full candidate, and rejects unchanged or previously
stored configurations. Either value may remain unchanged if the other changes.
Accepted candidates are submitted once and logged through the shared single/pair
submission workflow. Backend failures propagate without automatic retries.
Both pair entries are active in the round robin. The conversation dispatcher
uses the discovered tool name and argument fields for the assigned entry.

### Active optimization flow

The optimization flow sends text-only prompts. Every conversation starts with
`ProjectContext`, identifying Patrick Loeber's "Train an AI to Play Snake" tutorial
and the LLM's responsibility for choosing parameters. The initial conversation then uses
`FirstContact`, `Comparison`, and `FirstContactSingle()`.
Subsequent conversations use `Comparison` and `ComparisonSingle` to choose the
next single-parameter change from high-score history. Epsilon turns use
`ComparisonEpsilonPair` and `FirstContactEpsilonPair`; reward turns use
`ComparisonRewardPair` and `FirstContactRewardPair`. Each pair turn includes its
report and pair instructions. After seed rotation, the next entry uses the new
golden baseline. `LossPlot` and `ComparisonPlot` are no
longer included, so this flow does not require PNG rendering or a vision model.

`SnakeLab().get_num_sims()` returns the number of rows in Snake Lab's
`simulation_runs` table, across all statuses and including repeated configurations.
Reads use Ax3l's existing `DB_*` credentials and select the `snakelab` database.
Installation grants the Ax3l database user `SELECT` on `snakelab`.*. No separate
SnakeLab credentials are needed. Each call opens and closes its connection without
initializing tables. Simulation submissions still go through SnakeLab's ZMQ API.

At startup, `main-loop.py` checks the simulation count. If it is zero, it
submits the JSON spec's default configuration once and records the submission.
It polls the run through its terminal status and accepts the initial golden config
once its completed score is available. A restart before that acceptance resumes
the recorded initial submission. With an existing golden config it skips seeding.

The report server's `/experiment-highscores` page plots accepted config scores
against the total simulation count at acceptance. The `experiment_highscores`
table stores each score, seed, and count atomically with its golden creation event;
the event supplies the run reference and reason. Seed rotation records the new
baseline even when its score drops. The step line remains flat across unsuccessful
or pending submissions, extending to the current submission count. The page uses
self-contained Plotly JavaScript; reload it to update. A fresh installation starts
an empty history, and wiping events also deletes their score snapshots.

The loop resolves the current golden configuration and submits proposals through
`submit_single_value` or `submit_pair_values`. Each serialized prompt is stored in a `prompt_sent` entry
linked to its conversation, using the same snapshot sent to the model.
Invalid or duplicate proposals receive correction prompts. After an accepted
submission completes, the loop compares high scores, updates the golden
configuration when the score improves, and starts the next conversation.

Raw file capture is off by default. Set `DAx3l.RAW_LOGS_ENABLED = True` in
`ax3l/constants/DAx3l.py` to enable the capture files described below.
When off, no capture output directory or files are created, including under
`/var/lib/ax3l/snakelab`. Database logging continues; status and errors go to the
console (the systemd journal for service runs). Existing captures are retained.

From the checkout root, load the installed database credentials into the
environment, then point the loop at the running model server. For DEV:

```sh
set -a
. prod_etc/ax3l/database.env
set +a
.venv/bin/python -m ax3l.app.snakelab.main-loop --url http://HOST:27770
```

On production, source `/etc/ax3l/database.env` instead. The Python environment
must have the project's PyMySQL dependency installed.

The loop records conversation start/end, prompt snapshots, full reply JSON, and
LLM failures through `DbMgr.log()`. Events share a process ID printed in
`run.log`, and replies link to their prompt events. Reply metrics remain in
the captured JSON for now. Database errors stop the loop.

The active flow continues optimizing until stopped or an error occurs.
Use `--output PATH` to choose the optional capture directory. Service
installations run Ax3l from the installed `.venv`.

Prompt events record the assigned single parameter or pair name in `events.parameter`,
including retry feedback. The Event Log shows a Parameter column and filter when
Prompt is selected; prompt details retain the source and include the parameter.
This schema change requires recreating the event tables; existing tables are not migrated.
