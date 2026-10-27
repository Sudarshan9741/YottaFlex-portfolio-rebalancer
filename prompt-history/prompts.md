# AI prompt history

## Disclosure
This project was assembled with AI assistance. This file records the project-building prompts used in this ChatGPT conversation. If any other AI tool is used later, append every prompt sent to it, including follow-up/debugging prompts. Do not claim this file covers tools that were not used.

## Prompt 1 — Initial requirements summary
> hey this is the project statement tell me in simple an dshort format

Purpose: summarize the provided YottaFlex business requirements into a manageable project scope.

## Prompt 2 — Project implementation request
> do the complete project and give me in zip file

Purpose: request a runnable implementation and packaged ZIP artifact.

## Implementation disclosure
AI assistance was used to draft the generator, API, business-rule engine, user interface, tests, and documentation. The candidate must run the app and tests, inspect generated data and decisions, review the implementation, and add any further prompts they use. This record is not a substitute for understanding or independently validating the code.
## Prompt 3 — Runtime validation and repair
> Inspect the entire YottaFlex Portfolio Rebalancing System workspace, set up and run the Python application, verify the business logic and deterministic data generator, test the API and dashboard, add missing tests, fix evidenced failures, and report exact startup commands, results, limitations, and submission readiness without claiming unverified success.

Purpose: perform an evidence-based runtime, generator, business-rule, API, test, documentation, and security-readiness review while preserving the existing implementation.

## Prompt 4 — Complete remaining requirements
> Act as a senior Python engineer and QA engineer. Complete all remaining requirements in my existing YottaFlex AI Portfolio Rebalancing System. Implement drift-tolerance policy, explicit SQL integrity constraints with SQLite foreign-key enforcement, isolated tests for all five anomaly scenarios, complete automated/API/dashboard verification, full-scale deterministic reproducibility checks, documentation updates, AI disclosure, `.gitignore` review, and Git preparation without publishing or pushing anything without permission.

Purpose: close the remaining assessment requirements in the existing implementation. This task used AI assistance to modify the drift policy, constrained SQL seed/event persistence, tests, documentation, and validation workflow. No additional AI tools were used for this task.

## Prompt 5 — Browser visual and functional testing

The following is the original prompt recovered verbatim from the current conversation:

> Perform visual and functional browser testing of my existing YottaFlex AI Portfolio Rebalancing System.
>
> The FastAPI backend and API tests already pass. Now verify the actual dashboard in a browser.
>
> ### Tasks
>
> 1. Inspect the current project and identify the correct startup command.
> 2. Start the application and confirm it is accessible at http://127.0.0.1:8000/.
> 3. Use browser automation if available, such as Playwright or an existing browser-testing tool. Avoid adding unnecessary dependencies.
> 4. Open the dashboard and check for:
>
> - Page loads without a blank screen or JavaScript errors.
> - Portfolio selection works.
> - Current and target allocations and drift values display correctly.
> - Rebalance proposals can be generated.
> - Proposed trades and estimated fees are displayed.
> - Exceptions and warnings appear for relevant cases.
> - Loading, empty, and API error states are handled sensibly.
> - Layout remains usable at desktop and mobile viewport sizes.
> 5. Inspect the browser console and network requests for errors.
> 6. Fix genuine UI or API integration bugs in the existing code.
> 7. Rerun the relevant backend tests after making changes.
> 8. Capture screenshots of the working dashboard if screenshot capability is available.
>
> ### Evidence requirements
>
> - Do not claim browser testing passed unless you actually opened and tested the application in a browser.
> - If browser automation is unavailable, tell me exactly what tool or capability is missing and give me manual test steps.
> - Do not claim screenshots exist unless you actually saved them.
> - Summarize each test as PASS, FAIL, or NOT TESTED.
> Start now and complete the testing in the current workspace.

Purpose: perform real browser testing of the desktop and mobile dashboard, including API failure and exception-rendering behavior.

## Prompt 6 — Final prompt-history audit

The following is the original prompt recovered verbatim from the current conversation:

