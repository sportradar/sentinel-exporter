# Sentinel Exporter

This is a [prometheus](https://prometheus.io/) exporter for [redis sentinel](https://redis.io/topics/sentinel). For this mvp we only provide basic metrics from sentinel, which aren't available in redis exporters like [this](https://github.com/oliver006/redis_exporter). Most importantly the number of active and dead sentinel nodes so that you can monitor if a quorum is upheld.

## Install

To install simply run
```
$ pip install -r requirements.txt
```

## Running

```
python sentinel_exporter.py --host localhost --port 26379
```

### Flags

Name | Description | Default
-----|-------------|--------
-p --port | Which port sentinel is listening on | 26379
-H --host | The host sentinel is running on | localhost
-i --scrape-interval-seconds | How often to update the underlying metrics in seconds | 30
-m --metrics-port | The port that the metrics exporter will listen on | 9122

