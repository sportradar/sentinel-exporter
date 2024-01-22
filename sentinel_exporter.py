import logging
import argparse
import time

import redis.exceptions
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from redis.sentinel import Sentinel
from redis import Redis



parser = argparse.ArgumentParser(description="sentinel exporter for prometheus")
parser.add_argument('-p', '--port', type=int, default=26379)
parser.add_argument('-H', '--host', type=str, default="localhost")
parser.add_argument('-i', '--scrape-interval-seconds', type=int, default=10)
parser.add_argument('-m', '--metrics-port', type=int, default=9478)
parser.add_argument('-P', '--password', type=str, default="")
parser.add_argument('-U', '--user', type=str, default="")
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


master_info_gauge = AtomicGaugeCollector('sentinel_master_info',
                                         'Basic master information',
                                         ['master_name', 'master_ip'])
sentinels_current_gauge = AtomicGaugeCollector('sentinel_sentinels_current',
                                               'Number of running sentinels',
                                               ['master_name', 'state'])
sentinel_ckquorum_gauge = AtomicGaugeCollector('sentinel_ckquorum_info',
                                         "State sentinel cluster's ckquorum",
                                         ['master_name', 'state'])


def main():
    start_http_server(args.metrics_port)
    log.info("Connecting to sentinel on %s:%s", args.host, args.port)

    redis_sentinel = Sentinel(sentinels=[(args.host, args.port)],
                              sentinel_kwargs={'password': args.password, 'username': args.user})
    redis_client = Redis(host=args.host, port=args.port, password=args.password, username=args.user)
    log.info("Connected. Collecting metrics.")
    run_exporter(redis_client, redis_sentinel, args.scrape_interval_seconds)

def run_exporter(redis_client, redis_sentinel, sleeptime):
    while True:
        log.debug("fetching metrics")
        try:
            collect_metrics(redis_client, redis_sentinel)
        except Exception as e:
            log.exception("Error thrown while collecting metrics")
        finally:
            time.sleep(sleeptime)

def collect_metrics(redis_client, redis_sentinel):
    master_info = redis_client.sentinel_masters()
    log.debug('have %s masters', len(master_info))
    masters = master_info.keys()
    get_ckquorum(redis_sentinel, masters)
    update_master_info(master_info)
    update_sentinel_metrics(redis_client, masters)


def get_ckquorum(redis_sentinel, masters):
    for master in masters:
        try:
            redis_sentinel.sentinel_ckquorum(new_master_name=master)
            sentinel_ckquorum_gauge.set([master, 'OK'], 1)
        except redis.exceptions.ResponseError as response:
            response = str(response)
            if response.find('NOQUORUM') == -1:
                log.error("ERROR: Wrong exception from Redis",response)
            sentinel_ckquorum_gauge.set([master, 'FAIL'], 0)
    sentinel_ckquorum_gauge.update_metrics()


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
