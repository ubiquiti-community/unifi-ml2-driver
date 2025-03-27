#!/bin/bash

set -eux
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
UNIFI_TEST_BRIDGE=unifi
UNIFI_TEST_PORT_NAME=${UNIFI_PORT_NAME:-p_01}
NEUTRON_UNIFI_TEST_PORT_NAME=unifi_test

function clear_resources {
    sudo ovs-vsctl --if-exists del-port $UNIFI_TEST_PORT_NAME
    if neutron port-show $NEUTRON_UNIFI_TEST_PORT_NAME; then
        neutron port-delete $NEUTRON_UNIFI_TEST_PORT_NAME
    fi
}

function wait_for_openvswitch_agent {
    local openvswitch_agent
    local retries=10
    local retry_delay=20;
    local status=false
    openvswitch_agent="Open vSwitch agent"

    while [[ $retries -ge 0 ]]; do
        if neutron agent-list --fields agent_type | grep -q "Open vSwitch agent"; then
            status=true
            break
        fi
        retries=$((retries - 1))
        echo "$openvswitch_agent is not yet registered. $retries left."
        sleep $retry_delay
    done
    if ! $status; then
        echo "$openvswitch_agent is not started in $((retries * retry_delay))"
    fi
}

clear_resources

sudo ovs-vsctl add-port $UNIFI_TEST_BRIDGE $UNIFI_TEST_PORT_NAME
sudo ovs-vsctl clear port $UNIFI_TEST_PORT_NAME tag

switch_id=$(ip link show dev $UNIFI_TEST_BRIDGE | egrep -o "ether [A-Za-z0-9:]+"|sed "s/ether\ //")

wait_for_openvswitch_agent

# create and update Neutron port
expected_tag=$(python ${DIR}/exercise.py --switch_name $UNIFI_TEST_BRIDGE --port $UNIFI_TEST_PORT_NAME --switch_id=$switch_id)

new_tag=$(sudo ovs-vsctl get port $UNIFI_TEST_PORT_NAME tag)

clear_resources

if [ "${new_tag}" != "${expected_tag}" ]; then
    echo "FAIL: OVS port tag is not set correctly!"
    exit 1
else
    echo "SUCCESS: OVS port tag is set correctly"
fi
