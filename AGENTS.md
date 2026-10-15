# Agents

This repo is a crew, not a single prompt. Read `SKILL.md` first.

If you can spawn subagents, spawn one per file in `agents/` and do not let a reader see the composer's tools. Pass only the crop paths and the transcript lines that role is allowed to touch.

If you are one model, announce the role in a heading (`## layout`, `## body-reader`) and finish that role's file before the next heading. Do not transcribe during layout. Do not classify during reading.

The tests in `tests/test_skill.py` are the law for the Python half. Do not weaken them to make a book look finished.
