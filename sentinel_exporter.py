import logging
import argparse
import time
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from redis import Redis

parser = argparse.ArgumentParser(description="sentinel exporter for prometheus")
parser.add_argument('-p', '--port', type=int, default=26379)
parser.add_argument('-H', '--host', type=str, default="localhost")
parser.add_argument('-i', '--scrape-interval-seconds', type=int, default=30)
parser.add_argument('-m', '--metrics-port', type=int, default=9478)
parser.add_argument('--debug', action="store_true")
args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class AtomicGaugeCollector(object):
    def __init__(self, name, help_text, labels=tuple()):
        self.labels = labels
        self.name = name
        self.help_text = help_text
        self._data = {}
        self._next_data = {}
        REGISTRY.register(self)

    def collect(self):
        g = GaugeMetricFamily(self.name, self.help_text, labels=self.labels)
        for k, v in self._data.items():
            g.add_metric(k, v)
        yield g

    def set(self, labels, value):
        self._next_data[tuple(labels)] = value

    def update_metrics(self):
        self._data = self._next_data
        self._next_data = {}

master_info_gauge = AtomicGaugeCollector('sentinel_master_info', 'Basic master information', ['master_name', 'master_ip'])
sentinels_current_gauge = AtomicGaugeCollector('sentinel_sentinels_current', 'Number of running sentinels', ['master_name', 'state'])


def main():
    start_http_server(args.metrics_port)
    log.info("Connecting to sentinel on %s:%s", args.host, args.port)
    redis_client = Redis(host=args.host, port=args.port)
    run_exporter(redis_client, args.scrape_interval_seconds)

def run_exporter(redis_client, sleeptime):
    while True:
        log.debug("fetching metrics")
        try:
            collect_metrics(redis_client)
        except Exception as e:
            log.exception("Error thrown while collecting metrics")
        finally:
            time.sleep(sleeptime)

def collect_metrics(redis_client):
    master_info = redis_client.sentinel_masters()
    log.debug('have %s masters', len(master_info))
    masters = master_info.keys()
    update_master_info(master_info)
    update_sentinel_metrics(redis_client, masters)


def update_sentinel_metrics(redis_client, masters):
    _data = {}
    for master in masters:
        sentinel_info = redis_client.sentinel_sentinels(master)
        sentinel_count(master, sentinel_info)
    sentinels_current_gauge.update_metrics()

def sentinel_count(master_name, sentinels):
    up = 0
    down = 0
    for sentinel in sentinels:
        if sentinel.get('is_disconnected', True):
            down += 1
        else:
            up +=1
    log.debug('sentinel cluster %s has %s up, %s down sentinels', master_name, up, down)
    sentinels_current_gauge.set([master_name, "up"], up)
    sentinels_current_gauge.set([master_name, "down"], down)

def update_master_info(master_info):
    for k, v in master_info.items():
        labels = [k, v.get('ip', "")]
        master_info_gauge.set(labels, 1)
    master_info_gauge.update_metrics()

main()
