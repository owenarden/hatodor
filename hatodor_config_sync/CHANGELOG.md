# Changelog

## 0.6.0

- Add Home Assistant helpers and friendly show/hide scripts for a full-screen
  Message of the Day.
- Support automatically wrapped text messages and runtime-downloaded PNG photos
  without reflashing the E1001.
- Make the green button dismiss the current MOTD and automatically show a new
  revision when its ID, type, text, or image path changes; dismissal survives a
  device reboot without storing the message itself in flash.
- Keep polling checklist data behind the overlay and return to the current list
  immediately when the MOTD is dismissed or disabled.
- Preserve MOTD state through the daytime Canvas response wrapper.
- Correct the ESPHome minimum version to 2025.12.0, the first supported release
  for the existing Home Assistant-specific API connection check.
- Use ESP-IDF for verified HTTPS image downloads, and make the existing 75 ms
  green-button polling interval authoritative in the managed ESPHome source.
- Extend Config Sync checks to cover managed-file deployment, MOTD wiring, and
  the existing Super Productivity deadline mapping.

## 0.5.0

- Add a daytime combined view of Super Productivity reminders and Canvas
  assignments, including priority sections and QR-code assignment links.
- Preserve the Morning and Evening checklist behavior and the 0.4.0 deadline
  semantics in the combined dashboard response.

## 0.4.0

- Map Home Assistant's generic TodoItem `due` field to Super Productivity's
  actual `deadlineWithTime` / `deadlineDay` fields instead of SP's separate
  planned/scheduled `dueWithTime` / `dueDay` fields.
- Return a local-time deadline label for each dashboard item and display timed
  deadlines right-justified on the E1001 task rows.
- Preserve each task's deadline clock time at daily rollover while moving the
  deadline into the new dashboard day.
- Treat deadlines earlier than the rollover time as belonging to the following
  calendar date, so post-midnight Evening deadlines stay in the same dashboard day.
- Extend the Config Sync smoke test to verify the deadline mapping patch and its
  idempotence.

## 0.3.3

- Replace the green-button GPIO binary sensor with an interrupt-backed pulse
  counter so repeated presses are counted even while the blocking e-paper
  driver is refreshing the panel.
- Use software pulse counting with a 20 ms input filter to preserve multi-press
  batches while debouncing the mechanical button.
- Drain every accumulated green press into the existing toggle-and-advance
  batching logic after the main loop resumes.
- Delay authoritative reconciliation briefly after the last backend response so
  button edges captured during a display refresh are applied before polling can
  overwrite optimistic local state.

## 0.3.2

- Make the E1001 green button toggle either direction: incomplete to completed
  or completed back to incomplete.
- Advance the selection to the next row after every green-button toggle.
- Allow rapid green presses to batch locally before one e-paper redraw, so
  multiple consecutive tasks can be checked off without waiting for the panel.
- Send batched task status changes to Home Assistant/Super Productivity in
  parallel while preserving optimistic local state.
- Suppress authoritative checklist polling while green-button updates are in
  flight, then reconcile once the batch has finished.

## 0.3.1

- Reduce the E1001 redraw debounce from 150 ms to 30 ms so the panel refresh
  begins almost immediately after a button press.
- Replace ASCII `[ ]` / `[x]` markers with drawn circle/check icons that do not
  depend on font glyph support.
- Replace the large selected-row outline with a compact chevron marker.
- Render completed task titles with a lighter Inter weight so they visually
  recede on the monochrome panel.

## 0.3.0

- Patch the installed Super Productivity integration so its main project-task
  fetch uses `include_done=True`, keeping completed project tasks visible to
  Home Assistant until Hatodor's rollover logic resets or removes them.
- Make the E1001 green button mark the selected item complete locally before the
  Home Assistant/Super Productivity round trip, so completion feedback appears
  immediately instead of waiting on network/backend latency.
- Preserve the optimistic checkmark during an in-flight refresh and roll it back
  if Home Assistant rejects the completion update.
- Keep the 150 ms left/right partial-refresh debounce from 0.2.4.
- Extend the Config Sync smoke test to verify that the Super Productivity source
  patch is applied idempotently.

## 0.2.4

- Reduce the E1001 left/right selection redraw delay from 500 ms to 150 ms
  now that partial refresh is enabled, improving button responsiveness while
  still coalescing very rapid presses.

## 0.2.3

- Switch the reTerminal E1001 display to ESPHome's `7.50inV2p` partial-refresh
  driver to reduce full-screen flashing during interaction.
- Perform a full cleaning refresh every 30 display updates to limit ghosting.
- Increase the left/right button redraw debounce from 150 ms to 500 ms so
  rapid navigation presses are coalesced into a single e-paper refresh.

## 0.2.2

- Fix ESPHome compilation with current releases by letting `std::vector`
  globals use their C++ default constructors instead of ambiguous `{}`
  initializers.

## 0.2.1

- Make the reTerminal E1001 header follow the active dashboard list name.
- Track the source todo entity with the displayed items so completion is applied
  to the same list even if a time-window boundary is crossed during an update.
- Rename the ESPHome friendly name from Morning Dashboard to Daily Dashboard.

## 0.2.0

- Switch the dashboard backend from the aggregate Super Productivity Today list
  to three projects: Morning Routine, Reminders, and Evening Routine.
- Add configurable daily rollover, morning-end, and evening-start time helpers.
- Reopen completed Morning/Evening routine tasks at rollover without duplicating
  incomplete tasks.
- Keep incomplete Reminders indefinitely and remove completed Reminders only at
  the next daily rollover.
- Catch up a missed rollover after Home Assistant restarts.

## 0.1.0

- Initial one-shot config sync App.
- Deploy the Super Productivity Today morning-dashboard Home Assistant package.
- Deploy the reTerminal E1001 morning-dashboard ESPHome configuration.
