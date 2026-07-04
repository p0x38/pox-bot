# Bot Environment Variables

This project loads configuration from environment variables via Pydantic Settings and from JSON via the config manager. The environment variable format uses double underscores to represent nested fields, for example `TRACE_CONFIG__ENABLED`.

## Configuration Reference

### `TOKEN_CONFIG__DISCORD_TOKEN` / `token_config.discord_token`

#### Description
The Discord bot token used to authenticate the bot with Discord's API. This secret is required during startup, and the Discord gateway and REST clients will fail to initialize if it is missing or invalid.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TokenConfig.discord_token` |
| **Data Type** | `SecretStr` |
| **Default Value** | `""` |
| **Environment Key** | `TOKEN_CONFIG__DISCORD_TOKEN="your_discord_token"` |

#### Examples

**Scenario A: Local development**
```env
TOKEN_CONFIG__DISCORD_TOKEN=your_discord_token
```

---

### `TOKEN_CONFIG__LMSTUDIO_TOKEN` / `token_config.lmstudio_token`

#### Description
The LM Studio API token used by model-serving integrations if the bot includes LM Studio support. When set, the bot can authenticate outbound requests to LM Studio and route text generation traffic through that backend.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TokenConfig.lmstudio_token` |
| **Data Type** | `SecretStr` |
| **Default Value** | `""` |
| **Environment Key** | `TOKEN_CONFIG__LMSTUDIO_TOKEN="your_lmstudio_token"` |

#### Examples

**Scenario A: LM Studio enabled**
```env
TOKEN_CONFIG__LMSTUDIO_TOKEN=your_lmstudio_token
```

---

### `TOKEN_CONFIG__OPENAI_API_KEY` / `token_config.openai_api_key`

#### Description
The OpenAI API key used for OpenAI-backed language model features. It is consumed by the LLM integration layer, and missing this value disables any flows that require OpenAI authentication.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TokenConfig.openai_api_key` |
| **Data Type** | `SecretStr` |
| **Default Value** | `""` |
| **Environment Key** | `TOKEN_CONFIG__OPENAI_API_KEY="your_openai_key"` |

#### Examples

**Scenario A: OpenAI enabled**
```env
TOKEN_CONFIG__OPENAI_API_KEY=your_openai_key
```

---

### `TOKEN_CONFIG__OPENROUTER_API_KEY` / `token_config.openrouter_api_key`

