# Docker (Metrics)

The bot supports export of OpenTelemetry, Prometheus, Loki and Tempo (i guess)

so yeah here's code for setup in docker:

```yaml:docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--enable-feature=promql-experimental-functions'
      - '--web.enable-admin-api'

  grafana:
    image: grafana/grafana-oss:latest
    container_name: grafana
    restart: unless-stopped
    network_mode: host
    environment:
      - GF_SERVER_HTTP_PORT=3001
    volumes:
      - grafana-data:/var/lib/grafana

  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    restart: unless-stopped
    network_mode: host
    pid: host
    command:
      - --path.rootfs=/

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    container_name: otel-collector
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    command:
      - --config=/etc/otel-collector-config.yaml

  loki:
    image: grafana/loki:latest
    container_name: loki
    restart: unless-stopped
    network_mode: host
    volumes:
      - loki-data:/loki
      - ./loki/local-config.yaml:/etc/loki/local-config.yaml:ro
    command: -config.file=/etc/loki/local-config.yaml

  tempo:
    image: grafana/tempo:latest
    container_name: tempo
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./tempo/tempo-local.yaml:/etc/tempo/tempo-local.yaml:ro
      - tempo-data:/var/tempo
    command:
      - "-config.file=/etc/tempo/tempo-local.yaml"

volumes:
  prometheus-data:
  grafana-data:
  loki-data:
  tempo-data:

```

Also `enable-feature` thing is optional
