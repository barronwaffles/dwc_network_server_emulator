#!/bin/bash
#Variables used by the script in various sections to pre-fill long commandds
ROOT_UID="0"
apache="/etc/apache2/sites-available"
vh="./apache-hosts"
vh1="gamestats2.gs.nintendowifi.net"
vh2="gamestats.gs.nintendowifi.net"
vh3="nas-naswii-dls1-conntest.nintendowifi.net"
vh4="sake.gs.nintendowifi.net"
mod1="proxy.conf"
mod2="proxy_http.load"
mod3="proxy.load"
mod4="proxy" #This is a fallback module for use with OS's that don't support mod1, mod2 or mod3
cp="/etc/apache2/sites-enabled"
#Don't forget to install the git package before running this script
#Check if run as root
if [ "$UID" -ne "$ROOT_UID" ] ; then
	echo "You must be root to do that!"
	exit 1
fi

echo "Hello and welcome to my installation script. I assume you're running this as root?"
sleep 5s
echo "Okay! Gotta love when a plan comes together!"
echo "Let me install a few upgrade and packages on your system for you...."
echo "If you already have a package installed, I'll simply skip over it or upgrade it"
apt-get update -y --fix-missing
echo "Updated repo lists...."
echo "Installing package upgrades... go kill some time as this may take a few minutes..."
apt-get upgrade -y
clear
echo "Upgrades complete!"
echo "Now installing required packages..."
apt-get install apache2 python2.7 python-twisted dnsmasq -y
echo "Installing Apache, Python 2.7, Python Twisted and DNSMasq....."
clear
echo "Now that that's out of the way, let's do some apache stuff"
echo "Copying virtual hosts to sites-available for virtual hosting of the server"
cp ./$vh/$vh1 $apache/$vh1
cp ./$vh/$vh2 $apache/$vh2
cp ./$vh/$vh3 $apache/$vh3
cp ./$vh/$vh4 $apache/$vh4
sleep 5s
echo "Copying virtual hosts to sites-enabled for virtual hosting of the server"
cp ./$vh/$vh1 $cp/$vh1
cp ./$vh/$vh2 $cp/$vh2
cp ./$vh/$vh3 $cp/$vh3
cp ./$vh/$vh4 $cp/$vh4
sleep 5s
clear
echo "Okay! Lets hope nothing broke during this process..."
sleep 5s
echo "Now lets enable some modules so we can make all of this work..."
a2enmod $mod1 $mod2 $mod3
if [ $? != "0"] then:
	a2enmod $mod4
fi
echo "Great! Everything appears to be set up as far as Apache"
service apache2 restart
service apache2 reload
apachectl graceful
echo "If any errors occour besides the hostname or server name error please look into this yourself"
sleep 5s
clear
echo "----------Lets configure DNSMASQ now----------"
sleep 3s
echo "What is your EXTERNAL IP?"
read -e IP
cat >>/etc/dnsmasq.conf <<EOF
address=/nintendowifi.net/$IP
EOF
clear
echo "DNSMasq setup completed!"
clear
service dnsmasq restart
echo "Now, let's set up the admin page login info...."
sleep 3s
echo "Please type your user name: "
read -e USR
echo "Please enter the password you want to use: "
read -s PASS
cat > ./adminpageconf.json <<EOF
{"username":"$USR","password":"$PASS"}
EOF
echo "Username and password configured!"
echo "NOTE: To get to the admin page type in the IP of your server :9009/banhammer"
clear
echo "Now, I BELIEVE everything should be in working order. If not, you might have to do some troubleshooting"
echo "Assuming my coding hasnt gotten the best of me, you should be in the directory with all the python script along with a new .json file for the admin page info"
echo "I will now quit...."
exit 0
