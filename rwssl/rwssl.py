#! /usr/bin/env python
# -*- coding: utf-8 -*-
import glob, os
import nginx
import argparse
import commands

# ServerPilot vhosts directory
vhostsdir = '/etc/nginx-sp/vhosts.d/'
# Cron file of certbot
cronfile = '/etc/cron.d/rwsslrenew'
# Cron file of rwssl autopilot
rwsslcron = '/etc/cron.d/rwssl'

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

def get_conf_files(rootdir):
	if os.path.isdir(rootdir):
		confs = []
		for conf_file in glob.glob(rootdir+'/*.conf'):
			confs.append(conf_file)
		return confs
	return False

def ssl_installed(app):
	vhostfile = os.path.join(vhostsdir + app.get('appname')+'-ssl.conf')
	if os.path.exists(vhostfile):
		return True
	return False

def apps():
	spapps = []
	print(bcolors.HEADER+'Finding apps for serverpilot user.'+bcolors.ENDC)
	conf_files = get_conf_files(vhostsdir)
	if conf_files:
		for conf_file in conf_files:
			if '-ssl.conf' not in conf_file:
				appinfo = get_app_info(conf_file)
				if(appinfo):
					spapps.append(appinfo)
	if(len(spapps) > 0):
		print(bcolors.OKBLUE+str(len(spapps))+' apps found in total. Proceeding further...'+bcolors.ENDC)
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

def get_app_info(conf_file):
	domaininfo = False
	if os.path.exists(conf_file):
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
	return domaininfo

def install_sp_cron():
	if(os.path.exists(cronfile)):
		print(bcolors.OKBLUE+'CRON job is already added properly and renewals should work out of the box.'+bcolors.ENDC)
	else:
		try:
			with open(cronfile, 'w') as f:
				f.write("0 */6 * * * root /usr/local/bin/rwssl -r > /dev/null 2>&1\n")
			print(bcolors.OKGREEN+'Cron job has been successfully installed for SSL renewals.'+bcolors.ENDC)
		except:
			print(bcolors.FAIL+'CRON job cannot be added. Please ensure that you have root privileges.'+bcolors.ENDC)

def renew_ssls():
	cmd = 'certbot renew'
	commands.getstatusoutput(cmd)
	print(bcolors.OKBLUE+'Renewals should have been succeeded for all expiring SSLs.'+bcolors.ENDC)

def get_ssl(app):
	print(bcolors.OKBLUE+'Obtaining SSL certificate for the app '+bcolors.BOLD+app.get('appname')+'.'+bcolors.ENDC)
	checkcertbot = commands.getstatusoutput('certbot')
	errcodes = [32512]
	if checkcertbot[0] in errcodes:
		print(bcolors.OKBLUE+'Certbot (Let\'s Encrypt libraries) not found. Installing libs.'+bcolors.ENDC)
		certbotcmd = install_certbot();
		commands.getstatusoutput(certbotcmd)
		print(bcolors.OKGREEN+'Finished installing required libraries.'+bcolors.ENDC)
		print(bcolors.OKBLUE+'Retrying SSL certificate retrieval for the app '+bcolors.BOLD+app.get('appname')+'.'+bcolors.ENDC)
	if(os.path.isdir(app.get('root'))):
		domains = app.get('domains')
		cmd = certbot_command(app.get('root'), domains)
		cboutput = commands.getstatusoutput(cmd)[1]
		if 'Congratulations' in cboutput:
			print(bcolors.OKGREEN+'SSL certificate has been successfully obtained for '+' '.join(domains)+bcolors.ENDC)
			return True
		elif 'Failed authorization procedure' in cboutput:
			print(bcolors.FAIL+'DNS check failed. Please ensure that the domain(s) '+bcolors.BOLD+' '.join(domains)+bcolors.ENDC+bcolors.FAIL+' are resolving to your server as well as you have provided the correct root path of your app (including public).'+bcolors.ENDC)
		elif 'too many requests' in cboutput:
			print(bcolors.FAIL+'SSL certificates limit reached for '+' '.join(domains)+'. Please wait before obtaining another SSL.'+bcolors.ENDC)
		else:
			print(bcolors.FAIL+'Something went wrong. SSL certificate cannot be installed for '+bcolors.BOLD+' '.join(domains)+bcolors.ENDC)
	else:
		print(bcolors.FAIL+'Provided path of the app seems to be invalid.'+bcolors.ENDC)
		exit
	return False

def ssl_status():
	theapps = False
	allapps = apps()
	if(len(allapps) > 0):
		nonssl = []
		sslapps = []
		for app in allapps:
			if(ssl_installed(app)):
				sslapps.append(app)
			else:
				nonssl.append(app)
		theapps = {'ssl': sslapps, 'nonssl': nonssl}
	return theapps

