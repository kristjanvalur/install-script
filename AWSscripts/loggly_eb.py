#!/usr/bin/env python
#
# loggly_eb.py
# For configuring loggly on AWD elastic beanstalk instances.
# Tested on the following EB configurations:
# 64 bit Amazon Linux 2017.03 v.2.5.2 running Python 3.4


from __future__ import print_function
import os
import sys
import argparse
import subprocess
import shlex
import textwrap
import shutil
import six

LOGGLY_DISTRIBUTION_ID = "41058"
LOGS_01_HOST = "logs-01.loggly.com"
LOGGLY_SYSLOG_PORT = 514

# directory location for syslog
RSYSLOG_ETCDIR_CONF = '/etc/rsyslog.d'
# name and location of loggly syslog file
LOGGLY_RSYSLOG_CONFFILE = RSYSLOG_ETCDIR_CONF + '/22-loggly.conf'
# name and location of loggly syslog backup file
LOGGLY_RSYSLOG_CONFFILE_BACKUP = LOGGLY_RSYSLOG_CONFFILE + '.loggly.bk'
# rsyslog service name
RSYSLOG_SERVICE = 'rsyslog'


def main():

    # parse args
    parser = argparse.ArgumentParser(description='Initialize loggly logging')
    parser.add_argument('--account', '-a', default=os.environ.get('LOGGLY_ACCOUNT'), help='The Loggly account name (default from LOGGLY_ACCOUNT)')
    parser.add_argument('--token', '-t', default=os.environ.get('LOGGLY_TOKEN'), help='The Loggly authentication token (default from LOGGLY_TOKEN)')
    parser.add_argument('--tags', nargs='*', help='Additional tags (default from LOGGLY_TAGS)')
    parser.add_argument('--hostname', default=os.environ.get('LOGGLY_HOSTNAME'))
    parser.add_argument('--remove', '-r', action='store_true', help='remove loggly configuration')

    args = parser.parse_args()

    if args.remove:
        unconfigure()
        return

    if not args.account or not args.token:
        parser.print_usage()
        sys.exit(1)

    if args.tags is not None:
        tags = args.tags
    elif os.environ.get('LOGGLY_TAGS'):
        tags = shlex.split(os.environ['LOGGLY_TAGS'])
    else:
        tags = None

    config = {
        'account': args.account,
        'token': args.token,
        'tags': tags,
        'hostname': args.hostname,
    }
    configure(config)


def configure(config):
    log("INFO: Initiating Configure Loggly for Linux.")

    # if all the above check passes, write the 22-loggly.conf file
    write_rsyslog_conf(config)

    # restart rsyslog service
    restart_rsyslog()

    log("SUCCESS: Linux system successfully configured to send logs via Loggly.")


def write_rsyslog_conf(config):
    '''write the contents to 22-loggly.conf file'''
    contents = get_loggly_conf(config)
    write_script = False

    if os.path.exists(LOGGLY_RSYSLOG_CONFFILE):
        log("INFO: Loggly rsyslog file %r already exist." % LOGGLY_RSYSLOG_CONFFILE)
        with open(LOGGLY_RSYSLOG_CONFFILE, "rb") as fd:
            old_contents = fd.read()
        if six.b(contents) != old_contents:
            log("WARN: Loggly rsyslog file %r content has changed." % LOGGLY_RSYSLOG_CONFFILE)
            log("INFO: Going to back up the conf file: %r to %r" % (LOGGLY_RSYSLOG_CONFFILE, LOGGLY_RSYSLOG_CONFFILE_BACKUP))
            shutil.move(LOGGLY_RSYSLOG_CONFFILE, LOGGLY_RSYSLOG_CONFFILE_BACKUP)
            write_script = True
    else:
        write_script = True
    if write_script:
        with open(LOGGLY_RSYSLOG_CONFFILE, "wb") as fd:
            fd.write(six.b(contents))
    log("INFO: Loggly rsyslog file %r written." % LOGGLY_RSYSLOG_CONFFILE)


def unconfigure():
    log("INFO: Initiating uninstall Loggly for Linux.")

    # remove 22-loggly.conf file
    remove_loggly_conf()

    # restart rsyslog service
    restart_rsyslog()

    log("SUCCESS: Uninstalled Loggly configuration from Linux system.")


def remove_loggly_conf():
    '''delete 22-loggly.conf file'''
    if os.path.exists(LOGGLY_RSYSLOG_CONFFILE):
        os.unlink(LOGGLY_RSYSLOG_CONFFILE)


def restart_rsyslog():
    '''restart rsyslog'''
    log("INFO: Restarting the %s service." % RSYSLOG_SERVICE)
    code = subprocess.call(['service', RSYSLOG_SERVICE, 'restart'])
    if code:
        log("WARNING: %s did not restart gracefully. Please restart %s manually." % (RSYSLOG_SERVICE, RSYSLOG_SERVICE))


def log(msg):
    print(msg)
    if msg.startswith('ERROR'):
        sys.exit(1)


def get_loggly_conf(config):
    template = r'''
        #          -------------------------------------------------------
        #          Syslog Logging Directives for Loggly (%(account)s.loggly.com)
        #          -------------------------------------------------------
        # Define the template used for sending logs to Loggly. Do not change this format.
        $template LogglyFormat,"<%%pri%%>%%protocol-version%% %%timestamp:::date-rfc3339%% %(hostname)s %%app-name%% %%procid%% %%msgid%% [%(token)s@%(distribution_id)s %(tags)s] %%msg%%\n"

        $WorkDirectory /var/spool/rsyslog # where to place spool files
        $ActionQueueFileName fwdRule1 # unique name prefix for spool files
        $ActionQueueMaxDiskSpace 1g   # 1gb space limit (use as much as possible)
        $ActionQueueSaveOnShutdown on # save messages to disk on shutdown
        $ActionQueueType LinkedList   # run asynchronously
        $ActionResumeRetryCount -1    # infinite retries if host is down

        # Send messages to Loggly over TCP using the template.
        *.*             @@%(logs_host)s:%(logs_port)d;LogglyFormat
        #     -------------------------------------------------------
        '''

    # preprocess data
    args = dict(config)
    if not args.get('hostname'):
        args['hostname'] = '%HOSTNAME%'
    tags = ['Rsyslog']
    if args.get('tags'):
        tags += args['tags']
    args['tags'] = ' '.join((r'tag=\"%s\"' % tag) for tag in tags)

    args['distribution_id'] = LOGGLY_DISTRIBUTION_ID
    args['logs_host'] = LOGS_01_HOST
    args['logs_port'] = LOGGLY_SYSLOG_PORT

    return textwrap.dedent(template[1:]) % args


if __name__ == '__main__':
    main()
