"""Install

Routine to install a parser/writer/converter style.

"""

import os
import re
import sys
import site
import shutil
import urllib2
import zipfile
import textwrap
import distutils.dir_util
import distutils.errors
import os.path as pth
from glob import iglob
from imp import load_source
from lexor.command import config

DESC = """
Install a parser/writer/converter style.

"""


def add_parser(subp, fclass):
    """Add a parser to the main subparser. """
    tmpp = subp.add_parser('install', help='install a style',
                           formatter_class=fclass,
                           description=textwrap.dedent(DESC))
    tmpp.add_argument('style', type=str, nargs="?",
                      help='name of style to install')
    tmpp.add_argument('-u', '--user', action='store_true',
                      help='install in user-site')
    tmpp.add_argument('-g', '--global', action='store_true',
                      help='install globably, requires sudo')
    tmpp.add_argument('--path', type=str,
                      help='specify the installation path')


def _get_key_typedir(info, install_dir):
    """Helper function for install_style. """
    if info['to_lang']:
        key = '%s.%s.%s.%s' % (info['lang'], info['type'],
                               info['to_lang'], info['style'])
        typedir = '%s/%s.%s.%s'
        typedir = typedir % (install_dir, info['lang'], info['type'],
                             info['to_lang'])
    else:
        key = '%s.%s.%s' % (info['lang'], info['type'], info['style'])
        typedir = '%s/%s.%s'
        typedir = typedir % (install_dir, info['lang'], info['type'])
    return key, typedir

def install_style(style, install_dir):
    """Install a given style to the install_dir path. """
    if not style.startswith('/'):
        raise NameError('style parameter is not an absolute path')
    if not install_dir.startswith('/'):
        raise NameError('install_dir parameter is not an absolute path')

    mod = load_source('tmp_mod', style)
    info = mod.INFO
    key, typedir = _get_key_typedir(info, install_dir)

    if not os.path.exists(typedir):
        try:
            os.makedirs(typedir)
        except OSError:
            msg = 'OSError: unable to create directory. Did you `sudo`?\n'
            error(msg)

    moddir = os.path.splitext(style)[0]
    base, name = os.path.split(moddir)
    if base == '':
        base = '.'

    # Copy main file
    old = '%s/%s.py' % (base, name)
    new = '%s/%s-%s.py' % (typedir, name, info['ver'])
    sys.stdout.write('writing %s ... ' % new)
    try:
        print 'old = ', old
        print 'new = ', new
        shutil.copyfile(old, new)
    except OSError:
        msg = 'OSError: unable to copy file. Did you `sudo`?\n'
    sys.stdout.write('done\n')

    # Copy auxilary modules
    old = '%s/%s' % (base, name)
    new = '%s/%s-%s' % (typedir, name, info['ver'])
    sys.stdout.write('writing %s/* ... ' % new)
    try:
        distutils.dir_util.copy_tree(old, new)
    except distutils.errors.DistutilsFileError:
        pass
    sys.stdout.write('done\n')

    # Compile the style
    new = '%s/%s-%s.py' % (typedir, name, info['ver'])
    load_source('tmp_mod', new)

    # Compile the rest
    new = '%s/%s-%s/*.py' % (typedir, name, info['ver'])
    for path in iglob(new):
        load_source('tmp_mod', path)

    # Check if its on development
    cfg_file = config.read_config()
    if 'develop' in cfg_file:
        if key in cfg_file['develop']:
            del cfg_file['develop'][key]

    if 'version' in cfg_file:
        cfg_file['version'][key] = info['ver']
    else:
        cfg_file.add_section('version')
        cfg_file['version'][key] = info['ver']

    # Write configuration
    print config.CONFIG['path']
    print config.CONFIG['name']
    config.write_config(cfg_file)


def download_file(url, base='.'):
    """Download a file. """
    try:
        print '-> Retrieving %s' % url
        response = urllib2.urlopen(url)
        local_name = '%s/tmp_%s' % (base, os.path.basename(url))
        with open(local_name, "wb") as local_file:
            local_file.write(response.read())
    except urllib2.HTTPError, err:
        print "HTTP Error:", err.code, url
    except urllib2.URLError, err:
        print "URL Error:", err.reason, url
    return local_name


def unzip_file(local_name):
    """Extract the contents of a zip file. """
    zfile = zipfile.ZipFile(local_name)
    dirname = zfile.namelist()[0].split('/')[0]
    zfile.extractall()
    return dirname

def run():
    """Run the command. """
    arg = vars(config.CONFIG['arg'])
    if arg['global'] or arg['user']:
        pass
    else:
        pass
    
    
    print arg
    
    if not pth.exists('lexor.config'):
        with open('lexor.config', 'w') as _:
            pass
    
    
    cfg = config.get_cfg(['dependencies'])
    arg = config.CONFIG['arg']
    print arg
    print '--------'
    print cfg
    print '----'
    print config.CONFIG
    print '----'
    from lexor.command.cloud import cloud_request
    print cloud_request('match', {})
    print arg
    exit()
    if arg.path:
        install_dir = os.path.abspath(arg.path)
    elif arg.user:
        try:
            install_dir = '%s/lib/lexor' % site.getuserbase()
        except AttributeError:
            install_dir = 'lib/lexor'
    else:
        install_dir = '%s/lib/lexor' % sys.prefix

    style_file = arg.style
    if '.py' not in style_file:
        style_file = '%s.py' % style_file
    if os.path.exists(style_file):
        install_style(style_file, install_dir)
        return

    matches = []
    url = 'http://jmlopez-rod.github.io/lexor-lang/lexor-lang.url'
    print '-> Searching in %s' % url
    response = urllib2.urlopen(url)
    for line in response.readlines():
        name, url = line.split(':', 1)
        if arg.style in name:
            matches.append([name.strip(), url.strip()])

    cwd = os.getcwd()
    for match in matches:
        doc = urllib2.urlopen(match[1]).read()
        links = re.finditer(r' href="?([^\s^"]+)', doc)
        links = [link.group(1) for link in links if '.zip' in link.group(1)]
        for link in links:
            if 'master' in link:
                path = urllib2.urlparse.urlsplit(match[1])
                style_url = '%s://%s%s' % (path[0], path[1], link)
                local_name = download_file(style_url, '.')
                dirname = unzip_file(local_name)
                for path in iglob('%s/*.py' % dirname):
                    install_style(pth.abspath(path), install_dir)
                os.remove(local_name)
                shutil.rmtree(dirname)
