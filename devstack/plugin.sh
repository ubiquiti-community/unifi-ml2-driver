#!/usr/bin/env bash
# plugin.sh - DevStack plugin.sh dispatch script template

UNIFI_DIR=${UNIFI_DIR:-$DEST/networking-generic-switch}
UNIFI_INI_FILE='/etc/neutron/plugins/ml2/ml2_conf_unifi.ini'
UNIFI_SSH_KEY_FILENAME="networking-generic-switch"
UNIFI_SSH_PORT=${UNIFI_SSH_PORT:-}
UNIFI_DATA_DIR=""$DATA_DIR/networking-generic-switch""
# NOTE(pas-ha) NEVER SET THIS TO ANY EXISTING USER!
# you might get locked out of SSH when limitinig SSH sessions is enabled for this user,
# AND THIS USER WILL BE DELETED TOGETHER WITH ITS HOME DIR ON UNSTACK/CLEANUP!!!
# this is why it is left unconfigurable
UNIFI_USER="ngs_ovs_manager"
UNIFI_USER_HOME="$UNIFI_DATA_DIR/$UNIFI_USER"
UNIFI_KEY_AUTHORIZED_KEYS_FILE="$UNIFI_USER_HOME/.ssh/authorized_keys"

UNIFI_KEY_DIR="$UNIFI_DATA_DIR/keys"
UNIFI_KEY_FILE=${UNIFI_KEY_FILE:-"$UNIFI_KEY_DIR/$UNIFI_SSH_KEY_FILENAME"}
UNIFI_TEST_BRIDGE="unifi"
UNIFI_TEST_PORT="gs_port_01"
# 0 means unlimited
UNIFI_USER_MAX_SESSIONS=${UNIFI_USER_MAX_SESSIONS:-0}
# 0 would mean wait forever
UNIFI_DLM_ACQUIRE_TIMEOUT=${UNIFI_DLM_ACQUIRE_TIMEOUT:-120}

if ( [[ "$UNIFI_USER_MAX_SESSIONS" -gt 0 ]] ) && (! is_service_enabled etcd3); then
    die $LINENO "etcd3 service must be enabled to use coordination features of networking-generic-switch"
fi

function install_unifi {
    setup_develop $UNIFI_DIR
}

