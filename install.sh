#!/bin/sh

# NuvlaEdge advanced installation script
# This script is an alternative for the conventional one-command `docker compose ... ` installation/halt/remove methods
# It provides extra checks and guidance for making sure that:
#  1. there are no existing NuvlaEdge already running
#  2. handle existing installations before installing a new one
#  3. checks installation requirements
#  4. installs/updates/removes NuvlaEdge

compose_files="docker-compose.yml"
strategies="UPDATE OVERWRITE"
strategy="UPDATE"
actions="INSTALL REMOVE HALT"
action="INSTALL"
extra_env=""
env_file=""

usage()
{
    echo "NuvlaEdge advanced installation wrapper"
    echo ""
    echo "./install.sh"
    echo ""
    echo " -h --help"
    echo " --environment=KEY1=value1,KEY2=value2\t\t(optional) Comma-separated environment keypair values"
    echo " --env-path=PATH\t\t\t\t(optional) Path for env file"
    echo " --compose-files=file1.yml,file2.yml\t\t(optional) Comma-separated list of compose files to deploy. Default: ${compose_files}"
    echo " --installation-strategy=STRING\t\t\t(optional) Strategy when action=INSTALL. Must be on of: ${strategies}. Default: ${strategy}"
    echo "\t\t UPDATE - if NuvlaEdge is already running, replace outdated components and start stopped ones. Otherwise, install"
    echo "\t\t OVERWRITE - if NuvlaEdge is already running, shut it down and re-install. Otherwise, install"
    echo " --action=STRING\t\t\t\t(optional) What action to take. Must be on of: ${actions}. Default: ${action}"
    echo "\t\t INSTALL - runs 'docker compose up'"
    echo "\t\t REMOVE - removes NuvlaEdge and all associated data. Same as 'docker compose down -v"
    echo "\t\t HALT - shuts down NuvlaEdge but keeps data, so it can be revived later. Same as 'docker compose down"
    echo ""
}

while [ "$1" != "" ]; do
    PARAM=`echo $1 | awk -F= '{print $1}'`
    VALUE=`echo $1 | cut -d "=" -f 2-`
    case $PARAM in
        -h | --help)
            usage
            exit
            ;;
        --environment)
            extra_env=$VALUE
            ;;
        --env-file)
            env_file=$VALUE
            ;;
        --compose-files)
            compose_files=$VALUE
            ;;
        --installation-strategy)
            strategy=$VALUE
            ;;
        --action)
            action=$VALUE
            ;;
        *)
            echo "ERROR: unknown parameter \"$PARAM\""
            usage
            exit 1
            ;;
    esac
    shift
done

which docker >/dev/null
if [ $? -ne 0 ]
then
  echo "ERR: docker is not installed. Cannot continue"
  exit 1
fi

set -x

if [ ! -z "${extra_env}" ]
then
  echo "Setting up environment ${extra_env}"
  export $(echo ${extra_env} | tr ',' ' ') &>/dev/null
fi

command_compose_files=""
for file in $(echo ${compose_files} | tr ',' '\n')
do
  command_compose_files="${command_compose_files} -f ${file}"
done

command_env=""
if [ ! -z "${env_file}" ]
then
  command_env="${command_env} --env-file ${env_file}"
fi

if [ "${action}" = "REMOVE" ]
then
  echo "INFO: removing NuvlaEdge installation completely"
  docker compose -p nuvlaedge ${command_compose_files} ${command_env} down -v
  ([ ! -z "${env_file}" ] && rm "${env_file}")
elif [ "${action}" = "HALT" ]
then
  echo "INFO: halting NuvlaEdge. You can bring it back later by simply re-installing with the same parameters as before"
  docker compose -p nuvlaedge ${command_compose_files} ${command_env} down
elif [ "${action}" = "INSTALL" ]
then
  if [ "${strategy}" = "UPDATE" ]
  then
    existing_projects=$(docker compose -p nuvlaedge ${command_compose_files} ${command_env} ps -a -q)
    if [ ! -z "${existing_projects}" ]
    then
      echo "INFO: found an active NuvlaEdge installation. Updating it"
    else
      echo "INFO: no active NuvlaEdge installations found. Installing from scratch"
    fi
    docker compose -p nuvlaedge ${command_compose_files} ${command_env} up -d
  elif [ "${strategy}" = "OVERWRITE" ]
  then
    echo "WARNING: about to delete any existing NuvlaEdge installations...press Ctrl+c in the next 5 seconds to stop"
    sleep 5
    docker compose -p nuvlaedge ${command_compose_files} ${command_env} down -v --remove-orphans
    echo "INFO: installing NuvlaEdge from scratch"
    docker compose -p nuvlaedge ${command_compose_files} ${command_env} up -d
  else
    echo "WARNING: strategy ${strategy} not recognized. Use -h for help. Nothing to do"
  fi
else
  echo "WARNING: action ${action} not recognized. Use -h for help. Nothing to do"
  exit 0
fi