#### Description
The OpenRouter API key used for OpenRouter-based LLM requests. Setting this enables the bot to use OpenRouter as an alternative model endpoint.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TokenConfig.openrouter_api_key` |
| **Data Type** | `SecretStr` |
| **Default Value** | `""` |
| **Environment Key** | `TOKEN_CONFIG__OPENROUTER_API_KEY="your_openrouter_key"` |

#### Examples

**Scenario A: OpenRouter enabled**
```env
TOKEN_CONFIG__OPENROUTER_API_KEY=your_openrouter_key
```

---

### `DATABASE_CONFIG__HOST` / `database_config.host`

#### Description
The hostname or service name for the PostgreSQL database server. In a local Docker Compose deployment, this should usually be the database container name (for example `db`). If the host cannot be reached, database initialization fails.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `DatabaseConfig.host` |
| **Data Type** | `str` |
| **Default Value** | `127.0.0.1` |
| **Environment Key** | `DATABASE_CONFIG__HOST="127.0.0.1"` |

#### Examples

**Scenario A: Local host**
```env
DATABASE_CONFIG__HOST=127.0.0.1
```

**Scenario B: Docker Compose**
```env
DATABASE_CONFIG__HOST=db
```

---

### `DATABASE_CONFIG__PORT` / `database_config.port`

#### Description
The TCP port used to connect to PostgreSQL. If your database is exposed on a nonstandard port, update this value accordingly; otherwise keep the default.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `DatabaseConfig.port` |
| **Data Type** | `int` |
| **Default Value** | `5432` |
| **Environment Key** | `DATABASE_CONFIG__PORT="5432"` |

#### Examples

**Scenario A: Default PostgreSQL port**
```env
DATABASE_CONFIG__PORT=5432
```

---

### `DATABASE_CONFIG__USER` / `database_config.user`

#### Description
The database username used to authenticate with PostgreSQL. This credential is included in the SQLAlchemy DSN builder and must match an existing database role.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `DatabaseConfig.user` |
| **Data Type** | `str` |
| **Default Value** | `postgres` |
| **Environment Key** | `DATABASE_CONFIG__USER="postgres"` |

#### Examples

**Scenario A: Default DB user**
```env
DATABASE_CONFIG__USER=postgres
```

---

### `DATABASE_CONFIG__PASSWORD` / `database_config.password`

#### Description
The password for the PostgreSQL user. This secret is used to build the connection string and should be protected via environment variables or a secrets manager.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `DatabaseConfig.password` |
| **Data Type** | `SecretStr` |
| **Default Value** | `postgres` |
| **Environment Key** | `DATABASE_CONFIG__PASSWORD="supersecret"` |

#### Examples

**Scenario A: Local development**
```env
DATABASE_CONFIG__PASSWORD=supersecret
```

---

### `DATABASE_CONFIG__NAME` / `database_config.name`

#### Description
The name of the PostgreSQL database the bot uses for storage. This value is part of the generated DSN and controls which database the application connects to.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `DatabaseConfig.name` |
| **Data Type** | `str` |
| **Default Value** | `postgres` |
| **Environment Key** | `DATABASE_CONFIG__NAME="postgres"` |

#### Examples

**Scenario A: Custom app database**
```env
DATABASE_CONFIG__NAME=poxbot
```

---

### `DATABASE_CONFIG__DRIVER` / `database_config.driver`

#### Description
The SQLAlchemy driver string used to create the database DSN. This determines which database dialect and async driver the bot uses.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `DatabaseConfig.driver` |
| **Data Type** | `str` |
| **Default Value** | `postgresql+asyncpg` |
| **Environment Key** | `DATABASE_CONFIG__DRIVER="postgresql+asyncpg"` |

#### Examples

**Scenario A: Default async driver**
```env
DATABASE_CONFIG__DRIVER=postgresql+asyncpg
```

---

### `TRACE_CONFIG__ENABLED` / `trace_config.enabled`

#### Description
The global telemetry switch for the bot. When enabled, tracing, metrics export, and Loki log exports are initialized; when disabled, those telemetry pipelines are bypassed entirely.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.enabled` |
| **Data Type** | `bool` |
| **Default Value** | `true` |
| **Environment Key** | `TRACE_CONFIG__ENABLED="true"` |

#### Examples

**Scenario A: Telemetry enabled**
```env
TRACE_CONFIG__ENABLED=true
```

---

### `TRACE_CONFIG__OPENTELEMETRY_ENDPOINT` / `trace_config.opentelemetry_endpoint`

#### Description
Fallback OTLP endpoint for exporting traces and metrics. If dedicated trace or metric endpoints are not provided, this endpoint is used by the OTLP exporters.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.opentelemetry_endpoint` |
| **Data Type** | `str` |
| **Default Value** | `http://127.0.0.1:4317` |
| **Environment Key** | `TRACE_CONFIG__OPENTELEMETRY_ENDPOINT="http://127.0.0.1:4317"` |

#### Examples

**Scenario A: Local OpenTelemetry Collector**
```env
TRACE_CONFIG__OPENTELEMETRY_ENDPOINT=http://127.0.0.1:4317
```

---

### `TRACE_CONFIG__OTLP_TRACES_ENDPOINT` / `trace_config.otlp_traces_endpoint`