# NOTE(pas-ha) almost verbatim copy of devstack/tools/create-stack-user.sh
# adapted to be started w/o sudo from the start
function create_ovs_manager_user {

    # Give the non-root user the ability to run as **root** via ``sudo``
    is_package_installed sudo || install_package sudo

    if ! getent group $UNIFI_USER >/dev/null; then
        echo "Creating a group called $UNIFI_USER"
        sudo groupadd $UNIFI_USER
    fi

    if ! getent passwd $UNIFI_USER >/dev/null; then
        echo "Creating a user called $UNIFI_USER"
        mkdir -p $UNIFI_USER_HOME
        sudo useradd -g $UNIFI_USER -s /bin/bash -d $UNIFI_USER_HOME -m $UNIFI_USER
    fi

    echo "Giving $UNIFI_USER user passwordless sudo privileges"
    # UEC images ``/etc/sudoers`` does not have a ``#includedir``, add one
    sudo grep -q "^#includedir.*/etc/sudoers.d" /etc/sudoers ||
        echo "#includedir /etc/sudoers.d" | sudo tee -a /etc/sudoers
    ( umask 226 && echo "$UNIFI_USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/99_ngs_ovs_manager )

    # Hush the login banner for ovs user
    touch $UNIFI_USER_HOME/.hushlogin
}

function configure_for_dlm {
    # limit number of ssh connections for generic-switch user
    ( umask 226 && echo "$UNIFI_USER hard maxlogins $UNIFI_USER_MAX_SESSIONS" | sudo tee /etc/security/limits.d/ngs_ovs_manager.conf )
    # set lock acquire timeout
    populate_ml2_config $UNIFI_INI_FILE ngs_coordination acquire_timeout=$UNIFI_DLM_ACQUIRE_TIMEOUT
    # set ectd3 backend
    populate_ml2_config $UNIFI_INI_FILE ngs_coordination backend_url="etcd3+http://${SERVICE_HOST}:${ETCD_PORT:-2379}?api_version=v3"
    }

function configure_unifi_ssh_keypair {
    if [[ ! -d $UNIFI_USER_HOME/.ssh ]]; then
        sudo mkdir -p $UNIFI_USER_HOME/.ssh
        sudo chmod 700 $UNIFI_USER_HOME/.ssh
    fi
    # copy over stack user's authorized_keys to UNIFI_USER
    # mostly needed for multinode gate job
    if [[ -e "$HOME/.ssh/authorized_keys" ]]; then
        cat "$HOME/.ssh/authorized_keys" | sudo tee -a $UNIFI_KEY_AUTHORIZED_KEYS_FILE
    fi
    if [[ ! -e $UNIFI_KEY_FILE ]]; then
        if [[ ! -d $(dirname $UNIFI_KEY_FILE) ]]; then
            mkdir -p $(dirname $UNIFI_KEY_FILE)
        fi
        if [[ "$HOST_TOPLOGY" != "multinode" ]]; then
            # NOTE(TheJulia): Self management of ssh keys only works locally
            # and multinode CI jobs cannot leverage it.
            echo -e 'n\n' | ssh-keygen -q -t rsa -P '' -m PEM -f $UNIFI_KEY_FILE
        fi
    fi
    # NOTE(vsaienko) check for new line character, add if doesn't exist.
    if [[ "$(sudo tail -c1 $UNIFI_KEY_AUTHORIZED_KEYS_FILE | wc -l)" == "0" ]]; then
        echo "" | sudo tee -a $UNIFI_KEY_AUTHORIZED_KEYS_FILE
    fi
    cat $UNIFI_KEY_FILE.pub | sudo tee -a $UNIFI_KEY_AUTHORIZED_KEYS_FILE
    # remove duplicate keys.
    sudo sort -u -o $UNIFI_KEY_AUTHORIZED_KEYS_FILE $UNIFI_KEY_AUTHORIZED_KEYS_FILE
    sudo chown $UNIFI_USER:$UNIFI_USER $UNIFI_KEY_AUTHORIZED_KEYS_FILE
    sudo chown -R $UNIFI_USER:$UNIFI_USER $UNIFI_USER_HOME
}

function configure_unifi_user {
    create_ovs_manager_user
    configure_unifi_ssh_keypair
    if [[ "$UNIFI_USER_MAX_SESSIONS" -gt 0 ]]; then
        configure_for_dlm
    fi

}

function configure_unifi {
    if [[ -z "$Q_ML2_PLUGIN_MECHANISM_DRIVERS" ]]; then
        Q_ML2_PLUGIN_MECHANISM_DRIVERS='unifi'
    else
        if [[ ! $Q_ML2_PLUGIN_MECHANISM_DRIVERS =~ $(echo '\<unifi\>') ]]; then
            Q_ML2_PLUGIN_MECHANISM_DRIVERS+=',unifi'
        fi
    fi
    populate_ml2_config /$Q_PLUGIN_CONF_FILE ml2 mechanism_drivers=$Q_ML2_PLUGIN_MECHANISM_DRIVERS

    # set netmiko session log
    populate_ml2_config $UNIFI_INI_FILE ngs session_log_file=$UNIFI_DATA_DIR/netmiko_session.log

    # Generate SSH keypair
    configure_unifi_user

    if [[ "${IRONIC_NETWORK_SIMULATOR:-ovs}" == "ovs" ]]; then
        sudo ovs-vsctl --may-exist add-br $UNIFI_TEST_BRIDGE
        ip link show gs_port_01 || sudo ip link add gs_port_01 type dummy
        sudo ovs-vsctl --may-exist add-port $UNIFI_TEST_BRIDGE $UNIFI_TEST_PORT
        if [[ "$UNIFI_USER_MAX_SESSIONS" -gt 0 ]]; then
            # NOTE(pas-ha) these are used for concurrent tests in tempest plugin
            N_PORTS=$(($UNIFI_USER_MAX_SESSIONS * 2))
            for ((n=0;n<$N_PORTS;n++)); do
                sudo ovs-vsctl --may-exist add-port $UNIFI_TEST_BRIDGE ${UNIFI_TEST_PORT}_${n}
            done
        fi

        if [ -e "$HOME/.ssh/id_rsa" ] && [[ "$HOST_TOPOLOGY" == "multinode" ]]; then
            # NOTE(TheJulia): Reset the key pair to utilize a pre-existing key,
            # this is instead of generating one, which doesn't work in multinode
            # environments. This is because the keys are managed and placed by zuul.
            UNIFI_KEY_FILE="${HOME}/.ssh/id_rsa"
        fi

        # Create unifi ml2 config
        for switch in $UNIFI_TEST_BRIDGE $IRONIC_VM_NETWORK_BRIDGE; do
            local bridge_mac
            bridge_mac=$(ip link show dev $switch | egrep -o "ether [A-Za-z0-9:]+"|sed "s/ether\ //")
            switch="unifi:$switch"
            add_unifi_to_ml2_config $switch $UNIFI_KEY_FILE $UNIFI_USER ::1 netmiko_ovs_linux "$UNIFI_PORT" "$bridge_mac"
        done
        echo "HOST_TOPOLOGY: $HOST_TOPOLOGY"
        echo "HOST_TOPOLOGY_SUBNODES: $HOST_TOPOLOGY_SUBNODES"
        if [ -n "$HOST_TOPOLOGY_SUBNODES" ]; then
            # NOTE(vsaienko) with multinode topology we need to add switches from all
            # the subnodes to the config on primary node
            local cnt=0
            local section
            for node in $HOST_TOPOLOGY_SUBNODES; do
                cnt=$((cnt+1))
                section="unifi:sub${cnt}${IRONIC_VM_NETWORK_BRIDGE}"
                add_unifi_to_ml2_config $section $UNIFI_KEY_FILE $UNIFI_USER $node netmiko_ovs_linux "$UNIFI_PORT"
            done
        fi
    fi
    neutron_server_config_add $UNIFI_INI_FILE

}

function add_unifi_to_ml2_config {
    local switch_name=$1
    local key_file=$2
    local username=$3
    local ip=$4
    local device_type=$5
    local port=$6
    local ngs_mac_address=$7
    local password=$8
    local enable_secret=$9
    # Use curly braces above 9 to prevent expression expansion
    local trunk_interface="${10}"

    if [[ -n "$key_file" ]]; then
        populate_ml2_config $UNIFI_INI_FILE $switch_name key_file=$key_file
    elif [[ -n "$password" ]]; then
        populate_ml2_config $UNIFI_INI_FILE $switch_name password=$password
    fi
    populate_ml2_config $UNIFI_INI_FILE $switch_name username=$username
    populate_ml2_config $UNIFI_INI_FILE $switch_name ip=$ip
    populate_ml2_config $UNIFI_INI_FILE $switch_name device_type=$device_type
    if [[ -n "$enable_secret" ]]; then
        populate_ml2_config $UNIFI_INI_FILE $switch_name secret=$enable_secret
    fi
    if [[ -n "$port" ]]; then
        populate_ml2_config $UNIFI_INI_FILE $switch_name port=$port
    fi
    if [[ -n $ngs_mac_address ]]; then
        populate_ml2_config $UNIFI_INI_FILE $switch_name ngs_mac_address=$ngs_mac_address
    fi

    if [[ "$device_type" =~ "netmiko" && "$UNIFI_USER_MAX_SESSIONS" -gt 0 ]]; then
        populate_ml2_config $UNIFI_INI_FILE $switch_name ngs_max_connections=$UNIFI_USER_MAX_SESSIONS
    fi
    if [[ -n "$trunk_interface" ]]; then
        populate_ml2_config $UNIFI_INI_FILE $switch_name ngs_trunk_ports=$trunk_interface
    fi
}

function cleanup_networking_unifi {
    rm -f $UNIFI_INI_FILE
    if [[ -f $UNIFI_KEY_FILE ]]; then
        local key
        key=$(cat $UNIFI_KEY_FILE.pub)
        # remove public key from authorized_keys
        sudo grep -v "$key" $UNIFI_KEY_AUTHORIZED_KEYS_FILE > temp && sudo mv -f temp $UNIFI_KEY_AUTHORIZED_KEYS_FILE
        sudo chown $UNIFI_USER:$UNIFI_USER $UNIFI_KEY_AUTHORIZED_KEYS_FILE
        sudo chmod 0600 $UNIFI_KEY_AUTHORIZED_KEYS_FILE
    fi
    sudo ovs-vsctl --if-exists del-br $UNIFI_TEST_BRIDGE

    # remove generic switch user, its permissions and limits
    sudo rm -f /etc/sudoers.d/99_ngs_ovs_manager
    sudo rm -f /etc/security/limits.d/ngs_ovs_manager.conf
    sudo userdel --remove --force $UNIFI_USER
    sudo groupdel $UNIFI_USER

    sudo rm -rf $UNIFI_DATA_DIR
}

function ngs_configure_tempest {
    iniset $TEMPEST_CONFIG service_available ngs True
    iniset $TEMPEST_CONFIG ngs bridge_name $UNIFI_TEST_BRIDGE
    iniset $TEMPEST_CONFIG ngs port_name $UNIFI_TEST_PORT
    if [ $UNIFI_USER_MAX_SESSIONS -gt 0 ]; then
        iniset $TEMPEST_CONFIG ngs port_dlm_concurrency $(($UNIFI_USER_MAX_SESSIONS * 2))
    fi
    iniset $TEMPEST_CONFIG baremetal_feature_enabled trunks_supported True
}

# check for service enabled
if is_service_enabled unifi; then

    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing Generic_switch ML2"
        install_unifi

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after the other layer 1 and 2 services have been configured
        echo_summary "Configuring Generic_switch ML2"

        # Source ml2 plugin, set default config
        if is_service_enabled neutron; then
            source $RC_DIR/lib/neutron_plugins/ml2
            Q_PLUGIN_CONF_PATH=etc/neutron/plugins/ml2
            Q_PLUGIN_CONF_FILENAME=ml2_conf.ini
            Q_PLUGIN_CONF_FILE="/${Q_PLUGIN_CONF_PATH}/${Q_PLUGIN_CONF_FILENAME}"
            Q_PLUGIN_CLASS="ml2"
        fi

        configure_unifi
    elif [[ "$1" == "stack" && "$2" == "test-config" ]]; then
        if is_service_enabled tempest; then
            echo_summary "Configuring Tempest NGS"
            ngs_configure_tempest
        fi
    fi

    if [[ "$1" == "unstack" ]]; then
        echo_summary "Cleaning Networking-generic-switch"
        cleanup_networking_unifi
    fi
fi