def do_final_ssl_install(app):
	install = get_ssl(app)
	if(install):
		write_conf(app)

def add_autopilot_cron():
	if(os.path.exists(rwsslcron)):
		print(bcolors.OKBLUE+'Autopilot CRON job is already added and it should be working out of the box.'+bcolors.ENDC)
	else:
		try:
			with open(rwsslcron, 'w') as f:
				f.write("0,10 * * * * root /usr/local/bin/rwssl -f > /dev/null 2>&1\n")
			print(bcolors.OKGREEN+'Autopilot CRON job has been added and now SSL should get installed on your new apps automatically.'+bcolors.ENDC)
		except:
			print(bcolors.FAIL+'Autopilot CRON job cannot be added. Please ensure that you have root privileges.'+bcolors.ENDC)

def disable_autopilot_cron():
	if(os.path.exists(rwsslcron)):
		try:
			os.unlink(rwsslcron)
			print(bcolors.OKBLUE+'Autopilot CRON job has been disabled.'+bcolors.ENDC)
		except:
			print(bcolors.FAIL+'An error occured while disabling Autopilot CRON.'+bcolors.ENDC)
	else:
		print(bcolors.OKBLUE+'Autopilot CRON job is not configured yet. No action needed.'+bcolors.ENDC)

class bcolors:
	HEADER = '\033[95m'
	OKBLUE = '\033[94m'
	OKGREEN = '\033[92m'
	WARNING = '\033[93m'
	FAIL = '\033[91m'
	ENDC = '\033[0m'
	BOLD = '\033[1m'
	UNDERLINE = '\033[4m'

def main():
	global apps
	ap = argparse.ArgumentParser(description='A Python script that automates the SSL installation on Ubuntu servers managed by ServerPilot free plan.')
	ap.add_argument('-a', '--all', dest='all', help='Install SSL for all available apps.', action='store_const', const=True, default=False)
	ap.add_argument('-f', '--fresh', dest='fresh', help='Obtain and install SSL certificates for new (non-ssl) apps only.', action='store_const', const=True, default=False)
	ap.add_argument('-i', '--ignore', dest='ignoreapps', help='Comma-seperated app names to ignore some apps and install SSL for all others.', default=False)
	ap.add_argument('-n', '--name', dest='appname', help='Name of the app where SSL should be installed.', default=False)
	ap.add_argument('-r', '--renew', dest='renew', help='Renew all installed SSL certificates which are about to expire.', action='store_const', const=True, default=False)
	ap.add_argument('-ic', '--installcron', dest='installcron', help='Install the cron job for SSL renewals.', action='store_const', const=True, default=False)
	ap.add_argument('-ap', '--autopilot', dest='autopilot', help='A CRON job that attempts to automatically obtain SSL certificates for newly added apps.', action='store_const', const=True, default=False)
	ap.add_argument('-na', '--noautopilot', dest='noautopilot', help='Disable Autopilot mode and disable automatic SSLs for your apps.', action='store_const', const=True, default=False)

	args = ap.parse_args()

	if args.all is True:
		apps = apps()
		for app in apps:
			do_final_ssl_install(app)

	elif args.appname:
		vhostfile = vhostsdir+args.appname+'.conf'
		app = get_app_info(vhostfile)
		if app:
			do_final_ssl_install(app)
		else:
			print(bcolors.FAIL+'Provided app name seems to be invalid as we did not find any vhost files for it.'+bcolors.ENDC)
	elif args.ignoreapps:
		apps = apps()
		ignoreapps = args.ignoreapps.split(',')
		print(bcolors.OKBLUE+str(len(ignoreapps))+' apps are being ignored.'+bcolors.ENDC)
		for app in apps:
			if app.get('appname') not in ignoreapps:
				do_final_ssl_install(app)
	elif args.renew is True:
		renew_ssls()
	elif args.installcron is True:
		install_sp_cron()
	elif args.fresh is True:
		sslstatus = ssl_status()
		nonsslapps = sslstatus.get('nonssl')
		if(len(nonsslapps) > 0):
			print(bcolors.OKBLUE+str(len(nonsslapps))+' non-ssl apps found for which SSL can be obtained. Proceeding...'+bcolors.ENDC)
			for nonssl in nonsslapps:
				do_final_ssl_install(nonssl)
		else:
			print(bcolors.OKBLUE+'We could not find any apps without SSL certificates installed.'+bcolors.ENDC)
	elif args.autopilot is True:
		add_autopilot_cron()
	elif args.noautopilot is True:
		disable_autopilot_cron()
	else:
		ap.print_help()