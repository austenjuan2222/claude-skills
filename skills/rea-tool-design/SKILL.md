---
name: rea-tool-design
description: Design or change REA investigation tools, CLI/MCP contracts, provider capabilities, and Evidence semantics.
---

# REA tool design

Use the [tool-design guide](https://github.com/morluto/rea/blob/3c5c887a2cc7371a94fe0fd8b6c478dbf2af60db/docs/tool-design.md) for tool boundaries,
contract semantics, provider ownership, and discoverability. Inspect the current
contract and nearest existing tool relevant to the analyst question; source,
documentation, and live catalogs may describe different versions.

For a design request, return the proposed boundary, input/result shape, Evidence
semantics, nearest alternative, and verification approach. Implement when
requested, preserving the user's scope and existing authorization.

For implementation or verification, consult [testing](https://github.com/morluto/rea/blob/3c5c887a2cc7371a94fe0fd8b6c478dbf2af60db/docs/testing.md)
for the affected consumer and provider lanes, and
[contributing](https://github.com/morluto/rea/blob/3c5c887a2cc7371a94fe0fd8b6c478dbf2af60db/CONTRIBUTING.md) for generated-file ownership. Read
provider/workflow guides only as the task requires.