#### Description
The dedicated OTLP endpoint used specifically for trace export. If present, trace export uses this URL instead of the fallback endpoint.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.otlp_traces_endpoint` |
| **Data Type** | `str | None` |
| **Default Value** | `None` |
| **Environment Key** | `TRACE_CONFIG__OTLP_TRACES_ENDPOINT="http://127.0.0.1:4317"` |

#### Examples

**Scenario A: Separate trace collector**
```env
TRACE_CONFIG__OTLP_TRACES_ENDPOINT=http://collector:4317
```

---

### `TRACE_CONFIG__OTLP_METRICS_ENDPOINT` / `trace_config.otlp_metrics_endpoint`

#### Description
The dedicated OTLP endpoint used specifically for metric export. When set, metrics export uses this URL instead of the fallback endpoint.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.otlp_metrics_endpoint` |
| **Data Type** | `str | None` |
| **Default Value** | `None` |
| **Environment Key** | `TRACE_CONFIG__OTLP_METRICS_ENDPOINT="http://127.0.0.1:4317"` |

#### Examples

**Scenario A: Separate metrics collector**
```env
TRACE_CONFIG__OTLP_METRICS_ENDPOINT=http://collector:4317
```

---

### `TRACE_CONFIG__LOKI_URL` / `trace_config.loki_url`

#### Description
The Loki push API URL used for log ingestion. The logger factory will enable Loki export only when this URL is configured and valid.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.loki_url` |
| **Data Type** | `str` |
| **Default Value** | `http://127.0.0.1:3100/loki/api/v1/push` |
| **Environment Key** | `TRACE_CONFIG__LOKI_URL="http://127.0.0.1:3100/loki/api/v1/push"` |

#### Examples

**Scenario A: Local Loki**
```env
TRACE_CONFIG__LOKI_URL=http://127.0.0.1:3100/loki/api/v1/push
```

---

### `TRACE_CONFIG__PROMETHEUS_HOST` / `trace_config.prometheus_host`

#### Description
The bind host for the built-in Prometheus scrape endpoint. `0.0.0.0` exposes it to all interfaces, while `127.0.0.1` limits it to local access.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.prometheus_host` |
| **Data Type** | `str` |
| **Default Value** | `0.0.0.0` |
| **Environment Key** | `TRACE_CONFIG__PROMETHEUS_HOST="0.0.0.0"` |

#### Examples

**Scenario A: Container access**
```env
TRACE_CONFIG__PROMETHEUS_HOST=0.0.0.0
```

---

### `TRACE_CONFIG__PROMETHEUS_SERVER_PORT` / `trace_config.prometheus_server_port`

#### Description
The TCP port exposed by the Prometheus HTTP scrape endpoint. Prometheus should be configured to scrape the bot on this port.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.prometheus_server_port` |
| **Data Type** | `int` |
| **Default Value** | `8001` |
| **Environment Key** | `TRACE_CONFIG__PROMETHEUS_SERVER_PORT="8001"` |

#### Examples

**Scenario A: Default metrics port**
```env
TRACE_CONFIG__PROMETHEUS_SERVER_PORT=8001
```

---

### `TRACE_CONFIG__INSECURE` / `trace_config.insecure`

#### Description
Toggles insecure OTLP transport. When `true`, the exporters use plaintext HTTP/gRPC; when `false`, the collector is expected to support TLS.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.insecure` |
| **Data Type** | `bool` |
| **Default Value** | `true` |
| **Environment Key** | `TRACE_CONFIG__INSECURE="true"` |

#### Examples

**Scenario A: Plaintext OTLP**
```env
TRACE_CONFIG__INSECURE=true
```

---

### `TRACE_CONFIG__SAMPLING_RATIO` / `trace_config.sampling_ratio`

#### Description
The fraction of traces that are sampled and exported. A value of `1.0` samples all traces, while lower values reduce telemetry volume.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.sampling_ratio` |
| **Data Type** | `float` |
| **Default Value** | `1.0` |
| **Environment Key** | `TRACE_CONFIG__SAMPLING_RATIO="1.0"` |

#### Examples

**Scenario A: Full sampling**
```env
TRACE_CONFIG__SAMPLING_RATIO=1.0
```

---

### `TRACE_CONFIG__EXPORT_INTERVAL_MS` / `trace_config.export_interval_ms`

