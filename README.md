# HAPCAN

Home Assistant custom integration for connecting to a HAPCAN TCP gateway.

## Features

- Discovers HAPCAN modules on the bus and creates entities for supported device types.
- Supports relay, button, blind controller, RGB LED controller, and IR transmitter modules.
- Exposes HAPCAN button channels as event entities with `press_start`, `press_end`, `long_press_start`, `long_press_end`, `held_4s`, `open`, and `closed` event types.
- Provides diagnostic entities, including last-seen and voltage sensors where supported.
- Can periodically poll device voltages and manually scan the bus from the integration options.

## Requirements

- Home Assistant with HACS installed.
- A HAPCAN TCP gateway reachable from Home Assistant.
- The gateway IP address or hostname and TCP port. The integration defaults to port `1000`.

## Installation with HACS

Until this repository is included in the HACS default store:

1. In Home Assistant, open **HACS** and select **Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/Onixarts/ha_hapcan` and choose **Integration** as the category.
4. Find **HAPCAN** in HACS and install it.
5. Restart Home Assistant.

## Configuration

After restarting, go to **Settings > Devices & services > Add integration**, search for **HAPCAN**, click Install and enter the gateway host and port in a popup window.

Use the integration's options to change the connection details, configure the diagnostic voltage scan interval, or start a bus scan. An interval of `0` disables periodic voltage polling.

## IR remotes

For each discovered **INFRARED RECEIVER & TRANSMITTER** module, use the HAPCAN integration's **Add IR remote** action. Name the remote, press a button to identify it, then learn and name each button. The remote appears as its own device linked to the receiving module. Existing remotes can be renamed, have button names edited, or learn additional buttons.

Each remote exposes one event entity. Its `event_type` is the learned button name, so renaming a button can require updating automations that use it. For example:

```yaml
automation:
	- alias: IR remote volume up
		triggers:
			- trigger: state
				entity_id: event.ir_remote_tv
				attribute: event_type
				to: vol_up
		actions:
			- action: media_player.volume_up
				target:
					entity_id: media_player.living_room_tv
```

## Troubleshooting

- Confirm that Home Assistant can reach the gateway at the configured host and TCP port.
- Check the Home Assistant log for messages from `custom_components.hapcan.gateway`.
- If a module is not discovered, run **Scan Hapcan bus** from the integration options and check that the module is powered and connected to the bus.

## Issues

Report bugs and feature requests at <https://github.com/Onixarts/ha_hapcan/issues>.