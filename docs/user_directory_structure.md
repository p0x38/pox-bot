# User Directory Structure

The program uses platformdirs for user data directory storing for no reason.

## User data

- Description: Used to store persistent, user-specific data files required for the app's operation.
- Paths:
    - Linux: `~/.local/share/pox-bot/<version>`
    - macOS: `~/Library/Application Support/pox-bot/<version>`
    - Windows: `C:\Users\<User>\AppData\Local\p0x38\pox-bot\<version>`

## User configurations

- Description: The standard location for user configuration files.
- Paths:
    - Linux: `~/.config/pox-bot/<version>`
    - macOS: `~/Library/Application Support/pox-bot/<version>`
    - Windows: `C:\Users\<User>\AppData\Local\p0x38\pox-bot\<version>`

## User cache

- Description: For non-essential, temporary data that can be regenerated or re-downloaded anytime.
- Paths:
    - Linux: `~/.cache/pox-bot/<version>`
    - macOS: `~/Library/Caches/pox-bot/<version>`
    - Windows: `C:\Users\<User>\AppData\Local\p0x38\pox-bot\Cache\<version>`

## User state

- Description: Holds user-specific state data that should persist between restarts but isn't a configuration file.
- Paths:
    - Linux: `~/.local/state/pox-bot/<version>`
    - macOS: `~/Library/Application Support/pox-bot/<version>`
    - Windows: `C:\Users\<User>\AppData\Local\p0x38\pox-bot\<version>`

## User logs

- Description: Dedicated directory for application runtime log files. Separating logs makes debugging and log-rotation scripts easier to manage.
- Paths:
    - Linux: `~/.local/state/pox-bot/log/<version>`
    - macOS: `~/Library/Logs/pox-bot/<version>`
    - Windows: `C:\Users\<User>\AppData\Local\p0x38\pox-bot\Logs\<version>`

## User runtime

- Description: Used for highly transient files like Unix domain sockets, named pipes, or runtime locks. These are usually deleted automatically when the user logs out or the system reboots.
- Paths:
    - Linux: `/run/user/<uid>/pox-bot/<version>`
    - macOS: `~/Library/Caches/TemporaryItems/pox-bot/<version>`
    - Windows: `C:\Users\<User>\AppData\Local\Temp\p0x38\pox-bot\<version>`