#### Description
How often telemetry is flushed to the configured exporter in milliseconds. Higher values reduce export frequency and network overhead.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.export_interval_ms` |
| **Data Type** | `int` |
| **Default Value** | `15000` |
| **Environment Key** | `TRACE_CONFIG__EXPORT_INTERVAL_MS="15000"` |

#### Examples

**Scenario A: Default flush interval**
```env
TRACE_CONFIG__EXPORT_INTERVAL_MS=15000
```

---

### `TRACE_CONFIG__MAX_BATCH_SIZE` / `trace_config.max_batch_size`

#### Description
The maximum number of telemetry records batched before export. This controls throughput and can affect memory use.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `TraceConfig.max_batch_size` |
| **Data Type** | `int` |
| **Default Value** | `512` |
| **Environment Key** | `TRACE_CONFIG__MAX_BATCH_SIZE="512"` |

#### Examples

**Scenario A: Default batch size**
```env
TRACE_CONFIG__MAX_BATCH_SIZE=512
```

---

### `LOGGER__LEVEL` / `logger.level`

#### Description
The default log verbosity level for the bot. Messages below this severity are filtered out before being emitted to configured log handlers.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `LoggerConfig.level` |
| **Data Type** | `Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]` |
| **Default Value** | `DEBUG` |
| **Environment Key** | `LOGGER__LEVEL="INFO"` |

#### Examples

**Scenario A: Production verbosity**
```env
LOGGER__LEVEL=INFO
```

---

### `LOGGER__FILE_LOGGING__ENABLED` / `logger.file_logging.enabled`

#### Description
Enables or disables file logging. When enabled, the logger writes log files to the configured directory.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `FileLoggingConfig.enabled` |
| **Data Type** | `bool` |
| **Default Value** | `true` |
| **Environment Key** | `LOGGER__FILE_LOGGING__ENABLED="true"` |

#### Examples

**Scenario A: Persist logs to disk**
```env
LOGGER__FILE_LOGGING__ENABLED=true
```

---

### `LOGGER__FILE_LOGGING__DIRECTORY` / `logger.file_logging.directory`

#### Description
The directory where file logs are written when file logging is enabled. The bot must have write permission to this path.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `FileLoggingConfig.directory` |
| **Data Type** | `Path` |
| **Default Value** | `app_dir.user_log_path` |
| **Environment Key** | `LOGGER__FILE_LOGGING__DIRECTORY="/var/log/poxbot"` |

#### Examples

**Scenario A: Local log directory**
```env
LOGGER__FILE_LOGGING__DIRECTORY=/var/log/poxbot
```

---

### `LOGGER__FILE_LOGGING__ENCODING` / `logger.file_logging.encoding`

#### Description
The character encoding used for log files written to disk.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `FileLoggingConfig.encoding` |
| **Data Type** | `str` |
| **Default Value** | `utf-8` |
| **Environment Key** | `LOGGER__FILE_LOGGING__ENCODING="utf-8"` |

#### Examples

**Scenario A: UTF-8 encoded logs**
```env
LOGGER__FILE_LOGGING__ENCODING=utf-8
```

---

### `LOGGER__CONSOLE_LOGGING__LEVEL` / `logger.console_logging.level`

#### Description
The minimum log level printed to the console. Lower levels produce more verbose output during local development.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `ConsoleLoggingConfig.level` |
| **Data Type** | `Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]` |
| **Default Value** | `INFO` |
| **Environment Key** | `LOGGER__CONSOLE_LOGGING__LEVEL="INFO"` |

#### Examples

**Scenario A: Console info level**
```env
LOGGER__CONSOLE_LOGGING__LEVEL=INFO
```

---

### `LOGGER__CONSOLE_LOGGING__RICH_TRACEBACKS` / `logger.console_logging.rich_tracebacks`

#### Description
Enables rich tracebacks in the console output, improving stack trace readability during development.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `ConsoleLoggingConfig.rich_tracebacks` |
| **Data Type** | `bool` |
| **Default Value** | `true` |
| **Environment Key** | `LOGGER__CONSOLE_LOGGING__RICH_TRACEBACKS="true"` |

#### Examples

**Scenario A: Enable rich tracebacks**
```env
LOGGER__CONSOLE_LOGGING__RICH_TRACEBACKS=true
```

---

### `LOGGER__CONSOLE_LOGGING__MARKUP` / `logger.console_logging.markup`

#### Description
Enables markup rendering for console log output, allowing richer formatting when supported.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `ConsoleLoggingConfig.markup` |
| **Data Type** | `bool` |
| **Default Value** | `true` |
| **Environment Key** | `LOGGER__CONSOLE_LOGGING__MARKUP="true"` |

#### Examples

**Scenario A: Enable console markup**
```env
LOGGER__CONSOLE_LOGGING__MARKUP=true
```

---

### `LLM_CONFIG__MODEL_ID` / `llm_config.model_id`

#### Description
The identifier used by the LLM integration to choose a model. This field is used when the bot constructs requests for language model APIs.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `LLMConfig.model_id` |
| **Data Type** | `str` |
| **Default Value** | `""` |
| **Environment Key** | `LLM_CONFIG__MODEL_ID="llama3.1"` |

#### Examples

**Scenario A: Model selection**
```env
LLM_CONFIG__MODEL_ID=llama3.1
```

---

### `BOT_NAME` / `bot_name`

#### Description
The public name used to identify the bot in logs and any printed output. This is not the Discord username, but the local application identifier.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `BotSettings.bot_name` |
| **Data Type** | `str` |
| **Default Value** | `TehBot` |
| **Environment Key** | `BOT_NAME="TehBot"` |

#### Examples

**Scenario A: Custom bot name**
```env
BOT_NAME=TehBot
```

---

### `DEFAULT_LANGUAGE` / `default_language`

#### Description
The fallback language code used by the bot for translations and default locale decisions.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `BotSettings.default_language` |
| **Data Type** | `str` |
| **Default Value** | `en` |
| **Environment Key** | `DEFAULT_LANGUAGE="en"` |

#### Examples

**Scenario A: English locale**
```env
DEFAULT_LANGUAGE=en
```

---

### `BOT_PREFIX` / `bot_prefix`

#### Description
The prefix used for text commands in the bot's command parser. Changing this updates the command trigger for every prefix-style command.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `BotSettings.bot_prefix` |
| **Data Type** | `str` |
| **Default Value** | `pox/` |
| **Environment Key** | `BOT_PREFIX="pox/"` |

#### Examples

**Scenario A: Standard prefix**
```env
BOT_PREFIX=pox/
```

---

### `ENVIRONMENT` / `environment`

#### Description
The runtime environment label used by the application. This can be used to distinguish `development`, `staging`, and `production` deployments.

#### Technical Specifications
| Attribute | Details |
| :--- | :--- |
| **Pydantic Field** | `BotSettings.environment` |
| **Data Type** | `str` |
| **Default Value** | `development` |
| **Environment Key** | `ENVIRONMENT="development"` |

#### Examples

**Scenario A: Production deployment**
```env
ENVIRONMENT=production
```

---

## Example `.env`

```env
TOKEN_CONFIG__DISCORD_TOKEN=your_discord_token
TOKEN_CONFIG__OPENAI_API_KEY=your_openai_key
DATABASE_CONFIG__HOST=127.0.0.1
DATABASE_CONFIG__PORT=5432
TRACE_CONFIG__ENABLED=true
TRACE_CONFIG__LOKI_URL=http://127.0.0.1:3100/loki/api/v1/push
TRACE_CONFIG__PROMETHEUS_HOST=0.0.0.0
TRACE_CONFIG__PROMETHEUS_SERVER_PORT=8001
```

## Example `config.json`

```json
{
  "token_config": {
    "discord_token": "your_discord_token"
  },
  "database_config": {
    "host": "127.0.0.1",
    "port": 5432
  },
  "trace_config": {
    "enabled": true,
    "loki_url": "http://127.0.0.1:3100/loki/api/v1/push",
    "prometheus_host": "0.0.0.0",
    "prometheus_server_port": 8001
  }
}
```

## Notes

- The app uses `SettingsConfigDict` with `env_nested_delimiter="__"`, so nested values should be written with double underscores.
- Secret values such as tokens and passwords are stored as `SecretStr` in the schema, but plain strings are accepted in `.env` and JSON.