> Perform the final audit of prompt-history/prompts.md for my YottaFlex AI recruitment assignment.
>
> 1. Read the complete existing prompt-history file.
> 2. Compare it against all project-related prompts and AI interactions available in the current workspace and records.
> 3. Include the original prompts for project creation, debugging, validation, business-rule improvements, automated testing, reproducibility checks, browser testing, and final audits wherever the original text is available.
> 4. Preserve verbatim wording when the original prompt is available. Clearly label reconstructed or summarized prompts.
> 5. Include the latest browser-testing prompt used to verify desktop/mobile layouts, portfolio selection, proposal generation, exception rendering, and API failure handling.
> 6. Add an honest AI-use disclosure describing AI assistance and the checks I personally need to understand and review.
> 7. Do not invent missing prompts or claim that inaccessible conversations were checked.
> 8. Identify any missing original prompts that I need to recover or supply.
> 9. Save the updated file and verify that it is readable.
> Do not make a Git commit or publish the repository. Finish by reporting exactly what was recovered, what was reconstructed, and what remains missing.

Purpose: audit this prompt history for completeness and distinguish recovered wording from summaries.

## Recovered original project prompt

The initial large project prompt is available verbatim in the current conversation. It requested workspace inspection, setup and execution, business-logic verification, deterministic generation, expanded testing, API/dashboard validation, documentation readiness, prompt-history maintenance, and no GitHub publication without permission. The existing Prompt 3 entry above is a condensed reconstruction and is not a verbatim transcript of that longer message.

The full Prompt 4 wording is also available verbatim in the current conversation. The existing Prompt 4 entry above is a condensed reconstruction; its exact requirements were to implement drift tolerance, explicit SQL integrity constraints and SQLite foreign-key enforcement, isolated tests for all five anomaly scenarios, complete automated/API/dashboard verification, full-scale deterministic reproducibility checks, documentation and AI disclosure updates, `.gitignore` review, and local Git preparation without publishing or pushing without permission. The original Prompt 4 text is not repeated a second time in this file to avoid maintaining two copies that could diverge.

## Reconstructed or summarized entries

- **Prompt 1** and **Prompt 2** preserve the wording available in the existing file. Their purposes are summaries.
- **Prompt 3** and **Prompt 4** were already present in this file as condensed summaries before this audit. Their purpose descriptions and quoted text are reconstructed summaries, not verbatim transcripts; the longer originals remain available in the current conversation context but were not duplicated here.
- The exact original text for **Prompt 5** and **Prompt 6** was available in the current conversation and is included above.
- No separate original debugging-only prompt, automated-testing-only prompt, or reproducibility-only prompt was found in the accessible workspace records. Those topics were included within the larger project prompts and validation prompts; no additional wording is invented here.

## Honest AI-use disclosure

AI assistance was used to draft and modify the generator, data validation, rebalancing engine, SQLite persistence, FastAPI application, dashboard, tests, documentation, and prompt-history content. AI-assisted validation included Python execution, pytest, compilation, API smoke tests, deterministic full-scale generation, SQLite integrity checks, and browser automation. The browser checks used the available integrated Playwright tooling; no additional browser dependency was added.

The candidate must personally review and understand the source code, allocation and drift formulas, tolerance semantics, trade and fee rules, anomaly handling, SQL constraints and migration behavior, generator validation, API behavior, dashboard behavior, test assertions, generated outputs, and documented limitations before submission. The candidate must also verify that this record accurately reflects all other AI tools or conversations they used. Any prompts sent to other tools or inaccessible conversations are not represented here.

## Audit boundary and missing records

This audit compared the complete existing file with the project files in the current workspace and the project-related prompts visible in the current conversation. No claim is made about inaccessible sessions, deleted conversations, external AI tools, or unshared prompt logs. The candidate should supply or append the exact original wording for any such missing interactions, especially:

1. Any original prompt that created the initial ZIP/project implementation, if the short Prompt 2 wording is not the complete original.
2. Any separate debugging prompt not present in the current conversation.
3. Any prompts sent to other AI tools.
4. Any follow-up prompts from earlier conversations that are not visible in the current record.

## Prompt 7 — Final validation and GitHub release

The following release-task prompt was received verbatim in the current conversation and is summarized here only because the complete user message is already preserved in the conversation record:

> Act as a senior Python engineer, QA engineer, and Git/GitHub release engineer. Finish the remaining YottaFlex AI recruitment assessment requirements, verify the existing project, and publish it to the specified GitHub repository. Inspect the correct workspace and remote, verify labelled anomaly scenarios, all ten entities and validation rules, full-scale deterministic exports, prompt history, security and documentation, run the final tests and startup checks, stage only intended files, commit meaningful changes, push without force-pushing or exposing credentials, and report actual results. Do not rebuild the project, delete working code, fabricate checks, or claim a push succeeded if authentication or another error blocks it.

This is a reconstructed summary of the full release prompt, not a verbatim replacement. The complete original wording remains in the current conversation. No GitHub push was performed because GitHub CLI authentication was unavailable.
