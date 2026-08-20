# Changelog

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
