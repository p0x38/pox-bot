# PoxBot Privacy Policy

**Effective date:** 2026-11-01

## 1. Overview

This policy explains what information PoxBot stores, why it is stored,
how it is used, and how users can request an export or deletion.

PoxBot operates through the Discord platform. Discord accounts,
messages, servers, and other Discord resources are governed separately
by Discord's policies and controls.

## 2. Information stored by PoxBot

Depending on the features enabled by a server, PoxBot may store:

### Discord identifiers

- Discord user IDs
- Discord server IDs
- Discord channel IDs
- Discord message IDs

### User profiles and preferences

- User-provided profile descriptions
- User-provided nicknames
- Locale preferences
- Embed preferences

### Statistics and activity

- XP and levels
- Message counts
- Character counts
- Daily activity aggregates
- Command usage counts
- Last activity timestamps

### Economy data

- Wallet balances
- Bank balances
- Inventory records
- Transaction amounts and descriptions
- Economy feature timestamps

### Server feature records

- Ticket ownership associations
- Giveaway host associations
- Other records required to operate enabled server features

### Moderation records

PoxBot may store moderation-related information, such as:

- Moderation restriction records
- Moderation reasons
- Moderator identifiers
- Global Chat moderation case metadata
- Review status and timestamps
- Message fingerprints used for moderation and abuse prevention

Some moderation records may be retained for service security and
moderation operations even after a user requests deletion.

## 3. Message content and processing

PoxBot does not intend to maintain a persistent message-content
training dataset.

This does not mean that message content is never processed,
transmitted, or stored by individual features.

Some commands may process Discord message history when explicitly
invoked. Such processing is separate from persistent message storage.

The scope of any temporary processing depends on the feature being used.

### 3.1. Global Chat forwarding

When a message is sent in a channel configured for PoxBot Global Chat,
PoxBot forwards that message to Global Chat channels configured on
other participating Discord servers.

This means that message content is shared outside the Discord server
where it was originally posted.

Members of participating servers who have access to their respective
Global Chat channels may be able to view forwarded messages.

PoxBot does not control participating servers or their members.
Forwarded messages may be copied, saved, screenshotted, or otherwise
retained independently by other users.

Users should not send passwords, personal information, confidential
information, or other sensitive content through Global Chat.

### 3.2. Chatbot processing

When the chatbot feature is enabled, PoxBot may process message content
and conversation context to generate AI-powered responses.

Conversation history is maintained temporarily in application memory
to provide context for subsequent responses. This history is not
persisted to PoxBot's database or local conversation-history files.

In-memory conversation history is temporary and is cleared when the
relevant history is cleared or the bot process restarts.

To generate responses, relevant message content and conversation
context may be transmitted to the AI provider configured by the bot
operator.

The handling, retention, and processing of information by external
AI providers are subject to their respective privacy policies and
terms of service. PoxBot does not independently control their
data-retention practices.

Users should avoid submitting passwords, personal information,
confidential information, or other sensitive content to the chatbot.

### 3.3. Server audit logging

When server administrators enable PoxBot audit logging, PoxBot may
send audit events to the configured Discord channel.

Message edit events may include the previous and updated message
content. Message deletion events may include the deleted content
when the message is available in the bot's Discord message cache.

These audit-log messages are created in Discord channels managed by
the respective server. Access to them is controlled by that server's
channel permissions and administrators, not by PoxBot's privacy
database.

A PoxBot data export or deletion request does not automatically
remove audit-log messages already sent to a server's Discord channel.

### 3.4. Global Chat message references

PoxBot maintains message references to associate original messages
with their forwarded copies.

These references may contain:

- The original Discord message ID.
- The forwarded Discord message ID.
- The destination Discord server ID.
- The destination Discord channel ID.

These references are used to associate messages across participating
servers and support Global Chat operations.

The reference records do not independently identify the original
message author by Discord user ID.

### 3.5. Global Chat moderation records

When a Global Chat message is flagged or held for moderation,
PoxBot may create a moderation record to support moderation,
investigation, and abuse prevention.

Such records may contain:

- The author's Discord user ID.
- The original message ID.
- The associated Discord server and channel IDs.
- Moderation reason codes.
- A message fingerprint derived from message content and attachment
  metadata.
- The moderation case status.
- Creation and review timestamps.
- The Discord user ID of the moderator who reviewed the case,
  if applicable.

