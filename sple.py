#! /usr/bin/env python
# -*- coding: utf-8 -*-
import glob, os
import nginx
import argparse
import commands
# Argument parsing
ap = argparse.ArgumentParser(description='A Python script that automates the SSL installation on Ubuntu servers managed by ServerPilot free plan.')
ap.add_argument('-d', '--domain', dest='domain', help='Domain name of the app', default=False)
ap.add_argument('-r', '--root', dest='root', help='Root directory of the app including public', default=False)
ap.add_argument('-a', '--all', dest='all', help='Install SSL for all available apps.', action='store_const', const=True, default=False)
ap.add_argument('-n', '--name', dest='appname', help='Name of the app.', default=False)

args = ap.parse_args()
vhostsdir = '/etc/nginx-sp/vhosts.d/' # ServerPilot vhosts directory
class bcolors:
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'

def find_between(s, first, last):
	try:
		start = s.index( first ) + len( first )
		end = s.index( last, start )
		return s[start:end]
	except ValueError:
		return None

def search(value, data):
	for conf in data:
		blocks = conf.get('server')
		for block in blocks:
			found = block.get(value)
			if found:
				return found
	return None

def apps():
	spapps = []
	print(bcolors.HEADER+'Finding apps for serverpilot user.'+bcolors.ENDC)
	if os.path.isdir(vhostsdir):
		for conf_file in glob.glob(vhostsdir+'/*.conf'):
			if '-ssl.conf' not in conf_file:
				c = nginx.loadf(conf_file).as_dict
				data = c.get('conf')[-1:]
				try:
					domains = search('server_name', data).split() # All app domains
				except:
					domains = None
				try:
					root = search('root', data)
				except:
					root = None
				try:
					appname = find_between(root, 'apps/', '/')
				except:
					appname = None
				if(appname and domains and root):
					domaininfo = {'domains': domains, 'root': root, 'appname': appname}
					spapps.append(domaininfo)
	if(len(spapps) > 0):
		print(bcolors.OKBLUE+str(len(spapps))+' apps found! Proceeding further...'+bcolors.ENDC)
	else:
		print(bcolors.FAIL+'No apps found. Ensure that you have created some apps under free serverpilot user.'+bcolors.ENDC)
	return spapps

def certbot_command(root, domains):
	domainsstr = ''
	for domain in domains:
		domainsstr += ' -d '+domain
	cmd = "certbot certonly --webroot -w "+root+" --register-unsafely-without-email --agree-tos --force-renewal"+domainsstr
	return cmd

def write_conf(app):
	print(bcolors.OKBLUE+'Writing NGINX vhost file for the app '+bcolors.BOLD+app.get('appname')+bcolors.ENDC)
	appname = app.get('appname')
	root = app.get('root')
	confname = vhostsdir + appname + '-ssl.conf'
	domains = app.get('domains')
	c = nginx.Conf()
	s = nginx.Server()
	s.add(
		nginx.Comment('SSL conf added by rwssl (https://github.com/rehmatworks/serverpilot-letsencrypt)'),
		nginx.Key('listen', '443 ssl http2'),
		nginx.Key('listen', '[::]:443 ssl http2'),
		nginx.Key('server_name', ' '.join(domains)),
		nginx.Key('ssl', 'on'),
		nginx.Key('ssl_certificate', '/etc/letsencrypt/live/'+domains[0]+'/fullchain.pem'),
		nginx.Key('ssl_certificate_key', '/etc/letsencrypt/live/'+domains[0]+'/privkey.pem'),
		nginx.Key('root', root),
		nginx.Key('access_log', '/srv/users/serverpilot/log/'+appname+'/dev_nginx.access.log main'),
		nginx.Key('error_log', '/srv/users/serverpilot/log/'+appname+'/dev_nginx.error.log'),
		nginx.Key('proxy_set_header', 'Host $host'),
		nginx.Key('proxy_set_header', 'X-Real-IP $remote_addr'),
		nginx.Key('proxy_set_header', 'X-Forwarded-For $proxy_add_x_forwarded_for'),
		nginx.Key('proxy_set_header', 'X-Forwarded-SSL on'),
		nginx.Key('proxy_set_header', 'X-Forwarded-Proto $scheme'),
		nginx.Key('include', '/etc/nginx-sp/vhosts.d/'+appname+'.d/*.nonssl_conf'),
		nginx.Key('include', '/etc/nginx-sp/vhosts.d/'+appname+'.d/*.conf'),
	)
	c.add(s)
	try:
		nginx.dumpf(c, confname)
		print(bcolors.OKGREEN+'Virtual host file created!'+bcolors.ENDC)
		print(bcolors.OKBLUE+'Reloading NGINX server...'+bcolors.ENDC)
		os.system('sudo service nginx-sp reload')
		print(bcolors.OKGREEN+'SSL should have been installed and activated for the app '+bcolors.BOLD+app.get('appname')+bcolors.ENDC)
		return True
	except:
		print(bcolors.FAIL+'Virtual host file cannot be created!'+bcolors.ENDC)
		return False

def install_certbot():
	return 'sudo apt-get update && yes | sudo apt-get install software-properties-common && yes | sudo add-apt-repository ppa:certbot/certbot && yes | sudo apt-get update && yes | sudo apt-get install certbot'

def get_ssl(app):
	print(bcolors.OKBLUE+'Obtaining SSL certificate for '+app.get('appname')+'.'+bcolors.ENDC)
	checkcertbot = commands.getstatusoutput('certbot')
	errcodes = [32512]
	if checkcertbot[0] in errcodes:
		print(bcolors.OKBLUE+'Certbot (Let\'s Encrypt libraries) not found. Installing libs.'+bcolors.ENDC)
		certbotcmd = install_certbot();
		commands.getstatusoutput(certbotcmd)
		print(bcolors.OKGREEN+'Finished installing required libraries.'+bcolors.ENDC)
	if(os.path.isdir(app.get('root'))):
		domains = app.get('domains')
		cmd = certbot_command(app.get('root'), domains)
		cboutput = commands.getstatusoutput(cmd)[1]
		if 'Congratulations' in cboutput:
			print(bcolors.OKGREEN+'SSL has been successfully obtained for '+' '.join(domains)+bcolors.ENDC)
			return True
		elif 'Failed authorization procedure' in cboutput:
			print(bcolors.FAIL+'DNS check failed. Please ensure that the domain(s) '+bcolors.BOLD+' '.join(domains)+bcolors.ENDC+bcolors.FAIL+' are resolving to your server as well as you have provided the correct root path of your app (including public).'+bcolors.ENDC)
		elif 'too many requests' in cboutput:
			print(bcolors.FAIL+'SSL limit reached for '+' '.join(domains)+'. Please wait before obtaining another SSL.'+bcolors.ENDC)
		else:
			print(bcolors.FAIL+'Something went wrong. SSL cannot be installed for '+bcolors.BOLD+' '.join(domains)+bcolors.ENDC)
	else:
		print(bcolors.FAIL+'Provided path of the app seems to be invalid.'+bcolors.ENDC)
		exit
	return False

if args.all is True:
	apps = apps()
	for app in apps:
		install = get_ssl(app)
		if(install):
			write_conf(app)
else:
	if args.appname and args.domain and args.root:
		app = {'appname': args.appname, 'domains': [args.domain], 'root': args.root}
		install = get_ssl(app)
		if(install):
			write_conf(app)
	else:
		print(bcolors.OKBLUE+'No or incorrect arguments supplied. Type '+bcolors.BOLD+'rwssl -h'+bcolors.ENDC+bcolors.OKBLUE+' to get help.'+bcolors.ENDC)
