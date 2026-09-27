#!/usr/bin/env python3
"""Independent, reproducible verification of the AsyncAPI 3.0 document.

Run this file, don't trust a summary of it. Every check below either passes with printed
evidence or raises/prints FAIL loudly.
"""
import json
import sys
from pathlib import Path

import yaml

# Paths are resolved relative to this file's own location (the contracts/ folder
# of the repo), not hardcoded to the original sandbox layout, so this script runs
# unchanged in CI and on any checkout of the repository.
CONTRACTS_DIR = Path(__file__).resolve().parent
DOC_PATH = CONTRACTS_DIR / "events.asyncapi.yaml"
ENVELOPE_SRC_PATH = CONTRACTS_DIR / "event-envelope.schema.json"
CONNECTOR_HUB_PATH = CONTRACTS_DIR / "connector-hub-e-eventos.md"

errors = []
def check(cond, msg):
    if cond:
        print(f"OK   - {msg}")
    else:
        print(f"FAIL - {msg}")
        errors.append(msg)

# 1. YAML syntax validity (real parse, not eyeballing)
with open(DOC_PATH, "r", encoding="utf-8") as f:
    raw = f.read()
try:
    doc = yaml.safe_load(raw)
    check(True, "YAML parses without error")
except yaml.YAMLError as e:
    print("FAIL - YAML parse error:", e)
    sys.exit(1)

# 2. Top-level required AsyncAPI 3.0 keys
check(doc.get("asyncapi") == "3.0.0", "asyncapi version field == '3.0.0'")
check("info" in doc and "title" in doc["info"] and "version" in doc["info"], "info.title and info.version present")
check("channels" in doc and isinstance(doc["channels"], dict), "channels object present")
check("operations" in doc and isinstance(doc["operations"], dict), "operations object present")
check("components" in doc, "components object present")

# 3. The events from the source-of-truth table (extracted programmatically, not retyped from memory)
with open(CONNECTOR_HUB_PATH, "r", encoding="utf-8") as f:
    md = f.read()

import re
# Extract the catalog table block
start = md.index("## 2. Cat")
end = md.index("## 3.")
table_block = md[start:end]
rows = [l for l in table_block.splitlines() if l.startswith("| `")]
source_events = []
for row in rows:
    cells = [c.strip() for c in row.strip("|").split("|")]
    event_cell = cells[0]
    # event_cell may be like `CampaignApproved` / `CampaignRejected`
    names = re.findall(r"`([A-Za-z]+)`", event_cell)
    source_events.extend(names)

check(len(source_events) == 24,
      f"source table yields 23 rows but 24 distinct event NAMES (CampaignApproved/CampaignRejected share one "
      f"row) -- got {len(source_events)}: {source_events}")

# 4. Every source event has a channel, an operation, and a message in the AsyncAPI doc
channels = doc.get("channels", {})
operations = doc.get("operations", {})
messages = doc.get("components", {}).get("messages", {})

missing_channel = [e for e in source_events if e not in channels]
missing_message = [e for e in source_events if e not in messages]
op_names = set(operations.keys())
# operation names are onXxx-style; verify each event has exactly one operation whose channel $ref points to it
missing_operation = []
for e in source_events:
    found = False
    for op_name, op in operations.items():
        ref = op.get("channel", {}).get("$ref", "")
        if ref == f"#/channels/{e}":
            found = True
            break
    if not found:
        missing_operation.append(e)

check(not missing_channel, f"all 24 events have a channel entry (missing: {missing_channel})")
check(not missing_message, f"all 24 events have a components.messages entry (missing: {missing_message})")
check(not missing_operation, f"all 24 events have an operation referencing their channel (missing: {missing_operation})")
check(len(channels) == 24, f"channels object has exactly 24 entries (got {len(channels)})")
check(len(messages) == 24, f"components.messages has exactly 24 entries (got {len(messages)})")
check(len(operations) == 24, f"operations object has exactly 24 entries (got {len(operations)})")

# 5. Every channel's message $ref resolves to an existing components.messages entry
for cname, cval in channels.items():
    for mkey, mval in cval.get("messages", {}).items():
        ref = mval.get("$ref", "")
        target = ref.split("/")[-1] if ref else None
        check(target in messages, f"channel '{cname}' message ref '{ref}' resolves to components.messages['{target}']")

# 6. Every message payload $ref resolves to the EventEnvelope schema
schemas = doc.get("components", {}).get("schemas", {})
check("EventEnvelope" in schemas, "components.schemas.EventEnvelope is defined")
for mname, mval in messages.items():
    ref = mval.get("payload", {}).get("$ref", "")
    check(ref == "#/components/schemas/EventEnvelope", f"message '{mname}' payload references EventEnvelope (got '{ref}')")

# 7. EventEnvelope schema in the doc matches the real source schema field-for-field
with open(ENVELOPE_SRC_PATH, "r", encoding="utf-8") as f:
    src_envelope = json.load(f)

doc_envelope = schemas["EventEnvelope"]

check(set(doc_envelope["required"]) == set(src_envelope["required"]),
      f"EventEnvelope required fields match source exactly: {sorted(doc_envelope['required'])}")

src_props = set(src_envelope["properties"].keys())
doc_props = set(doc_envelope["properties"].keys())
check(src_props == doc_props, f"EventEnvelope property set matches source exactly (doc={sorted(doc_props)}, src={sorted(src_props)})")

# Deep-check actor sub-object enum
check(doc_envelope["properties"]["actor"]["properties"]["kind"]["enum"] ==
      src_envelope["properties"]["actor"]["properties"]["kind"]["enum"],
      "actor.kind enum matches source exactly")

check(doc_envelope["properties"]["event_type"]["pattern"] == src_envelope["properties"]["event_type"]["pattern"],
      "event_type pattern matches source exactly")

check(doc_envelope["additionalProperties"] == src_envelope["additionalProperties"] == False,
      "additionalProperties: false preserved from source")

# 8. Validate the EventEnvelope schema definition itself is valid JSON Schema (draft 2020-12)
import jsonschema
try:
    jsonschema.Draft202012Validator.check_schema(doc_envelope)
    check(True, "EventEnvelope schema (as embedded in AsyncAPI doc) is a valid Draft 2020-12 JSON Schema")
except jsonschema.exceptions.SchemaError as e:
    print("FAIL - embedded EventEnvelope schema invalid:", e)
    errors.append("embedded schema invalid")

# 9. Validate the worked example payload in CampaignBriefSubmitted against the embedded schema
example = messages["CampaignBriefSubmitted"]["examples"][0]["payload"]
try:
    jsonschema.validate(instance=example, schema=doc_envelope)
    check(True, "CampaignBriefSubmitted worked example validates against embedded EventEnvelope schema")
except jsonschema.exceptions.ValidationError as e:
    print("FAIL - example does not validate:", e)
    errors.append("example invalid")

# 10. Cross-check policy_decision_id "exige" (**exige** or bare "exige") annotations in message summaries
# against the source table, for a sample of the events marked mandatory
mandatory_marked_bold = ["PublicationStarted", "PlatformResourceCreated", "PublicationPartiallyFailed",
                          "CompensationExecuted", "OptimizationApplied"]
for e in mandatory_marked_bold:
    summary = messages[e]["summary"]
    check("**exige**" in summary, f"'{e}' message summary carries **exige** (mandatory policy_decision_id) as in source table")

print()
if errors:
    print(f"=== {len(errors)} CHECK(S) FAILED ===")
    sys.exit(1)
else:
    print(f"=== ALL CHECKS PASSED ({len(source_events)} events verified end-to-end) ===")
