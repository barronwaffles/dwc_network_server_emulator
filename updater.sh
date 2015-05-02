#!/bin/bash
#
#
# This script will automatically pull in any changes on the public git so your server is at the latest version
# It is recommended you kill master server first before running
#
#
#
echo "===================================ALTWFC Server Updater==================================="
echo
echo "1) - Initiate the update process"
echo "2) - Quit"
read -p "Please make your choice"
until [ $REPLY -le "2" ] ; do
clear
echo "===================================ALTWFC Server Updater==================================="
echo
echo "1) - Initiate the update process"
echo "2) - Quit"
echo
echo "$REPLY is an invalid entry"
read -p "Please make your choice"
done
#The menu will keep looping until either 1 or 2 are picked
if [ $REPLY == "1" ] ; then
echo "Updating now...."
sleep 1s
git pull
echo "-done-"
fi
if [ $REPLY == "2" ] ; then
exit
fi
exit 0