The moderation case stores a message fingerprint rather than the
full message body. However, fingerprints are not necessarily
anonymous: they may still be associated with a particular user or
message through the other identifiers retained in the record.

Moderation records are subject to the retention practices described
in Section 9.

### 3.6. Deletion of Global Chat messages

Deleting an original message does not guarantee that every forwarded
copy will also be deleted.

PoxBot may use its message references to locate associated forwarded
messages. However, it may not always be able to locate or delete
every copy, for example when a message is no longer accessible or
PoxBot lacks the necessary Discord permissions.

Furthermore, a privacy deletion request based only on a Discord user
ID may not be sufficient to identify all Global Chat messages
associated with that user. The message reference records do not
contain the original author's user ID.

Copies independently retained by other users or servers, including
screenshots and other external records, cannot be reliably removed
by PoxBot.

## 4. Purposes of processing

Stored information is used to:

- Operate bot features requested by users or server administrators.
- Maintain statistics and activity features.
- Operate economy and inventory features.
- Manage tickets and giveaways.
- Apply moderation restrictions and review moderation events.
- Forward messages between participating Global Chat servers.
- Associate original Global Chat messages with forwarded copies.
- Diagnose errors and maintain service reliability.

## 5. Data export

Users can request a copy of supported personal data through:

`/privacy export`

The export is provided as a JSON attachment in a private Discord
interaction response.

The export only includes information that PoxBot can associate with
the requesting user and that is covered by the export implementation.

Because Global Chat message references do not independently contain
the original author's Discord user ID, they may not all be identifiable
or included in an export requested using only that user ID.

## 6. Data deletion

Users can request deletion through:

`/privacy delete`

The command requires confirmation before deletion begins.

Deletion may remove:

- User statistics
- Daily activity records
- User profiles
- User preferences
- Economy accounts and inventory
- Economy transactions
- Ticket ownership associations

Some operational records may be anonymized or retained, particularly
where they are needed for moderation or service security.

Global Chat message references and forwarded messages may not all
be identifiable through a deletion request based only on the user's
Discord ID. Deletion of PoxBot database records also does not
guarantee deletion of forwarded Discord messages or audit-log messages
already sent to Discord channels managed by server administrators.

The bot will report how many records were deleted, anonymized,
and retained, as supported by the deletion implementation.

## 7. Information not controlled by PoxBot

A PoxBot deletion request does not automatically delete:

- Discord accounts
- Messages stored by Discord
- Messages forwarded to other participating Discord servers
- Audit-log messages already sent to Discord channels managed by server administrators
- Discord server memberships
- Discord channels
- Records held independently by server administrators
- Copies, screenshots, or other records retained independently
  by other users
- Data held by external infrastructure providers

Users may need to use Discord's own controls or contact the relevant
service operator for those records.

## 8. Logs and infrastructure

PoxBot produces operational logs and telemetry to diagnose failures,
monitor service health, and maintain service reliability.

Depending on the runtime configuration, application logs may be
written to the console and local log files.

When file logging is enabled, log files are configured for daily
rotation, with up to 365 rotated log files retained.

PoxBot also supports forwarding application logs to a configured
Grafana Loki endpoint and exporting telemetry data through the
OpenTelemetry Protocol (OTLP).

PoxBot can additionally expose Prometheus-compatible metrics through
a configured metrics endpoint.

These integrations may operate using locally hosted services or
externally managed infrastructure, depending on the deployment
configuration.

Operational logs and telemetry may contain Discord identifiers,
command metadata, error information, request metadata, and other
technical data.

The actual infrastructure providers, data access controls, and
retention practices depend on the services configured by the bot
operator.

## 9. Retention

When file logging is enabled, PoxBot is configured to rotate log
files daily and retain up to 365 rotated files.

Actual log retention may vary depending on runtime configuration,
application activity, and log storage management.

Moderation restriction records may contain expiration timestamps.
These timestamps determine whether a restriction is considered
active and do not necessarily indicate that the underlying
database record has been deleted.

Global Chat moderation records may remain stored for moderation
and service security purposes.

PoxBot does not currently enforce a single fixed retention period
across all categories of database records.

Retention of externally managed logs, telemetry, and backups depends
on the respective infrastructure and storage configuration.

Removing a record from the main application database does not
necessarily remove copies held in logs, backups, or external
infrastructure.

## 10. Contact

For privacy questions or requests that cannot be completed through
the bot, contact:

[p0x38](https://github.com/p0x38)