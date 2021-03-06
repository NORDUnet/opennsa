import os
from distutils.core import setup
from distutils.command.install import install
from distutils.command.install_data import install_data

from opennsa import __version__


# nasty global for relocation
RELOCATE = None

class InstallOpenNSA(install):

    def finalize_options(self):
        install.finalize_options(self)

        global RELOCATE ; RELOCATE = self.home



class InstallOpenNSAData(install_data):
    # this class is used for relocating datafiles, and remove existing etc files
    # so we don't overwrite the configuration of existing sites

    def finalize_options(self):
        install_data.finalize_options(self)

        # relocation
        if RELOCATE:
            print('relocating to {}'.format(RELOCATE))
            for (prefix, files) in reversed(self.data_files):
                if prefix.startswith('/'):
                    new_prefix = os.path.join(RELOCATE, prefix[1:])
                    self.data_files.remove((prefix, files))
                    self.data_files.append((new_prefix, files))

        # check that we don't overwrite /etc files
        for (prefix, files) in reversed(self.data_files):
            if prefix.startswith(os.path.join(RELOCATE or '/', 'etc')):
                for basefile in files:
                    fn = os.path.join(prefix, os.path.basename(basefile))
                    if os.path.exists(fn):
                        print('Skipping installation of {} (already exists)'.format(fn))
                        files.remove(basefile)
            if not files:
                self.data_files.remove((prefix, []))


cmdclasses = {'install': InstallOpenNSA, 'install_data': InstallOpenNSAData} 


setup(name='opennsa',
      version=__version__,
      description='Implementation of the Network Service Interface (NSI)',
      author='Henrik Thostrup Jensen',
      author_email='htj@nordu.net',
      url='http://www.nordu.net/',
      packages=['opennsa',
                'opennsa/backends',
                'opennsa/backends/common',
                'opennsa/cli',
                'opennsa/plugins',
                'opennsa/discovery',
                'opennsa/discovery/bindings',
                'opennsa/protocols',
                'opennsa/protocols/nsi2',
                'opennsa/protocols/nsi2/bindings',
                'opennsa/protocols/rest',
                'opennsa/protocols/shared',
                'opennsa/shared',
                'opennsa/topology',
               ],

      cmdclass = cmdclasses,

      data_files=[
        ('bin',                     ['onsa']),
        ('/etc',                    ['datafiles/opennsa.conf']),
        ('/etc/init.d',             ['datafiles/opennsa']),
      ]

)

