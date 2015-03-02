#!/bin/bash
ROOT_UID="0"
#Please put this script into your home folder
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
apt-get update -y >/dev/null
echo "Updated repo lists...."
echo "Installing package upgrades... go kill some time as this may take a few minutes..."
apt-get upgrade -y >/dev/null
clear
echo "Upgrades complete!"
echo "Now installing required packages..."
apt-get install apache2 python2.7 python-twisted git dnsmasq -y >/dev/null
echo "Installing Apache, Python 2.7, Python Twisted, GitHub and DNSMasq....."
clear
echo "Where is your Apache config directory?"
echo "For example: /etc/apache2"
read -e APACHEDIR
echo "The path your provided is: $APACHEDIR"
echo "Now I will clone the github repo to the directory of where this script is"
git clone https://github.com/BeanJr/dwc_network_server_emulator
echo "Now that that's out of the way, let's do some apache stuff"
cd "$APACHEDIR"
echo "I've changed directory to $APACHEDIR"
echo "Creating sites to sites-available for virtual hosting of the server"
echo "changing directory to sites-available"
cd "$APACHEDIR/sites-available/"
cat > /"$APACHDRIR/gamestats2.gs.nintendowifi.net" <<EOF
<VirtualHost *:80>
        ServerAdmin webmaster@localhost
        ServerName gamestats2.gs.nintendowifi.net
        ServerAlias "gamestats2.gs.nintendowifi.net, gamestats2.gs.nintendowifi.net"
 
        ProxyPreserveHost On
 
        ProxyPass / http://127.0.0.1:9002/
        ProxyPassReverse / http://127.0.0.1:9002/
</VirtualHost>
EOF

cat > /"$APACHDRIR/gamestats.gs.nintendowifi.net" <<EOF
<VirtualHost *:80>
        ServerAdmin webmaster@localhost
        ServerName gamestats.gs.nintendowifi.net
        ServerAlias "gamestats.gs.nintendowifi.net, gamestats.gs.nintendowifi.net"
        ProxyPreserveHost On
        ProxyPass / http://127.0.0.1:9002/
        ProxyPassReverse / http://127.0.0.1:9002/
</VirtualHost>
EOF

cat > /"$APACHDRIR/nas-naswii-dls1-conntest.nintendowifi.net" <<EOF
<VirtualHost *:80>
        ServerAdmin webmaster@localhost
        ServerName naswii.nintendowifi.net
        ServerAlias "naswii.nintendowifi.net, naswii.nintendowifi.net"
        ServerAlias "nas.nintendowifi.net"
        ServerAlias "nas.nintendowifi.net, nas.nintendowifi.net"
        ServerAlias "dls1.nintendowifi.net"
        ServerAlias "dls1.nintendowifi.net, dls1.nintendowifi.net"
        ServerAlias "conntest.nintendowifi.net"
        ServerAlias "conntest.nintendowifi.net, conntest.nintendowifi.net"
        ProxyPreserveHost On
        ProxyPass / http://127.0.0.1:9000/
        ProxyPassReverse / http://127.0.0.1:9000/
</VirtualHost>
EOF

cat > /"$APACHDRIR/sake.gs.nintendowifi.net" <<EOF
<VirtualHost *:80>
        ServerAdmin webmaster@localhost
        ServerName sake.gs.nintendowifi.net
        ServerAlias sake.gs.nintendowifi.net *.sake.gs.nintendowifi.net
        ServerAlias secure.sake.gs.nintendowifi.net
        ServerAlias secure.sake.gs.nintendowifi.net *.secure.sake.gs.nintendowifi.net
 
        ProxyPass / http://127.0.0.1:8000/
 
        CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
EOF

clear
echo "Okay! Lets hope nothing broke during this process..."
sleep 5s
echo "Now lets enable the sites so Apache can use them"
a2ensite gamestats2.gs.nintendowifi.net gamestats.gs.nintendowifi.net nas-naswii-dls1-conntest.nintendowifi.net sake.gs.nintendowifi.net
echo "Now lets enable some modules so we can make all of this work..."
a2enmod proxy.conf proxy_http.load proxy.load
echo "Great! Everything appears to be set up as far as Apache"
service apache2 restart
service apache2 reload
echo "If any errors occour besides the hostname or server name error please look into this yourself as my bash scripting knowledge is very limited"
sleep 5s
echo "----------Lets configure DNSMASQ now----------"
sleep 3s
echo "What is your EXTERNAL IP?"
read -e IP
cat >>/etc/dnsmasq.conf <<EOF
address=/nintendowifi.net/$IP
EOF
clear
echo "DNSMasq setup completed!"
echo "Let's go back to the home directory where all this began"
cd
clear
cd "dwc_network_server_emulator"
echo "Now, let's set up the admin page login info...."
sleep 3s
echo "Please type your user name: "
read -e USR
echo "Please enter the password you want to use: "
read -s PASS
cat > adminpageconf.json <<EOF
{"username":"$USR","password":"$PASS"}
EOF
echo "Username and password configured!"
echo "NOTE: To get to the admin page type in the IP of your server :9009/banhammer"
clear
echo "Now, I BELIEVE everything should be in working order. If not, you might have to do some troubleshooting"
echo "Assuming my coding hasnt gotten the best of me, you should be in the directory with all the python script along with a new .json file for the admin page info"
echo "I will now quit...."
exit 1
