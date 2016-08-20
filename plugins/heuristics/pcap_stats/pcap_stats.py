#!/usr/bin/env python
#
#   Copyright (c) 2016 In-Q-Tel, Inc, All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""
Given parsed hex pcaps, pull
from rabbitmq and generate statistics
for them, periodically update database with new stats.

NOTE: need to add a periodic database update

Created on 22 June 2016
@author: lanhamt

rabbitmq:
    host:       poseidon-rabbit
    exchange:   topic-poseidon-internal
    queue(in):  features_tcpdump
        keys:   poseidon.tcpdump_parser.#
"""
import ast
import logging
import sys
import thread
import threading
import time

import pika
import requests
from pcap_stats_utils import FlowRecord
from pcap_stats_utils import MachineNode
from pcap_stats_utils import TimeRecord
from pymongo import MongoClient


flowRecordLock = threading.Lock()
module_logger = logging.getLogger('plugins.heuristics.pcap_stats.pcap_stats')


def rabbit_init(host, exchange, queue_name):  # pragma: no cover
    """
    Connects to rabbitmq using the given hostname,
    exchange, and queue. Retries on failure until success.
    Binds routing keys appropriate for module, and returns
    the channel and connection.
    """
    wait = True
    while wait:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=host))
            channel = connection.channel()
            channel.exchange_declare(exchange=exchange, type='topic')
            result = channel.queue_declare(name=queue_name, exclusive=True)
            wait = False
            module_logger.info('connected to rabbitmq...')
        except:
            module_logger.info('waiting for connection to rabbitmq...')
            time.sleep(2)
            wait = True

    binding_keys = sys.argv[1:]
    if not binding_keys:
        ostr = 'Usage: %s [binding_key]...' % (sys.argv[0])
        module_logger.error(ostr)

        sys.exit(1)

    for binding_key in binding_keys:
        channel.queue_bind(exchange=exchange,
                           queue=queue_name,
                           routing_key=binding_key)

    module_logger.info(' [*] Waiting for logs. To exit press CTRL+C')
    return channel, connection


def db_update_worker():
    """
    Function to be executed by separate worker
    thread to connect to poseidon-storage-interface
    and update based on machines in the flow records.
    Then sleeps for 10 sec before waking up for next
    update

    NOTE: install with
    thread.start_new_thread(db_update_worker)

    ISSUE: add bool to flow record for whether it
    needs to be updated (ie any changes from last
    update) and at end of update, reset it.
    """
    """
    global flowRecordLock
    while True:
        try:
            TODO: fix url for appropriate rest call
            url = 'http://poseidon-storage-interface/v1/storage/update'
            resp = requests.get(url)
            # check update conditions
            # flowRecordLock.acquire()
            # update with rest call for appropriate docs
            # flowRecordLock.release()
        except:
            module_logger.error('database update failed...')
        time.sleep(10)
    """


network_machines = []


def analyze_pcap(ch, method, properties, body, flow):
    """
    Takes pcap record and updates flow graph for
    networked machines.

    TODO: fix flow object - can't have it in the callback,
    determine module useage for fix; right now taken as
    parameter to allow unit testing
    """
    global network_machines

    pcap = ast.literal_eval(body)
    if pcap['src_ip'] in network_machines and \
            pcap['dest_ip'] in network_machines:
        # both machines in network
        flow.update(
            pcap['src_ip'],
            True,
            pcap['dest_ip'],
            True,
            pcap['length'],
            pcap)
    elif pcap['src_ip'] in network_machines:
        # machine in network talking to outside
        flow.update(
            pcap['src_ip'],
            True,
            pcap['dest_ip'],
            False,
            pcap['length'],
            pcap)
    elif pcap['dest_ip'] in network_machines:
        # outside talking to network machine
        flow.update(
            pcap['src_ip'],
            False,
            pcap['dest_ip'],
            True,
            pcap['length'],
            pcap)
    else:
        # neither machine in network (list needs to be updated)
        pass


if __name__ == '__main__':
    host = 'poseidon-rabbit'
    exchange = 'topic-poseidon-internal'
    queue_name = 'features_tcpdump'
    channel, connection = rabbit_init(host=host,
                                      exchange=exchange,
                                      queue_name=queue_name)
    channel.basic_consume(analyze_pcap, queue=queue_name, no_ack=True)
    channel.start_consuming()