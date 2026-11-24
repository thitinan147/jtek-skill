---
name: jt-agents
description: Keeps the owner's list of reviewers, ~/.config/jtek/agents.json, true to the coding agents and models this machine really has, by running the script's own survey and proposing an ordered list the owner approves. Use when the user types /jt-agents, and only then.
disable-model-invocation: true
---

# jt-agents

jtek prefers a second look from another vendor's model than the author's. `jtek.py reviewer` picks that model from `~/.config/jtek/agents.json`, the owner's list. This skill keeps that list true. It proposes; the owner decides. It never writes the file before the owner says yes.

## What the list is

```json
{"reviewers": [
  {"command": "codex exec -m <model>", "vendor": "openai", "model": "<model>"},
  {"command": "cursor-agent -p --model <model>", "vendor": "xai", "model": "<model>"}
]}
```

- **`command`** starts a session that shares none of the author's conversation. The prompt goes after it. `jtek.py reviewer` prints it and never runs it.
- **`vendor`** is who made the model, not who made the program: an agent that serves several vendors has one entry per model.
- **`model`** is the name the verdict's `--by` carries.
- **The order is the owner's ranking.** The first installed entry of another vendor than the author's reviews. Without one, the first installed entry of the author's own vendor does. With no entry installed, or no file, the reviewer is a fresh session of the author's own model.

The list holds only models the owner trusts to review. A reviewer has to tell a `seen:` line from the run it cites, and a small model misses that, so a model the owner would not trust alone does not belong here, whatever its vendor.

The list chooses which other session reviews. It cannot make the author the reviewer of its own change, and it cannot waive a review: no line in it does either.

## 1. Survey

Run `jtek.py doctor --agents`, from the scripts folder of `jt-work`. It needs no repository. It prints each agent program it found on PATH, how a session is started with it, the models of a program that can list them, and the list as it is now.

It says what it did not check. Do not fill those gaps by guessing:

- **A program with no command that lists models:** read that program's own help or its settings for the names. When you cannot find them, ask the owner.
- **Whether a program is signed in:** ask the owner before you run anything that would use their account. With their yes, start the command once with a prompt that only asks for the word `ok`.
- **An agent the script does not know, or a shell alias:** ask the owner for the real command.

## 2. Ask

Ask at most two questions, each with a few options to pick from:

- Which of the models found the owner trusts to review. Offer the survey's names. Do not rank models from what you remember of them: that goes stale, and the owner knows which ones they pay for and use.
- The order, when more than one is left.

## 3. Propose

Show the owner, in their own language:

- The file as it would be, each entry with where its program was found.
- What you would drop from the present list, and why: the program is gone, or the model is no longer listed.
- What you could not check.

Write `agents.json` only after the owner says yes, and only what they accepted. Then run `jtek.py doctor --agents` again and show its `reviewers:` lines, and run `jtek.py reviewer --vendor <the vendor of your own model>` and show what it picks.

## What this skill does not do

- It does not install an agent, sign in to one, or change its settings.
- It does not put a token, a key, or a password in the file. A command that needs one reads it from where that agent keeps it.
- It does not start a review. `jt-work` and `/jt` do, with the command the script prints.
