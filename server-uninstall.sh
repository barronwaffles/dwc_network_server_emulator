#!/bin/bash
ROOT_UID="0"
#This script is highly experimental and MAY NOT REMOVE EVERYTHING
#Please test!
#Please put this script into your home folder
#Save all your work before running this script as it will do a final reboot
#Check if run as root
#This script will leave the git cloned folder in your home folder
#Feel free to remove it when you're all done
if [ "$UID" -ne "$ROOT_UID" ] ; then
	echo "You must be root to do that!"
	exit 1
fi

echo "Hello and welcome to my uninstall script. I assume you're running this as root?"
sleep 3s
echo "Okay! Gotta love when a plan comes together!"
echo "Where is your Apache config directory?"
echo "For example: /etc/apache2"
echo "No trailing / please as this will break things"
read -e APACHEDIR
echo "The path your provided is: $APACHEDIR/"
cd "$APACHEDIR"
echo "I've changed directory to $APACHEDIR/"
echo "Removing sites in sites-available for virtual hosting of the server"
echo "changing directory to sites-available"
cd "$APACHEDIR/sites-available/"
rm -r -f $APACHEDIR/sites-available/gamestats2.gs.nintendowifi.net
rm -r -f $APACHEDIR/sites-available/gamestats.gs.nintendowifi.net
rm -r -f $APACHEDIR/sites-available/nas-naswii-dls1-conntest.nintendowifi.net
rm -r -f $APACHEDIR/sites-available/sake.gs.nintendowifi.net
clear
echo "Okay! Lets hope nothing broke during this process..."
sleep 5s
echo "Now lets disable the sites...."
a2dissite gamestats2.gs.nintendowifi.net gamestats.gs.nintendowifi.net nas-naswii-dls1-conntest.nintendowifi.net sake.gs.nintendowifi.net
echo "Now lets disable some modules..."
a2dismod proxy.conf proxy_http.load proxy.load
echo "Great! Everything appears to be remove as far as Apache"
service apache2 restart
service apache2 reload
clear
echo "Let me remove some packages from your system...."
echo "If you already have a package remove, I'll simply skip over it"
apt-get remove apache2 python2.7 python-twisted git dnsmasq -y --purge >/dev/null
echo "Removing and purging configurations for Apache, Python, Python Twisted, GitHub and DNSMASQ"
clear
echo "Now, I BELIEVE everything should be in working order. If not, you might have to do some troubleshooting"
echo "Assuming my coding hasnt gotten the best of me, you should be in the directory with all the python script along with a new .json file for the admin page info"
echo "I will now reboot...."
echo "NOTE: I've left the git clone in your home folder. Do whatever you want with it"
echo "Rebooting in 15 seconds...."
sleep 15s
reboot
